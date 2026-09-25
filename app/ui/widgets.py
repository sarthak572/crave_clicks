"""Reusable UI building blocks for CafePOS."""

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtGui import QFocusEvent, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import Color, icon, pixmap


class AutoSelectDoubleSpinBox(QDoubleSpinBox):
    """A QDoubleSpinBox that automatically selects all text when focused."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Money and rate fields are typed, not stepped, so the arrow buttons only add noise.
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Select all text on focus so typing replaces the existing value."""
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


def set_variant(widget: QWidget, variant: str) -> None:
    """Choose a button's visual variant (primary, success, danger, ghost, dashed) from the stylesheet."""
    widget.setProperty("variant", variant)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def make_button(text: str, variant: str | None = None, icon_name: str | None = None) -> QPushButton:
    """Create a pointer-cursor button with an optional variant and icon."""
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if variant:
        set_variant(button, variant)
    if icon_name:
        light = variant in ("primary", "success")
        colors = {"danger": Color.DANGER}
        button.setIcon(icon(icon_name, "#FFFFFF" if light else colors.get(variant, Color.TEXT_MUTED)))
        button.setIconSize(QSize(18, 18))
    return button


def style_dialog_buttons(
    buttons: QDialogButtonBox, primary: QDialogButtonBox.StandardButton
) -> None:
    """Give a dialog's confirm button the primary look and make it the Enter-key default."""
    for button in buttons.buttons():
        button.setCursor(Qt.CursorShape.PointingHandCursor)
    confirm = buttons.button(primary)
    set_variant(confirm, "primary")
    confirm.setDefault(True)


def make_card() -> QFrame:
    """Create an empty white rounded surface."""
    card = QFrame()
    card.setObjectName("card")
    return card


def make_divider() -> QFrame:
    """Create a one-pixel horizontal rule for use inside cards."""
    divider = QFrame()
    divider.setObjectName("cardDivider")
    divider.setFixedHeight(1)
    return divider


def dialog_header(title: str, subtitle: str = "") -> QWidget:
    """Create the title block shown at the top of every dialog."""
    header = QWidget()
    layout = QVBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("dialogTitle")
    layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
    return header


def make_empty_state(icon_name: str, title: str, text: str = "") -> QWidget:
    """Create a centered placeholder for screens that have nothing to show yet."""
    holder = QWidget()
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(6)
    layout.addStretch()

    badge = QLabel()
    badge.setObjectName("emptyIcon")
    badge.setFixedSize(64, 64)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setPixmap(pixmap(icon_name, Color.TEXT_FAINT, 28))
    layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
    layout.addSpacing(6)

    title_label = QLabel(title)
    title_label.setObjectName("emptyTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)
    if text:
        text_label = QLabel(text)
        text_label.setObjectName("emptyText")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setWordWrap(True)
        layout.addWidget(text_label)
    layout.addStretch()
    return holder


class PageHeader(QWidget):
    """Title bar for a screen: back button, title, subtitle and a slot for actions."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.back_button = make_button("Back", "ghost", "arrow-left")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("pageTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("pageSubtitle")
        self.subtitle_label.setVisible(bool(subtitle))

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(0)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(10)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.back_button)
        layout.addLayout(titles)
        layout.addStretch()
        layout.addLayout(self.actions)

    def set_subtitle(self, text: str) -> None:
        """Update the line of context under the title."""
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    def add_action(self, widget: QWidget) -> None:
        """Place a control (search box, export button) on the right of the header."""
        self.actions.addWidget(widget)


class StatCard(QFrame):
    """A headline number with a title and an icon, used for dashboard and report summaries."""

    def __init__(
        self, title: str, icon_name: str, text_value: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")

        title_label = QLabel(title)
        title_label.setObjectName("statTitle")

        self.icon_label = QLabel()
        self.icon_label.setObjectName("statIcon")
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setPixmap(pixmap(icon_name, Color.ACCENT, 20))

        self.value_label = QLabel("0")
        # Names (a best-selling item) are text rather than numbers, so they get a smaller, wrapping value.
        self.value_label.setObjectName("statValueText" if text_value else "statValue")
        self.value_label.setWordWrap(text_value)

        top_row = QHBoxLayout()
        top_row.addWidget(title_label, 1, Qt.AlignmentFlag.AlignTop)
        top_row.addWidget(self.icon_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)
        layout.addLayout(top_row)
        layout.addWidget(self.value_label)


class RevealStatCard(StatCard):
    """A StatCard that keeps its value hidden until it is clicked, then hides it again by itself.

    Used for figures that should not be visible to anyone glancing at the screen, such as revenue.
    """

    AUTO_HIDE_MS = 10_000
    MASK = "₹ ••••••"

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, "eye-off", parent=parent)
        self._text = ""
        self._revealed = False
        self._auto_hide = QTimer(self)
        self._auto_hide.setSingleShot(True)
        self._auto_hide.setInterval(self.AUTO_HIDE_MS)
        self._auto_hide.timeout.connect(self.hide_value)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._render()

    def is_revealed(self) -> bool:
        """Return whether the real value is currently showing."""
        return self._revealed

    def set_value(self, text: str) -> None:
        """Store the real value; it is only displayed while revealed."""
        self._text = text
        self._render()

    def toggle(self) -> None:
        """Show the value (and start the auto-hide timer), or hide it again."""
        self._revealed = not self._revealed
        if self._revealed:
            self._auto_hide.start()
        else:
            self._auto_hide.stop()
        self._render()

    def hide_value(self) -> None:
        """Mask the value again."""
        self._revealed = False
        self._auto_hide.stop()
        self._render()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Toggle on a left click anywhere on the card."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        super().mousePressEvent(event)

    def _render(self) -> None:
        self.value_label.setText(self._text if self._revealed else self.MASK)
        self.icon_label.setPixmap(pixmap("eye" if self._revealed else "eye-off", Color.ACCENT, 20))
        self.setToolTip("Click to hide" if self._revealed else "Click to show")


class SegmentedControl(QWidget):
    """A row of mutually exclusive, equally sized choices (for example Cash / UPI / Split)."""

    currentChanged = Signal(int)

    def __init__(self, options: list[tuple[str, str | None]], parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._texts = [text for text, _icon in options]
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for index, (text, icon_name) in enumerate(options):
            button = QPushButton(f"  {text}" if icon_name else text)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if icon_name:
                button.setIcon(icon(icon_name, Color.TEXT_MUTED, Color.ACCENT))
                button.setIconSize(QSize(18, 18))
            self._group.addButton(button, index)
            layout.addWidget(button, 1)
            self._buttons.append(button)
        self._buttons[0].setChecked(True)
        self._group.idToggled.connect(self._on_toggled)

    def buttons(self) -> list[QPushButton]:
        """Return the choice buttons in display order."""
        return list(self._buttons)

    def currentIndex(self) -> int:
        """Return the index of the selected choice."""
        return self._group.checkedId()

    def currentText(self) -> str:
        """Return the label of the selected choice."""
        return self._texts[self.currentIndex()]

    def setCurrentIndex(self, index: int) -> None:
        """Select a choice by position."""
        self._buttons[index].setChecked(True)

    def _on_toggled(self, index: int, checked: bool) -> None:
        if checked:
            self.currentChanged.emit(index)
