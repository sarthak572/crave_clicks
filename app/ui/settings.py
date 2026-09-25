"""Settings window for editing cafe configuration and viewing app info."""

from collections.abc import Callable
import platform
import sys

from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrinterInfo
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.runtime_paths import application_directory
from app.services import online_orders
from app.services.configuration import (
    get_default_printer,
    get_gst_rate,
    get_whatsapp_settings,
    load_configuration,
    save_configuration,
    save_default_printer,
    save_whatsapp_settings,
)
from app.services.whatsapp import WhatsAppError, send_local_message
from app.ui.widgets import AutoSelectDoubleSpinBox, PageHeader, make_button, make_card, make_divider


class SettingsWindow(QWidget):
    """Manage application configuration and display system information."""

    def __init__(self) -> None:
        super().__init__()

        self._back_callback: Callable[[], None] | None = None

        self.setObjectName("page")
        self.setWindowTitle("Settings")
        self.resize(820, 560)
        self.setMinimumSize(620, 400)

        header = PageHeader("Settings", "Cafe details, taxes and printing")
        self.back_button = header.back_button
        self.back_button.clicked.connect(self.go_back)

        # Section 1: Configuration Card
        config_card = make_card()
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(24, 20, 24, 20)
        config_layout.setSpacing(14)

        config_title = QLabel("Configuration")
        config_title.setObjectName("cardTitle")
        config_layout.addWidget(config_title)
        config_layout.addWidget(make_divider())

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(24)
        form_layout.setVerticalSpacing(14)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.cafe_name_input = QLineEdit()
        self.cafe_name_input.setPlaceholderText("e.g. Daily Roast Cafe")

        self.receipt_footer_input = QLineEdit()
        self.receipt_footer_input.setPlaceholderText("e.g. Thank you for visiting!")

        self.gst_rate_input = AutoSelectDoubleSpinBox()
        self.gst_rate_input.setRange(0, 100)
        self.gst_rate_input.setDecimals(2)
        self.gst_rate_input.setSuffix(" %")
        self.gst_rate_input.setSpecialValueText(" ")  # blank at zero, like the other amount inputs
        self.gst_rate_input.setMaximumWidth(160)

        gst_hint = QLabel(
            "GST is added on top of the menu price. Each bill shows this rate split equally "
            "into CGST and SGST and the total includes it. Leave blank if you do not charge GST. "
            "Changing it affects new bills only."
        )
        gst_hint.setWordWrap(True)
        gst_hint.setObjectName("pageSubtitle")

        self.printer_input = QComboBox()

        form_layout.addRow(self._field_label("Cafe Name"), self.cafe_name_input)
        form_layout.addRow(self._field_label("Receipt Footer"), self.receipt_footer_input)
        gst_cell = QVBoxLayout()
        gst_cell.setSpacing(6)
        gst_cell.addWidget(self.gst_rate_input)
        gst_cell.addWidget(gst_hint)
        form_layout.addRow(self._field_label("GST Rate"), gst_cell)
        form_layout.addRow(self._field_label("Default Printer"), self.printer_input)

        config_layout.addLayout(form_layout)

        self.save_button = make_button("Save Configuration", "primary", "check")
        self.save_button.clicked.connect(self.save_settings)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.save_button)
        config_layout.addLayout(btn_row)

        # Section 2: Application Information Card
        info_card = make_card()
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(24, 20, 24, 20)
        info_layout.setSpacing(14)

        info_title = QLabel("Application Information")
        info_title.setObjectName("cardTitle")
        info_layout.addWidget(info_title)
        info_layout.addWidget(make_divider())

        info_form = QFormLayout()
        info_form.setContentsMargins(0, 0, 0, 0)
        info_form.setHorizontalSpacing(24)
        info_form.setVerticalSpacing(12)
        info_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        from app.services.configuration import get_database_path, get_reports_folder
        db_path = get_database_path()
        reports_dir = get_reports_folder()

        self.db_label = QLabel(str(db_path))
        self.db_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        db_change_btn = make_button("Change", "secondary")
        db_change_btn.clicked.connect(self.change_db_location)
        db_row = QHBoxLayout()
        db_row.setContentsMargins(0, 0, 0, 0)
        db_row.addWidget(self.db_label, 1)
        db_row.addWidget(db_change_btn)

        self.reports_label = QLabel(str(reports_dir))
        self.reports_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        reports_change_btn = make_button("Change", "secondary")
        reports_change_btn.clicked.connect(self.change_reports_location)
        reports_row = QHBoxLayout()
        reports_row.setContentsMargins(0, 0, 0, 0)
        reports_row.addWidget(self.reports_label, 1)
        reports_row.addWidget(reports_change_btn)

        self.version_label = QLabel("v1.0 (Offline Desktop POS)")
        self.platform_label = QLabel(f"{platform.system()} {platform.release()} ({sys.platform})")

        for value_label in (self.db_label, self.reports_label, self.version_label, self.platform_label):
            value_label.setObjectName("infoValue")

        info_form.addRow(self._field_label("Database Location"), db_row)
        info_form.addRow(self._field_label("Reports Folder"), reports_row)
        info_form.addRow(self._field_label("Application Version"), self.version_label)
        info_form.addRow(self._field_label("Platform"), self.platform_label)

        info_layout.addLayout(info_form)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(16)
        content_layout.addWidget(config_card)
        content_layout.addWidget(self.create_whatsapp_card())
        content_layout.addWidget(info_card)
        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(header)
        layout.addWidget(scroll, 1)

        self.load_settings()

    def create_whatsapp_card(self) -> QWidget:
        """Build the optional WhatsApp online-orders settings."""
        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("WhatsApp Orders")
        title.setObjectName("cardTitle")
        layout.addWidget(title)
        layout.addWidget(make_divider())

        self.whatsapp_enabled_input = QCheckBox("Receive WhatsApp orders in CafePOS")
        self.country_code_input = QLineEdit()
        self.country_code_input.setMaximumWidth(100)
        self.auto_ack_input = QCheckBox("Automatically tell customers we received their message")

        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.addRow("", self.whatsapp_enabled_input)
        form.addRow(self._field_label("Country code"), self.country_code_input)
        form.addRow("", self.auto_ack_input)
        layout.addLayout(form)

        hint = QLabel(
            "WhatsApp orders come in through the Local WhatsApp server (started from the "
            "Online Orders screen). Link your phone there first using a pairing code."
        )
        hint.setObjectName("pageSubtitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.whatsapp_status_label = QLabel()
        self.whatsapp_status_label.setObjectName("pageSubtitle")
        self.whatsapp_status_label.setWordWrap(True)

        self.save_whatsapp_button = make_button("Save WhatsApp Settings", "primary", "check")
        self.save_whatsapp_button.clicked.connect(self.save_whatsapp)
        self.test_phone_input = QLineEdit()
        self.test_phone_input.setPlaceholderText("Your phone, e.g. 98765 43210")
        self.test_phone_input.setMaximumWidth(220)
        self.test_message_button = make_button("Send Test Message", "ghost", "phone")
        self.test_message_button.clicked.connect(self.send_test_message)

        self.pairing_code_button = make_button("Get Pairing Code", "ghost", "phone")
        self.pairing_code_button.clicked.connect(self.request_pairing_code)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addWidget(self.test_phone_input)
        actions.addWidget(self.test_message_button)
        actions.addWidget(self.pairing_code_button)
        actions.addStretch()
        actions.addWidget(self.save_whatsapp_button)
        layout.addLayout(actions)
        layout.addWidget(self.whatsapp_status_label)
        return card

    def load_whatsapp_settings(self) -> None:
        """Show the saved WhatsApp settings in the inputs."""
        settings = get_whatsapp_settings()
        self.whatsapp_enabled_input.setChecked(bool(settings["enabled"]))
        self.country_code_input.setText(str(settings["country_code"]))
        self.auto_ack_input.setChecked(bool(settings["auto_ack"]))
        self.whatsapp_status_label.setText("")

    def save_whatsapp(self) -> None:
        """Store the WhatsApp settings; the poller picks them up within seconds."""
        try:
            save_whatsapp_settings({
                "enabled": self.whatsapp_enabled_input.isChecked(),
                "country_code": self.country_code_input.text().strip(),
                "auto_ack": self.auto_ack_input.isChecked(),
            })
        except Exception:
            QMessageBox.critical(self, "Settings", "Could not save the WhatsApp settings.")
            return
        self.whatsapp_status_label.setText("WhatsApp settings saved.")

    def request_pairing_code(self) -> None:
        """Request a pairing code for local whatsapp."""
        from PySide6.QtCore import QThread, Signal
        country_code = self.country_code_input.text().strip() or "91"
        phone = online_orders.normalize_phone(self.test_phone_input.text(), country_code)
        if len(phone) < 10:
            self.whatsapp_status_label.setText("Enter a valid phone number.")
            return
            
        self.pairing_code_button.setEnabled(False)
        self.whatsapp_status_label.setText("Requesting pairing code... This may take up to 20 seconds.")

        class PairingWorker(QThread):
            result_signal = Signal(str, str)
            def run(self):
                from app.services.whatsapp import request_pairing_code
                try:
                    code = request_pairing_code(phone, timeout=30.0)
                    if code:
                        self.result_signal.emit("success", code)
                    else:
                        self.result_signal.emit("error", "Failed to get pairing code.")
                except Exception as e:
                    self.result_signal.emit("error", str(e))

        self._pairing_worker = PairingWorker(self)
        def on_result(status: str, msg: str):
            self.pairing_code_button.setEnabled(True)
            if status == "success":
                self.whatsapp_status_label.setText(f"Pairing Code: {msg}")
            else:
                self.whatsapp_status_label.setText(f"Error: {msg}")
                
        self._pairing_worker.result_signal.connect(on_result)
        self._pairing_worker.start()

    def send_test_message(self) -> None:
        """Send a plain test message through the Local WhatsApp server to prove it works."""
        country_code = self.country_code_input.text().strip() or "91"
        phone = online_orders.normalize_phone(self.test_phone_input.text(), country_code)
        if len(phone) < 11:
            self.whatsapp_status_label.setText("Enter a full phone number to send the test to.")
            return
        sure = QMessageBox.question(
            self, "Send test message", f"Send a real test message to +{phone}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if sure != QMessageBox.StandardButton.Yes:
            return

        shop = self.cafe_name_input.text().strip() or "our shop"
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            send_local_message(phone, f"Test message from {shop}. WhatsApp is connected.")
            message = f"Test message sent to +{phone}. Check that phone."
        except WhatsAppError as error:
            message = f"Not sent. {error}"
        finally:
            QApplication.restoreOverrideCursor()
        self.whatsapp_status_label.setText(message)

    @staticmethod
    def _field_label(text: str) -> QLabel:
        """Create a muted caption for a settings row."""
        label = QLabel(text)
        label.setObjectName("infoKey")
        label.setMinimumWidth(150)
        return label

    def set_back_callback(self, callback: Callable[[], None]) -> None:
        """Set the navigation action for the screen's Back button."""
        self._back_callback = callback

    def go_back(self) -> None:
        """Return to the dashboard shell."""
        if self._back_callback is not None:
            self._back_callback()

    def load_settings(self) -> None:
        """Load current configuration into inputs."""
        config = load_configuration()
        self.cafe_name_input.setText(str(config.get("cafe_name", "")))
        self.receipt_footer_input.setText(str(config.get("receipt_footer", "")))
        self.gst_rate_input.setValue(get_gst_rate())

        self.printer_input.clear()
        self.printer_input.addItem("None", "")
        available = [info.printerName() for info in QPrinterInfo.availablePrinters()]
        for p in available:
            self.printer_input.addItem(p, p)

        current_printer = get_default_printer()
        if current_printer:
            idx = self.printer_input.findData(current_printer)
            if idx >= 0:
                self.printer_input.setCurrentIndex(idx)
            else:
                self.printer_input.addItem(f"{current_printer} (Disconnected)", current_printer)
                self.printer_input.setCurrentIndex(self.printer_input.count() - 1)
        self.load_whatsapp_settings()

    def save_settings(self) -> None:
        """Save settings entries to local config."""
        cafe_name = self.cafe_name_input.text().strip()
        receipt_footer = self.receipt_footer_input.text().strip()
        printer_name = str(self.printer_input.currentData() or "")

        if not cafe_name:
            QMessageBox.warning(self, "Settings", "Cafe Name cannot be empty.")
            return

        try:
            save_configuration(cafe_name, receipt_footer, gst_rate=self.gst_rate_input.value())
            # save_configuration keeps other settings, so choosing "None" must clear the printer.
            save_default_printer(printer_name)
            QMessageBox.information(self, "Settings", "Settings saved successfully.")
        except Exception:
            QMessageBox.critical(self, "Settings", "Could not save configuration.")

    def change_db_location(self) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from app.services.configuration import save_paths
        
        new_path, _ = QFileDialog.getSaveFileName(self, "Select Database Location", self.db_label.text(), "SQLite Database (*.db)")
        if new_path:
            self.db_label.setText(new_path)
            save_paths(self.db_label.text(), self.reports_label.text())
            QMessageBox.information(self, "Restart Required", "Please restart CafePOS for the new database location to take effect.")

    def change_reports_location(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from app.services.configuration import save_paths
        
        new_dir = QFileDialog.getExistingDirectory(self, "Select Reports Folder", self.reports_label.text())
        if new_dir:
            self.reports_label.setText(new_dir)
            save_paths(self.db_label.text(), self.reports_label.text())

