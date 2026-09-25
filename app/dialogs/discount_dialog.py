"""Dialog for configuring an order discount."""

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.services.orders import CartLine, Discount, calculate_order_totals
from app.ui.widgets import AutoSelectDoubleSpinBox, dialog_header, make_button, style_dialog_buttons


class DiscountDialog(QDialog):
    """Apply or clear the single discount allowed on an order."""

    def __init__(
        self,
        cart_lines: Iterable[CartLine],
        current_discount: Discount | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.cart_lines = list(cart_lines)
        self.discount: Discount | None = current_discount
        self.setWindowTitle("Discount")
        self.setMinimumWidth(440)

        self.type_input = QComboBox()
        self.type_input.addItem("Flat Amount", "flat")
        self.type_input.addItem("Percentage", "percentage")

        self.target_input = QComboBox()
        self.target_input.addItem("Whole Bill", None)
        for line in self.cart_lines:
            self.target_input.addItem(line.item_name, line.menu_item_id)

        self.value_input = AutoSelectDoubleSpinBox()
        self.value_input.setDecimals(2)
        self.value_input.setMaximum(999_999.99)
        self.value_input.setSpecialValueText(" ")

        if current_discount is not None:
            self.type_input.setCurrentIndex(self.type_input.findData(current_discount.kind))
            self.target_input.setCurrentIndex(self.target_input.findData(current_discount.menu_item_id))
            self.value_input.setValue(current_discount.value)
        self.type_input.currentIndexChanged.connect(self.update_value_affix)
        self.update_value_affix()

        self.error_label = QLabel()
        self.error_label.setObjectName("formError")
        self.error_label.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(14)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.addRow(self.field_label("Type"), self.type_input)
        form_layout.addRow(self.field_label("Apply to"), self.target_input)
        form_layout.addRow(self.field_label("Value"), self.value_input)

        clear_button = make_button("Clear", "danger", "trash")
        clear_button.clicked.connect(self.clear_discount)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_discount)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons, QDialogButtonBox.StandardButton.Apply)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.addWidget(clear_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(dialog_header("Apply Discount", "Take a flat amount or a percentage off the whole bill or one item."))
        layout.addLayout(form_layout)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons_layout)

    @staticmethod
    def field_label(text: str) -> QLabel:
        """Create a muted caption for a form row."""
        label = QLabel(text)
        label.setObjectName("infoKey")
        return label

    def update_value_affix(self) -> None:
        """Show ₹ for flat discounts and % for percentage discounts."""
        is_percentage = self.type_input.currentData() == "percentage"
        self.value_input.setPrefix("" if is_percentage else "₹ ")
        self.value_input.setSuffix(" %" if is_percentage else "")

    def apply_discount(self) -> None:
        """Validate and apply the selected discount."""
        menu_item_id = self.target_input.currentData(Qt.ItemDataRole.UserRole)
        discount = Discount(
            kind=self.type_input.currentData(),
            value=self.value_input.value(),
            scope="item" if menu_item_id is not None else "order",
            menu_item_id=menu_item_id,
        )
        try:
            calculate_order_totals(self.cart_lines, discount)
        except ValueError as error:
            self.error_label.setText(str(error))
            return

        self.discount = discount
        self.accept()

    def clear_discount(self) -> None:
        """Remove the current discount from the order."""
        self.discount = None
        self.accept()
