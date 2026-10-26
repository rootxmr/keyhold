# Contributing

Thanks for helping. Keyhold aims to stay small, readable and boring in the
best sense: code that is easy to audit matters more than features.

## Setup

```bash
git clone https://github.com/rootxmr/keyhold.git
cd keyhold
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m keyhold
```

## Before opening a pull request

```bash
ruff format .
ruff check .
pytest
```

CI runs the same checks on Linux, Windows and macOS.

## Guidelines

- **No network code.** Keyhold must never make a network connection. No
  update checks, favicon downloads, breach lookups or analytics.
- **No home-made cryptography.** Use libsodium (via PyNaCl) primitives. Any
  change to `crypto.py` or the file format needs tests and a clear rationale
  in the PR, and must keep existing vaults readable (bump `FORMAT_VERSION` and
  keep a reader for the old version).
- **Keep dependencies minimal.** Every dependency is attack surface. Discuss
  before adding one.
- **Tests** for any change to `crypto.py`, `vault.py` or `generator.py`.
- **UI**: keep it quiet and minimal. Reuse the colours in `ui/theme.py`
  rather than adding new ones.
- Never include real passwords or vault files in issues, tests or commits.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Please report privately.

## License

By contributing you agree that your contributions are licensed under the
GNU GPL v3.0 or later, the same license as the project.
