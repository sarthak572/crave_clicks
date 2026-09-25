"""Dialog for viewing and voiding a completed order."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import session_scope
from app.models import Order
from app.services import get_order, void_order
from app.services.printing import ReceiptPrintError, format_round_off, gst_breakdown_lines, print_receipt
from app.ui.widgets import dialog_header, make_button, make_card


class OrderDetailsDialog(QDialog):
    """Show immutable order snapshots and allow a completed order to be voided."""

    def __init__(
        self,
        order_id: int,
        on_order_voided: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.order_id = order_id
        self.on_order_voided = on_order_voided
        self.setWindowTitle("Order Details")
        self.resize(820, 700)
        self.setMinimumSize(700, 600)

        self.bill_number_label = QLabel()
        self.status_label = QLabel()
        self.status_label.setObjectName("statusPill")
        self.service_type_label = QLabel()
        self.bill_time_label = QLabel()
        self.discount_type_label = QLabel()
        self.discount_scope_label = QLabel()
        self.discount_value_label = QLabel()
        self.gst_label = QLabel()
        self.gst_label.setTextFormat(Qt.TextFormat.PlainText)
        self.round_off_label = QLabel()
        self.payment_breakdown_label = QLabel()
        self.payment_breakdown_label.setTextFormat(Qt.TextFormat.PlainText)

        info_card = make_card()
        info_grid = QGridLayout(info_card)
        info_grid.setContentsMargins(22, 18, 22, 18)
        info_grid.setHorizontalSpacing(20)
        info_grid.setVerticalSpacing(12)
        info_grid.setColumnStretch(1, 1)
        info_grid.setColumnStretch(3, 1)
        info_rows = (
            (("Bill Number", self.bill_number_label), ("Service Type", self.service_type_label)),
            (("Bill Time", self.bill_time_label), ("Payment Breakdown", self.payment_breakdown_label)),
            (("Discount Type", self.discount_type_label), ("Discount Scope", self.discount_scope_label)),
            (("Discount Value", self.discount_value_label), ("GST", self.gst_label)),
            (("Round Off", self.round_off_label),),
        )
        for row, pair in enumerate(info_rows):
            for offset, (caption, value_label) in zip((0, 2), pair):
                key_label = QLabel(caption)
                key_label.setObjectName("infoKey")
                value_label.setObjectName("infoValue")
                value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                key_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                info_grid.addWidget(key_label, row, offset)
                info_grid.addWidget(value_label, row, offset + 1)

        self.items_table = QTableWidget(0, 4)
        self.items_table.setHorizontalHeaderLabels(["Item", "Quantity", "Unit Price", "Internal Note"])
        self.items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.items_table.setShowGrid(False)
        self.items_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.verticalHeader().setDefaultSectionSize(42)
        items_header = self.items_table.horizontalHeader()
        items_header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        items_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        items_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        items_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        items_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            self.items_table.horizontalHeaderItem(column).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.void_button = make_button("Void Order", "danger", "trash")
        self.void_button.clicked.connect(self.void_current_order)
        self.reprint_button = make_button("Reprint", None, "printer")
        self.reprint_button.clicked.connect(self.reprint_order)
        close_button = make_button("Close", "primary")
        close_button.setDefault(True)
        close_button.clicked.connect(self.reject)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.addWidget(self.void_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.reprint_button)
        buttons_layout.addWidget(close_button)

        header_row = QHBoxLayout()
        header_row.addWidget(dialog_header("Order Details", "Completed bills cannot be edited. Void an order to correct it."), 1)
        header_row.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignTop)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addLayout(header_row)
        layout.addWidget(info_card)
        layout.addWidget(self.items_table, 1)
        layout.addLayout(buttons_layout)

        self.load_order()

    def load_order(self) -> None:
        """Load immutable details from the completed order and item snapshots."""
        with session_scope() as session:
            order = get_order(session, self.order_id)
            if order is None:
                self.reject()
                return

            self._populate(order)

    def _populate(self, order: Order) -> None:
        """Populate the dialog while related records are available in the session."""
        is_void = bool(order.is_void)
        self.bill_number_label.setText(str(order.bill_number))
        self.status_label.setText("VOIDED" if is_void else "Completed")
        self.status_label.setProperty("state", "void" if is_void else "ok")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.service_type_label.setText(order.service_type)
        self.bill_time_label.setText(f"{order.order_date} {order.order_time}")
        self.discount_type_label.setText(self._discount_type_text(order))
        self.discount_scope_label.setText(self._discount_scope_text(order))
        self.discount_value_label.setText(self._discount_value_text(order))
        self.gst_label.setText(self._gst_text(order))
        self.round_off_label.setText(format_round_off(order.round_off) if order.round_off else "None")
        self.payment_breakdown_label.setText(self._payment_breakdown_text(order))
        self.void_button.setEnabled(not is_void)
        self.reprint_button.setEnabled(not is_void)

        self.items_table.setRowCount(len(order.items))
        for row, item in enumerate(order.items):
            values = (
                item.item_name,
                str(item.quantity),
                f"₹{item.unit_price:.2f}",
                item.note or "",
            )
            for column, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                if column in (1, 2):
                    table_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.items_table.setItem(row, column, table_item)

    def void_current_order(self) -> None:
        """Confirm and permanently mark this completed order as voided."""
        confirmed = QMessageBox.question(
            self,
            "Void Order",
            "Void this order? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        with session_scope() as session:
            if not void_order(session, self.order_id):
                return

        self.load_order()
        if self.on_order_voided is not None:
            self.on_order_voided()

    def reprint_order(self) -> None:
        """Print this completed order unless it has been voided."""
        try:
            printed = print_receipt(self.order_id, self)
        except ReceiptPrintError:
            QMessageBox.warning(self, "CafePOS", "Receipt could not be printed.")
            return

        if printed:
            QMessageBox.information(self, "CafePOS", "Bill Printed")

    @staticmethod
    def _discount_type_text(order: Order) -> str:
        if order.discount_type is None:
            return "None"
        return order.discount_type.split("_", maxsplit=1)[0].replace("_", " ").title()

    @staticmethod
    def _discount_scope_text(order: Order) -> str:
        scope = order.discount_scope
        if scope is None and order.discount_type and "_" in order.discount_type:
            scope = order.discount_type.rsplit("_", maxsplit=1)[1]
        return scope.title() if scope else "None"

    @staticmethod
    def _discount_value_text(order: Order) -> str:
        if order.discount_value is None:
            return "—"
        if order.discount_type and order.discount_type.startswith("percentage"):
            return f"{order.discount_value:.2f}%"
        return f"₹{order.discount_value:.2f}"

    @staticmethod
    def _gst_text(order: Order) -> str:
        lines = gst_breakdown_lines(order)
        if not lines:
            return "Not applied"
        return f"{order.gst_rate:g}%\n" + "\n".join(f"{label} ₹{amount:.2f}" for label, amount in lines)

    @staticmethod
    def _payment_breakdown_text(order: Order) -> str:
        def format_amount(amount: float) -> str:
            return f"{int(amount)}" if amount.is_integer() else f"{amount:.2f}"

        if order.split_payments:
            return "\n".join(
                f"{payment.payment_mode} ₹{format_amount(payment.amount)}"
                for payment in order.split_payments
            )
        return f"{order.payment_mode} ₹{format_amount(order.total)}"
