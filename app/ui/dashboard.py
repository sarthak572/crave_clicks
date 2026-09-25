"""CafePOS's single-window navigation shell and dashboard."""

from datetime import date, datetime

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import session_scope
from app.dialogs import OrderDetailsDialog
from app.models import OnlineOrder
from app.services import get_menu_items, get_orders_for_period, get_report_summary, online_orders
from app.services.configuration import get_whatsapp_settings, load_configuration
from app.services.printing import get_default_printer
from app.services.whatsapp import WhatsAppOrderService
from app.ui.billing import BillingWindow
from app.ui.menu_management import MenuManagementWindow
from app.ui.online_orders import NewOrderToast, OnlineOrdersWindow
from app.ui.reports import ReportsWindow
from app.ui.settings import SettingsWindow
from app.ui.theme import Color, icon, pixmap
from app.ui.widgets import RevealStatCard, StatCard, make_button, make_card, make_empty_state

SIDEBAR_WIDTH = 220
RECENT_ORDER_LIMIT = 6


def greeting_for(hour: int) -> str:
    """Return a time-of-day greeting for the dashboard header."""
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def format_order_time(order_time: str) -> str:
    """Show a stored HH:MM:SS bill time as a friendly 12-hour time."""
    try:
        return datetime.strptime(order_time, "%H:%M:%S").strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return order_time


class DashboardWindow(QMainWindow):
    """Host every CafePOS screen in one stacked main window."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("CafePOS")
        self.setMinimumSize(1100, 660)
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(
            min(1360, int(available.width() * 0.94)) if available else 1360,
            min(820, int(available.height() * 0.92)) if available else 820,
        )

        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)

        self.dashboard_page = self.create_dashboard_page()
        self.billing_window = BillingWindow()
        self.menu_management_window = MenuManagementWindow()
        self.reports_window = ReportsWindow()
        self.settings_window = SettingsWindow()
        self.whatsapp = WhatsAppOrderService(self)
        self.online_orders_window = OnlineOrdersWindow(self.whatsapp)

        # The sidebar is a frameless, fixed dock so the stacked pages stay the central widget.
        self.nav_dock = QDockWidget(self)
        self.nav_dock.setObjectName("navDock")
        self.nav_dock.setTitleBarWidget(QWidget())
        self.nav_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.nav_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.nav_dock.setWidget(self.create_sidebar())
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.nav_dock)

        for page in (
            self.dashboard_page,
            self.billing_window,
            self.online_orders_window,
            self.menu_management_window,
            self.reports_window,
            self.settings_window,
        ):
            self.add_page(page)

        self._nav_pages = (
            (self.dashboard_button, self.dashboard_page),
            (self.new_order_button, self.billing_window),
            (self.online_orders_button, self.online_orders_window),
            (self.reports_button, self.reports_window),
            (self.menu_management_button, self.menu_management_window),
            (self.settings_button, self.settings_window),
        )
        self.pages.currentChanged.connect(lambda _index: self.sync_navigation())

        self.billing_window.set_back_callback(self.return_to_dashboard)
        self.menu_management_window.set_back_callback(self.return_to_dashboard)
        self.reports_window.set_back_callback(self.return_to_dashboard)
        self.settings_window.set_back_callback(self.return_to_dashboard)
        self.online_orders_window.set_back_callback(self.return_to_dashboard)
        self.online_orders_window.set_make_bill_callback(self.make_bill_for_online_order)
        self.online_orders_window.changed.connect(self.update_online_orders_badge)
        self.billing_window.online_order_billed.connect(self.on_online_order_billed)
        self.whatsapp.new_order.connect(self.on_new_online_order)
        self.whatsapp.orders_changed.connect(self.update_online_orders_badge)
        self.whatsapp.connection_changed.connect(self.update_whatsapp_status)

        self.new_order_toast = NewOrderToast(self)
        self.new_order_toast.view_requested.connect(self.show_online_orders_for_new)
        self.beep_timer = QTimer(self)
        self.beep_timer.setInterval(4000)
        self.beep_timer.timeout.connect(self.beep_for_new_orders)

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(30_000)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start()

        self.refresh_dashboard_data()
        self.sync_navigation()

    # ------------------------------------------------------------------ layout

    def create_sidebar(self) -> QWidget:
        """Build the dark navigation rail with the brand, page buttons and system status."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 22, 16, 16)
        layout.setSpacing(4)

        brand_mark = QLabel()
        brand_mark.setObjectName("brandMark")
        brand_mark.setFixedSize(44, 44)
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setPixmap(pixmap("cup", "#FFFFFF", 24))
        self.brand_name_label = QLabel("CafePOS")
        self.brand_name_label.setObjectName("brandName")
        brand_tag = QLabel("Point of Sale")
        brand_tag.setObjectName("brandTag")
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_text.addWidget(self.brand_name_label)
        brand_text.addWidget(brand_tag)
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(4, 0, 0, 0)
        brand_row.setSpacing(12)
        brand_row.addWidget(brand_mark)
        brand_row.addLayout(brand_text, 1)
        layout.addLayout(brand_row)
        layout.addSpacing(26)

        caption = QLabel("NAVIGATION")
        caption.setObjectName("navCaption")
        caption.setContentsMargins(14, 0, 0, 6)
        layout.addWidget(caption)

        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        entries = (
            ("dashboard_button", "Dashboard", "home", self.return_to_dashboard),
            ("new_order_button", "New Order", "plus-square", self.open_new_order),
            ("online_orders_button", "Online Orders", "inbox", self.open_online_orders),
            ("reports_button", "Reports", "chart", self.open_reports),
            ("menu_management_button", "Menu", "list", self.open_menu_management),
            ("settings_button", "Settings", "sliders", self.open_settings),
        )
        for attribute, text, icon_name, handler in entries:
            button = QPushButton(f"  {text}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setIcon(icon(icon_name, Color.SIDEBAR_TEXT, "#FFFFFF"))
            button.setIconSize(QSize(20, 20))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, action=handler: action())
            nav_group.addButton(button)
            setattr(self, attribute, button)
            layout.addWidget(button)

        layout.addStretch()
        layout.addWidget(self._sidebar_divider())
        layout.addSpacing(8)

        self.sidebar_database_label = QLabel(
            '<span style="color:#3DBE7A;">●</span>&nbsp;&nbsp;Local database · Offline'
        )
        self.sidebar_database_label.setObjectName("sidebarStatus")
        self.sidebar_database_label.setTextFormat(Qt.TextFormat.RichText)
        self.sidebar_printer_label = QLabel("Printer: Not Configured")
        self.sidebar_printer_label.setObjectName("sidebarStatus")
        self.sidebar_whatsapp_label = QLabel("WhatsApp: Off")
        self.sidebar_whatsapp_label.setObjectName("sidebarStatus")
        version_label = QLabel("CafePOS v1.0")
        version_label.setObjectName("sidebarVersion")
        for label in (
            self.sidebar_database_label, self.sidebar_printer_label, self.sidebar_whatsapp_label, version_label
        ):
            label.setContentsMargins(4, 0, 0, 0)
            layout.addWidget(label)
        return sidebar

    @staticmethod
    def _sidebar_divider() -> QFrame:
        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFixedHeight(1)
        return divider

    def create_dashboard_page(self) -> QWidget:
        """Build the home screen: greeting, headline numbers, recent orders and system status."""
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(22)

        self.header_greeting = QLabel()
        self.header_greeting.setObjectName("pageSubtitle")
        self.header_cafe_name = QLabel("CafePOS")
        self.header_cafe_name.setObjectName("pageTitle")
        self.header_datetime = QLabel()
        self.header_datetime.setObjectName("pageSubtitle")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(self.header_greeting)
        titles.addWidget(self.header_cafe_name)

        self.dashboard_new_order_button = make_button("  New Order", "primary", "plus")
        self.dashboard_new_order_button.setIconSize(QSize(20, 20))
        self.dashboard_new_order_button.setObjectName("heroButton")
        self.dashboard_new_order_button.clicked.connect(self.open_new_order)

        header_row = QHBoxLayout()
        header_row.setSpacing(18)
        header_row.addLayout(titles)
        header_row.addStretch()
        header_row.addWidget(self.header_datetime, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self.dashboard_new_order_button)
        layout.addLayout(header_row)

        orders_card = StatCard("Today's Orders", "receipt")
        revenue_card = RevealStatCard("Today's Revenue")
        avg_card = StatCard("Average Bill Value", "trend")
        menu_card = StatCard("Menu Items", "layers")
        self.orders_count_val = orders_card.value_label
        self.revenue_card = revenue_card
        self.avg_bill_val = avg_card.value_label
        self.menu_count_val = menu_card.value_label
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        for card in (orders_card, revenue_card, avg_card, menu_card):
            stats_row.addWidget(card, 1)
        layout.addLayout(stats_row)

        lower_row = QHBoxLayout()
        lower_row.setSpacing(16)
        lower_row.addWidget(self.create_recent_orders_card(), 3)
        lower_row.addLayout(self.create_side_cards(), 1)
        layout.addLayout(lower_row, 1)
        return page

    def create_recent_orders_card(self) -> QWidget:
        """Build the list of today's latest bills."""
        card = make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(10)

        title = QLabel("Recent orders")
        title.setObjectName("cardTitle")
        view_all = make_button("View all", "ghost")
        view_all.clicked.connect(self.open_reports)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(20, 0, 12, 0)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(view_all)
        layout.addLayout(title_row)

        self.recent_orders_table = QTableWidget(0, 5)
        self.recent_orders_table.setObjectName("embeddedTable")
        self.recent_orders_table.setHorizontalHeaderLabels(["Bill", "Time", "Service", "Payment", "Amount"])
        self.recent_orders_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_orders_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recent_orders_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_orders_table.setShowGrid(False)
        self.recent_orders_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recent_orders_table.verticalHeader().setVisible(False)
        self.recent_orders_table.verticalHeader().setDefaultSectionSize(46)
        self.recent_orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent_orders_table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.recent_orders_table.horizontalHeaderItem(4).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.recent_orders_table.cellDoubleClicked.connect(self.open_order_details)
        layout.addWidget(self.recent_orders_table, 1)

        self.recent_orders_empty = make_empty_state(
            "inbox", "No orders yet today", "Completed bills will appear here."
        )
        layout.addWidget(self.recent_orders_empty, 1)
        return card

    def create_side_cards(self) -> QVBoxLayout:
        """Build the best-seller and system-status cards beside the recent orders."""
        best_card = make_card()
        best_layout = QVBoxLayout(best_card)
        best_layout.setContentsMargins(18, 16, 18, 16)
        best_layout.setSpacing(6)
        best_caption = QLabel("BEST SELLER TODAY")
        best_caption.setObjectName("sectionLabel")
        star = QLabel()
        star.setPixmap(pixmap("star", Color.ACCENT, 22))
        self.best_seller_label = QLabel("No sales yet")
        self.best_seller_label.setObjectName("cardTitle")
        self.best_seller_label.setWordWrap(True)
        best_row = QHBoxLayout()
        best_row.setSpacing(10)
        best_row.addWidget(star, 0, Qt.AlignmentFlag.AlignTop)
        best_row.addWidget(self.best_seller_label, 1)
        best_layout.addWidget(best_caption)
        best_layout.addLayout(best_row)

        system_card = make_card()
        system_layout = QVBoxLayout(system_card)
        system_layout.setContentsMargins(18, 16, 18, 16)
        system_layout.setSpacing(10)
        system_caption = QLabel("SYSTEM")
        system_caption.setObjectName("sectionLabel")
        system_layout.addWidget(system_caption)

        self.status_database_label = QLabel("Connected")
        self.status_printer_label = QLabel("Not Configured")
        version_status = QLabel("v1.0 (Offline)")
        for name, value_label in (
            ("Database", self.status_database_label),
            ("Printer", self.status_printer_label),
            ("Version", version_status),
        ):
            key_label = QLabel(name)
            key_label.setObjectName("infoKey")
            value_label.setObjectName("infoValue")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row = QHBoxLayout()
            row.addWidget(key_label)
            row.addStretch()
            row.addWidget(value_label)
            system_layout.addLayout(row)

        column = QVBoxLayout()
        column.setSpacing(16)
        column.addWidget(best_card)
        column.addWidget(system_card)
        column.addStretch()
        return column

    # -------------------------------------------------------------- navigation

    def add_page(self, page: QWidget) -> None:
        """Add a CafePOS screen to the single-window page stack."""
        self.pages.addWidget(page)

    def show_page(self, page: QWidget) -> None:
        """Display a screen already registered in the page stack."""
        self.pages.setCurrentWidget(page)

    def sync_navigation(self) -> None:
        """Highlight the sidebar button of the page being shown."""
        current = self.pages.currentWidget()
        if current is not self.dashboard_page:
            self.revenue_card.hide_value()
        for button, page in self._nav_pages:
            button.setChecked(page is current)

    def confirm_leave_billing(self) -> bool:
        """Ask before an unfinished order is discarded; return whether navigation may continue."""
        if self.pages.currentWidget() is self.billing_window and self.billing_window.has_active_cart():
            discard = QMessageBox.question(
                self,
                "CafePOS",
                "Discard current order?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if discard != QMessageBox.StandardButton.Yes:
                self.sync_navigation()
                return False
            self.billing_window.reset_order()
        return True

    def return_to_dashboard(self) -> None:
        """Return to the dashboard, confirming before discarding a cart."""
        if not self.confirm_leave_billing():
            return

        self.refresh_dashboard_data()
        self.show_page(self.dashboard_page)

    def open_new_order(self) -> None:
        """Open billing, optionally discarding an existing unfinished cart."""
        if self.billing_window.has_active_cart():
            discard = QMessageBox.question(
                self,
                "CafePOS",
                "Discard current order?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if discard == QMessageBox.StandardButton.Yes:
                self.billing_window.reset_order()

        self.billing_window.load_menu()
        self.show_page(self.billing_window)
        self.sync_navigation()

    def open_menu_management(self) -> None:
        """Open the Menu Management window."""
        if not self.confirm_leave_billing():
            return
        self.menu_management_window.load_items()
        self.show_page(self.menu_management_window)

    def open_reports(self) -> None:
        """Open the reports window with current local order data."""
        if not self.confirm_leave_billing():
            return
        self.reports_window.refresh_reports()
        self.show_page(self.reports_window)

    def open_settings(self) -> None:
        """Open the Settings window."""
        if not self.confirm_leave_billing():
            return
        self.settings_window.load_settings()
        self.show_page(self.settings_window)

    def open_order_details(self, row: int, _column: int) -> None:
        """Open a recent order's details when its row is double-clicked."""
        bill_item = self.recent_orders_table.item(row, 0)
        if bill_item is None:
            return
        dialog = OrderDetailsDialog(bill_item.data(Qt.ItemDataRole.UserRole), self.refresh_dashboard_data, self)
        dialog.exec()

    # ------------------------------------------------------------ WhatsApp orders

    def start_whatsapp(self) -> None:
        """Begin fetching WhatsApp orders in the background (does nothing while switched off)."""
        self.whatsapp.start()
        self.update_online_orders_badge()

    def stop_whatsapp(self) -> None:
        """Stop the background fetching before the application closes."""
        self.beep_timer.stop()
        self.whatsapp.stop()

    def open_online_orders(self) -> None:
        """Open the Online Orders screen."""
        if not self.confirm_leave_billing():
            return
        self.online_orders_window.refresh()
        self.show_page(self.online_orders_window)
        self.sync_navigation()

    def show_online_orders_for_new(self) -> None:
        """Bring CafePOS to the front on the Online Orders screen (from the pop-up)."""
        self.raise_()
        self.activateWindow()
        self.open_online_orders()

    def make_bill_for_online_order(self, order_id: int) -> None:
        """Open Billing with a WhatsApp order's items already in the cart."""
        if self.billing_window.has_active_cart():
            discard = QMessageBox.question(
                self,
                "CafePOS",
                "Discard current order?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if discard != QMessageBox.StandardButton.Yes:
                return
        note = self.billing_window.start_online_order(order_id)
        self.show_page(self.billing_window)
        self.sync_navigation()
        if note:
            QMessageBox.information(self, "Online order", note)

    def on_online_order_billed(self) -> None:
        """Return to the online orders list once a WhatsApp order has been billed."""
        self.update_online_orders_badge()
        self.open_online_orders()

    def on_new_online_order(self, order_id: int) -> None:
        """Announce a new WhatsApp order: pop-up, taskbar flash and a beep."""
        try:
            with session_scope() as session:
                order = session.get(OnlineOrder, order_id)
                summary = ""
                if order is not None:
                    text = " ".join(order.message_text.split())
                    text = text if len(text) <= 90 else text[:87] + "..."
                    summary = (
                        f"{online_orders.order_number(order)} from "
                        f"{order.customer_name or online_orders.display_phone(order.customer_phone)}\n{text}"
                    )
        except Exception:
            summary = "A customer sent an order."
        self.update_online_orders_badge()
        self.new_order_toast.announce(summary)
        QApplication.alert(self, 0)
        QApplication.beep()

    def update_online_orders_badge(self) -> None:
        """Show or hide the Online Orders button and how many orders are waiting."""
        enabled = bool(get_whatsapp_settings()["enabled"])
        self.online_orders_button.setVisible(enabled)
        self.sidebar_whatsapp_label.setVisible(enabled)
        try:
            with session_scope() as session:
                waiting = online_orders.count_new(session)
        except Exception:
            waiting = 0
        self.online_orders_button.setText(f"  Online Orders ({waiting})" if waiting else "  Online Orders")
        if enabled and waiting:
            if not self.beep_timer.isActive():
                self.beep_timer.start()
        else:
            self.beep_timer.stop()

    def beep_for_new_orders(self) -> None:
        """Keep beeping every few seconds until every new order has been accepted or rejected."""
        try:
            with session_scope() as session:
                waiting = online_orders.count_new(session)
        except Exception:
            waiting = 0
        if waiting:
            QApplication.beep()
        else:
            self.beep_timer.stop()

    def update_whatsapp_status(self, state: str) -> None:
        """Show whether the WhatsApp connection is working in the sidebar."""
        short = state if len(state) <= 30 else state[:27] + "..."
        self.sidebar_whatsapp_label.setText(f"WhatsApp: {short}")
        self.sidebar_whatsapp_label.setToolTip(state)

    # -------------------------------------------------------------------- data

    def update_clock(self) -> None:
        """Refresh the greeting and the date/time shown in the header."""
        now = datetime.now()
        self.header_greeting.setText(f"{greeting_for(now.hour)}, here is today's overview")
        self.header_datetime.setText(
            f"{now:%A}, {now.day} {now:%B %Y}  ·  {now.hour % 12 or 12}:{now:%M} {now:%p}"
        )

    def refresh_dashboard_data(self) -> None:
        """Refresh summary metrics, header info, and system status."""
        config = load_configuration()
        cafe_name = str(config.get("cafe_name") or "CafePOS")
        self.header_cafe_name.setText(cafe_name)
        metrics = QFontMetrics(self.brand_name_label.font())
        self.brand_name_label.setText(
            metrics.elidedText(cafe_name, Qt.TextElideMode.ElideRight, SIDEBAR_WIDTH - 100)
        )
        self.brand_name_label.setToolTip(cafe_name)
        self.update_clock()

        today = date.today()
        recent_orders: list[tuple[int, str, str, str, str, float, bool]] = []
        best_seller: str | None = None
        try:
            with session_scope() as session:
                summary = get_report_summary(session, today, today)
                items = get_menu_items(session)
                orders = get_orders_for_period(session, today, today)[:RECENT_ORDER_LIMIT]
                orders_count = summary.order_count
                revenue = summary.total_revenue
                best_seller = summary.most_sold_item
                menu_count = len(items)
                avg_bill = (revenue / orders_count) if orders_count > 0 else 0.0
                recent_orders = [
                    (
                        order.id,
                        str(order.bill_number),
                        order.order_time,
                        order.service_type,
                        order.payment_mode,
                        order.total,
                        bool(order.is_void),
                    )
                    for order in orders
                ]
        except Exception:
            orders_count = 0
            revenue = 0.0
            menu_count = 0
            avg_bill = 0.0

        self.orders_count_val.setText(str(orders_count))
        self.revenue_card.set_value(f"₹{revenue:.2f}")
        self.menu_count_val.setText(str(menu_count))
        self.avg_bill_val.setText(f"₹{avg_bill:.2f}")
        self.best_seller_label.setText(best_seller or "No sales yet")
        self.populate_recent_orders(recent_orders)

        printer = get_default_printer() or "Not Configured"
        self.status_printer_label.setText(printer)
        self.sidebar_printer_label.setText(f"Printer: {printer}")
        self.update_online_orders_badge()
        self.update_whatsapp_status(self.whatsapp.connection)

    def populate_recent_orders(self, orders: list[tuple[int, str, str, str, str, float, bool]]) -> None:
        """Fill the recent-orders table, marking voided bills in red."""
        self.recent_orders_table.setRowCount(len(orders))
        for row, (order_id, bill_number, order_time, service_type, payment_mode, total, is_void) in enumerate(orders):
            values = (
                f"#{bill_number}" + ("  (VOIDED)" if is_void else ""),
                format_order_time(order_time),
                service_type,
                payment_mode,
                f"₹{total:.2f}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, order_id)
                if column == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if is_void:
                    item.setForeground(QColor(Color.DANGER))
                self.recent_orders_table.setItem(row, column, item)

        self.recent_orders_table.setVisible(bool(orders))
        self.recent_orders_empty.setVisible(not orders)

    def showEvent(self, event: object) -> None:
        """Refresh metrics whenever the dashboard becomes visible."""
        super().showEvent(event)
        self.refresh_dashboard_data()
