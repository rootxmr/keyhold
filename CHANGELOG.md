# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-26

### Added

- Encrypted local vault: Argon2id key derivation and XChaCha20-Poly1305
  authenticated encryption (vault format version 1).
- Optional key file as a second unlock factor.
- Entries with title, username, password, website and notes; search.
- Generator for passwords, EFF passphrases, BIP39 seed phrases, PINs and hex keys.
- `keyhold gen` command-line generator.
- Clipboard auto-clear, excluded from Windows clipboard history and KDE Klipper.
- Auto-lock on inactivity and optional lock on minimise.
- Change master password / key file.
- Atomic saves with a `.bak` copy of the previous version.
