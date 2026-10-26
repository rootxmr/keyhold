"""Non-secret app settings and default file locations.

Only preferences and the path of the last vault are stored here, in plain
JSON. Nothing in this file is sensitive.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "Keyhold"
VAULT_SUFFIX = ".keyhold"


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME.lower()


def config_dir() -> Path:
    if sys.platform in ("win32", "darwin"):
        return data_dir()
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME.lower()


def default_vault_path() -> Path:
    return data_dir() / f"vault{VAULT_SUFFIX}"


@dataclass
class Settings:
    last_vault: str = ""
    autolock_minutes: int = 5
    clipboard_seconds: int = 20
    lock_on_minimize: bool = False

    @classmethod
    def path(cls) -> Path:
        return config_dir() / "settings.json"

    @classmethod
    def load(cls) -> Settings:
        try:
            data = json.loads(cls.path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name: f.type for f in fields(cls)}
        settings = cls()
        for name, value in data.items():
            if name in known and type(value).__name__ == known[name]:
                setattr(settings, name, value)
        return settings

    def save(self) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
