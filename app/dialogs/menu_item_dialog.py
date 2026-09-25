"""Dialog for creating and editing menu items."""

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets import AutoSelectDoubleSpinBox, dialog_header, style_dialog_buttons


class MenuItemDialog(QDialog):
    """Collect valid name, category, and price values for a menu item."""

    def __init__(
        self,
        title: str,
        categories: Iterable[str],
        name: str = "",
        category: str = "",
        price: float = 0.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setMinimumWidth(440)

        self.name_input = QLineEdit(name)
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems(categories)
        self.category_input.setCurrentText(category)

        self.price_input = AutoSelectDoubleSpinBox()
        self.price_input.setDecimals(2)
        self.price_input.setMaximum(999_999.99)
        self.price_input.setSpecialValueText(" ")
        self.price_input.setPrefix("₹ ")
        self.price_input.setValue(price)

        self.error_label = QLabel()
        self.error_label.setObjectName("formError")
        self.error_label.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(14)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.addRow(self.field_label("Name"), self.name_input)
        form_layout.addRow(self.field_label("Category"), self.category_input)
        form_layout.addRow(self.field_label("Price"), self.price_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons, QDialogButtonBox.StandardButton.Save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(dialog_header(title, "Type a new category to create it. Prices are entered before GST."))
        layout.addLayout(form_layout)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        self.name_input.setFocus()

    @staticmethod
    def field_label(text: str) -> QLabel:
        """Create a muted caption for a form row."""
        label = QLabel(text)
        label.setObjectName("infoKey")
        return label

    @property
    def values(self) -> tuple[str, str, float]:
        """Return the values entered in the dialog."""
        return (
            self.name_input.text().strip(),
            self.category_input.currentText().strip(),
            self.price_input.value(),
        )

    def save(self) -> None:
        """Validate the inputs before closing with an accepted result."""
        name, category, price = self.values
        if not name:
            self.error_label.setText("Name is required.")
            return
        if not category:
            self.error_label.setText("Category is required.")
            return
        if price <= 0:
            self.error_label.setText("Price must be greater than 0.")
            return

        self.accept()
