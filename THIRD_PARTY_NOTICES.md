# Third-party notices

Keyhold itself is licensed under the GNU General Public License v3.0 or later
(see `LICENSE`). It bundles or depends on the following works.

## Bundled data

### EFF Large Wordlist — `keyhold/wordlists/eff_large.txt`

- Source: https://www.eff.org/dice
- Copyright © Electronic Frontier Foundation
- License: Creative Commons Attribution 3.0 United States (CC BY 3.0 US),
  https://creativecommons.org/licenses/by/3.0/us/
- Changes: the dice-roll column was removed, leaving one word per line.

### BIP39 English wordlist — `keyhold/wordlists/bip39_english.txt`

- Source: https://github.com/bitcoin/bips/blob/master/bip-0039/english.txt
- SHA-256: `2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda`
- Authors: Marek Palatinus, Pavol Rusnak, Aaron Voisine, Sean Bowe (BIP-0039).
  The same list is distributed under the MIT License by the reference
  implementation, https://github.com/trezor/python-mnemonic
- Unmodified.

## Runtime dependencies (installed separately, not vendored)

| Package  | License        | Notes                                   |
|----------|----------------|-----------------------------------------|
| PyNaCl   | Apache-2.0     | Python bindings to libsodium            |
| libsodium| ISC            | Argon2id, XChaCha20-Poly1305 (via PyNaCl)|
| PySide6  | LGPL-3.0       | Qt for Python, the user interface       |
| Qt 6     | LGPL-3.0       | Bundled inside the PySide6 wheels       |

When distributing a frozen build (e.g. PyInstaller), you must comply with the
LGPL for Qt/PySide6: ship their license texts and allow users to replace the
Qt libraries. Building from source, as described in the README, satisfies this.
