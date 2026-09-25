"""CafePOS visual theme: palette, SVG icon set and the application stylesheet."""

from functools import lru_cache
from pathlib import Path
import tempfile

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication


class Color:
    """Design tokens shared by the stylesheet and custom-painted widgets."""

    BG = "#F3F1EE"
    SURFACE = "#FFFFFF"
    SURFACE_ALT = "#FAF8F5"
    HOVER = "#F1EDE8"
    BORDER = "#E6E1DA"
    BORDER_STRONG = "#D3CCC3"
    TEXT = "#1F1B18"
    TEXT_MUTED = "#6B645D"
    TEXT_FAINT = "#8F877F"

    SIDEBAR = "#1E1814"
    SIDEBAR_HOVER = "#2D251F"
    SIDEBAR_TEXT = "#D6CCC2"
    SIDEBAR_MUTED = "#948A80"
    SIDEBAR_LINE = "#382E27"

    ACCENT = "#C9551D"
    ACCENT_HOVER = "#B44A17"
    ACCENT_PRESSED = "#9E4013"
    ACCENT_SOFT = "#FBEBDF"

    SUCCESS = "#1E8449"
    SUCCESS_HOVER = "#186D3B"
    SUCCESS_SOFT = "#E3F3E9"

    DANGER = "#B3261E"
    DANGER_SOFT = "#FBEAE8"

    VEG = "#1E8E3E"
    NON_VEG = "#C0392B"


FONT_STACK = '"Segoe UI", "Helvetica Neue", Arial, sans-serif'

# 24x24 stroke icons (round caps and joins), drawn to match one another.
_ICON_PATHS: dict[str, str] = {
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-4.5v-6.5h-7V21H4a1 1 0 0 1-1-1z"/>',
    "plus-square": '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M12 8v8M8 12h8"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M8 17v-5M13 17V8M18 17v-8"/>',
    "list": '<path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4.5" cy="6" r="1"/>'
    '<circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
    "sliders": '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/>'
    '<circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
    "arrow-left": '<path d="M19 12H5M11 18l-6-6 6-6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "trash": '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 10v6M14 10v6"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13 7 4 4"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
    "tag": '<path d="M3 3h8l10 10-8 8L3 11z"/><circle cx="7.5" cy="7.5" r="1.3"/>',
    "printer": '<path d="M7 9V3h10v6"/><path d="M7 17H4v-7a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v7h-3"/>'
    '<rect x="7" y="14" width="10" height="7"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "cup": '<path d="M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M17 11h1.5a2.5 2.5 0 0 1 0 5H17"/>'
    '<path d="M8 3.5v2M12 3.5v2"/>',
    "cash": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.6"/>'
    '<path d="M6 12h.01M18 12h.01"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2.2"/><path d="M11 18h2"/>',
    "split": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M12 4.5v15"/>',
    "rupee": '<path d="M6 4h12M6 9h12M6 4c6 0 9 1.5 9 5s-3 5-9 5l7 6"/>',
    "receipt": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9.5 8h5M9.5 12h5"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "star": '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "layers": '<path d="M12 3 3 8l9 5 9-5z"/><path d="m3 13 9 5 9-5"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'
    '<path d="M4 4l16 16"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "inbox": '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5.5 5h13L21 13v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6z"/>',
    "cart": '<path d="M3 4h2.5l2.2 10.5a1 1 0 0 0 1 .8h8.6a1 1 0 0 0 1-.8L20 8H6.2"/>'
    '<circle cx="9.5" cy="19.5" r="1.3"/><circle cx="17" cy="19.5" r="1.3"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.5-4M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.5 4M20 20v-4h-4"/>',
}


@lru_cache(maxsize=None)
def _render(name: str, color: str, size: int) -> QPixmap:
    """Rasterise one icon at twice the requested size so it stays crisp on HiDPI screens."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round">{_ICON_PATHS[name]}</svg>'
    )
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def pixmap(name: str, color: str = Color.TEXT, size: int = 20) -> QPixmap:
    """Return a named icon as a pixmap."""
    return _render(name, color, size)


@lru_cache(maxsize=None)
def icon(name: str, color: str = Color.TEXT_MUTED, on_color: str | None = None, size: int = 20) -> QIcon:
    """Return a named icon; ``on_color`` is used while a checkable button is checked."""
    result = QIcon()
    result.addPixmap(_render(name, color, size), QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(_render(name, on_color or color, size), QIcon.Mode.Normal, QIcon.State.On)
    return result


def dot_pixmap(color: str | None, size: int = 10) -> QPixmap:
    """Return a small filled dot (or an empty spacer of the same size when ``color`` is None)."""
    scale = 2
    dot = QPixmap(size * scale, size * scale)
    dot.fill(Qt.GlobalColor.transparent)
    if color:
        painter = QPainter(dot)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(dot.rect().adjusted(2, 2, -2, -2))
        painter.end()
    dot.setDevicePixelRatio(scale)
    return dot


def _chevron_path() -> str:
    """Write the combo-box arrow to a cache file, because stylesheets can only load images from paths."""
    target = Path(tempfile.gettempdir()) / "cafepos-theme" / "chevron-down.png"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _render("chevron-down", Color.TEXT_MUTED, 14).save(str(target), "PNG")
    except OSError:
        return ""
    return target.as_posix()


_STYLESHEET = """
QWidget {
    color: @TEXT@;
    font-family: @FONT@;
    font-size: 14px;
}
QMainWindow, QDialog, QWidget#page {
    background-color: @BG@;
}
QMessageBox {
    background-color: @SURFACE@;
}
QMessageBox QLabel {
    min-width: 260px;
    font-size: 14px;
}
QMessageBox QPushButton {
    min-width: 84px;
}
QLabel {
    background: transparent;
}
QToolTip {
    background-color: @TEXT@;
    color: #FFFFFF;
    border: none;
    padding: 6px 10px;
}

/* ---------- Navigation sidebar ---------- */
QDockWidget#navDock {
    border: none;
}
QMainWindow::separator {
    width: 0px;
    height: 0px;
    background: transparent;
}
QFrame#sidebar {
    background-color: @SIDEBAR@;
    border: none;
}
QLabel#brandMark {
    background-color: @ACCENT@;
    border-radius: 12px;
}
QLabel#brandName {
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 700;
}
QLabel#brandTag {
    color: @SIDEBAR_MUTED@;
    font-size: 12px;
}
QLabel#navCaption {
    color: @SIDEBAR_MUTED@;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#navButton {
    background-color: transparent;
    color: @SIDEBAR_TEXT@;
    border: none;
    border-radius: 10px;
    padding: 12px 14px;
    text-align: left;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#navButton:hover {
    background-color: @SIDEBAR_HOVER@;
    color: #FFFFFF;
}
QPushButton#navButton:checked {
    background-color: @ACCENT@;
    color: #FFFFFF;
}
QFrame#sidebarDivider {
    background-color: @SIDEBAR_LINE@;
    border: none;
    min-height: 1px;
    max-height: 1px;
}
QLabel#sidebarStatus {
    color: @SIDEBAR_TEXT@;
    font-size: 12px;
}
QLabel#sidebarVersion {
    color: @SIDEBAR_MUTED@;
    font-size: 11px;
}

/* ---------- Surfaces and typography ---------- */
QFrame#card {
    background-color: @SURFACE@;
    border: 1px solid @BORDER@;
    border-radius: 14px;
}
QFrame#cardDivider {
    background-color: @BORDER@;
    border: none;
    min-height: 1px;
    max-height: 1px;
}
QLabel#pageTitle {
    font-size: 24px;
    font-weight: 700;
}
QLabel#dialogTitle {
    font-size: 20px;
    font-weight: 700;
}
QLabel#emptyIcon {
    background-color: @HOVER@;
    border-radius: 32px;
}
QLabel#pageSubtitle {
    color: @TEXT_MUTED@;
    font-size: 13px;
}
QLabel#cardTitle {
    font-size: 16px;
    font-weight: 700;
}
QLabel#sectionLabel {
    color: @TEXT_MUTED@;
    font-size: 12px;
    font-weight: 700;
}
QLabel#muted {
    color: @TEXT_MUTED@;
}
QLabel#statTitle {
    color: @TEXT_MUTED@;
    font-size: 13px;
    font-weight: 600;
}
QLabel#statValue {
    font-size: 26px;
    font-weight: 700;
}
QLabel#statValueText {
    font-size: 18px;
    font-weight: 700;
}
QLabel#statIcon {
    background-color: @ACCENT_SOFT@;
    border-radius: 12px;
}
QLabel#emptyTitle {
    color: @TEXT@;
    font-size: 15px;
    font-weight: 700;
}
QLabel#emptyText {
    color: @TEXT_MUTED@;
    font-size: 13px;
}
QLabel#chip {
    background-color: @HOVER@;
    color: @TEXT_MUTED@;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#statusPill {
    background-color: @SUCCESS_SOFT@;
    color: @SUCCESS@;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 700;
}
QLabel#statusPill[state="void"] {
    background-color: @DANGER_SOFT@;
    color: @DANGER@;
}
QLabel#statusPill[state="new"] {
    background-color: @ACCENT_SOFT@;
    color: @ACCENT@;
}
QLabel#messageBox {
    background-color: @SURFACE_ALT@;
    border: 1px solid @BORDER@;
    border-radius: 10px;
    padding: 12px 14px;
    font-size: 14px;
}
QLabel#totalLabel {
    font-size: 22px;
    font-weight: 700;
}
QLabel#totalCaption {
    font-size: 15px;
    font-weight: 700;
}
QLabel#formError {
    color: @DANGER@;
    font-size: 13px;
    font-weight: 600;
}
QLabel#infoKey {
    color: @TEXT_MUTED@;
}
QLabel#infoValue {
    font-weight: 600;
}

/* ---------- Inputs ---------- */
QLineEdit, QAbstractSpinBox, QComboBox {
    background-color: @SURFACE@;
    color: @TEXT@;
    border: 1px solid @BORDER_STRONG@;
    border-radius: 10px;
    padding: 9px 12px;
    min-height: 20px;
    selection-background-color: @ACCENT_SOFT@;
    selection-color: @TEXT@;
}
QLineEdit:hover, QAbstractSpinBox:hover, QComboBox:hover {
    border-color: @TEXT_FAINT@;
}
QLineEdit:focus, QAbstractSpinBox:focus, QComboBox:focus, QComboBox:on {
    border: 1px solid @ACCENT@;
}
QLineEdit:disabled, QAbstractSpinBox:disabled, QComboBox:disabled {
    background-color: @SURFACE_ALT@;
    color: @TEXT_FAINT@;
}
QLineEdit#noteInput {
    background-color: @SURFACE_ALT@;
    border: 1px solid @BORDER@;
    border-radius: 8px;
    padding: 5px 10px;
    min-height: 18px;
    font-size: 12px;
}
QLineEdit#noteInput:focus {
    background-color: @SURFACE@;
    border: 1px solid @ACCENT@;
}
QLineEdit#compactInput {
    background-color: @SURFACE@;
    border: 1px solid @BORDER_STRONG@;
    border-radius: 8px;
    padding: 6px 12px;
    min-height: 18px;
}
QLineEdit#compactInput:focus {
    border: 1px solid @ACCENT@;
}
QLineEdit#searchInput {
    padding: 10px 12px;
    border-radius: 12px;
}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
    width: 0px;
    border: none;
}
QComboBox {
    padding-right: 30px;
    min-width: 120px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 30px;
    border: none;
}
QComboBox::down-arrow {
    image: url("@CHEVRON@");
    width: 14px;
    height: 14px;
}
QComboBox QAbstractItemView {
    background-color: @SURFACE@;
    border: 1px solid @BORDER_STRONG@;
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    selection-background-color: @ACCENT_SOFT@;
    selection-color: @TEXT@;
}
QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 0 8px;
    border-radius: 6px;
}
QComboBox QAbstractItemView::item:selected {
    background-color: @ACCENT_SOFT@;
    color: @TEXT@;
}

/* ---------- Buttons ---------- */
QPushButton {
    background-color: @SURFACE@;
    color: @TEXT@;
    border: 1px solid @BORDER_STRONG@;
    border-radius: 10px;
    padding: 9px 18px;
    min-height: 20px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: @SURFACE_ALT@;
    border-color: @TEXT_FAINT@;
}
QPushButton:pressed {
    background-color: @HOVER@;
}
QPushButton:default {
    border-color: @ACCENT@;
}
QPushButton:disabled {
    background-color: #EEEAE5;
    color: #A39B93;
    border-color: @BORDER@;
}
QPushButton[variant="primary"] {
    background-color: @ACCENT@;
    color: #FFFFFF;
    border: 1px solid @ACCENT@;
}
QPushButton[variant="primary"]:hover {
    background-color: @ACCENT_HOVER@;
    border-color: @ACCENT_HOVER@;
}
QPushButton[variant="primary"]:pressed {
    background-color: @ACCENT_PRESSED@;
}
QPushButton[variant="success"] {
    background-color: @SUCCESS@;
    color: #FFFFFF;
    border: 1px solid @SUCCESS@;
    font-size: 16px;
    font-weight: 700;
    padding: 11px 18px;
}
QPushButton[variant="success"]:hover {
    background-color: @SUCCESS_HOVER@;
    border-color: @SUCCESS_HOVER@;
}
QPushButton[variant="success"]:disabled {
    background-color: #E4DFD9;
    color: #A39B93;
    border-color: #E4DFD9;
}
QPushButton[variant="danger"] {
    color: @DANGER@;
    border: 1px solid #E6BDB9;
}
QPushButton[variant="danger"]:hover {
    background-color: @DANGER_SOFT@;
    border-color: @DANGER@;
}
QPushButton[variant="danger"]:disabled {
    color: #C9A9A6;
}
QPushButton[variant="ghost"] {
    background-color: transparent;
    border: 1px solid transparent;
    color: @TEXT_MUTED@;
    padding: 8px 12px;
}
QPushButton[variant="ghost"]:hover {
    background-color: #E9E4DE;
    color: @TEXT@;
}
QPushButton[variant="dashed"] {
    background-color: @SURFACE_ALT@;
    border: 1px dashed @BORDER_STRONG@;
    color: @TEXT_MUTED@;
}
QPushButton[variant="dashed"]:hover {
    border-color: @ACCENT@;
    color: @ACCENT@;
    background-color: @ACCENT_SOFT@;
}
QPushButton#segment {
    background-color: @SURFACE@;
    border: 1px solid @BORDER_STRONG@;
    color: @TEXT_MUTED@;
    padding: 7px 8px;
}
QPushButton#segment:hover {
    background-color: @SURFACE_ALT@;
}
QPushButton#segment:checked {
    background-color: @ACCENT_SOFT@;
    border: 1px solid @ACCENT@;
    color: @ACCENT@;
}
QPushButton#heroButton {
    padding: 12px 22px;
    font-size: 15px;
}
QPushButton#linkButton {
    padding: 3px 8px;
    min-height: 18px;
    font-size: 12px;
}
QPushButton#qtyButton {
    background-color: @SURFACE@;
    border: 1px solid @BORDER_STRONG@;
    border-radius: 8px;
    padding: 0px;
    min-height: 30px;
    max-height: 30px;
    min-width: 30px;
    max-width: 30px;
}
QPushButton#noteToggle {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 0px;
    min-height: 30px;
    max-height: 30px;
    min-width: 30px;
    max-width: 30px;
}
QPushButton#noteToggle:hover {
    background-color: @HOVER@;
}
QPushButton#noteToggle:checked {
    background-color: @ACCENT_SOFT@;
    border: 1px solid @ACCENT@;
}
QPushButton#qtyButton:hover {
    background-color: @ACCENT_SOFT@;
    border-color: @ACCENT@;
}
QLabel#qtyValue {
    font-size: 15px;
    font-weight: 700;
    min-width: 22px;
}

/* ---------- Cart lines ---------- */
QFrame#cartLine {
    background: transparent;
    border: none;
    border-bottom: 1px solid #F0ECE7;
}
QLabel#lineName {
    font-size: 13px;
    font-weight: 600;
}
QLabel#lineUnit {
    color: @TEXT_MUTED@;
    font-size: 12px;
}
QLabel#lineTotal {
    font-weight: 700;
}

/* ---------- Lists ---------- */
QListWidget#categoryList, QListWidget#itemGrid {
    background-color: transparent;
    border: none;
    outline: 0;
}
QListWidget#categoryList::item {
    color: @TEXT@;
    padding: 11px 12px;
    margin: 1px 0px;
    border-radius: 10px;
    font-weight: 600;
}
QListWidget#categoryList::item:hover {
    background-color: #E9E4DE;
}
QListWidget#categoryList::item:selected, QListWidget#categoryList::item:selected:!active {
    background-color: @ACCENT@;
    color: #FFFFFF;
}

QListWidget#orderList {
    background-color: transparent;
    border: none;
    outline: 0;
}
QListWidget#orderList::item {
    color: @TEXT@;
    padding: 12px 14px;
    margin: 2px 0px;
    border: 1px solid @BORDER@;
    border-radius: 12px;
    background-color: @SURFACE@;
}
QListWidget#orderList::item:hover {
    background-color: @HOVER@;
}
QListWidget#orderList::item:selected, QListWidget#orderList::item:selected:!active {
    background-color: @ACCENT_SOFT@;
    border: 1px solid @ACCENT@;
    color: @TEXT@;
}

/* ---------- Tables ---------- */
QTableView {
    background-color: @SURFACE@;
    alternate-background-color: @SURFACE_ALT@;
    border: 1px solid @BORDER@;
    border-radius: 14px;
    gridline-color: transparent;
    outline: 0;
    selection-background-color: @ACCENT_SOFT@;
    selection-color: @TEXT@;
}
QTableView::item {
    padding: 0px 14px;
    border-bottom: 1px solid #F0ECE7;
}
QTableView::item:selected {
    background-color: @ACCENT_SOFT@;
    color: @TEXT@;
}
QTableWidget#embeddedTable {
    border: none;
    border-top: 1px solid @BORDER@;
    border-radius: 0px;
    background-color: transparent;
    alternate-background-color: transparent;
}
QTableWidget#embeddedTable QHeaderView::section {
    background-color: @SURFACE@;
    border-radius: 0px;
    padding-left: 20px;
}
QTableWidget#embeddedTable::item {
    padding-left: 20px;
}
QHeaderView {
    background-color: transparent;
}
QHeaderView::section {
    background-color: @SURFACE_ALT@;
    color: @TEXT_MUTED@;
    font-size: 12px;
    font-weight: 700;
    text-align: left;
    border: none;
    border-bottom: 1px solid @BORDER@;
    padding: 12px 14px;
}
QHeaderView::section:first {
    border-top-left-radius: 13px;
}
QHeaderView::section:last {
    border-top-right-radius: 13px;
}
QTableCornerButton::section {
    background-color: @SURFACE_ALT@;
    border: none;
}

/* ---------- Tabs ---------- */
QTabWidget::pane {
    border: none;
    background: transparent;
}
QTabWidget::tab-bar {
    left: 0px;
}
QTabBar {
    background: transparent;
}
QTabBar::tab {
    background-color: @SURFACE@;
    color: @TEXT_MUTED@;
    border: 1px solid @BORDER@;
    border-radius: 10px;
    padding: 9px 22px;
    margin-right: 8px;
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    background-color: @SURFACE_ALT@;
    color: @TEXT@;
}
QTabBar::tab:selected {
    background-color: @ACCENT@;
    border-color: @ACCENT@;
    color: #FFFFFF;
}

/* ---------- Misc controls ---------- */
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #CFC7BE;
    border-radius: 4px;
    min-height: 36px;
    margin: 0px 2px;
}
QScrollBar::handle:vertical:hover {
    background: #B5ACA2;
}
QScrollBar:horizontal {
    background: transparent;
    height: 12px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #CFC7BE;
    border-radius: 4px;
    min-width: 36px;
    margin: 2px 0px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}
QGroupBox {
    border: 1px solid @BORDER@;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: @TEXT_MUTED@;
    font-weight: 600;
}
QCheckBox, QRadioButton {
    spacing: 8px;
    padding: 3px 0;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 2px solid @ACCENT@;
    background-color: @SURFACE@;
}
QCheckBox::indicator {
    border-radius: 4px;
}
QRadioButton::indicator {
    border-radius: 9px;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: @ACCENT@;
}
"""


def build_stylesheet() -> str:
    """Return the application stylesheet with the design tokens filled in."""
    tokens = {name: value for name, value in vars(Color).items() if not name.startswith("_")}
    tokens["FONT"] = FONT_STACK
    tokens["CHEVRON"] = _chevron_path()
    stylesheet = _STYLESHEET
    for name, value in tokens.items():
        stylesheet = stylesheet.replace(f"@{name}@", value)
    return stylesheet


def apply_theme(application: QApplication) -> None:
    """Keep every control readable regardless of the operating-system color scheme."""
    palette = application.palette()
    for group in (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Disabled,
    ):
        palette.setColor(group, QPalette.ColorRole.Window, QColor(Color.BG))
        palette.setColor(group, QPalette.ColorRole.WindowText, QColor(Color.TEXT))
        palette.setColor(group, QPalette.ColorRole.Base, QColor(Color.SURFACE))
        palette.setColor(group, QPalette.ColorRole.AlternateBase, QColor(Color.SURFACE_ALT))
        palette.setColor(group, QPalette.ColorRole.Text, QColor(Color.TEXT))
        palette.setColor(group, QPalette.ColorRole.Button, QColor(Color.SURFACE))
        palette.setColor(group, QPalette.ColorRole.ButtonText, QColor(Color.TEXT))
        palette.setColor(group, QPalette.ColorRole.PlaceholderText, QColor(Color.TEXT_FAINT))
        palette.setColor(group, QPalette.ColorRole.Highlight, QColor(Color.ACCENT_SOFT))
        palette.setColor(group, QPalette.ColorRole.HighlightedText, QColor(Color.TEXT))
    application.setPalette(palette)
    application.setStyleSheet(build_stylesheet())
