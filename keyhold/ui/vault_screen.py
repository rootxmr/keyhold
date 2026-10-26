"""The unlocked view: entry list on the left, details on the right."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRect, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from .. import generator
from ..vault import Entry, Vault
from . import theme
from .generator_dialog import GeneratorDialog
from .widgets import PasswordEdit, SecureClipboard, StrengthMeter, button, field, label, separator

ENTRY_ID = Qt.UserRole
SUBTITLE = Qt.UserRole + 1
MASK = "•" * 12


class _EntryDelegate(QStyledItemDelegate):
    """Two-line rows: title, then username in a muted tone."""

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), 50)

    def paint(self, painter: QPainter, option, index) -> None:
        self.initStyleOption(option, index)
        title = index.data(Qt.DisplayRole)
        option.text = ""
        option.widget.style().drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)

        r = option.rect.adjusted(18, 8, -12, -8)
        subtitle = index.data(SUBTITLE) or ""
        half = r.height() // 2
        painter.save()
        font = QFont(option.font)
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT))
        top = QRect(r.left(), r.top(), r.width(), half) if subtitle else r
        self._draw_elided(painter, top, title)
        if subtitle:
            painter.setFont(option.font)
            painter.setPen(QColor(theme.MUTED))
            self._draw_elided(painter, QRect(r.left(), r.top() + half, r.width(), half), subtitle)
        painter.restore()

    @staticmethod
    def _draw_elided(painter: QPainter, rect: QRect, text: str) -> None:
        elided = painter.fontMetrics().elidedText(text, Qt.ElideRight, rect.width())
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, elided)


class _DetailRow(QWidget):
    def __init__(self, caption: str, value: str, *, mono: bool = False, secret: bool = False):
        super().__init__()
        self._value = value
        self._secret = secret
        self._text = label(MASK if secret else value, "mono" if mono or secret else None)
        self._text.setTextInteractionFlags(Qt.NoTextInteraction if secret else Qt.TextSelectableByMouse)
        self._text.setWordWrap(not secret)
        self._actions = QHBoxLayout()
        self._actions.setSpacing(2)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._text, 1)
        row.addLayout(self._actions)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(label(caption.upper(), "fieldLabel"))
        layout.addLayout(row)

    def add_action(self, text: str, slot) -> QPushButton:
        btn = button(text, "ghost", slot)
        self._actions.addWidget(btn)
        return btn

    def toggle_reveal(self) -> bool:
        """Switch between masked and plain text; returns True if now revealed."""
        reveal = self._text.text() == MASK
        self._text.setText(self._value if reveal else MASK)
        self._text.setTextInteractionFlags(Qt.TextSelectableByMouse if reveal else Qt.NoTextInteraction)
        return reveal


class EntryDialog(QDialog):
    def __init__(self, clipboard: SecureClipboard, clipboard_seconds: int, entry: Entry | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit entry" if entry else "New entry")
        self.setMinimumWidth(460)
        self._clipboard = clipboard
        self._clipboard_seconds = clipboard_seconds
        entry = entry or Entry()

        self.title = QLineEdit(entry.title)
        self.title.setPlaceholderText("e.g. Email, Bank, GitHub")
        self.username = QLineEdit(entry.username)
        self.password = PasswordEdit()
        self.password.setText(entry.password)
        self.password.setObjectName("mono")
        self.url = QLineEdit(entry.url)
        self.url.setPlaceholderText("https://")
        self.notes = QPlainTextEdit(entry.notes)
        self.notes.setFixedHeight(90)
        self.notes.setTabChangesFocus(True)
        self._meter = StrengthMeter()
        self.password.textChanged.connect(
            lambda t: self._meter.set_bits(generator.estimate_entropy(t), show_bits=False)
        )
        self._meter.set_bits(generator.estimate_entropy(entry.password), show_bits=False)
        self._error = label("", "error")

        pw_row = QWidget()
        pw = QHBoxLayout(pw_row)
        pw.setContentsMargins(0, 0, 0, 0)
        pw.addWidget(self.password, 1)
        pw.addWidget(button("Generate", on_click=self._generate))

        save = button("Save", "primary", self._save)
        save.setDefault(True)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(button("Cancel", on_click=self.reject))
        actions.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(field("Title", self.title))
        layout.addWidget(field("Username", self.username))
        layout.addWidget(field("Password", pw_row))
        layout.addWidget(self._meter)
        layout.addWidget(field("Website", self.url))
        layout.addWidget(field("Notes", self.notes))
        layout.addWidget(self._error)
        layout.addLayout(actions)
        self.title.setFocus()

    def _generate(self) -> None:
        dlg = GeneratorDialog(self._clipboard, self._clipboard_seconds, picker=True, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.value:
            self.password.setText(dlg.value)

    def _save(self) -> None:
        if not self.title.text().strip():
            self._error.setText("Give the entry a title.")
            self.title.setFocus()
            return
        self.accept()

    def values(self) -> dict[str, str]:
        return {
            "title": self.title.text().strip(),
            "username": self.username.text().strip(),
            "password": self.password.text(),
            "url": self.url.text().strip(),
            "notes": self.notes.toPlainText(),
        }


class VaultScreen(QWidget):
    lock_requested = Signal()
    change_password_requested = Signal()
    switch_vault_requested = Signal()
    settings_requested = Signal()
    about_requested = Signal()

    def __init__(self, clipboard: SecureClipboard):
        super().__init__()
        self.vault: Vault | None = None
        self.clipboard_seconds = 20
        self._clipboard = clipboard

        # Top bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search  (Ctrl+F)")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _text: self._refresh())
        menu = QMenu(self)
        menu.addAction("Change master password…", self.change_password_requested.emit)
        menu.addAction("Open another vault…", self.switch_vault_requested.emit)
        menu.addAction("Settings…", self.settings_requested.emit)
        menu.addSeparator()
        menu.addAction("About Keyhold", self.about_requested.emit)
        more = button("•••", "ghost")
        more.setToolTip("More")
        more.setMenu(menu)
        more.setStyleSheet("QPushButton::menu-indicator { width: 0; }")

        top = QHBoxLayout()
        top.setContentsMargins(16, 12, 16, 12)
        top.setSpacing(8)
        top.addWidget(self._search, 1)
        top.addWidget(button("New entry", "primary", self._new_entry))
        top.addWidget(button("Generator", on_click=self._open_generator))
        top.addWidget(more)
        top.addWidget(button("Lock", on_click=self.lock_requested.emit))

        # Entry list
        self._list = QListWidget()
        self._list.setItemDelegate(_EntryDelegate(self._list))
        self._list.setFixedWidth(280)
        self._list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self._list.currentItemChanged.connect(self._show_current)
        self._list.itemDoubleClicked.connect(lambda _: self._copy_field("password"))

        # Detail pane
        self._detail_host = QScrollArea()
        self._detail_host.setWidgetResizable(True)
        self._detail_host.setFrameShape(QScrollArea.NoFrame)
        self._empty = self._empty_state()
        self._detail_stack = QStackedWidget()
        self._detail_stack.addWidget(self._empty)
        self._detail_stack.addWidget(self._detail_host)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._list)
        body.addWidget(self._detail_stack, 1)

        self._status = label("", "muted")
        status_row = QHBoxLayout()
        status_row.setContentsMargins(16, 6, 16, 8)
        status_row.addWidget(self._status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addWidget(separator())
        layout.addLayout(body, 1)
        layout.addWidget(separator())
        layout.addLayout(status_row)

        QShortcut(QKeySequence.Find, self, self._search.setFocus)
        QShortcut(QKeySequence.New, self, self._new_entry)
        QShortcut(QKeySequence("Ctrl+L"), self, self.lock_requested.emit)
        QShortcut(QKeySequence("Ctrl+G"), self, self._open_generator)
        QShortcut(QKeySequence("Ctrl+B"), self, lambda: self._copy_field("username"))
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, lambda: self._copy_field("password"))
        QShortcut(QKeySequence("Ctrl+E"), self, self._edit_current)
        QShortcut(QKeySequence.Delete, self._list, self._delete_current)

    # -- public ------------------------------------------------------------

    def load(self, vault: Vault) -> None:
        self.vault = vault
        self._search.clear()
        self._refresh()
        self._list.setFocus()

    def unload(self) -> None:
        self.vault = None
        self._search.clear()
        self._list.clear()
        self._set_detail(None)
        self._status.setText("")

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    # -- list --------------------------------------------------------------

    def _refresh(self, select_id: str | None = None) -> None:
        if self.vault is None:
            return
        current = select_id or self._current_id()
        self._list.blockSignals(True)
        self._list.clear()
        entries = self.vault.search(self._search.text().strip())
        for e in entries:
            item = QListWidgetItem(e.title or "(untitled)")
            item.setData(ENTRY_ID, e.id)
            item.setData(SUBTITLE, e.username or e.url)
            self._list.addItem(item)
        self._list.blockSignals(False)
        row = next((i for i, e in enumerate(entries) if e.id == current), 0 if entries else -1)
        self._list.setCurrentRow(row)
        self._show_current()
        total = len(self.vault.entries)
        self._status.setText(f"{total} entr{'y' if total == 1 else 'ies'}  ·  {self.vault.path}")

    def _current_id(self) -> str | None:
        item = self._list.currentItem()
        return item.data(ENTRY_ID) if item else None

    def _current_entry(self) -> Entry | None:
        entry_id = self._current_id()
        return self.vault.get(entry_id) if self.vault and entry_id else None

    # -- detail ------------------------------------------------------------

    def _empty_state(self) -> QWidget:
        w = QWidget()
        w.setObjectName("root")
        layout = QVBoxLayout(w)
        layout.addStretch()
        self._empty_label = label("No entries yet", "muted")
        self._empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._empty_label)
        layout.addStretch()
        return w

    def _show_current(self, *_args) -> None:
        self._set_detail(self._current_entry())

    def _set_detail(self, entry: Entry | None) -> None:
        if entry is None:
            has_entries = bool(self.vault and self.vault.entries)
            self._empty_label.setText("No matches" if has_entries else "No entries yet. Press Ctrl+N to add one.")
            self._detail_stack.setCurrentIndex(0)
            return

        page = QWidget()
        page.setObjectName("root")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)
        layout.addWidget(label(entry.title or "(untitled)", "heading"))

        if entry.username:
            row = _DetailRow("Username", entry.username)
            row.add_action("Copy", lambda: self._copy_field("username"))
            layout.addWidget(row)
        if entry.password:
            row = _DetailRow("Password", entry.password, secret=True)
            reveal = row.add_action("Show", lambda: reveal.setText("Hide" if row.toggle_reveal() else "Show"))
            row.add_action("Copy", lambda: self._copy_field("password"))
            layout.addWidget(row)
        if entry.url:
            row = _DetailRow("Website", entry.url)
            row.add_action("Open", lambda: self._open_url(entry.url))
            row.add_action("Copy", lambda: self._copy_field("url"))
            layout.addWidget(row)
        if entry.notes:
            layout.addWidget(_DetailRow("Notes", entry.notes))

        modified = datetime.fromtimestamp(entry.modified).strftime("%d %b %Y, %H:%M")
        layout.addWidget(label(f"Modified {modified}", "muted"))

        actions = QHBoxLayout()
        actions.addWidget(button("Edit", on_click=self._edit_current))
        actions.addWidget(button("Delete", "danger", self._delete_current))
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

        old = self._detail_host.takeWidget()
        if old is not None:
            old.deleteLater()
        self._detail_host.setWidget(page)
        self._detail_stack.setCurrentIndex(1)

    # -- actions -----------------------------------------------------------

    def _copy_field(self, name: str) -> None:
        entry = self._current_entry()
        if entry is None or not getattr(entry, name):
            return
        self._clipboard.copy(getattr(entry, name), self.clipboard_seconds)
        what = {"username": "Username", "password": "Password", "url": "Website"}[name]
        suffix = f", clears in {self.clipboard_seconds}s" if self.clipboard_seconds else ""
        self._status.setText(f"{what} copied{suffix}")

    def _open_url(self, url: str) -> None:
        if "://" not in url:
            url = "https://" + url
        QDesktopServices.openUrl(QUrl(url))

    def _open_generator(self) -> None:
        GeneratorDialog(self._clipboard, self.clipboard_seconds, parent=self).exec()

    def _new_entry(self) -> None:
        if self.vault is None:
            return
        dlg = EntryDialog(self._clipboard, self.clipboard_seconds, parent=self)
        if dlg.exec() == QDialog.Accepted:
            if self._save(lambda: self.vault.add(Entry(**dlg.values()))):
                self._search.clear()
                self._refresh(self.vault.entries[-1].id)

    def _edit_current(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        dlg = EntryDialog(self._clipboard, self.clipboard_seconds, entry, parent=self)
        if dlg.exec() == QDialog.Accepted:
            if self._save(lambda: self.vault.update(entry.id, **dlg.values())):
                self._refresh(entry.id)

    def _delete_current(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete entry",
            f"Delete “{entry.title}”? This cannot be undone.",
            QMessageBox.Delete | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer == QMessageBox.Delete and self._save(lambda: self.vault.delete(entry.id)):
            self._refresh()

    def _save(self, change) -> bool:
        try:
            change()
        except OSError as exc:
            QMessageBox.critical(self, "Could not save", f"The vault could not be written:\n{exc}")
            return False
        return True
