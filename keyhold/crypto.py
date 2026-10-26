"""Vault file encryption.

Key derivation: Argon2id (memory-hard, resists GPU/ASIC cracking).
Encryption:     XChaCha20-Poly1305 (authenticated encryption, 192-bit random nonces).
Both primitives come from libsodium via PyNaCl.

File layout (all integers big-endian):

    offset  size  field
    0       4     magic  b"KHLD"
    4       1     format version
    5       1     KDF id (1 = Argon2id v1.3)
    6       4     Argon2 opslimit (iterations)
    10      8     Argon2 memlimit (bytes)
    18      16    salt
    34      24    nonce
    58      ...   ciphertext + 16-byte Poly1305 tag

The whole header is passed to the AEAD as associated data, so any change to
the KDF parameters, salt or nonce makes decryption fail.

The plaintext is padded to a multiple of PAD_BLOCK bytes so the file size
reveals only a coarse estimate of how much is stored.
"""

from __future__ import annotations

import hashlib
import secrets
import struct
import unicodedata
from dataclasses import dataclass

from nacl import pwhash
from nacl.bindings import (
    crypto_aead_xchacha20poly1305_ietf_decrypt,
    crypto_aead_xchacha20poly1305_ietf_encrypt,
)
from nacl.exceptions import CryptoError

MAGIC = b"KHLD"
FORMAT_VERSION = 1
KDF_ARGON2ID = 1

SALT_SIZE = pwhash.argon2id.SALTBYTES  # 16
NONCE_SIZE = 24
KEY_SIZE = 32
PAD_BLOCK = 4096

_HEADER = struct.Struct(">4sBBIQ16s24s")
HEADER_SIZE = _HEADER.size

# Bounds accepted when reading a file, so a crafted header cannot make us
# allocate absurd amounts of memory or spin forever.
_MIN_OPS = pwhash.argon2id.OPSLIMIT_MIN
_MAX_OPS = 64
_MIN_MEM = 8 * 1024 * 1024
_MAX_MEM = 4 * 1024 * 1024 * 1024


class VaultError(Exception):
    """Base class for vault errors."""


class VaultFormatError(VaultError):
    """The file is not a vault, or uses an unsupported format."""


class AuthenticationError(VaultError):
    """Wrong master password / key file, or the file was tampered with.

    These cases are deliberately indistinguishable.
    """


@dataclass(frozen=True)
class KdfParams:
    opslimit: int = pwhash.argon2id.OPSLIMIT_MODERATE  # 3 passes
    memlimit: int = pwhash.argon2id.MEMLIMIT_MODERATE  # 256 MiB

    def validate(self) -> None:
        if not _MIN_OPS <= self.opslimit <= _MAX_OPS:
            raise VaultFormatError(f"Argon2 opslimit out of range: {self.opslimit}")
        if not _MIN_MEM <= self.memlimit <= _MAX_MEM:
            raise VaultFormatError(f"Argon2 memlimit out of range: {self.memlimit}")


# Presets offered when creating a vault.
KDF_PRESETS = {
    "moderate": KdfParams(),
    "high": KdfParams(
        opslimit=pwhash.argon2id.OPSLIMIT_SENSITIVE,  # 4 passes
        memlimit=pwhash.argon2id.MEMLIMIT_SENSITIVE,  # 1 GiB
    ),
}


def _composite_secret(password: str, keyfile: bytes | None) -> bytes:
    """Combine the master password and optional key file into KDF input.

    The password is NFC-normalised so the same passphrase typed on different
    systems produces the same bytes.
    """
    pw = unicodedata.normalize("NFC", password).encode("utf-8")
    parts = [hashlib.blake2b(pw, digest_size=32, person=b"keyhold.pw").digest()]
    if keyfile is not None:
        parts.append(hashlib.blake2b(keyfile, digest_size=32, person=b"keyhold.kf").digest())
    return b"".join(parts)


class VaultKey:
    """A derived encryption key together with the parameters that produced it."""

    __slots__ = ("_key", "salt", "params")

    def __init__(self, key: bytes, salt: bytes, params: KdfParams):
        self._key = key
        self.salt = salt
        self.params = params

    @classmethod
    def derive(
        cls,
        password: str,
        keyfile: bytes | None = None,
        params: KdfParams | None = None,
        salt: bytes | None = None,
    ) -> VaultKey:
        params = params or KdfParams()
        params.validate()
        salt = salt if salt is not None else secrets.token_bytes(SALT_SIZE)
        key = pwhash.argon2id.kdf(
            KEY_SIZE,
            _composite_secret(password, keyfile),
            salt,
            opslimit=params.opslimit,
            memlimit=params.memlimit,
        )
        return cls(key, salt, params)

    def forget(self) -> None:
        """Drop the reference to the key material.

        Python cannot guarantee the bytes are wiped from memory; see SECURITY.md.
        """
        self._key = b""


def _pad(data: bytes) -> bytes:
    body = struct.pack(">I", len(data)) + data
    return body + b"\x00" * (-len(body) % PAD_BLOCK)


def _unpad(data: bytes) -> bytes:
    if len(data) < 4:
        raise VaultFormatError("Decrypted payload is truncated")
    (length,) = struct.unpack_from(">I", data)
    if length > len(data) - 4:
        raise VaultFormatError("Decrypted payload has an invalid length")
    return data[4 : 4 + length]


def encrypt(key: VaultKey, plaintext: bytes) -> bytes:
    """Encrypt plaintext into a complete vault file blob."""
    nonce = secrets.token_bytes(NONCE_SIZE)
    header = _HEADER.pack(
        MAGIC,
        FORMAT_VERSION,
        KDF_ARGON2ID,
        key.params.opslimit,
        key.params.memlimit,
        key.salt,
        nonce,
    )
    ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(_pad(plaintext), header, nonce, key._key)
    return header + ciphertext


def parse_header(blob: bytes) -> tuple[KdfParams, bytes, bytes]:
    """Return (kdf params, salt, nonce) from a vault blob, validating it."""
    if len(blob) < HEADER_SIZE + 16:
        raise VaultFormatError("File is too small to be a Keyhold vault")
    magic, version, kdf_id, ops, mem, salt, nonce = _HEADER.unpack_from(blob)
    if magic != MAGIC:
        raise VaultFormatError("Not a Keyhold vault")
    if version != FORMAT_VERSION:
        raise VaultFormatError(f"Unsupported vault version {version}")
    if kdf_id != KDF_ARGON2ID:
        raise VaultFormatError(f"Unsupported key derivation function {kdf_id}")
    params = KdfParams(opslimit=ops, memlimit=mem)
    params.validate()
    return params, salt, nonce


def decrypt(blob: bytes, password: str, keyfile: bytes | None = None) -> tuple[VaultKey, bytes]:
    """Derive the key from the password and decrypt a vault blob.

    Returns the key (so later saves can skip the slow KDF) and the plaintext.
    """
    params, salt, _ = parse_header(blob)
    key = VaultKey.derive(password, keyfile, params, salt)
    return key, decrypt_with_key(blob, key)


def decrypt_with_key(blob: bytes, key: VaultKey) -> bytes:
    _, _, nonce = parse_header(blob)
    header, ciphertext = blob[:HEADER_SIZE], blob[HEADER_SIZE:]
    try:
        padded = crypto_aead_xchacha20poly1305_ietf_decrypt(ciphertext, header, nonce, key._key)
    except CryptoError:
        raise AuthenticationError("Wrong master password or key file, or the vault is corrupted") from None
    return _unpad(padded)
