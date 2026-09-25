"""Dialogs for accepting or rejecting a WhatsApp order."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.services.online_orders import REJECT_REASONS
from app.ui.widgets import AutoSelectDoubleSpinBox, dialog_header, style_dialog_buttons

PREP_MINUTES = (10, 15, 20, 30, 45, 60)


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("infoKey")
    return label


class AcceptOrderDialog(QDialog):
    """Ask how long the order will take and what total to tell the customer."""

    def __init__(self, order_label: str, suggested_total: float | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Accept order")
        self.setMinimumWidth(420)

        self.minutes_input = QComboBox()
        for minutes in PREP_MINUTES:
            self.minutes_input.addItem(f"{minutes} minutes", minutes)
        self.minutes_input.setCurrentIndex(PREP_MINUTES.index(20))

        self.total_input = AutoSelectDoubleSpinBox()
        self.total_input.setDecimals(2)
        self.total_input.setMaximum(999_999.99)
        self.total_input.setPrefix("₹ ")
        if suggested_total:
            self.total_input.setValue(suggested_total)

        hint = QLabel("The customer is told this total in the accepted message. It does not create the bill.")
        hint.setObjectName("pageSubtitle")
        hint.setWordWrap(True)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(14)
        form.addRow(_field_label("Ready in"), self.minutes_input)
        form.addRow(_field_label("Total to tell customer"), self.total_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Accept order")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons, QDialogButtonBox.StandardButton.Ok)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(dialog_header("Accept order", order_label))
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    @property
    def prep_minutes(self) -> int:
        return int(self.minutes_input.currentData())

    @property
    def quoted_total(self) -> float | None:
        value = self.total_input.value()
        return value if value > 0 else None


class RejectOrderDialog(QDialog):
    """Ask why the order cannot be taken; the reason is sent to the customer."""

    def __init__(self, order_label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reject order")
        self.setMinimumWidth(420)

        self.reason_input = QComboBox()
        self.reason_input.setEditable(True)
        self.reason_input.addItems(REJECT_REASONS)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(14)
        form.addRow(_field_label("Reason"), self.reason_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Reject order")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons, QDialogButtonBox.StandardButton.Ok)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(dialog_header("Reject order", order_label))
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def reason(self) -> str:
        return self.reason_input.currentText().strip() or REJECT_REASONS[0]
