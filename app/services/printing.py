"""Receipt rendering, printer selection, and local printer preference storage."""

from html import escape

from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo
from PySide6.QtWidgets import QWidget

from app.database import session_scope
from app.models import Order
from app.services import configuration
from app.services.reports import get_order


# Kept as a module-level alias so callers and integration checks can target a
# temporary configuration file without affecting the application's real one.
CONFIG_PATH = configuration.CONFIG_PATH


class ReceiptPrintError(RuntimeError):
    """Raised when a saved receipt cannot be sent to a printer."""


def print_receipt(order_id: int, parent: QWidget | None = None) -> bool:
    """Print a completed order, returning False only when printer selection is cancelled."""
    receipt_html = receipt_html_for_order_id(order_id)
    printer = select_printer(parent)
    if printer is None:
        return False

    try:
        if hasattr(printer, "isValid") and not printer.isValid():
            raise ReceiptPrintError("Receipt printer is unavailable.")
        document = QTextDocument()
        document.setDocumentMargin(10)
        document.setHtml(receipt_html)
        document.print_(printer)
    except Exception as error:
        raise ReceiptPrintError("Receipt could not be printed.") from error

    return True


def select_printer(parent: QWidget | None = None) -> QPrinter | None:
    """Return the saved printer or let the user choose one through the native dialog."""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    saved_printer = get_default_printer()
    available_printers = {info.printerName() for info in QPrinterInfo.availablePrinters()}

    if saved_printer and saved_printer in available_printers:
        printer.setPrinterName(saved_printer)
        return printer

    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Choose Receipt Printer")
    if not dialog.exec():
        return None

    printer_name = printer.printerName()
    if not printer_name:
        raise ReceiptPrintError("No printer was selected.")
    save_default_printer(printer_name)
    return printer


def get_default_printer() -> str | None:
    """Return the saved printer name, if receipt printing has selected one before."""
    return configuration.get_default_printer(CONFIG_PATH)


def save_default_printer(printer_name: str) -> None:
    """Persist the printer choice without changing any other configuration values."""
    try:
        configuration.save_default_printer(printer_name, CONFIG_PATH)
    except OSError as error:
        raise ReceiptPrintError("Printer selection could not be saved.") from error


def receipt_html_for_order_id(order_id: int) -> str:
    """Build a receipt from immutable completed-order snapshots."""
    with session_scope() as session:
        order = get_order(session, order_id)
        if order is None:
            raise ReceiptPrintError("Order could not be found.")
        if order.is_void:
            raise ReceiptPrintError("Voided orders cannot be reprinted.")
        return receipt_html(order)


def receipt_html(order: Order) -> str:
    """Render a clean receipt that adapts to the selected thermal or A4 page size."""
    config = _load_config()
    cafe_name = _text_config(config, "cafe_name", "Cafe Name") or "CafePOS"
    receipt_footer = _text_config(config, "receipt_footer", "Receipt Footer")
    item_rows = "".join(
        "<tr>"
        f"<td>{escape(item.item_name)}{_note_html(item.note)}</td>"
        f"<td class='number'>{item.quantity}</td>"
        f"<td class='number'>₹{item.unit_price:.2f}</td>"
        f"<td class='number'>₹{item.quantity * item.unit_price:.2f}</td>"
        "</tr>"
        for item in order.items
    )
    payment_lines = _payment_lines_html(order)
    discount_line = _discount_line_html(order)
    footer_html = f"<p class='footer'>{escape(receipt_footer)}</p>" if receipt_footer else ""

    return f"""
        <html>
          <head>
            <style>
              body {{ font-family: sans-serif; font-size: 9pt; color: #111; }}
              .receipt {{ width: 100%; max-width: 180mm; margin: 0 auto; }}
              h1 {{ font-size: 16pt; text-align: center; margin: 0 0 4px; }}
              .center {{ text-align: center; margin: 2px 0; }}
              table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
              th {{ border-bottom: 1px solid #111; text-align: left; padding: 4px 0; }}
              td {{ padding: 4px 0; vertical-align: top; }}
              .number {{ text-align: right; white-space: nowrap; }}
              .summary {{ margin-top: 8px; }}
              .summary td {{ padding: 2px 0; }}
              .total td {{ border-top: 1px solid #111; font-weight: bold; padding-top: 5px; }}
              .note {{ font-size: 8pt; color: #444; }}
              .footer {{ text-align: center; margin-top: 14px; }}
            </style>
          </head>
          <body>
            <div class="receipt">
              <h1>{escape(cafe_name)}</h1>
              <p class="center">Bill #{order.bill_number} · {escape(order.order_date)} {escape(order.order_time)}</p>
              <p class="center">{escape(order.service_type)} · {escape(order.payment_mode)}</p>
              <table>
                <tr><th>Item</th><th class="number">Qty</th><th class="number">Price</th><th class="number">Amount</th></tr>
                {item_rows}
              </table>
              <table class="summary">
                <tr><td>Subtotal</td><td class="number">₹{order.subtotal:.2f}</td></tr>
                {discount_line}
                {_gst_rows_html(order)}
                {_round_off_row_html(order)}
                <tr class="total"><td>Total</td><td class="number">₹{order.total:.2f}</td></tr>
                {payment_lines}
              </table>
              {footer_html}
            </div>
          </body>
        </html>
    """


def _load_config() -> dict[str, object]:
    """Read the optional local configuration without requiring first-run setup."""
    return configuration.load_configuration(CONFIG_PATH)


def _text_config(config: dict[str, object], *keys: str) -> str | None:
    return configuration.text_value(config, *keys)


def _note_html(note: str | None) -> str:
    if not note:
        return ""
    return f"<br><span class='note'>{escape(note)}</span>"


def _discount_line_html(order: Order) -> str:
    if order.discount_value is None:
        return ""
    # Without GST the amount after the discount is the total less the round-off, not the total itself.
    after_discount = order.taxable_amount if order.taxable_amount is not None else order.total - (order.round_off or 0)
    amount = round(order.subtotal - after_discount, 2)
    return f"<tr><td>Discount</td><td class='number'>−₹{amount:.2f}</td></tr>"


def gst_breakdown_lines(order: Order) -> list[tuple[str, float]]:
    """Return the GST split saved on an order, or nothing when it had no GST."""
    if not order.gst_rate or order.cgst is None or order.sgst is None or order.taxable_amount is None:
        return []
    half_rate = f"{order.gst_rate / 2:g}"
    return [
        ("Taxable Value", order.taxable_amount),
        (f"CGST @ {half_rate}%", order.cgst),
        (f"SGST @ {half_rate}%", order.sgst),
    ]


def format_round_off(amount: float) -> str:
    """Show a round-off with its sign, for example +₹0.10 or −₹0.30."""
    return f"{'+' if amount > 0 else '−'}₹{abs(amount):.2f}"


def _round_off_row_html(order: Order) -> str:
    """Summary row for the rupee round-off, or nothing when the bill needed none."""
    if not order.round_off:
        return ""
    return f"<tr><td>Round Off</td><td class='number'>{format_round_off(order.round_off)}</td></tr>"


def _gst_rows_html(order: Order) -> str:
    """Summary rows for the GST added to this bill, or nothing when it had none."""
    return "".join(
        f"<tr><td>{escape(label)}</td><td class='number'>₹{amount:.2f}</td></tr>"
        for label, amount in gst_breakdown_lines(order)
    )


def _payment_lines_html(order: Order) -> str:
    if order.split_payments:
        return "".join(
            f"<tr><td>{escape(payment.payment_mode)}</td><td class='number'>₹{payment.amount:.2f}</td></tr>"
            for payment in order.split_payments
        )
    return f"<tr><td>{escape(order.payment_mode)}</td><td class='number'>₹{order.total:.2f}</td></tr>"
