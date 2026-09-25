"""First-launch configuration dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets import dialog_header, style_dialog_buttons


class FirstLaunchDialog(QDialog):
    """Collect the café details required before the dashboard is shown."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("CafePOS Setup")
        self.setMinimumWidth(480)

        self.cafe_name_input = QLineEdit()
        self.cafe_name_input.setPlaceholderText("e.g. Daily Roast Cafe")
        self.receipt_footer_input = QLineEdit()
        self.receipt_footer_input.setPlaceholderText("Thank you for visiting")
        self.error_label = QLabel()
        self.error_label.setObjectName("formError")
        self.error_label.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(14)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.addRow(self.field_label("Cafe Name"), self.cafe_name_input)
        form_layout.addRow(self.field_label("Receipt Footer"), self.receipt_footer_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons, QDialogButtonBox.StandardButton.Save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)
        layout.addWidget(
            dialog_header("Welcome to CafePOS", "Tell us about your cafe to get started. You can change this later in Settings.")
        )
        layout.addLayout(form_layout)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        self.cafe_name_input.setFocus()

    @staticmethod
    def field_label(text: str) -> QLabel:
        """Create a muted caption for a form row."""
        label = QLabel(text)
        label.setObjectName("infoKey")
        return label

    @property
    def values(self) -> tuple[str, str]:
        """Return normalized setup values."""
        return self.cafe_name_input.text().strip(), self.receipt_footer_input.text().strip()

    def save(self) -> None:
        """Require a café name before completing first-launch setup."""
        cafe_name, _receipt_footer = self.values
        if not cafe_name:
            self.error_label.setText("Cafe Name is required.")
            return
        self.accept()
