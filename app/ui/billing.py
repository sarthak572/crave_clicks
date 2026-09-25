"""Billing window for creating completed cafe orders."""

from collections.abc import Callable

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.database import session_scope
from app.dialogs.discount_dialog import DiscountDialog
from app.models import OnlineOrder
from app.services import online_orders
from app.services.configuration import get_gst_rate, get_whatsapp_settings
from app.services.printing import ReceiptPrintError, format_round_off, print_receipt
from app.services import (
    CartLine,
    Discount,
    calculate_bill_totals,
    get_categories,
    get_menu_items,
    save_order,
    validate_payment,
)
from app.ui.item_grid import DIET_ROLE, PRICE_ROLE, QUANTITY_ROLE, ItemGridView, diet_type, wrap_lines
from app.ui.theme import Color, dot_pixmap, icon
from app.ui.widgets import (
    AutoSelectDoubleSpinBox,
    PageHeader,
    SegmentedControl,
    make_button,
    make_card,
    make_divider,
    make_empty_state,
)


# Width reserved for an item's name in the cart; the stepper, note button and total take the rest.
CART_NAME_WIDTH = 136


class BillingWindow(QWidget):
    """Build and complete one in-memory cafe order at a time."""

    online_order_billed = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.online_order_id: int | None = None
        self.cart: dict[int, CartLine] = {}
        self.discount: Discount | None = None
        self.menu_items: dict[int, object] = {}
        self._open_notes: set[int] = set()
        self._back_callback: Callable[[], None] | None = None

        self.setObjectName("page")
        self.setWindowTitle("New Order")
        self.resize(1100, 700)
        self.setMinimumSize(820, 520)

        header = PageHeader("New Order")
        self.back_button = header.back_button
        self.back_button.clicked.connect(self.go_back)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Search menu items")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(300)
        self.search_input.addAction(icon("search", Color.TEXT_FAINT), QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(self.load_menu)
        header.add_action(self.search_input)

        self.categories_list = QListWidget()
        self.categories_list.setObjectName("categoryList")
        self.categories_list.setIconSize(QSize(10, 10))
        self.categories_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.categories_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.categories_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.categories_list.setWordWrap(False)
        self.categories_list.currentTextChanged.connect(self.refresh_item_list)

        self.items_list = ItemGridView()
        self.items_list.itemClicked.connect(self.add_menu_item)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 18, 28, 20)
        layout.setSpacing(14)
        layout.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self.create_categories_panel())
        body.addWidget(self.create_menu_panel(), 1)
        body.addWidget(self.create_cart_panel())
        layout.addLayout(body, 1)

        self.load_menu()
        self.refresh_cart()

    def set_back_callback(self, callback: Callable[[], None]) -> None:
        """Set the navigation action for the screen's Back button."""
        self._back_callback = callback

    def go_back(self) -> None:
        """Return to the dashboard through the application navigation shell."""
        if self._back_callback is not None:
            self._back_callback()

    def create_categories_panel(self) -> QWidget:
        """Create the category rail on the left."""
        panel = QWidget()
        panel.setFixedWidth(232)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        caption = QLabel("CATEGORIES")
        caption.setObjectName("sectionLabel")
        layout.addWidget(caption)
        layout.addWidget(self.categories_list, 1)
        return panel

    def create_menu_panel(self) -> QWidget:
        """Create the central menu item panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.items_title = QLabel("Items")
        self.items_title.setObjectName("cardTitle")
        self.items_count_chip = QLabel()
        self.items_count_chip.setObjectName("chip")
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(self.items_title)
        title_row.addWidget(self.items_count_chip)
        title_row.addStretch()
        layout.addLayout(title_row)

        self.items_empty_state = make_empty_state(
            "search", "No items found", "Try a different search or pick another category."
        )
        layout.addWidget(self.items_list, 1)
        layout.addWidget(self.items_empty_state, 1)
        return panel

    def create_cart_panel(self) -> QWidget:
        """Create the order ticket: cart lines, totals, payment and the Done button."""
        panel = make_card()
        panel.setFixedWidth(380)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel("Current Order")
        title.setObjectName("cardTitle")
        self.cart_count_chip = QLabel()
        self.cart_count_chip.setObjectName("chip")
        title_row = QHBoxLayout()
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.cart_count_chip)
        layout.addLayout(title_row)

        self.online_banner = QLabel()
        self.online_banner.setObjectName("statusPill")
        self.online_banner.setWordWrap(True)
        self.online_banner.hide()
        layout.addWidget(self.online_banner)

        self.service_type_input = SegmentedControl([("Dine In", None), ("Takeaway", None), ("Delivery", None)])
        layout.addWidget(self.service_type_input)

        self.customer_phone_input = QLineEdit()
        self.customer_phone_input.setObjectName("compactInput")
        self.customer_phone_input.setPlaceholderText("Customer phone (optional)")
        layout.addWidget(self.customer_phone_input)

        self.cart_content = QWidget()
        self.cart_layout = QVBoxLayout(self.cart_content)
        self.cart_layout.setContentsMargins(0, 0, 4, 0)
        self.cart_layout.setSpacing(0)

        self.cart_scroll = QScrollArea()
        self.cart_scroll.setWidgetResizable(True)
        self.cart_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cart_scroll.setWidget(self.cart_content)
        layout.addWidget(self.cart_scroll, 1)
        layout.addWidget(make_divider())

        self.subtotal_label = QLabel()
        self.discount_label = QLabel()
        self.cgst_title = QLabel()
        self.cgst_label = QLabel()
        self.sgst_title = QLabel()
        self.sgst_label = QLabel()
        self.round_off_title = QLabel("Round off")
        self.round_off_label = QLabel()
        self.total_label = QLabel()
        self.total_label.setObjectName("totalLabel")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.discount_button = make_button("Add", "ghost", "tag")
        self.discount_button.setIconSize(QSize(16, 16))
        self.discount_button.setObjectName("linkButton")
        self.discount_button.clicked.connect(self.open_discount_dialog)

        discount_title = QLabel("Discount")
        discount_title.setObjectName("muted")
        discount_cell = QHBoxLayout()
        discount_cell.setContentsMargins(0, 0, 0, 0)
        discount_cell.setSpacing(6)
        discount_cell.addWidget(discount_title)
        discount_cell.addWidget(self.discount_button)
        discount_cell.addStretch()

        subtotal_title = QLabel("Subtotal")
        summary = QGridLayout()
        summary.setContentsMargins(0, 0, 0, 0)
        summary.setHorizontalSpacing(8)
        summary.setVerticalSpacing(4)
        summary.setColumnStretch(0, 1)
        rows = (
            (subtotal_title, self.subtotal_label),
            (discount_cell, self.discount_label),
            (self.cgst_title, self.cgst_label),
            (self.sgst_title, self.sgst_label),
            (self.round_off_title, self.round_off_label),
        )
        for row, (title_item, value_label) in enumerate(rows):
            if isinstance(title_item, QLabel):
                title_item.setObjectName("muted")
                summary.addWidget(title_item, row, 0)
            else:
                summary.addLayout(title_item, row, 0)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            summary.addWidget(value_label, row, 1)
        layout.addLayout(summary)

        total_caption = QLabel("Total")
        total_caption.setObjectName("totalCaption")
        total_row = QHBoxLayout()
        total_row.addWidget(total_caption)
        total_row.addStretch()
        total_row.addWidget(self.total_label)
        layout.addLayout(total_row)

        self.payment_control = SegmentedControl([("Cash", "cash"), ("UPI", "phone"), ("Split", "split")])
        self.cash_radio, self.upi_radio, self.split_radio = self.payment_control.buttons()
        for button in (self.cash_radio, self.upi_radio, self.split_radio):
            button.toggled.connect(self.update_payment_controls)

        self.split_cash_input = self.amount_input()
        self.split_upi_input = self.amount_input()
        self.split_form = QWidget()
        split_layout = QHBoxLayout(self.split_form)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(10)
        for caption_text, amount_field in (("Cash amount", self.split_cash_input), ("UPI amount", self.split_upi_input)):
            column = QVBoxLayout()
            column.setSpacing(4)
            caption = QLabel(caption_text)
            caption.setObjectName("sectionLabel")
            column.addWidget(caption)
            column.addWidget(amount_field)
            split_layout.addLayout(column, 1)

        layout.addWidget(self.payment_control)
        layout.addWidget(self.split_form)

        self.done_button = make_button("Complete Order", "success", "check")
        self.done_button.setIconSize(QSize(20, 20))
        self.done_button.clicked.connect(self.complete_order)
        layout.addWidget(self.done_button)

        return panel

    @staticmethod
    def amount_input() -> QDoubleSpinBox:
        """Create a two-decimal payment amount input."""
        amount_input = AutoSelectDoubleSpinBox()
        amount_input.setDecimals(2)
        amount_input.setMaximum(999_999.99)
        amount_input.setSpecialValueText(" ")
        return amount_input

    def load_menu(self) -> None:
        """Load menu data and refresh the category and item lists."""
        selected_category = self.categories_list.currentItem()
        selected_category_name = selected_category.text() if selected_category else ""

        with session_scope() as session:
            categories = get_categories(session)
            items = get_menu_items(session, self.search_input.text().strip())

        self.menu_items = {item.id: item for item in items}
        self.categories_list.blockSignals(True)
        self.categories_list.clear()
        for category in categories:
            category_item = QListWidgetItem(category)
            marker = {"veg": Color.VEG, "nonveg": Color.NON_VEG}.get(diet_type(category))
            category_item.setIcon(QIcon(dot_pixmap(marker)))
            category_item.setSizeHint(QSize(0, 44))
            self.categories_list.addItem(category_item)
        if categories:
            matching_items = self.categories_list.findItems(selected_category_name, Qt.MatchFlag.MatchExactly)
            self.categories_list.setCurrentItem(matching_items[0] if matching_items else self.categories_list.item(0))
        self.categories_list.blockSignals(False)
        self.refresh_item_list()

    def refresh_item_list(self) -> None:
        """Show items for the selected category or the current name search."""
        selected_category = self.categories_list.currentItem()
        category_name = selected_category.text() if selected_category else ""
        search_text = self.search_input.text().strip()
        show_all_matching_items = bool(search_text)

        self.items_list.clear()
        for menu_item in self.menu_items.values():
            if not show_all_matching_items and menu_item.category != category_name:
                continue

            item = QListWidgetItem(menu_item.name)
            item.setData(Qt.ItemDataRole.UserRole, menu_item.id)
            item.setData(PRICE_ROLE, f"₹{menu_item.price:.2f}")
            item.setData(DIET_ROLE, diet_type(menu_item.category))
            item.setData(QUANTITY_ROLE, self.cart[menu_item.id].quantity if menu_item.id in self.cart else 0)
            self.items_list.addItem(item)

        count = self.items_list.count()
        self.items_title.setText(f"Results for “{search_text}”" if show_all_matching_items else (category_name or "Items"))
        self.items_count_chip.setText(f"{count} item" if count == 1 else f"{count} items")
        self.items_list.setVisible(count > 0)
        self.items_empty_state.setVisible(count == 0)

    def add_menu_item(self, item: QListWidgetItem) -> None:
        """Add a clicked item to the cart unless it is already present."""
        menu_item_id = item.data(Qt.ItemDataRole.UserRole)
        if menu_item_id in self.cart:
            return

        menu_item = self.menu_items[menu_item_id]
        self.cart[menu_item_id] = CartLine(
            menu_item_id=menu_item.id,
            item_name=menu_item.name,
            unit_price=menu_item.price,
        )
        self.refresh_cart(scroll_to_bottom=True)

    def change_quantity(self, menu_item_id: int, amount: int) -> None:
        """Change a cart line quantity and remove it when it reaches zero."""
        line = self.cart.get(menu_item_id)
        if line is None:
            return

        line.quantity += amount
        if line.quantity <= 0:
            del self.cart[menu_item_id]
            if self.discount and self.discount.menu_item_id == menu_item_id:
                self.discount = None

        self.refresh_cart()

    def create_cart_row(self, line: CartLine) -> QWidget:
        """Create one compact cart line: name, quantity stepper and total, with the note tucked away."""
        item_id = line.menu_item_id
        row = QFrame()
        row.setObjectName("cartLine")
        row.setToolTip(f"₹{line.unit_price:.2f} each")
        # "Minimum" stops the cart layout from squashing rows below their natural height; overflow scrolls.
        row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 8, 0, 8)
        row_layout.setSpacing(6)

        # Qt's own word wrap puts the whole cart into height-for-width mode, and the scroll area then
        # squashes the rows together instead of scrolling. Wrap the name ourselves so every row has a
        # plain, fixed size.
        name_label = QLabel()
        name_label.setObjectName("lineName")
        name_label.ensurePolished()
        name_lines = wrap_lines(line.item_name, name_label.font(), CART_NAME_WIDTH, max_lines=3)
        name_label.setText("\n".join(name_lines))
        name_label.setFixedSize(CART_NAME_WIDTH, name_label.fontMetrics().lineSpacing() * len(name_lines) + 2)

        decrease_button = QPushButton()
        decrease_button.setObjectName("qtyButton")
        decrease_button.setIcon(icon("minus", Color.TEXT, size=16))
        decrease_button.setIconSize(QSize(16, 16))
        decrease_button.setFixedSize(30, 30)
        decrease_button.setCursor(Qt.CursorShape.PointingHandCursor)
        decrease_button.clicked.connect(lambda _checked=False: self.change_quantity(item_id, -1))
        quantity_label = QLabel(str(line.quantity))
        quantity_label.setObjectName("qtyValue")
        quantity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        increase_button = QPushButton()
        increase_button.setObjectName("qtyButton")
        increase_button.setIcon(icon("plus", Color.TEXT, size=16))
        increase_button.setIconSize(QSize(16, 16))
        increase_button.setFixedSize(30, 30)
        increase_button.setCursor(Qt.CursorShape.PointingHandCursor)
        increase_button.clicked.connect(lambda _checked=False: self.change_quantity(item_id, 1))

        note_input = QLineEdit(line.note or "")
        note_input.setObjectName("noteInput")
        note_input.setPlaceholderText("Internal note")
        note_input.textChanged.connect(lambda note: self.set_note(item_id, note))
        note_input.setVisible(bool(line.note) or item_id in self._open_notes)

        note_button = QPushButton()
        note_button.setObjectName("noteToggle")
        note_button.setCheckable(True)
        note_button.setChecked(note_input.isVisible())
        note_button.setToolTip("Add an internal note")
        note_button.setIcon(icon("edit", Color.TEXT_FAINT, Color.ACCENT, size=16))
        note_button.setIconSize(QSize(16, 16))
        note_button.setFixedSize(30, 30)
        note_button.setCursor(Qt.CursorShape.PointingHandCursor)
        note_button.toggled.connect(lambda shown: self.toggle_note(item_id, note_input, shown))

        total = QLabel(f"₹{line.unit_price * line.quantity:.2f}")
        total.setObjectName("lineTotal")
        total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total.setMinimumWidth(58)

        main_row = QHBoxLayout()
        main_row.setSpacing(4)
        main_row.addWidget(name_label, 1)
        main_row.addWidget(decrease_button)
        main_row.addWidget(quantity_label)
        main_row.addWidget(increase_button)
        main_row.addWidget(note_button)
        main_row.addWidget(total)

        row_layout.addLayout(main_row)
        row_layout.addWidget(note_input)
        return row

    def toggle_note(self, menu_item_id: int, note_input: QLineEdit, shown: bool) -> None:
        """Show or hide a cart line's note field, remembering the choice across cart refreshes."""
        note_input.setVisible(shown)
        self.cart_layout.invalidate()
        self.cart_layout.activate()
        if shown:
            self._open_notes.add(menu_item_id)
            note_input.setFocus()
        else:
            self._open_notes.discard(menu_item_id)

    def refresh_cart(self, scroll_to_bottom: bool = False) -> None:
        """Render the current cart, totals, and checkout state."""
        while self.cart_layout.count():
            widget = self.cart_layout.takeAt(0).widget()
            if widget is not None:
                # Detach now so the old rows disappear immediately instead of on the next event-loop pass.
                widget.setParent(None)
                widget.deleteLater()

        if self.cart:
            for line in sorted(self.cart.values(), key=lambda cart_line: cart_line.item_name.lower()):
                row = self.create_cart_row(line)
                self.cart_layout.addWidget(row)
                row.show()
            self.cart_layout.addStretch()
        else:
            empty_state = make_empty_state("cart", "No items yet", "Tap a menu item to add it to this order.")
            self.cart_layout.addWidget(empty_state)
            empty_state.show()
        # Widgets added to an already-visible parent stay hidden until a queued event shows them, and a
        # layout ignores hidden widgets. Showing the rows here and re-laying out now lets the scroll area
        # see the real height straight away; otherwise it squashes the rows instead of scrolling.
        self.cart_content.ensurePolished()
        self.cart_layout.invalidate()
        self.cart_layout.activate()

        gst_rate = get_gst_rate()
        if self.cart:
            bill = calculate_bill_totals(list(self.cart.values()), self.discount, gst_rate)
            subtotal, discount_amount, cgst, sgst, total, round_off = (
                bill.subtotal, bill.discount_amount, bill.cgst, bill.sgst, bill.total, bill.round_off
            )
        else:
            subtotal = discount_amount = cgst = sgst = total = round_off = 0.0

        self.subtotal_label.setText(f"₹{subtotal:.2f}")
        self.discount_label.setText(f"−₹{discount_amount:.2f}" if discount_amount else f"₹{discount_amount:.2f}")
        half_rate = f"{gst_rate / 2:g}%"
        self.cgst_title.setText(f"CGST @ {half_rate}")
        self.sgst_title.setText(f"SGST @ {half_rate}")
        self.cgst_label.setText(f"₹{cgst:.2f}")
        self.sgst_label.setText(f"₹{sgst:.2f}")
        for gst_widget in (self.cgst_title, self.cgst_label, self.sgst_title, self.sgst_label):
            gst_widget.setVisible(gst_rate > 0)
        self.round_off_label.setText(format_round_off(round_off) if round_off else "")
        for round_off_widget in (self.round_off_title, self.round_off_label):
            round_off_widget.setVisible(bool(round_off))
        self.total_label.setText(f"₹{total:.2f}")
        self.discount_button.setText("Add" if self.discount is None else "Edit")
        self.discount_button.setEnabled(bool(self.cart))
        self.done_button.setText(f"Complete Order  ·  ₹{total:.2f}" if self.cart else "Complete Order")
        self.done_button.setEnabled(bool(self.cart))
        quantity = sum(line.quantity for line in self.cart.values())
        self.cart_count_chip.setText(f"{quantity} item" if quantity == 1 else f"{quantity} items")
        self.sync_item_quantities()
        self.update_payment_controls()

        if scroll_to_bottom:
            QTimer.singleShot(
                0,
                lambda: self.cart_scroll.verticalScrollBar().setValue(
                    self.cart_scroll.verticalScrollBar().maximum()
                ),
            )

    def sync_item_quantities(self) -> None:
        """Show each menu card's in-cart quantity so the cashier can see what is already added."""
        for index in range(self.items_list.count()):
            item = self.items_list.item(index)
            line = self.cart.get(item.data(Qt.ItemDataRole.UserRole))
            item.setData(QUANTITY_ROLE, line.quantity if line else 0)
        self.items_list.viewport().update()

    def open_discount_dialog(self) -> None:
        """Open the discount dialog for the current cart."""
        if not self.cart:
            return

        dialog = DiscountDialog(list(self.cart.values()), self.discount, self)
        if dialog.exec():
            self.discount = dialog.discount
            self.refresh_cart()

    def update_payment_controls(self) -> None:
        """Show split inputs only when Split Payment is selected."""
        self.split_form.setVisible(self.split_radio.isChecked())

    def payment_details(self) -> tuple[str, dict[str, float] | None]:
        """Return the selected payment mode and any split amounts."""
        if self.split_radio.isChecked():
            return "Split", {
                "Cash": self.split_cash_input.value(),
                "UPI": self.split_upi_input.value(),
            }
        if self.upi_radio.isChecked():
            return "UPI", None
        return "Cash", None

    def complete_order(self) -> None:
        """Validate, confirm, save, and clear the current order."""
        lines = list(self.cart.values())
        payment_mode, split_payments = self.payment_details()
        gst_rate = get_gst_rate()
        customer_phone = self.customer_phone()
        if customer_phone is None:
            QMessageBox.warning(self, "Customer phone", "The customer's phone number looks incomplete.")
            return
        try:
            total = calculate_bill_totals(lines, self.discount, gst_rate).total
            validate_payment(payment_mode, total, split_payments)
        except ValueError as error:
            title = "Payment mismatch" if str(error) == "Payment mismatch." else "Invalid discount"
            QMessageBox.warning(self, title, str(error))
            return

        confirmed = QMessageBox.question(
            self,
            "CafePOS",
            "Complete Order?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        with session_scope() as session:
            order = save_order(
                session,
                lines,
                self.discount,
                payment_mode,
                split_payments,
                service_type=self.service_type_input.currentText(),
                gst_rate=gst_rate,
                source="WhatsApp" if self.online_order_id else "Counter",
                customer_phone=customer_phone or None,
            )
            if self.online_order_id:
                online_orders.mark_billed(session, self.online_order_id, order.id)
        billed_online_order = self.online_order_id is not None

        should_print = QMessageBox.question(
            self,
            "CafePOS",
            "Print receipt?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if should_print == QMessageBox.StandardButton.Yes:
            self.print_completed_order(order.id)
            
        if billed_online_order and customer_phone:
            should_send = QMessageBox.question(
                self,
                "CafePOS",
                "Send bill to customer via WhatsApp?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if should_send == QMessageBox.StandardButton.Yes:
                from app.services.whatsapp import send_local_message
                text = f"Your bill is ready! Total amount: ₹{total:.2f}. Thank you for your order."
                try:
                    send_local_message(customer_phone, text)
                    QMessageBox.information(self, "CafePOS", "Bill sent via WhatsApp!")
                except Exception as e:
                    QMessageBox.warning(self, "CafePOS", f"Failed to send bill: {e}")
                    
        self.reset_order()
        if billed_online_order:
            self.online_order_billed.emit()

    def print_completed_order(self, order_id: int) -> None:
        """Print a saved order while keeping it available if printing fails."""
        try:
            printed = print_receipt(order_id, self)
        except ReceiptPrintError:
            QMessageBox.warning(self, "CafePOS", "Receipt could not be printed.")
            return

        if printed:
            QMessageBox.information(self, "CafePOS", "Bill Printed")

    def customer_phone(self) -> str | None:
        """The typed phone number with country code, "" when blank, None when incomplete."""
        digits = "".join(ch for ch in self.customer_phone_input.text() if ch.isdigit())
        if not digits:
            return ""
        if len(digits) < 10:
            return None
        return online_orders.normalize_phone(digits, str(get_whatsapp_settings()["country_code"]))

    def start_online_order(self, online_order_id: int) -> str:
        """Fill the cart from a WhatsApp order. Returns a note when items could not be matched."""
        with session_scope() as session:
            order = session.get(OnlineOrder, online_order_id)
            if order is None:
                return "That order no longer exists."
            wanted = online_orders.cart_items(order)
            phone = order.customer_phone
            label = f"WhatsApp order {online_orders.order_number(order)} · {online_orders.display_phone(phone)}"
            menu = {item.id: item for item in get_menu_items(session)}

        self.reset_order()
        unmatched = 0
        for entry in wanted:
            try:
                item_id = int(entry.get("id"))
            except (TypeError, ValueError):
                unmatched += 1
                continue
            menu_item = menu.get(item_id)
            if menu_item is None:
                unmatched += 1
                continue
            self.cart[menu_item.id] = CartLine(
                menu_item_id=menu_item.id,
                item_name=menu_item.name,
                unit_price=menu_item.price,
                quantity=max(1, int(entry.get("qty") or 1)),
            )

        self.online_order_id = online_order_id
        self.customer_phone_input.setText(phone)
        self.online_banner.setText(label)
        self.online_banner.show()
        self.refresh_cart()

        if not wanted:
            return "Add the items from the customer's message, then press Complete Order."
        if unmatched:
            return f"{unmatched} item(s) in the order could not be matched to your menu. Please add them by hand."
        return ""

    def has_active_cart(self) -> bool:
        """Return whether the current unfinished order contains any items."""
        return bool(self.cart)

    def reset_order(self) -> None:
        """Discard the in-memory cart and return to a new empty order."""
        self.cart.clear()
        self._open_notes.clear()
        self.discount = None
        self.online_order_id = None
        self.online_banner.hide()
        self.customer_phone_input.clear()
        self.service_type_input.setCurrentIndex(0)
        self.cash_radio.setChecked(True)
        self.split_cash_input.setValue(0)
        self.split_upi_input.setValue(0)
        self.refresh_cart()

    def set_note(self, menu_item_id: int, note: str) -> None:
        """Store a cart line's internal note for the completed order snapshot."""
        line = self.cart.get(menu_item_id)
        if line is not None:
            line.note = note.strip() or None

    def showEvent(self, event: object) -> None:
        """Refresh menu availability whenever the billing window is shown."""
        super().showEvent(event)
        self.load_menu()
