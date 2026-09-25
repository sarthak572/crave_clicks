"""Tappable menu-item cards for the billing screen."""

import re

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QResizeEvent, QTextLayout
from PySide6.QtWidgets import QAbstractItemView, QListView, QListWidget, QStyle, QStyledItemDelegate, QWidget

from app.ui.theme import Color

QUANTITY_ROLE = Qt.ItemDataRole.UserRole + 1
DIET_ROLE = Qt.ItemDataRole.UserRole + 2
PRICE_ROLE = Qt.ItemDataRole.UserRole + 3

_MIN_CARD_WIDTH = 164
_CARD_HEIGHT = 108
_GUTTER = 6
_SCROLLBAR_ALLOWANCE = 18  # 12px bar plus its 2px margins, with a little to spare


def diet_type(category: str) -> str | None:
    """Return "veg" or "nonveg" when a category name says so (for example "Pizza - Premium Non-Veg")."""
    name = category.lower()
    if re.search(r"non[\s-]?veg", name):
        return "nonveg"
    if re.search(r"\bveg\b", name):
        return "veg"
    return None


def wrap_lines(text: str, font: QFont, width: int, max_lines: int = 2) -> list[str]:
    """Break text into at most ``max_lines`` lines that fit ``width``, eliding the end when it is longer."""
    layout = QTextLayout(text, font)
    layout.beginLayout()
    spans: list[tuple[int, int]] = []
    while len(spans) < max_lines:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(width)
        spans.append((line.textStart(), line.textLength()))
    layout.endLayout()

    lines = [text[start : start + length].strip() for start, length in spans]
    consumed = spans[-1][0] + spans[-1][1] if spans else 0
    if consumed < len(text):
        lines[-1] = QFontMetrics(font).elidedText(text[spans[-1][0] :].strip(), Qt.TextElideMode.ElideRight, width)
    return lines


class MenuItemCardDelegate(QStyledItemDelegate):
    """Paint each menu item as a card with its name, price, veg marker and in-cart quantity."""

    def sizeHint(self, option: object, index: object) -> QSize:
        view = getattr(option, "widget", None)
        return view.gridSize() if view is not None else QSize(_MIN_CARD_WIDTH, _CARD_HEIGHT)

    def paint(self, painter: QPainter, option: object, index: object) -> None:
        quantity = index.data(QUANTITY_ROLE) or 0
        diet = index.data(DIET_ROLE)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        card = QRectF(option.rect).adjusted(_GUTTER, _GUTTER, -_GUTTER, -_GUTTER)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if quantity:
            border, fill, width = QColor(Color.ACCENT), QColor(Color.ACCENT_SOFT), 1.6
        elif hovered:
            border, fill, width = QColor(Color.TEXT_FAINT), QColor(Color.SURFACE_ALT), 1.0
        else:
            border, fill, width = QColor(Color.BORDER), QColor(Color.SURFACE), 1.0
        painter.setPen(QPen(border, width))
        painter.setBrush(fill)
        painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)

        pad = 14
        name_font = QFont(option.font)
        name_font.setPixelSize(14)
        name_font.setWeight(QFont.Weight.DemiBold)
        name_width = int(card.width() - pad * 2 - (18 if diet else 0))
        painter.setFont(name_font)
        painter.setPen(QColor(Color.TEXT))
        metrics = QFontMetrics(name_font)
        baseline = card.top() + 12 + metrics.ascent()
        for line in wrap_lines(index.data(Qt.ItemDataRole.DisplayRole) or "", name_font, name_width):
            painter.drawText(int(card.left() + pad), int(baseline), line)
            baseline += metrics.lineSpacing()

        price_font = QFont(option.font)
        price_font.setPixelSize(15)
        price_font.setWeight(QFont.Weight.Bold)
        painter.setFont(price_font)
        painter.setPen(QColor(Color.ACCENT))
        price_box = QRectF(card.left() + pad, card.bottom() - 34, card.width() - pad * 2 - 44, 24)
        painter.drawText(price_box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, index.data(PRICE_ROLE) or "")

        if diet:
            self._paint_diet_marker(painter, QRectF(card.right() - pad - 14, card.top() + 12, 14, 14), diet)
        if quantity:
            self._paint_badge(painter, card, f"×{quantity}", option.font)

        painter.restore()

    @staticmethod
    def _paint_diet_marker(painter: QPainter, box: QRectF, diet: str) -> None:
        """Draw the Indian food-labelling mark: a square outline holding a green or red dot."""
        color = QColor(Color.VEG if diet == "veg" else Color.NON_VEG)
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box.adjusted(0.75, 0.75, -0.75, -0.75), 3, 3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(box.center(), 3.2, 3.2)

    @staticmethod
    def _paint_badge(painter: QPainter, card: QRectF, text: str, base_font: QFont) -> None:
        """Draw the quantity pill in the card's bottom-right corner."""
        font = QFont(base_font)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Bold)
        width = max(34, QFontMetrics(font).horizontalAdvance(text) + 18)
        pill = QRectF(card.right() - 12 - width, card.bottom() - 12 - 24, width, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Color.ACCENT))
        painter.drawRoundedRect(pill, 12, 12)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)


class ItemGridView(QListWidget):
    """A wrapping grid of menu-item cards whose columns stretch to fill the available width."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("itemGrid")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setItemDelegate(MenuItemCardDelegate(self))
        self.setGridSize(QSize(_MIN_CARD_WIDTH, _CARD_HEIGHT))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Re-flow the cards into as many equal columns as fit."""
        super().resizeEvent(event)
        # Size against the widget width minus the scrollbar's footprint, whether or not it is showing.
        # Otherwise the scrollbar appearing shrinks the viewport, the cells no longer fit and the grid
        # collapses to a single column.
        available = self.width() - 2 * self.frameWidth() - _SCROLLBAR_ALLOWANCE
        if available <= 0:
            return
        columns = max(1, available // _MIN_CARD_WIDTH)
        width = available // columns
        if width != self.gridSize().width():
            self.setGridSize(QSize(width, _CARD_HEIGHT))
