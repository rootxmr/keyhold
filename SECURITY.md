# Security

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
(Security tab → "Report a vulnerability") on this repository. Include steps to
reproduce, and the version and OS. You should get a reply within a week.

## Threat model

Keyhold is designed to protect your secrets when an attacker **gets a copy of
your vault file** (stolen laptop, seized USB stick, leaked backup, synced to
the wrong place) but does **not** know your master password or have your key
file.

Against that attacker, the only practical attack is guessing the master
password offline. Argon2id makes every guess cost 256 MiB of memory and
several passes over it, which makes GPU and ASIC cracking expensive. The
strength of your master password is still what matters most: a random
six-word passphrase (~77 bits) is far out of reach; `Summer2024!` is not.

Keyhold **cannot** protect you if:

- Your computer is compromised while the vault is unlocked (malware, a
  keylogger capturing the master password, someone reading process memory).
- Someone with access to your unlocked session reads the screen or clipboard.
- You use a weak or reused master password.

Running Keyhold on Tails, which boots clean every time, greatly reduces the
first risk.

## Cryptographic design

All primitives come from [libsodium](https://doc.libsodium.org/) via
[PyNaCl](https://pynacl.readthedocs.io/). Keyhold implements no cryptographic
primitives of its own.

### Key derivation

```
pw_hash  = BLAKE2b-256(NFC(master_password), person="keyhold.pw")
kf_hash  = BLAKE2b-256(key_file_bytes,        person="keyhold.kf")   # only if a key file is used
secret   = pw_hash || kf_hash
key      = Argon2id(secret, salt, opslimit, memlimit) → 32 bytes
```

- The password is Unicode NFC-normalised so the same passphrase typed on
  different systems produces the same key.
- The salt is 16 random bytes, regenerated whenever the master password or
  key file changes.
- Defaults: `opslimit=3`, `memlimit=256 MiB` (libsodium "moderate"). The
  "Maximum" preset uses `opslimit=4`, `memlimit=1 GiB` (libsodium "sensitive").
- The parameters are stored in the file header, so they can be raised in the
  future without breaking old vaults.

The pre-hash only fixes the input length and combines the two factors; it does
not reduce the work an attacker must do, since every guess still has to pass
through Argon2id.

### Encryption

- XChaCha20-Poly1305 (IETF AEAD), 256-bit key.
- A new random 192-bit nonce on every save. With 192-bit nonces, random
  generation is safe without counters.
- The complete 58-byte header (magic, version, KDF id, KDF parameters, salt,
  nonce) is passed as associated data. Changing any byte of the header or
  ciphertext makes decryption fail.
- Wrong password, wrong key file and tampering all produce the same error.
- Before encryption, the plaintext is length-prefixed and zero-padded to a
  multiple of 4096 bytes, so the file size only roughly reveals how much is
  stored.

### File format (version 1)

All integers are big-endian.

| Offset | Size | Field                                         |
|-------:|-----:|-----------------------------------------------|
| 0      | 4    | Magic `KHLD`                                  |
| 4      | 1    | Format version (`1`)                          |
| 5      | 1    | KDF id (`1` = Argon2id v1.3)                  |
| 6      | 4    | Argon2 opslimit                               |
| 10     | 8    | Argon2 memlimit (bytes)                       |
| 18     | 16   | Salt                                          |
| 34     | 24   | Nonce                                         |
| 58     | …    | Ciphertext, followed by 16-byte Poly1305 tag  |

Decrypted payload: `uint32 length || JSON || zero padding`. The JSON is:

```json
{"version": 1, "entries": [{"id": "…", "title": "…", "username": "…",
  "password": "…", "url": "…", "notes": "…", "created": 1700000000.0,
  "modified": 1700000000.0}]}
```

On open, KDF parameters are checked against sane bounds (opslimit 1–64,
memlimit 8 MiB–4 GiB) so a crafted file cannot exhaust memory.

### Generator

- Randomness: Python's `secrets` module (the OS CSPRNG).
- Passwords: one character from each enabled set is guaranteed, the rest
  drawn uniformly from the combined pool, then shuffled. Reported entropy is
  `length × log2(pool)`; the guarantee lowers this very slightly.
- Passphrases: words drawn uniformly from the 7,776-word EFF list,
  12.9 bits per word.
- Seed phrases: BIP39, entropy from the CSPRNG, SHA-256 checksum, verified
  against the official test vectors.

### Saving

Saves write to `<vault>.tmp`, `fsync`, copy the current vault to
`<vault>.bak`, then atomically rename the temp file over the vault. On
Linux/macOS the file is created with mode `0600`. After a master password
change the vault is saved twice so the `.bak` is also under the new key.

## Known limitations

- **Memory.** Python strings are immutable and garbage-collected, so Keyhold
  cannot reliably wipe secrets from RAM. While unlocked, decrypted entries
  are in process memory, and could end up in swap or a crash dump. Locking
  drops all references, but the memory is only reused, not zeroed. Full-disk
  encryption (or Tails, which has no swap) mitigates the swap risk.
- **Clipboard.** Other programs running as your user can read the clipboard
  while a secret is on it. Keyhold clears it after the timeout (only if it
  still holds the copied value) and asks clipboard managers on Windows and KDE
  not to record it; other clipboard managers may ignore that.
- **Old copies.** Changing the master password does not affect copies of the
  vault made earlier (backups, USB sticks). Those still open with the old
  password. Deleting files on SSDs and flash drives does not reliably erase
  them.
- **Password strength meter.** The meter for passwords you type yourself is
  a rough, character-pool estimate. It cannot detect dictionary words or
  patterns. Generated secrets show their exact entropy.
- **No audit.** The code is small and readable, and the cryptography is
  delegated to libsodium, but Keyhold has not been professionally audited.
