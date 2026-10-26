"""The password generator dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import generator
from .widgets import SecureClipboard, StrengthMeter, button, field, label

MODES = ("Password", "Passphrase", "Seed phrase", "PIN", "Key")


class _Range(QWidget):
    """A slider paired with a spin box."""

    changed = Signal(int)

    def __init__(self, low: int, high: int, value: int):
        super().__init__()
        self.slider = QSlider(Qt.Horizontal)
        self.spin = QSpinBox()
        for w in (self.slider, self.spin):
            w.setRange(low, high)
            w.setValue(value)
        self.spin.setFixedWidth(64)
        self.spin.setAlignment(Qt.AlignCenter)
        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.spin.valueChanged.connect(self.changed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)

    def value(self) -> int:
        return self.spin.value()


def _column(*widgets: QWidget) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)
    for w in widgets:
        layout.addWidget(w)
    layout.addStretch()
    return page


def _row(*widgets: QWidget) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(18)
    for w in widgets:
        layout.addWidget(w)
    layout.addStretch()
    return row


class GeneratorDialog(QDialog):
    """Generate a secret. In picker mode a "Use" button returns the value."""

    _last_mode = 0  # remembered for the session

    def __init__(self, clipboard: SecureClipboard, clipboard_seconds: int, *, picker: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generator")
        self.setMinimumWidth(580)
        self._clipboard = clipboard
        self._clipboard_seconds = clipboard_seconds
        self.value = ""

        # Mode switcher
        self._modes = QButtonGroup(self)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        for i, name in enumerate(MODES):
            b = button(name)
            b.setCheckable(True)
            self._modes.addButton(b, i)
            mode_row.addWidget(b)
        mode_row.addStretch()

        # Output
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setObjectName("mono")
        self._output.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self._output.setFixedHeight(88)
        self._output.setTabChangesFocus(True)
        self._meter = StrengthMeter()

        # Options per mode
        self._stack = QStackedWidget()
        self._stack.addWidget(self._password_page())
        self._stack.addWidget(self._passphrase_page())
        self._stack.addWidget(self._seed_page())
        self._stack.addWidget(self._pin_page())
        self._stack.addWidget(self._key_page())

        self._error = label("", "error")
        self._error.hide()

        regenerate = button("Regenerate", on_click=self.generate)
        copy = button("Copy", on_click=self._copy)
        actions = QHBoxLayout()
        actions.addWidget(regenerate)
        actions.addWidget(copy)
        actions.addStretch()
        if picker:
            actions.addWidget(button("Cancel", on_click=self.reject))
            use = button("Use", "primary", self._use)
            use.setDefault(True)
            actions.addWidget(use)
        else:
            close = button("Close", "primary", self.accept)
            actions.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addLayout(mode_row)
        layout.addWidget(self._output)
        layout.addWidget(self._meter)
        layout.addWidget(self._error)
        layout.addWidget(self._stack)
        layout.addLayout(actions)

        self._modes.idToggled.connect(self._on_mode)
        self._modes.button(GeneratorDialog._last_mode).setChecked(True)
        regenerate.setFocus()

    # -- option pages ------------------------------------------------------

    def _password_page(self) -> QWidget:
        self._pw_length = _Range(4, 128, 24)
        self._pw_upper = QCheckBox("A–Z")
        self._pw_lower = QCheckBox("a–z")
        self._pw_digits = QCheckBox("0–9")
        self._pw_symbols = QCheckBox("!@#$%")
        self._pw_ambiguous = QCheckBox("Avoid look-alikes (l 1 O 0)")
        for box in (self._pw_upper, self._pw_lower, self._pw_digits, self._pw_symbols):
            box.setChecked(True)
        self._pw_length.changed.connect(self.generate)
        for box in (self._pw_upper, self._pw_lower, self._pw_digits, self._pw_symbols, self._pw_ambiguous):
            box.toggled.connect(self.generate)
        return _column(
            field("Length", self._pw_length),
            _row(self._pw_upper, self._pw_lower, self._pw_digits, self._pw_symbols),
            self._pw_ambiguous,
        )

    def _passphrase_page(self) -> QWidget:
        self._pp_words = _Range(3, 20, 6)
        self._pp_sep = QComboBox()
        for text, sep in (("Hyphen  -", "-"), ("Space", " "), ("Period  .", "."), ("Underscore  _", "_"), ("None", "")):
            self._pp_sep.addItem(text, sep)
        self._pp_cap = QCheckBox("Capitalize")
        self._pp_num = QCheckBox("Add a number")
        self._pp_words.changed.connect(self.generate)
        self._pp_sep.currentIndexChanged.connect(self.generate)
        self._pp_cap.toggled.connect(self.generate)
        self._pp_num.toggled.connect(self.generate)
        return _column(
            field("Words", self._pp_words),
            _row(field("Separator", self._pp_sep), self._pp_cap, self._pp_num),
            label("Words from the EFF large wordlist, ~12.9 bits each.", "muted"),
        )

    def _seed_page(self) -> QWidget:
        self._seed_words = QComboBox()
        for n in generator.SEED_WORD_COUNTS:
            self._seed_words.addItem(f"{n} words", n)
        self._seed_words.setCurrentIndex(len(generator.SEED_WORD_COUNTS) - 1)
        self._seed_words.currentIndexChanged.connect(self.generate)
        return _column(
            field("Length", self._seed_words),
            label(
                "BIP39 English mnemonic with a valid checksum. For a real cryptocurrency "
                "wallet, prefer letting the wallet device generate its own seed.",
                "muted",
                wrap=True,
            ),
        )

    def _pin_page(self) -> QWidget:
        self._pin_length = _Range(4, 16, 6)
        self._pin_length.changed.connect(self.generate)
        return _column(field("Digits", self._pin_length))

    def _key_page(self) -> QWidget:
        self._key_bytes = QComboBox()
        for n in (16, 24, 32, 64):
            self._key_bytes.addItem(f"{n * 8}-bit  ({n * 2} hex characters)", n)
        self._key_bytes.setCurrentIndex(2)
        self._key_bytes.currentIndexChanged.connect(self.generate)
        return _column(field("Size", self._key_bytes))

    # -- behaviour ---------------------------------------------------------

    def _on_mode(self, mode: int, checked: bool) -> None:
        if checked:
            GeneratorDialog._last_mode = mode
            self._stack.setCurrentIndex(mode)
            self.generate()

    def generate(self) -> None:
        mode = self._modes.checkedId()
        try:
            if mode == 0:
                result = generator.generate_password(
                    self._pw_length.value(),
                    upper=self._pw_upper.isChecked(),
                    lower=self._pw_lower.isChecked(),
                    digits=self._pw_digits.isChecked(),
                    symbols=self._pw_symbols.isChecked(),
                    exclude_ambiguous=self._pw_ambiguous.isChecked(),
                )
            elif mode == 1:
                result = generator.generate_passphrase(
                    self._pp_words.value(),
                    separator=self._pp_sep.currentData(),
                    capitalize=self._pp_cap.isChecked(),
                    add_number=self._pp_num.isChecked(),
                )
            elif mode == 2:
                result = generator.generate_seed_phrase(self._seed_words.currentData())
            elif mode == 3:
                result = generator.generate_pin(self._pin_length.value())
            else:
                result = generator.generate_hex(self._key_bytes.currentData())
        except ValueError as exc:
            self.value = ""
            self._output.clear()
            self._meter.set_bits(0)
            self._error.setText(str(exc))
            self._error.show()
            return
        self._error.hide()
        self.value = result.value
        self._output.setPlainText(result.value)
        self._meter.set_bits(result.entropy)

    def _copy(self) -> None:
        if self.value:
            self._clipboard.copy(self.value, self._clipboard_seconds)

    def _use(self) -> None:
        if self.value:
            self.accept()
