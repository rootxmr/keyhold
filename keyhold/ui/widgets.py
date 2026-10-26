"""Small reusable widgets and helpers."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

from PySide6.QtCore import QMimeData, QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..generator import strength_label
from . import theme


def label(text: str = "", name: str | None = None, *, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def button(text: str, name: str | None = None, on_click: Callable | None = None) -> QPushButton:
    btn = QPushButton(text)
    if name:
        btn.setObjectName(name)
    btn.setCursor(Qt.PointingHandCursor)
    if on_click:
        btn.clicked.connect(on_click)
    return btn


def separator() -> QFrame:
    line = QFrame()
    line.setObjectName("separator")
    line.setFrameShape(QFrame.NoFrame)
    line.setFixedHeight(1)
    return line


def field(caption: str, widget: QWidget) -> QWidget:
    """A small uppercase caption above a widget."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    layout.addWidget(label(caption.upper(), "fieldLabel"))
    layout.addWidget(widget)
    return box


def centered(content: QWidget, width: int = 380) -> QWidget:
    """Place content in a fixed-width column centred in the available space."""
    content.setFixedWidth(width)
    outer = QWidget()
    outer.setObjectName("root")
    h = QHBoxLayout(outer)
    h.addStretch()
    v = QVBoxLayout()
    v.addStretch()
    v.addWidget(content)
    v.addStretch()
    h.addLayout(v)
    h.addStretch()
    return outer


class PasswordEdit(QLineEdit):
    """A masked line edit with an inline Show/Hide toggle."""

    def __init__(self, placeholder: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.Password)
        self.setPlaceholderText(placeholder)
        self._toggle = QToolButton(self)
        self._toggle.setText("Show")
        self._toggle.setCursor(Qt.PointingHandCursor)
        self._toggle.setFocusPolicy(Qt.NoFocus)
        self._toggle.setToolTip("Show or hide (Ctrl+H)")
        self._toggle.clicked.connect(self.toggle_visible)

    def set_visible(self, visible: bool) -> None:
        self.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        self._toggle.setText("Hide" if visible else "Show")

    def toggle_visible(self) -> None:
        self.set_visible(self.echoMode() == QLineEdit.Password)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_H and event.modifiers() & Qt.ControlModifier:
            self.toggle_visible()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        hint = self._toggle.sizeHint()
        self._toggle.move(self.width() - hint.width() - 6, (self.height() - hint.height()) // 2)
        self.setTextMargins(0, 0, hint.width() + 4, 0)


class StrengthMeter(QWidget):
    """A thin four-segment bar plus a caption describing entropy."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._bits = 0.0
        self._bar = _Bar()
        self._caption = label("", "muted")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._bar, 1)
        layout.addWidget(self._caption)

    def set_bits(self, bits: float, *, show_bits: bool = True) -> None:
        self._bits = bits
        self._bar.set_bits(bits)
        if bits <= 0:
            self._caption.setText("")
        elif show_bits:
            self._caption.setText(f"{bits:.0f} bits · {strength_label(bits)}")
        else:
            self._caption.setText(strength_label(bits))


class _Bar(QWidget):
    def __init__(self):
        super().__init__()
        self._bits = 0.0
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_bits(self, bits: float) -> None:
        self._bits = bits
        self.update()

    def paintEvent(self, _event) -> None:
        if self._bits <= 0:
            filled, color = 0, theme.BORDER
        elif self._bits < 40:
            filled, color = 1, theme.DANGER
        elif self._bits < 64:
            filled, color = 2, theme.WARN
        elif self._bits < 100:
            filled, color = 3, theme.OK
        else:
            filled, color = 4, theme.OK
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        gap = 4
        seg = (self.width() - gap * 3) / 4
        for i in range(4):
            p.setBrush(QColor(color if i < filled else theme.BORDER))
            p.drawRoundedRect(QRectF(i * (seg + gap), 0, seg, self.height()), 2, 2)


class Task(QObject):
    """Run a blocking function (e.g. Argon2) on a background thread.

    Callbacks are delivered on the GUI thread. Connect only bound methods of
    QObjects so Qt can route the queued call to the right thread.
    """

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, fn: Callable[[], object], on_success, on_failure, parent: QObject):
        super().__init__(parent)
        self._fn = fn
        self.succeeded.connect(on_success, Qt.QueuedConnection)
        self.failed.connect(on_failure, Qt.QueuedConnection)
        self.succeeded.connect(self.deleteLater, Qt.QueuedConnection)
        self.failed.connect(self.deleteLater, Qt.QueuedConnection)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            signal, payload = self.failed, exc
        else:
            signal, payload = self.succeeded, result
        try:
            signal.emit(payload)
        except RuntimeError:
            pass  # the receiving widget was destroyed while we worked


class SecureClipboard(QObject):
    """Copies secrets and wipes them from the clipboard after a timeout.

    Also marks the data so Windows clipboard history / cloud sync and KDE
    Klipper skip it.
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._secret: str | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear)

    def copy(self, text: str, seconds: int) -> None:
        mime = QMimeData()
        mime.setText(text)
        if sys.platform == "win32":
            win = 'application/x-qt-windows-mime;value="{}"'
            mime.setData(win.format("ExcludeClipboardContentFromMonitorProcessing"), b"\x01\x00\x00\x00")
            mime.setData(win.format("CanIncludeInClipboardHistory"), b"\x00\x00\x00\x00")
            mime.setData(win.format("CanUploadToCloudClipboard"), b"\x00\x00\x00\x00")
        else:
            mime.setData("x-kde-passwordManagerHint", b"secret")
        QGuiApplication.clipboard().setMimeData(mime)
        self._secret = text
        if seconds > 0:
            self._timer.start(seconds * 1000)

    def clear(self) -> None:
        """Clear the clipboard, but only if it still holds what we put there."""
        self._timer.stop()
        if self._secret is not None:
            clipboard = QGuiApplication.clipboard()
            if clipboard.text() == self._secret:
                clipboard.clear()
            self._secret = None
