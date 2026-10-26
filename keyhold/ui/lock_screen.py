"""Unlock and create-vault screens."""

from __future__ import annotations

import secrets
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .. import generator
from ..config import VAULT_SUFFIX
from ..crypto import KDF_PRESETS, AuthenticationError, VaultError
from ..vault import Vault
from .widgets import PasswordEdit, StrengthMeter, Task, button, centered, field, label

VAULT_FILTER = f"Keyhold vault (*{VAULT_SUFFIX});;All files (*)"
MAX_KEYFILE_SIZE = 64 * 1024 * 1024


def read_keyfile(path: str) -> bytes | None:
    if not path:
        return None
    p = Path(path)
    if p.stat().st_size > MAX_KEYFILE_SIZE:
        raise ValueError("Key file is larger than 64 MiB")
    return p.read_bytes()


class KeyFilePicker(QWidget):
    """Optional key file: a checkbox that reveals a path field."""

    def __init__(self, *, allow_create: bool = False):
        super().__init__()
        self._enabled = QCheckBox("Also require a key file")
        self._path = QLineEdit()
        self._path.setPlaceholderText("Path to key file")
        self._row = QWidget()
        row = QHBoxLayout(self._row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._path, 1)
        row.addWidget(button("Browse", on_click=self._browse))
        if allow_create:
            row.addWidget(button("New", on_click=self._create))
        self._row.setVisible(False)
        self._enabled.toggled.connect(self._row.setVisible)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._enabled)
        layout.addWidget(self._row)

    def path(self) -> str:
        return self._path.text().strip() if self._enabled.isChecked() else ""

    def is_incomplete(self) -> bool:
        return self._enabled.isChecked() and not self.path()

    def reset(self) -> None:
        self._enabled.setChecked(False)
        self._path.clear()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose key file")
        if path:
            self._path.setText(path)

    def _create(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save new key file", "keyhold.key")
        if path:
            Path(path).write_bytes(secrets.token_bytes(64))
            self._path.setText(path)


class UnlockScreen(QWidget):
    unlocked = Signal(object)  # Vault
    create_requested = Signal()
    path_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._path = ""
        self._path_label = label("", "muted")
        self._password = PasswordEdit("Master password")
        self._password.returnPressed.connect(self._unlock)
        self._keyfile = KeyFilePicker()
        self._error = label("", "error", wrap=True)
        self._submit = button("Unlock", "primary", self._unlock)

        path_row = QHBoxLayout()
        path_row.addWidget(self._path_label, 1)
        path_row.addWidget(button("Change", "link", self._choose_vault))

        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setSpacing(14)
        layout.addWidget(label("Keyhold", "title"))
        layout.addLayout(path_row)
        layout.addSpacing(6)
        layout.addWidget(self._password)
        layout.addWidget(self._keyfile)
        layout.addWidget(self._error)
        layout.addWidget(self._submit)
        layout.addWidget(button("Create a new vault", "link", self.create_requested.emit))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(centered(col))

    @property
    def vault_path(self) -> str:
        return self._path

    def set_vault_path(self, path: str) -> None:
        self._path = path
        self._path_label.setText(Path(path).name)
        self._path_label.setToolTip(path)

    def reset(self) -> None:
        self._password.clear()
        self._password.set_visible(False)
        self._error.setText("")
        self._set_busy(False)
        self._password.setFocus()

    def _choose_vault(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open vault", str(Path(self._path).parent), VAULT_FILTER)
        if path:
            self.set_vault_path(path)
            self.path_changed.emit(path)
            self._error.setText("")

    def _set_busy(self, busy: bool) -> None:
        self._submit.setEnabled(not busy)
        self._password.setEnabled(not busy)
        self._submit.setText("Unlocking…" if busy else "Unlock")

    def _unlock(self) -> None:
        if not self._submit.isEnabled():
            return
        password = self._password.text()
        if not password:
            self._error.setText("Enter your master password.")
            return
        if self._keyfile.is_incomplete():
            self._error.setText("Choose a key file or untick the option.")
            return
        try:
            keyfile = read_keyfile(self._keyfile.path())
        except (OSError, ValueError) as exc:
            self._error.setText(f"Could not read key file: {exc}")
            return
        self._error.setText("")
        self._set_busy(True)
        path = self._path
        Task(lambda: Vault.open(path, password, keyfile), self._on_unlocked, self._on_failed, self)

    def _on_unlocked(self, vault: Vault) -> None:
        self._password.clear()
        self._keyfile.reset()
        self._set_busy(False)
        self.unlocked.emit(vault)

    def _on_failed(self, exc: Exception) -> None:
        self._set_busy(False)
        if isinstance(exc, AuthenticationError):
            self._error.setText("Wrong master password or key file.")
        elif isinstance(exc, FileNotFoundError):
            self._error.setText("Vault file not found. Choose another or create a new vault.")
        elif isinstance(exc, (VaultError, OSError)):
            self._error.setText(str(exc))
        else:
            self._error.setText(f"Unexpected error: {exc}")
        self._password.selectAll()
        self._password.setFocus()


class CreateScreen(QWidget):
    created = Signal(object)  # Vault
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        self._location = QLineEdit()
        loc_row = QWidget()
        loc = QHBoxLayout(loc_row)
        loc.setContentsMargins(0, 0, 0, 0)
        loc.addWidget(self._location, 1)
        loc.addWidget(button("Browse", on_click=self._browse))

        self._password = PasswordEdit("Master password")
        self._confirm = PasswordEdit("Repeat master password")
        self._meter = StrengthMeter()
        self._password.textChanged.connect(self._on_password)
        suggest = button("Suggest a passphrase", "link", self._suggest)

        self._kdf = QComboBox()
        self._kdf.addItem("Standard  —  Argon2id, 256 MiB, 3 passes", "moderate")
        self._kdf.addItem("Maximum  —  Argon2id, 1 GiB, 4 passes (slower)", "high")
        self._keyfile = KeyFilePicker(allow_create=True)
        self._error = label("", "error", wrap=True)
        self._submit = button("Create vault", "primary", self._create)

        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setSpacing(14)
        layout.addWidget(label("New vault", "title"))
        layout.addWidget(
            label(
                "Your master password cannot be recovered. If you forget it, "
                "the vault is gone for good. A long passphrase is easiest to remember.",
                "muted",
                wrap=True,
            )
        )
        layout.addWidget(field("Location", loc_row))
        layout.addWidget(field("Master password", self._password))
        layout.addWidget(self._meter)
        layout.addWidget(self._confirm)
        layout.addWidget(suggest)
        layout.addWidget(field("Key derivation", self._kdf))
        layout.addWidget(self._keyfile)
        layout.addWidget(self._error)
        layout.addWidget(self._submit)
        layout.addWidget(button("Back", "link", self.cancelled.emit))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(centered(col, 420))

    def reset(self, default_path: str) -> None:
        self._location.setText(default_path)
        for edit in (self._password, self._confirm):
            edit.clear()
            edit.set_visible(False)
        self._keyfile.reset()
        self._error.setText("")
        self._set_busy(False)
        self._password.setFocus()

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save vault as", self._location.text(), VAULT_FILTER)
        if path:
            if not path.endswith(VAULT_SUFFIX) and "." not in Path(path).name:
                path += VAULT_SUFFIX
            self._location.setText(path)

    def _on_password(self, text: str) -> None:
        self._meter.set_bits(generator.estimate_entropy(text), show_bits=False)

    def _suggest(self) -> None:
        phrase = generator.generate_passphrase(6)
        for edit in (self._password, self._confirm):
            edit.setText(phrase.value)
            edit.set_visible(True)
        self._meter.set_bits(phrase.entropy)

    def _set_busy(self, busy: bool) -> None:
        self._submit.setEnabled(not busy)
        self._submit.setText("Creating…" if busy else "Create vault")

    def _create(self) -> None:
        if not self._submit.isEnabled():
            return
        path = self._location.text().strip()
        password = self._password.text()
        if not path:
            self._error.setText("Choose where to save the vault.")
            return
        if Path(path).exists():
            self._error.setText("A file already exists at that location.")
            return
        if len(password) < 8:
            self._error.setText("Use at least 8 characters. A passphrase of 5+ words is better.")
            return
        if password != self._confirm.text():
            self._error.setText("The passwords don't match.")
            return
        if self._keyfile.is_incomplete():
            self._error.setText("Choose a key file or untick the option.")
            return
        try:
            keyfile = read_keyfile(self._keyfile.path())
        except (OSError, ValueError) as exc:
            self._error.setText(f"Could not read key file: {exc}")
            return
        params = KDF_PRESETS[self._kdf.currentData()]
        self._error.setText("")
        self._set_busy(True)
        Task(lambda: Vault.create(path, password, keyfile, params), self._on_created, self._on_failed, self)

    def _on_created(self, vault: Vault) -> None:
        self._password.clear()
        self._confirm.clear()
        self._set_busy(False)
        self.created.emit(vault)

    def _on_failed(self, exc: Exception) -> None:
        self._set_busy(False)
        self._error.setText(f"Could not create the vault: {exc}")
