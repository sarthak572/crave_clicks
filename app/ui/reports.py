"""Reports window for completed cafe orders."""

from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.database import session_scope
from app.dialogs import OrderDetailsDialog
from app.models import Order
from app.services import ReportSummary, get_orders_for_period, get_report_summary
from app.services.excel_export import export_report_to_xlsx
from app.ui.theme import Color
from app.ui.widgets import PageHeader, StatCard, make_button, make_empty_state


class ReportTab(QWidget):
    """A single reporting-period view with summary values and an order table."""

    def __init__(self, empty_message: str = "No orders today.") -> None:
        super().__init__()

        orders_card = StatCard("Orders", "receipt")
        revenue_card = StatCard("Revenue", "rupee")
        most_sold_card = StatCard("Most Sold Item", "star", text_value=True)
        self.order_count_label = orders_card.value_label
        self.revenue_label = revenue_card.value_label
        self.most_sold_item_label = most_sold_card.value_label
        summary_row = QHBoxLayout()
        summary_row.setSpacing(16)
        for card in (orders_card, revenue_card, most_sold_card):
            summary_row.addWidget(card, 1)

        self.empty_state = make_empty_state("inbox", empty_message, "Completed bills will appear here.")

        self.orders_table = QTableWidget(0, 4)
        self.orders_table.setHorizontalHeaderLabels(
            ["Bill Number", "Order Value", "Time", "Payment Method"]
        )
        self.orders_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.orders_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.orders_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.orders_table.setShowGrid(False)
        self.orders_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.orders_table.verticalHeader().setVisible(False)
        self.orders_table.verticalHeader().setDefaultSectionSize(48)
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.orders_table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(16)
        layout.addLayout(summary_row)
        layout.addWidget(self.empty_state, 1)
        layout.addWidget(self.orders_table, 1)


class ReportsWindow(QWidget):
    """Display today, current-week, and current-month completed-order reports."""

    def __init__(self) -> None:
        super().__init__()

        self._back_callback: Callable[[], None] | None = None

        self.setObjectName("page")
        self.setWindowTitle("Reports")
        self.resize(820, 560)
        self.setMinimumSize(620, 400)

        header = PageHeader("Reports", "Sales summaries and order history")
        self.back_button = header.back_button
        self.back_button.clicked.connect(self.go_back)
        self.export_button = make_button("Export Excel", None, "download")
        self.export_button.clicked.connect(self.export_current_report)
        header.add_action(self.export_button)

        self.tabs = QTabWidget()
        self.report_tabs = {
            "Today": ReportTab("No orders today."),
            "Weekly": ReportTab("No orders this week."),
            "Monthly": ReportTab("No orders this month."),
        }
        for title, report_tab in self.report_tabs.items():
            self.tabs.addTab(report_tab, title)
            report_tab.orders_table.cellDoubleClicked.connect(
                lambda row, _column, tab=report_tab: self.open_order_details(tab, row)
            )

        self.tabs.currentChanged.connect(self.refresh_current_tab)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(header)
        layout.addWidget(self.tabs, 1)
        self.refresh_reports()

    def set_back_callback(self, callback: Callable[[], None]) -> None:
        """Set the navigation action for the screen's Back button."""
        self._back_callback = callback

    def go_back(self) -> None:
        """Return to the dashboard through the application navigation shell."""
        if self._back_callback is not None:
            self._back_callback()

    def refresh_reports(self) -> None:
        """Refresh all period summaries and tables from the local database."""
        for title, report_tab in self.report_tabs.items():
            self._load_tab(title, report_tab)

    def refresh_current_tab(self) -> None:
        """Refresh the selected period when its tab becomes active."""
        title = self.tabs.tabText(self.tabs.currentIndex())
        self._load_tab(title, self.report_tabs[title])

    def _load_tab(self, title: str, report_tab: ReportTab) -> None:
        """Load one period's summary and display every order, including voided ones."""
        start_date, end_date = self.period_dates(title)
        with session_scope() as session:
            summary = get_report_summary(session, start_date, end_date)
            orders = get_orders_for_period(session, start_date, end_date)

        self._populate_summary(report_tab, summary)
        self._populate_orders(report_tab, orders)

    @staticmethod
    def period_dates(title: str, today: date | None = None) -> tuple[date, date]:
        """Return the current calendar period represented by a report tab."""
        today = today or date.today()
        if title == "Today":
            return today, today
        if title == "Weekly":
            return today - timedelta(days=today.weekday()), today
        if title == "Monthly":
            return today.replace(day=1), today
        raise ValueError(f"Unknown report period: {title}")

    @staticmethod
    def _populate_summary(report_tab: ReportTab, summary: ReportSummary) -> None:
        report_tab.order_count_label.setText(str(summary.order_count))
        report_tab.revenue_label.setText(f"₹{summary.total_revenue:.2f}")
        report_tab.most_sold_item_label.setText(summary.most_sold_item or "No sales")

    @staticmethod
    def _populate_orders(report_tab: ReportTab, orders: list[Order]) -> None:
        report_tab.orders_table.setRowCount(len(orders))
        for row, order in enumerate(orders):
            bill_number = str(order.bill_number)
            if order.is_void:
                bill_number = f"{bill_number} (VOIDED)"

            values = (
                bill_number,
                f"₹{order.total:.2f}",
                order.order_time,
                order.payment_mode,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if order.is_void:
                    item.setForeground(QColor(Color.DANGER))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, order.id)
                report_tab.orders_table.setItem(row, column, item)

        report_tab.orders_table.setVisible(bool(orders))
        report_tab.empty_state.setVisible(not orders)

    def open_order_details(self, report_tab: ReportTab, row: int) -> None:
        """Open the clicked order's immutable historical details."""
        bill_number_item = report_tab.orders_table.item(row, 0)
        if bill_number_item is None:
            return

        order_id = bill_number_item.data(Qt.ItemDataRole.UserRole)
        dialog = OrderDetailsDialog(order_id, self.refresh_reports, self)
        dialog.exec()

    def export_current_report(self) -> None:
        """Export the active report period to an Excel workbook."""
        from app.services.configuration import get_reports_folder
        
        title = self.tabs.tabText(self.tabs.currentIndex())
        start_date, end_date = self.period_dates(title)
        
        reports_dir = get_reports_folder()
        reports_dir.mkdir(parents=True, exist_ok=True)
        filename = str(reports_dir / f"CafePOS_Report_{date.today().isoformat()}.xlsx")
        
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            filename,
            "Excel Workbook (*.xlsx)",
        )
        if not destination:
            return
        if not destination.lower().endswith(".xlsx"):
            destination = f"{destination}.xlsx"

        try:
            with session_scope() as session:
                summary = get_report_summary(session, start_date, end_date)
                orders = get_orders_for_period(session, start_date, end_date)
                export_report_to_xlsx(
                    Path(destination),
                    f"CafePOS {title} Report",
                    start_date,
                    end_date,
                    summary,
                    orders,
                )
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "CafePOS", f"Report could not be exported.\n{error}")
            return

        QMessageBox.information(self, "CafePOS", "Export Successful")

    def showEvent(self, event: object) -> None:
        """Ensure reports are current whenever the window is shown."""
        super().showEvent(event)
        self.refresh_reports()
