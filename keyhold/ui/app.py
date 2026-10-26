"""Main window, app-level dialogs and the `run()` entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
)

from .. import __version__, crypto, generator
from ..config import Settings, default_vault_path
from ..crypto import AuthenticationError
from ..vault import Vault
from . import theme
from .lock_screen import VAULT_FILTER, CreateScreen, KeyFilePicker, UnlockScreen, read_keyfile
from .vault_screen import VaultScreen
from .widgets import PasswordEdit, SecureClipboard, StrengthMeter, Task, button, field, label

_ACTIVITY_EVENTS = {
    QEvent.KeyPress,
    QEvent.MouseButtonPress,
    QEvent.MouseMove,
    QEvent.Wheel,
}


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(380)
        self._autolock = QSpinBox()
        self._autolock.setRange(0, 240)
        self._autolock.setSuffix(" min")
        self._autolock.setSpecialValueText("Never")
        self._autolock.setValue(settings.autolock_minutes)
        self._clip = QSpinBox()
        self._clip.setRange(0, 600)
        self._clip.setSuffix(" s")
        self._clip.setSpecialValueText("Never")
        self._clip.setValue(settings.clipboard_seconds)
        self._minimize = QCheckBox("Lock when the window is minimised")
        self._minimize.setChecked(settings.lock_on_minimize)

        save = button("Save", "primary", self.accept)
        save.setDefault(True)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(button("Cancel", on_click=self.reject))
        actions.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(field("Lock after inactivity", self._autolock))
        layout.addWidget(field("Clear clipboard after", self._clip))
        layout.addWidget(self._minimize)
        layout.addSpacing(6)
        layout.addLayout(actions)

    def apply_to(self, settings: Settings) -> None:
        settings.autolock_minutes = self._autolock.value()
        settings.clipboard_seconds = self._clip.value()
        settings.lock_on_minimize = self._minimize.isChecked()


class ChangePasswordDialog(QDialog):
    def __init__(self, vault: Vault, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change master password")
        self.setMinimumWidth(420)
        self._vault = vault
        self._current = PasswordEdit("Current master password")
        self._current_kf = KeyFilePicker()
        self._new = PasswordEdit("New master password")
        self._confirm = PasswordEdit("Repeat new master password")
        self._meter = StrengthMeter()
        self._new.textChanged.connect(lambda t: self._meter.set_bits(generator.estimate_entropy(t), show_bits=False))
        self._new_kf = KeyFilePicker(allow_create=True)
        self._error = label("", "error", wrap=True)
        self._submit = button("Change password", "primary", self._apply)
        self._submit.setDefault(True)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(button("Cancel", on_click=self.reject))
        actions.addWidget(self._submit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(field("Current", self._current))
        layout.addWidget(self._current_kf)
        layout.addSpacing(8)
        layout.addWidget(field("New", self._new))
        layout.addWidget(self._meter)
        layout.addWidget(self._confirm)
        layout.addWidget(self._new_kf)
        layout.addWidget(self._error)
        layout.addLayout(actions)

    def _apply(self) -> None:
        current, new = self._current.text(), self._new.text()
        if len(new) < 8:
            self._error.setText("Use at least 8 characters for the new password.")
            return
        if new != self._confirm.text():
            self._error.setText("The new passwords don't match.")
            return
        if self._current_kf.is_incomplete() or self._new_kf.is_incomplete():
            self._error.setText("Choose a key file or untick the option.")
            return
        try:
            current_kf = read_keyfile(self._current_kf.path())
            new_kf = read_keyfile(self._new_kf.path())
        except (OSError, ValueError) as exc:
            self._error.setText(f"Could not read key file: {exc}")
            return
        vault = self._vault

        def work() -> None:
            crypto.decrypt(vault.path.read_bytes(), current, current_kf)  # verify current credentials
            vault.change_master_key(new, new_kf)

        self._error.setText("")
        self._submit.setEnabled(False)
        self._submit.setText("Re-encrypting…")
        Task(work, self._done, self._failed, self)

    def _done(self, _result) -> None:
        self.accept()

    def _failed(self, exc: Exception) -> None:
        self._submit.setEnabled(True)
        self._submit.setText("Change password")
        if isinstance(exc, AuthenticationError):
            self._error.setText("The current password or key file is wrong.")
        else:
            self._error.setText(f"Could not change the password: {exc}")


class MainWindow(QMainWindow):
    def __init__(self, vault_path: str | None = None):
        super().__init__()
        self.setWindowTitle("Keyhold")
        self.resize(940, 620)
        self.setMinimumSize(760, 500)

        self.settings = Settings.load()
        self.clipboard = SecureClipboard(self)
        self.vault: Vault | None = None

        self._unlock = UnlockScreen()
        self._create = CreateScreen()
        self._main = VaultScreen(self.clipboard)
        self._stack = QStackedWidget()
        for screen in (self._unlock, self._create, self._main):
            self._stack.addWidget(screen)
        self.setCentralWidget(self._stack)

        self._unlock.unlocked.connect(self._open)
        self._unlock.create_requested.connect(self._show_create)
        self._unlock.path_changed.connect(self._remember_path)
        self._create.created.connect(self._open)
        self._create.cancelled.connect(self._show_unlock)
        self._main.lock_requested.connect(self.lock)
        self._main.change_password_requested.connect(self._change_password)
        self._main.switch_vault_requested.connect(self._switch_vault)
        self._main.settings_requested.connect(self._edit_settings)
        self._main.about_requested.connect(self._about)

        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(self.lock)
        QApplication.instance().installEventFilter(self)

        path = vault_path or self.settings.last_vault or str(default_vault_path())
        self._unlock.set_vault_path(path)
        if Path(path).exists():
            self._show_unlock()
        else:
            self._show_create()

    # -- screens -----------------------------------------------------------

    def _show_unlock(self) -> None:
        self._stack.setCurrentWidget(self._unlock)
        self._unlock.reset()

    def _show_create(self) -> None:
        target = Path(self._unlock.vault_path)
        n = 2
        while target.exists():  # suggest a free name next to the current vault
            target = target.with_name(f"vault-{n}{default_vault_path().suffix}")
            n += 1
        self._create.reset(str(target))
        self._stack.setCurrentWidget(self._create)

    def _open(self, vault: Vault) -> None:
        self.vault = vault
        self._remember_path(str(vault.path))
        self._unlock.set_vault_path(str(vault.path))
        self._main.clipboard_seconds = self.settings.clipboard_seconds
        self._main.load(vault)
        self._stack.setCurrentWidget(self._main)
        self._reset_idle()

    def lock(self) -> None:
        self._idle.stop()
        if self.vault is None:
            return
        # Close any open dialogs (entry editor, generator) so no secrets linger on screen.
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()
        self.clipboard.clear()
        self._main.unload()
        self.vault.lock()
        self.vault = None
        self._show_unlock()

    # -- menu actions ------------------------------------------------------

    def _change_password(self) -> None:
        if self.vault and ChangePasswordDialog(self.vault, self).exec() == QDialog.Accepted:
            self._main.set_status("Master password changed")

    def _switch_vault(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open vault", str(Path(self._unlock.vault_path).parent), VAULT_FILTER
        )
        if path:
            self.lock()
            self._unlock.set_vault_path(path)
            self._remember_path(path)

    def _edit_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply_to(self.settings)
            self._save_settings()
            self._main.clipboard_seconds = self.settings.clipboard_seconds
            self._reset_idle()

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About Keyhold",
            f"<b>Keyhold {__version__}</b><br><br>"
            "An offline, open-source password manager.<br>"
            "Argon2id key derivation · XChaCha20-Poly1305 encryption.<br><br>"
            "Licensed under the GNU GPL v3 or later.",
        )

    # -- settings ----------------------------------------------------------

    def _remember_path(self, path: str) -> None:
        self.settings.last_vault = path
        self._save_settings()

    def _save_settings(self) -> None:
        try:
            self.settings.save()
        except OSError:
            pass  # preferences are a convenience; never block on them

    # -- auto-lock ---------------------------------------------------------

    def _reset_idle(self) -> None:
        if self.vault is not None and self.settings.autolock_minutes > 0:
            self._idle.start(self.settings.autolock_minutes * 60_000)
        else:
            self._idle.stop()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() in _ACTIVITY_EVENTS and self.vault is not None:
            self._reset_idle()
        return False

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.WindowStateChange and self.isMinimized() and self.settings.lock_on_minimize:
            self.lock()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        self.lock()
        super().closeEvent(event)


ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"


def run(vault_path: str | None = None) -> int:
    if sys.platform == "win32":
        # Group under our own taskbar entry and icon instead of python.exe's.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Keyhold")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Keyhold")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setStyleSheet(theme.STYLESHEET)
    window = MainWindow(vault_path)
    window.show()
    return app.exec()
