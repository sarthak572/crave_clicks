"""Menu management window."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import session_scope
from app.dialogs.menu_item_dialog import MenuItemDialog
from app.services import (
    add_menu_item,
    get_categories,
    get_menu_items,
    soft_delete_menu_item,
    update_menu_item,
)
from app.ui.theme import Color, icon
from app.ui.widgets import PageHeader, make_button, make_empty_state


class MenuManagementWindow(QWidget):
    """Manage the cafe's current menu items."""

    def __init__(self) -> None:
        super().__init__()

        self._back_callback: Callable[[], None] | None = None

        self.setObjectName("page")
        self.setWindowTitle("Menu Management")
        self.resize(820, 560)
        self.setMinimumSize(620, 400)

        self.header = PageHeader("Menu Management", "Add, edit and remove the items you sell")
        self.back_button = self.header.back_button
        self.back_button.clicked.connect(self.go_back)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Search by item name")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(320)
        self.search_input.addAction(icon("search", Color.TEXT_FAINT), QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(self.load_items)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Category", "Price"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.horizontalHeaderItem(2).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.empty_state = make_empty_state("search", "No items found", "Try a different search or add a new item.")

        self.add_button = make_button("Add Item", "primary", "plus")
        self.add_button.clicked.connect(self.add_item)
        self.edit_button = make_button("Edit", None, "edit")
        self.edit_button.clicked.connect(self.edit_item)
        self.delete_button = make_button("Delete", "danger", "trash")
        self.delete_button.clicked.connect(self.delete_item)

        self.count_label = QLabel()
        self.count_label.setObjectName("chip")

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addWidget(self.search_input)
        toolbar.addWidget(self.count_label)
        toolbar.addStretch()
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.add_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(self.header)
        layout.addLayout(toolbar)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty_state, 1)

        self.load_items()

    def set_back_callback(self, callback: Callable[[], None]) -> None:
        """Set the navigation action for the screen's Back button."""
        self._back_callback = callback

    def go_back(self) -> None:
        """Return to the dashboard through the application navigation shell."""
        if self._back_callback is not None:
            self._back_callback()

    def load_items(self) -> None:
        """Load active menu items that match the current name search."""
        with session_scope() as session:
            items = get_menu_items(session, self.search_input.text().strip())

        self.table.setRowCount(len(items))
        for row, menu_item in enumerate(items):
            name_item = QTableWidgetItem(menu_item.name)
            name_item.setData(Qt.ItemDataRole.UserRole, menu_item.id)
            price_item = QTableWidgetItem(f"{menu_item.price:.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(menu_item.category))
            self.table.setItem(row, 2, price_item)

        self.count_label.setText(f"{len(items)} item" if len(items) == 1 else f"{len(items)} items")
        self.table.setVisible(bool(items))
        self.empty_state.setVisible(not items)

    def load_categories(self) -> list[str]:
        """Load the current list of available categories."""
        with session_scope() as session:
            return get_categories(session)

    def selected_item(self) -> tuple[int, str, str, float] | None:
        """Return the selected table row's values, if a row is selected."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        row = selected_rows[0].row()
        name_item = self.table.item(row, 0)
        return (
            name_item.data(Qt.ItemDataRole.UserRole),
            name_item.text(),
            self.table.item(row, 1).text(),
            float(self.table.item(row, 2).text()),
        )

    def add_item(self) -> None:
        """Open the dialog and add a new menu item when accepted."""
        dialog = MenuItemDialog("Add Item", self.load_categories(), parent=self)
        if not dialog.exec():
            return

        name, category, price = dialog.values
        with session_scope() as session:
            add_menu_item(session, name, category, price)
        self.load_items()

    def edit_item(self) -> None:
        """Open the dialog for the currently selected menu item."""
        selected_item = self.selected_item()
        if selected_item is None:
            self.show_selection_message()
            return

        menu_item_id, name, category, price = selected_item
        dialog = MenuItemDialog(
            "Edit Item",
            self.load_categories(),
            name,
            category,
            price,
            self,
        )
        if not dialog.exec():
            return

        name, category, price = dialog.values
        with session_scope() as session:
            update_menu_item(session, menu_item_id, name, category, price)
        self.load_items()

    def delete_item(self) -> None:
        """Soft-delete the currently selected item without confirmation."""
        selected_item = self.selected_item()
        if selected_item is None:
            self.show_selection_message()
            return

        menu_item_id = selected_item[0]
        with session_scope() as session:
            soft_delete_menu_item(session, menu_item_id)
        self.load_items()

    def show_selection_message(self) -> None:
        """Ask the user to select a menu item before an edit or delete action."""
        QMessageBox.information(self, "Menu Management", "Select a menu item first.")
