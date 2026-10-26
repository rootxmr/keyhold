import pytest

from keyhold import crypto
from keyhold.crypto import AuthenticationError, KdfParams, VaultFormatError, VaultKey


def test_roundtrip(fast_kdf):
    key = VaultKey.derive("correct horse battery staple", params=fast_kdf)
    blob = crypto.encrypt(key, b"secret data")
    _, plaintext = crypto.decrypt(blob, "correct horse battery staple")
    assert plaintext == b"secret data"


def test_ciphertext_does_not_contain_plaintext(fast_kdf):
    key = VaultKey.derive("pw", params=fast_kdf)
    assert b"hunter2" not in crypto.encrypt(key, b"hunter2" * 10)


def test_each_encryption_uses_fresh_nonce(fast_kdf):
    key = VaultKey.derive("pw", params=fast_kdf)
    assert crypto.encrypt(key, b"x") != crypto.encrypt(key, b"x")


def test_wrong_password(fast_kdf):
    blob = crypto.encrypt(VaultKey.derive("right", params=fast_kdf), b"data")
    with pytest.raises(AuthenticationError):
        crypto.decrypt(blob, "wrong")


def test_keyfile_is_required_when_used(fast_kdf):
    blob = crypto.encrypt(VaultKey.derive("pw", b"key file bytes", params=fast_kdf), b"data")
    with pytest.raises(AuthenticationError):
        crypto.decrypt(blob, "pw")
    with pytest.raises(AuthenticationError):
        crypto.decrypt(blob, "pw", b"other key file")
    assert crypto.decrypt(blob, "pw", b"key file bytes")[1] == b"data"


def test_unicode_password_is_normalised(fast_kdf):
    composed, decomposed = "café", "café"
    blob = crypto.encrypt(VaultKey.derive(composed, params=fast_kdf), b"data")
    assert crypto.decrypt(blob, decomposed)[1] == b"data"


@pytest.mark.parametrize("offset", [6, 20, 40, crypto.HEADER_SIZE + 3, -1])
def test_tampering_is_detected(fast_kdf, offset):
    blob = bytearray(crypto.encrypt(VaultKey.derive("pw", params=fast_kdf), b"data"))
    blob[offset] ^= 0x01
    with pytest.raises((AuthenticationError, VaultFormatError)):
        crypto.decrypt(bytes(blob), "pw")


def test_size_is_padded(fast_kdf):
    key = VaultKey.derive("pw", params=fast_kdf)
    assert len(crypto.encrypt(key, b"a")) == len(crypto.encrypt(key, b"a" * 3000))


def test_rejects_non_vault():
    with pytest.raises(VaultFormatError):
        crypto.decrypt(b"not a vault at all" * 10, "pw")


def test_rejects_absurd_kdf_params(fast_kdf):
    blob = bytearray(crypto.encrypt(VaultKey.derive("pw", params=fast_kdf), b"data"))
    blob[10:18] = (2**60).to_bytes(8, "big")  # memlimit
    with pytest.raises(VaultFormatError):
        crypto.decrypt(bytes(blob), "pw")


def test_default_params_are_strong():
    p = KdfParams()
    assert p.memlimit >= 256 * 1024 * 1024
    assert p.opslimit >= 3
