"""The vault: a list of entries, kept encrypted in a single local file."""

from __future__ import annotations

import copy
import json
import os
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import crypto
from .crypto import KdfParams, VaultError, VaultFormatError, VaultKey

PAYLOAD_VERSION = 1


def _now() -> float:
    return time.time()


@dataclass
class Entry:
    title: str = ""
    username: str = ""
    password: str = ""
    url: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created: float = field(default_factory=_now)
    modified: float = field(default_factory=_now)

    @classmethod
    def from_dict(cls, data: dict) -> Entry:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def matches(self, query: str) -> bool:
        q = query.casefold()
        return any(q in s.casefold() for s in (self.title, self.username, self.url, self.notes))


class Vault:
    """An unlocked vault. Every mutating call is persisted immediately."""

    def __init__(self, path: Path, key: VaultKey, entries: list[Entry] | None = None):
        self.path = Path(path)
        self._key = key
        self.entries: list[Entry] = entries or []
        self._locked = False
        # Serialises saves against lock(), so a save running on a worker
        # thread can never write out the emptied entry list.
        self._io = threading.Lock()

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def create(
        cls,
        path: str | os.PathLike,
        password: str,
        keyfile: bytes | None = None,
        params: KdfParams | None = None,
    ) -> Vault:
        path = Path(path)
        if path.exists():
            raise FileExistsError(f"{path} already exists")
        vault = cls(path, VaultKey.derive(password, keyfile, params))
        vault.save()
        return vault

    @classmethod
    def open(cls, path: str | os.PathLike, password: str, keyfile: bytes | None = None) -> Vault:
        path = Path(path)
        key, plaintext = crypto.decrypt(path.read_bytes(), password, keyfile)
        try:
            payload = json.loads(plaintext.decode("utf-8"))
            if payload.get("version") != PAYLOAD_VERSION:
                raise VaultFormatError(f"Unsupported payload version {payload.get('version')}")
            entries = [Entry.from_dict(e) for e in payload["entries"]]
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise VaultFormatError("Vault contents are malformed") from exc
        return cls(path, key, entries)

    def lock(self) -> None:
        with self._io:
            self._locked = True
            self._key.forget()
            self.entries = []

    def change_master_key(self, password: str, keyfile: bytes | None = None, params: KdfParams | None = None) -> None:
        """Re-encrypt with a new password / key file and a fresh salt."""
        old_key = self._key
        self._key = VaultKey.derive(password, keyfile, params or old_key.params)
        try:
            self.save()
        except BaseException:
            self._key = old_key
            raise
        # Save again so the .bak copy is also under the new key, rather than
        # leaving a backup that still opens with the old password.
        self.save()

    @property
    def kdf_params(self) -> KdfParams:
        return self._key.params

    # -- persistence -------------------------------------------------------

    def _serialize(self) -> bytes:
        payload = {"version": PAYLOAD_VERSION, "entries": [asdict(e) for e in self.entries]}
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def save(self) -> None:
        """Write atomically, keeping the previous version as `<name>.bak`."""
        with self._io:
            if self._locked:
                raise VaultError("The vault is locked")
            self._write(crypto.encrypt(self._key, self._serialize()))

    def _write(self, blob: bytes) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(blob)
                fh.flush()
                os.fsync(fh.fileno())
            if self.path.exists():
                shutil.copy2(self.path, self.path.with_name(self.path.name + ".bak"))
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()

    # -- entries -----------------------------------------------------------

    def get(self, entry_id: str) -> Entry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    def _commit(self, mutate) -> None:
        """Apply a change and save it; roll back in memory if saving fails."""
        snapshot = copy.deepcopy(self.entries)
        try:
            mutate()
            self.save()
        except BaseException:
            self.entries = snapshot
            raise

    def add(self, entry: Entry) -> Entry:
        self._commit(lambda: self.entries.append(entry))
        return entry

    def update(self, entry_id: str, **changes: str) -> Entry:
        if self.get(entry_id) is None:
            raise KeyError(entry_id)
        for name in changes:
            if name in ("id", "created", "modified") or name not in Entry.__dataclass_fields__:
                raise AttributeError(f"Cannot set field {name!r}")

        def mutate() -> None:
            entry = self.get(entry_id)
            for name, value in changes.items():
                setattr(entry, name, value)
            entry.modified = _now()

        self._commit(mutate)
        return self.get(entry_id)

    def delete(self, entry_id: str) -> None:
        def mutate() -> None:
            self.entries = [e for e in self.entries if e.id != entry_id]

        self._commit(mutate)

    def search(self, query: str = "") -> list[Entry]:
        found = [e for e in self.entries if e.matches(query)] if query else list(self.entries)
        return sorted(found, key=lambda e: e.title.casefold())
