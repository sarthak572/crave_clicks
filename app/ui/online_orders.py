"""Online Orders screen: WhatsApp orders waiting for the owner, plus the pop-up that
announces a new one."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QSize, QTimer, Qt, Signal, QProcess
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.database import session_scope
from app.dialogs.online_order_dialogs import AcceptOrderDialog, RejectOrderDialog
from app.models import OnlineOrder
from app.runtime_paths import application_directory
from app.services import CartLine, calculate_bill_totals, get_menu_items, online_orders
from app.services.configuration import get_gst_rate
from app.services.whatsapp import WhatsAppOrderService
from app.ui.widgets import (
    PageHeader,
    SegmentedControl,
    make_button,
    set_variant,
    make_card,
    make_divider,
    make_empty_state,
)

_PILL_STATE = {online_orders.NEW: "new", online_orders.REJECTED: "void"}


def age_text(received_at: str, now: datetime | None = None) -> str:
    """How long ago an order arrived, in words a busy owner can read at a glance."""
    try:
        received = datetime.fromisoformat(received_at)
    except ValueError:
        return received_at
    seconds = int(((now or datetime.now()) - received).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return received.strftime("%d %b, %I:%M %p").lstrip("0")


class NewOrderToast(QFrame):
    """A small pop-up in the corner that announces a new order without stealing focus."""

    view_requested = Signal()
    SHOW_SECONDS = 20

    def __init__(self, parent: QWidget) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(340)

        self.title_label = QLabel("New WhatsApp order")
        self.title_label.setObjectName("cardTitle")
        self.text_label = QLabel()
        self.text_label.setObjectName("infoValue")
        self.text_label.setWordWrap(True)

        view_button = make_button("View", "primary")
        view_button.clicked.connect(self._on_view)
        dismiss_button = make_button("Dismiss", "ghost")
        dismiss_button.clicked.connect(self.hide)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(dismiss_button)
        buttons.addWidget(view_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)
        layout.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def announce(self, text: str) -> None:
        """Show the pop-up near the bottom-right corner of the main window."""
        self.text_label.setText(text)
        self.adjustSize()
        anchor = self.parentWidget()
        if anchor is not None:
            corner = anchor.mapToGlobal(anchor.rect().bottomRight())
            self.move(corner.x() - self.width() - 24, corner.y() - self.height() - 24)
        self.show()
        self.raise_()
        self._timer.start(self.SHOW_SECONDS * 1000)

    def _on_view(self) -> None:
        self.hide()
        self.view_requested.emit()

from PySide6.QtWidgets import QDialog
from PySide6.QtGui import QPixmap

class QRDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scan to Link WhatsApp")
        self.setFixedSize(380, 380)
        self.layout = QVBoxLayout(self)
        self.label = QLabel("Waiting for QR Code...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)
        self.current_qr = ""

    def update_qr(self, base64_str: str) -> None:
        if base64_str == self.current_qr: return
        self.current_qr = base64_str
        import base64
        try:
            data = base64_str.split(",")[1]
            pixmap = QPixmap()
            pixmap.loadFromData(base64.b64decode(data))
            self.label.setPixmap(pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            self.label.setText(f"Error loading QR: {e}")

class OnlineOrdersWindow(QWidget):
    """List WhatsApp orders and let the owner accept, reject and update them."""

    changed = Signal()  # an order changed status, so counters elsewhere should refresh

    def __init__(self, service: WhatsAppOrderService) -> None:
        super().__init__()

        self.service = service
        self._back_callback: Callable[[], None] | None = None
        self._make_bill_callback: Callable[[int], None] | None = None
        self._selected_id: int | None = None

        self.setObjectName("page")
        self.setWindowTitle("Online Orders")

        header = PageHeader("Online Orders", "WhatsApp orders from your customers")
        self.back_button = header.back_button
        self.back_button.clicked.connect(self.go_back)
        self.connection_label = QLabel("WhatsApp: Off")
        self.connection_label.setObjectName("chip")
        header.add_action(self.connection_label)
        
        self.server_button = make_button("Start Server", "success", "refresh")
        self.server_button.clicked.connect(self.toggle_server)
        header.add_action(self.server_button)
        
        self.node_process = QProcess(self)
        self.node_process.finished.connect(self.on_server_stopped)

        self.qr_dialog = None
        self.service.connection_changed.connect(self.update_status)
        self.service.qr_code_received.connect(self.show_qr_code)
        self.update_status(self.service.connection)

        self.filter_control = SegmentedControl([("Active", None), ("Done", None)])
        self.filter_control.setMinimumWidth(200)
        self.filter_control.currentChanged.connect(lambda _index: self.refresh())
        header.add_action(self.filter_control)

        # Left: the orders
        self.order_list = QListWidget()
        self.order_list.setObjectName("orderList")
        self.order_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.order_list.currentItemChanged.connect(self._on_current_changed)
        self.list_empty = make_empty_state("inbox", "No online orders", "New WhatsApp orders will appear here.")
        list_panel = QWidget()
        list_panel.setFixedWidth(380)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(self.order_list, 1)
        list_layout.addWidget(self.list_empty, 1)

        # Right: the selected order
        self.detail_card = make_card()
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(24, 20, 24, 20)
        detail_layout.setSpacing(14)

        self.detail_empty = make_empty_state("inbox", "Select an order", "Pick an order on the left to see it here.")

        self.detail_content = QWidget()
        content_layout = QVBoxLayout(self.detail_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        self.title_label = QLabel()
        self.title_label.setObjectName("cardTitle")
        self.status_pill = QLabel()
        self.status_pill.setObjectName("statusPill")
        title_row = QHBoxLayout()
        title_row.addWidget(self.title_label)
        title_row.addStretch()
        title_row.addWidget(self.status_pill)
        content_layout.addLayout(title_row)
        content_layout.addWidget(make_divider())

        self.customer_value = self._value_label()
        self.phone_value = self._value_label()
        self.received_value = self._value_label()
        self.prep_value = self._value_label()
        self.total_value = self._value_label()
        self.message_status_value = self._value_label()
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(8)
        for caption, value in (
            ("Customer", self.customer_value),
            ("Phone", self.phone_value),
            ("Received", self.received_value),
            ("Ready in", self.prep_value),
            ("Total told to customer", self.total_value),
            ("Last message to customer", self.message_status_value),
        ):
            key = QLabel(caption)
            key.setObjectName("infoKey")
            form.addRow(key, value)
        content_layout.addLayout(form)

        message_caption = QLabel("CUSTOMER'S MESSAGE")
        message_caption.setObjectName("sectionLabel")
        self.message_box = QLabel()
        self.message_box.setObjectName("messageBox")
        self.message_box.setWordWrap(True)
        self.message_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message_box.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(message_caption)
        content_layout.addWidget(self.message_box, 1)

        self.custom_msg_input = QLineEdit()
        self.custom_msg_input.setPlaceholderText("Type a custom message...")
        self.custom_msg_send = make_button("Send", "primary", "edit")
        self.custom_msg_send.clicked.connect(lambda: self.send_custom_message())
        
        custom_row = QHBoxLayout()
        custom_row.addWidget(self.custom_msg_input, 1)
        custom_row.addWidget(self.custom_msg_send)
        content_layout.addLayout(custom_row)

        self.accept_button = make_button("Accept", "success", "check")
        self.reject_button = make_button("Reject", "danger", "x")
        self.ready_button = make_button("Order Ready", "primary", "check")
        self.delivery_button = make_button("Out for Delivery", "primary", "cart")
        self.bill_button = make_button("Make Bill", "primary", "receipt")
        self.resend_button = make_button("Resend Message", "ghost", "refresh")
        for button in (self.accept_button, self.ready_button, self.delivery_button, self.bill_button):
            button.setMinimumHeight(44)
            button.setIconSize(QSize(20, 20))
        self.accept_button.clicked.connect(self.on_accept_clicked)
        self.reject_button.clicked.connect(self.on_reject_clicked)
        self.ready_button.clicked.connect(lambda: self._act(self.mark_ready))
        self.delivery_button.clicked.connect(lambda: self._act(self.mark_out_for_delivery))
        self.bill_button.clicked.connect(lambda: self._act(self.make_bill))
        self.resend_button.clicked.connect(lambda: self._act(self.resend_message))

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        for button in (
            self.accept_button, self.ready_button, self.delivery_button, self.bill_button,
            self.reject_button, self.resend_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch()
        content_layout.addLayout(button_row)

        detail_layout.addWidget(self.detail_content, 1)
        detail_layout.addWidget(self.detail_empty, 1)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(list_panel)
        body.addWidget(self.detail_card, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        layout.addWidget(header)
        layout.addLayout(body, 1)

        self.service.orders_changed.connect(self.refresh)
        self.service.connection_changed.connect(self.set_connection)
        self.set_connection(self.service.connection)
        self.refresh()

    @staticmethod
    def _value_label() -> QLabel:
        label = QLabel()
        label.setObjectName("infoValue")
        label.setWordWrap(True)
        return label

    # ------------------------------------------------------------- navigation
    def set_back_callback(self, callback: Callable[[], None]) -> None:
        self._back_callback = callback

    def set_make_bill_callback(self, callback: Callable[[int], None]) -> None:
        """The dashboard opens Billing with the order's items already in the cart."""
        self._make_bill_callback = callback

    def go_back(self) -> None:
        if self._back_callback is not None:
            self._back_callback()
            
    def update_status(self, state: str) -> None:
        self.connection_label.setText(f"WhatsApp: {state}")
        if state == "Connected" and self.qr_dialog is not None:
            self.qr_dialog.accept()
            self.qr_dialog = None

    def show_qr_code(self, qr_str: str) -> None:
        if self.qr_dialog is None:
            self.qr_dialog = QRDialog(self)
            self.qr_dialog.show()
        self.qr_dialog.update_qr(qr_str)

    def toggle_server(self) -> None:
        import subprocess
        if self.node_process.state() == QProcess.ProcessState.NotRunning:
            # Clean up any orphaned node processes before starting
            subprocess.run(["taskkill", "/F", "/IM", "node.exe"], capture_output=True)
            self.server_button.setText("Stop Server")
            set_variant(self.server_button, "danger")
            work_dir = application_directory() / "local_whatsapp"
            script = work_dir / "start_whatsapp.ps1"
            if not script.is_file():
                QMessageBox.warning(
                    self, "WhatsApp server",
                    f"Could not find the Local WhatsApp server folder at:\n{work_dir}",
                )
                self.server_button.setText("Start Server")
                set_variant(self.server_button, "success")
                return
            self.node_process.setWorkingDirectory(str(work_dir))
            self.node_process.start("powershell", ["-ExecutionPolicy", "ByPass", "-File", str(script)])
        else:
            self.server_button.setText("Start Server")
            set_variant(self.server_button, "success")
            # Force kill node.exe because PowerShell doesn't forward the kill signal
            subprocess.run(["taskkill", "/F", "/IM", "node.exe"], capture_output=True)
            self.node_process.kill()

    def on_server_stopped(self) -> None:
        self.server_button.setText("Start Server")
        set_variant(self.server_button, "success")

    def select_order(self, order_id: int) -> None:
        """Show ``order_id`` (switching between the Active and Done lists if needed)."""
        with session_scope() as session:
            order = session.get(OnlineOrder, order_id)
            done = order is not None and order.status in online_orders.DONE_STATUSES
        self._selected_id = order_id
        wanted = 1 if done else 0
        if self.filter_control.currentIndex() != wanted:
            self.filter_control.setCurrentIndex(wanted)
        self.refresh()

    def set_connection(self, state: str) -> None:
        text = state if len(state) < 60 else state[:57] + "..."
        self.connection_label.setText(f"WhatsApp: {text}")
        self.connection_label.setToolTip(state)

    # --------------------------------------------------------------- the list
    def refresh(self) -> None:
        """Reload the list and the detail panel from the database."""
        showing_done = self.filter_control.currentIndex() == 1
        statuses = online_orders.DONE_STATUSES if showing_done else online_orders.ACTIVE_STATUSES
        with session_scope() as session:
            orders = online_orders.list_orders(session, statuses)
            rows = [
                (order.id, online_orders.order_number(order), order.status,
                 order.customer_name or online_orders.display_phone(order.customer_phone), order.received_at)
                for order in orders
            ]
        rows.sort(key=lambda row: (row[2] != online_orders.NEW, -row[0]) if not showing_done else (False, -row[0]))

        self.order_list.blockSignals(True)
        self.order_list.clear()
        keep_row = -1
        for index, (order_id, number, status, who, received_at) in enumerate(rows):
            item = QListWidgetItem(f"{number}   ·   {status}\n{who}   ·   {age_text(received_at)}")
            item.setData(Qt.ItemDataRole.UserRole, order_id)
            self.order_list.addItem(item)
            if order_id == self._selected_id:
                keep_row = index
        if keep_row < 0 and rows:
            keep_row = 0
        if keep_row >= 0:
            self.order_list.setCurrentRow(keep_row)
            self._selected_id = rows[keep_row][0]
        else:
            self._selected_id = None
        self.order_list.blockSignals(False)

        self.order_list.setVisible(bool(rows))
        self.list_empty.setVisible(not rows)
        self._show_detail(self._selected_id)

    def _on_current_changed(self, current: QListWidgetItem | None, _previous: object) -> None:
        self._selected_id = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        self._show_detail(self._selected_id)

    # ------------------------------------------------------------- the detail
    def _show_detail(self, order_id: int | None) -> None:
        order = None
        if order_id is not None:
            with session_scope() as session:
                found = session.get(OnlineOrder, order_id)
                if found is not None:
                    order = {
                        "number": online_orders.order_number(found),
                        "status": found.status,
                        "name": found.customer_name or "Not shared",
                        "phone": online_orders.display_phone(found.customer_phone),
                        "received": age_text(found.received_at),
                        "prep": f"{found.prep_minutes} minutes" if found.prep_minutes else "-",
                        "total": f"₹{found.quoted_total:.2f}" if found.quoted_total is not None else "-",
                        "last_message": found.last_message or "None yet",
                        "text": found.message_text or "(no text)",
                    }

        self.detail_content.setVisible(order is not None)
        self.detail_empty.setVisible(order is None)
        if order is None:
            return

        status = order["status"]
        self.title_label.setText(f"Order {order['number']}")
        self.status_pill.setText(status)
        self.status_pill.setProperty("state", _PILL_STATE.get(status, ""))
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)
        self.customer_value.setText(order["name"])
        self.phone_value.setText(order["phone"])
        self.received_value.setText(order["received"])
        self.prep_value.setText(order["prep"])
        self.total_value.setText(order["total"])
        self.message_status_value.setText(order["last_message"])
        self.message_box.setText(order["text"])

        self.accept_button.setVisible(status == online_orders.NEW)
        self.ready_button.setVisible(status == online_orders.ACCEPTED)
        self.delivery_button.setVisible(status == online_orders.ACCEPTED)
        self.bill_button.setVisible(status in (
            online_orders.ACCEPTED, online_orders.READY, online_orders.OUT_FOR_DELIVERY,
        ))
        self.reject_button.setVisible(status in (online_orders.NEW, online_orders.ACCEPTED))
        self.resend_button.setVisible("NOT sent" in order["last_message"])

    # ---------------------------------------------------------------- actions
    def _act(self, action: Callable[[int], None]) -> None:
        if self._selected_id is None:
            return
        try:
            action(self._selected_id)
        except online_orders.OnlineOrderError as error:
            QMessageBox.warning(self, "Online order", str(error))

    def estimate_total(self, order_id: int) -> float | None:
        """The bill total for a catalog order (menu prices plus GST), or None when unknown."""
        with session_scope() as session:
            order = session.get(OnlineOrder, order_id)
            wanted = online_orders.cart_items(order) if order is not None else []
            menu = {item.id: item for item in get_menu_items(session)}
        lines = []
        for entry in wanted:
            try:
                item = menu.get(int(entry.get("id")))
            except (TypeError, ValueError):
                item = None
            if item is not None:
                lines.append(CartLine(item.id, item.name, item.price, max(1, int(entry.get("qty") or 1))))
        if not lines:
            return None
        return calculate_bill_totals(lines, None, get_gst_rate()).total

    def on_accept_clicked(self) -> None:
        if self._selected_id is None:
            return
        dialog = AcceptOrderDialog(
            f"Order W{self._selected_id} from {self.phone_value.text()}",
            self.estimate_total(self._selected_id),
            self,
        )
        if dialog.exec():
            self._act(lambda order_id: self.accept_order(order_id, dialog.prep_minutes, dialog.quoted_total))

    def on_reject_clicked(self) -> None:
        if self._selected_id is None:
            return
        dialog = RejectOrderDialog(f"Order W{self._selected_id} from {self.phone_value.text()}", self)
        if dialog.exec():
            self._act(lambda order_id: self.reject_order(order_id, dialog.reason))

    def _move(self, order_id: int, status: str, **details: object) -> None:
        with session_scope() as session:
            online_orders.change_status(session, order_id, status, **details)
        self.service.send_status_message(order_id, online_orders.STATUS_MESSAGE[status])
        self.refresh()
        self.changed.emit()

    def accept_order(self, order_id: int, prep_minutes: int, quoted_total: float | None) -> None:
        """Accept the order and tell the customer it is being prepared."""
        self._move(order_id, online_orders.ACCEPTED, prep_minutes=prep_minutes, quoted_total=quoted_total)

    def reject_order(self, order_id: int, reason: str) -> None:
        """Reject the order and tell the customer why."""
        self._move(order_id, online_orders.REJECTED, reason=reason)

    def mark_ready(self, order_id: int) -> None:
        self._move(order_id, online_orders.READY)

    def mark_out_for_delivery(self, order_id: int) -> None:
        self._move(order_id, online_orders.OUT_FOR_DELIVERY)

    def resend_message(self, order_id: int) -> None:
        """Send the message for the order's current status again."""
        with session_scope() as session:
            order = session.get(OnlineOrder, order_id)
            event_key = online_orders.STATUS_MESSAGE.get(order.status) if order is not None else None
        if event_key is None:
            raise online_orders.OnlineOrderError("There is no message to resend for this order.")
        self.service.send_status_message(order_id, event_key)

    def send_custom_message(self) -> None:
        if self._selected_id is None:
            return
        text = self.custom_msg_input.text().strip()
        if not text:
            return
        self._act(lambda order_id: self.service.send_status_message(order_id, f"custom:{text}"))
        self.custom_msg_input.clear()

    def make_bill(self, order_id: int) -> None:
        if self._make_bill_callback is not None:
            self._make_bill_callback(order_id)
