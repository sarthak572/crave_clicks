"""Keep a complete Excel copy of every order and the menu.

SQLite stays the live store used for billing. ``CafePOS_Data.xlsx`` (beside
cafepos.db) is rebuilt from the database in a background thread when CafePOS
starts, then every two hours if orders or the menu changed in the meantime, and
once more when CafePOS is closed. The owner can open one ordinary Excel file
and find all of their data. The file is written to a temporary name and swapped
in, so it is never left half-written; if Excel currently has it open, the
update is retried automatically until it can be saved.
"""

from __future__ import annotations

import os
import re
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select

from app.database import add_change_listener, session_scope
from app.models import MenuItem, Order, OrderItem, SplitPayment
from app.runtime_paths import application_directory, logs_directory
from app.services.excel_export import _column_name


WORKBOOK_NAME = "CafePOS_Data.xlsx"
SYNC_INTERVAL_SECONDS = 2 * 60 * 60
RETRY_SECONDS = 15.0

# Indexes into the cellXfs list in _styles_xml().
DEFAULT, HEADER, MONEY, DATE, TIME, INTEGER, TITLE, WRAP = range(8)

_EXCEL_EPOCH = date(1899, 12, 30)
_ILLEGAL_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Sheet:
    """One worksheet: a header row, data rows, and per-column layout."""

    name: str
    headers: list[str]
    widths: list[int]
    styles: list[int]
    rows: list[list[object]]
    table: bool = True  # header row + filter + frozen pane; False for free text


def workbook_path() -> Path:
    """Return where the Excel data file lives."""
    return application_directory() / WORKBOOK_NAME


# --------------------------------------------------------------------------
# Building the sheets from the database
# --------------------------------------------------------------------------


def build_sheets() -> list[Sheet]:
    """Read the whole database and return the worksheets to save."""
    with session_scope() as session:
        orders = session.execute(
            select(
                Order.id, Order.bill_number, Order.order_date, Order.order_time,
                Order.service_type, Order.payment_mode, Order.subtotal,
                Order.discount_type, Order.discount_value, Order.discount_menu_item_id,
                Order.total, Order.gst_rate, Order.taxable_amount, Order.cgst, Order.sgst, Order.is_void,
                Order.source, Order.customer_phone, Order.round_off,
            ).order_by(Order.id)
        ).all()
        items = session.execute(
            select(
                OrderItem.order_id, OrderItem.menu_item_id, OrderItem.item_name,
                OrderItem.quantity, OrderItem.unit_price, OrderItem.note,
            ).order_by(OrderItem.id)
        ).all()
        splits = session.execute(
            select(SplitPayment.order_id, SplitPayment.payment_mode, SplitPayment.amount)
            .order_by(SplitPayment.id)
        ).all()
        menu = session.execute(
            select(
                MenuItem.id, MenuItem.category, MenuItem.name, MenuItem.price, MenuItem.is_deleted
            ).order_by(MenuItem.is_deleted, MenuItem.category, MenuItem.name, MenuItem.id)
        ).all()

    items_by_order: dict[int, list] = defaultdict(list)
    for line in items:
        items_by_order[line.order_id].append(line)
    splits_by_order: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for split in splits:
        splits_by_order[split.order_id][split.payment_mode] += split.amount

    order_rows: list[list[object]] = []
    item_rows: list[list[object]] = []
    daily: dict[str, dict[str, float]] = {}
    sold: dict[str, list[float]] = {}

    for order in orders:
        lines = items_by_order.get(order.id, [])
        paid = _payment_amounts(order.payment_mode, order.total, splits_by_order.get(order.id))
        # GST is added after the discount, so compare the subtotal with the pre-GST amount.
        # Without GST the pre-round-off amount is the total less its round-off.
        after_discount = (
            order.taxable_amount if order.taxable_amount is not None else order.total - (order.round_off or 0)
        )
        discount_amount = round(order.subtotal - after_discount, 2)
        order_date, order_time = _excel_date(order.order_date), _excel_time(order.order_time)
        status = "VOIDED" if order.is_void else "Completed"

        order_rows.append([
            order.id, order.bill_number, order_date, order_time, order.service_type,
            order.payment_mode, paid.get("Cash", 0.0), paid.get("UPI", 0.0),
            "; ".join(f"{line.quantity} x {line.item_name}" for line in lines),
            order.subtotal, _discount_label(order, lines), order.discount_value,
            discount_amount, order.total, order.gst_rate, order.taxable_amount, order.cgst,
            order.sgst, status, order.source or "Counter", order.customer_phone or "",
        ])
        for line in lines:
            item_rows.append([
                order.id, order.bill_number, order_date, order_time, status, line.item_name,
                line.quantity, line.unit_price, round(line.quantity * line.unit_price, 2),
                line.note or "",
            ])

        day = daily.setdefault(order.order_date, defaultdict(float))
        if order.is_void:
            day["voided"] += 1
            day["voided_amount"] += order.total
            continue
        day["orders"] += 1
        day["revenue"] += order.total
        day["cash"] += paid.get("Cash", 0.0)
        day["upi"] += paid.get("UPI", 0.0)
        day["discount"] += discount_amount
        day["taxable"] += order.taxable_amount or 0.0
        day["cgst"] += order.cgst or 0.0
        day["sgst"] += order.sgst or 0.0
        for line in lines:
            totals = sold.setdefault(line.item_name, [0, 0.0])
            totals[0] += line.quantity
            totals[1] += line.quantity * line.unit_price

    daily_rows = [
        [
            _excel_date(day), int(d["orders"]), round(d["revenue"], 2), round(d["cash"], 2),
            round(d["upi"], 2), round(d["discount"], 2), round(d["taxable"], 2), round(d["cgst"], 2),
            round(d["sgst"], 2), int(d["voided"]), round(d["voided_amount"], 2),
        ]
        for day, d in sorted(daily.items())
    ]
    sold_rows = [
        [name, qty, round(revenue, 2)]
        for name, (qty, revenue) in sorted(sold.items(), key=lambda entry: (-entry[1][0], entry[0]))
    ]
    menu_rows = [
        [row.category, row.name, row.price, "Removed" if row.is_deleted else "Active", row.id]
        for row in menu
    ]

    return [
        _read_me_sheet(),
        Sheet(
            "Orders",
            ["Order ID", "Bill No", "Date", "Time", "Service Type", "Payment Mode", "Cash Paid",
             "UPI Paid", "Items", "Subtotal", "Discount", "Discount Value (% or ₹)",
             "Discount Amount", "Total", "GST Rate %", "Taxable Value", "CGST", "SGST", "Status",
             "Source", "Customer Phone"],
            [10, 9, 12, 10, 14, 14, 12, 12, 60, 12, 30, 14, 14, 12, 11, 14, 11, 11, 12, 11, 16],
            [INTEGER, INTEGER, DATE, TIME, DEFAULT, DEFAULT, MONEY, MONEY, DEFAULT, MONEY,
             DEFAULT, DEFAULT, MONEY, MONEY, DEFAULT, MONEY, MONEY, MONEY, DEFAULT, DEFAULT, DEFAULT],
            order_rows,
        ),
        Sheet(
            "Order Items",
            ["Order ID", "Bill No", "Date", "Time", "Status", "Item", "Qty", "Unit Price",
             "Line Total", "Note"],
            [10, 9, 12, 10, 12, 42, 7, 12, 12, 30],
            [INTEGER, INTEGER, DATE, TIME, DEFAULT, DEFAULT, INTEGER, MONEY, MONEY, DEFAULT],
            item_rows,
        ),
        Sheet(
            "Daily Summary",
            ["Date", "Orders", "Revenue", "Cash", "UPI", "Discounts Given", "Taxable Value",
             "CGST", "SGST", "Voided Orders", "Voided Amount"],
            [12, 9, 14, 14, 14, 16, 14, 11, 11, 14, 16],
            [DATE, INTEGER, MONEY, MONEY, MONEY, MONEY, MONEY, MONEY, MONEY, INTEGER, MONEY],
            daily_rows,
        ),
        Sheet(
            "Item Sales",
            ["Item", "Qty Sold", "Sales (before discount)"],
            [42, 10, 22],
            [DEFAULT, INTEGER, MONEY],
            sold_rows,
        ),
        Sheet(
            "Menu",
            ["Category", "Item", "Price", "Status", "Item ID"],
            [30, 42, 12, 10, 9],
            [DEFAULT, DEFAULT, MONEY, DEFAULT, INTEGER],
            menu_rows,
        ),
    ]


def _payment_amounts(mode: str, total: float, split: dict[str, float] | None) -> dict[str, float]:
    if mode == "Split":
        return dict(split or {})
    return {mode: total}


def _discount_label(order: object, lines: list) -> str:
    """Turn the stored ``kind_scope`` discount code into readable text."""
    if not order.discount_type:
        return ""
    kind, _, scope = order.discount_type.partition("_")
    label = "Percentage" if kind == "percentage" else "Flat"
    if scope != "item":
        return f"{label} - Whole Bill"
    line = next((line for line in lines if line.menu_item_id == order.discount_menu_item_id), None)
    return f"{label} - Item: {line.item_name}" if line else f"{label} - Item"


def _excel_date(value: str) -> int | str:
    try:
        return (date.fromisoformat(value) - _EXCEL_EPOCH).days
    except ValueError:
        return value


def _excel_time(value: str) -> float | str:
    try:
        parsed = datetime.strptime(value, "%H:%M:%S")
    except ValueError:
        return value
    return (parsed.hour * 3600 + parsed.minute * 60 + parsed.second) / 86400


def _read_me_sheet() -> Sheet:
    lines = [
        ("CafePOS data file", TITLE),
        ("This workbook is a complete copy of your CafePOS data. It is rewritten automatically "
         "every 2 hours and when CafePOS is closed, so the newest bills may not appear until then.", WRAP),
        ("", DEFAULT),
        ("Do not type into this file - changes made here are overwritten at the next update "
         "and never reach the POS. Copy it, or use Save As, if you want to work with the numbers.", WRAP),
        ("If the file is open in Excel, the POS keeps trying in the background and updates it as "
         "soon as you close it.", WRAP),
        ("", DEFAULT),
        ("Sheets", TITLE),
        ("Orders - one row per bill, including voided bills (Status column) and its GST split (CGST and SGST).", WRAP),
        ("Order Items - one row per item sold on each bill.", WRAP),
        ("Daily Summary - orders, revenue, cash/UPI split, discounts and CGST/SGST per day (voided bills excluded).", WRAP),
        ("Item Sales - quantity and sales per item across all time (voided bills excluded).", WRAP),
        ("Menu - the current menu; removed items are kept and marked Removed.", WRAP),
        ("", DEFAULT),
        (f"Last updated: {datetime.now():%Y-%m-%d %H:%M:%S}", DEFAULT),
    ]
    return Sheet("Read Me", [], [110], [WRAP], [[text, style] for text, style in lines], table=False)


# --------------------------------------------------------------------------
# Writing the .xlsx file (no third-party dependency)
# --------------------------------------------------------------------------


def write_workbook(destination: Path, sheets: list[Sheet]) -> None:
    """Write ``sheets`` to ``destination`` atomically."""
    temporary = destination.with_name(destination.name + ".tmp")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", _root_relationships_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships_xml(len(sheets)))
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, sheet in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(sheet))
    try:
        os.replace(temporary, destination)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _sheet_xml(sheet: Sheet) -> str:
    column_count = len(sheet.widths)
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    ]
    if sheet.table:
        parts.append(
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
            'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        )
    parts.append("<cols>")
    for index, width in enumerate(sheet.widths, start=1):
        parts.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')
    parts.append("</cols><sheetData>")

    row_number = 0
    if sheet.table:
        row_number = 1
        parts.append('<row r="1">')
        for column, header in enumerate(sheet.headers, start=1):
            parts.append(_cell(column, 1, header, HEADER))
        parts.append("</row>")
    for values in sheet.rows:
        row_number += 1
        parts.append(f'<row r="{row_number}">')
        if sheet.table:
            for column, value in enumerate(values, start=1):
                parts.append(_cell(column, row_number, value, sheet.styles[column - 1]))
        else:  # free-text sheets carry (text, style) pairs
            parts.append(_cell(1, row_number, values[0], values[1]))
        parts.append("</row>")
    parts.append("</sheetData>")
    if sheet.table:
        parts.append(f'<autoFilter ref="A1:{_column_name(column_count)}{max(row_number, 1)}"/>')
    parts.append("</worksheet>")
    return "".join(parts)


def _cell(column: int, row: int, value: object, style: int) -> str:
    if value is None or value == "":
        return ""
    reference = f"{_column_name(column)}{row}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{reference}" s="{style}"><v>{value!r}</v></c>'
    text = escape(_ILLEGAL_XML.sub("", str(value)))
    return f'<c r="{reference}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _content_types_xml(sheet_count: int) -> str:
    sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{sheets}</Types>"
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(sheets: list[Sheet]) -> str:
    entries = []
    for index, sheet in enumerate(sheets, start=1):
        entries.append(f'<sheet name="{escape(sheet.name)}" sheetId="{index}" r:id="rId{index}"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{"".join(entries)}</sheets></workbook>'
    )


def _workbook_relationships_xml(sheet_count: int) -> str:
    sheets = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, sheet_count + 1)
    )
    styles = (
        f'<Relationship Id="rId{sheet_count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{sheets}{styles}</Relationships>"
    )


def _xf_xml(number_format: int, font: int, fill: int, border: int, alignment: str) -> str:
    attributes = (
        f'numFmtId="{number_format}" fontId="{font}" fillId="{fill}" borderId="{border}" xfId="0" '
        'applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"'
    )
    if alignment:
        return f'<xf {attributes} applyAlignment="1">{alignment}</xf>'
    return f"<xf {attributes}/>"


def _styles_xml() -> str:
    """Styles indexed by DEFAULT, HEADER, MONEY, DATE, TIME, INTEGER, TITLE, WRAP."""
    wrap = '<alignment wrapText="1" vertical="top"/>'
    xfs = [  # (numFmtId, fontId, fillId, borderId, alignment)
        (0, 0, 0, 0, ""),      # DEFAULT
        (0, 1, 2, 1, ""),      # HEADER: bold, fill, bottom border
        (164, 0, 0, 0, ""),    # MONEY
        (165, 0, 0, 0, ""),    # DATE
        (166, 0, 0, 0, ""),    # TIME
        (1, 0, 0, 0, ""),      # INTEGER
        (0, 2, 0, 0, ""),      # TITLE: large bold
        (0, 0, 0, 0, wrap),    # WRAP
    ]
    xf_xml = "".join(_xf_xml(*xf) for xf in xfs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="3">'
        '<numFmt numFmtId="164" formatCode="&quot;₹&quot;#,##0.00"/>'
        '<numFmt numFmtId="165" formatCode="yyyy\\-mm\\-dd"/>'
        '<numFmt numFmtId="166" formatCode="hh:mm:ss"/>'
        "</numFmts>"
        '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="14"/><name val="Calibri"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF0EAE3"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
        '<border><left/><right/><top/><bottom style="thin"><color rgb="FF8B5E3C"/></bottom><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        f'<cellXfs count="{len(xfs)}">{xf_xml}</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


# --------------------------------------------------------------------------
# Background synchronisation
# --------------------------------------------------------------------------


class DataWorkbookSync:
    """Rebuilds the Excel data file in a background thread at a regular interval."""

    def __init__(self, path: Path | None = None, interval: float = SYNC_INTERVAL_SECONDS) -> None:
        self.path = path or workbook_path()
        self.interval = interval
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._write_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="excel-sync", daemon=True)

    def start(self) -> None:
        """Begin syncing and schedule a first full write of existing data."""
        self.mark_dirty()  # before the thread runs, or it could sleep a whole interval first
        self._thread.start()

    def mark_dirty(self) -> None:
        """Note that data changed, so the next scheduled sync must rewrite the workbook."""
        self._wake.set()

    def sync_now(self) -> bool:
        """Rebuild and save the workbook now. Returns whether it succeeded."""
        with self._write_lock:
            try:
                write_workbook(self.path, build_sheets())
            except Exception as error:  # locked by Excel, disk full, ...
                _log_error(f"Excel data file not updated: {error!r}")
                return False
            return True

    def stop(self) -> None:
        """Stop the background thread and make one last attempt to save any pending change."""
        self._stop.set()
        pending = self._wake.is_set()
        self._wake.set()
        self._thread.join(timeout=10)
        if pending:
            self.sync_now()

    def _run(self) -> None:
        """Write pending changes now, then again every ``interval`` seconds."""
        while not self._stop.is_set():
            delay = self.interval
            if self._wake.is_set():
                self._wake.clear()
                if not self.sync_now():
                    self._wake.set()
                    delay = RETRY_SECONDS  # locked by Excel or disk problem: try again soon
            if self._stop.wait(delay):
                return


_active_sync: DataWorkbookSync | None = None


def start_data_sync() -> DataWorkbookSync:
    """Start mirroring the database into the Excel data file (call once at startup)."""
    global _active_sync
    if _active_sync is None:
        _active_sync = DataWorkbookSync()
        add_change_listener(_active_sync.mark_dirty)
        _active_sync.start()
    return _active_sync


def stop_data_sync() -> None:
    """Finish any pending Excel update before the application exits."""
    if _active_sync is not None:
        _active_sync.stop()


def _log_error(message: str) -> None:
    try:
        with open(logs_directory() / f"{date.today().isoformat()}.log", "a", encoding="utf-8") as log:
            log.write(f"{datetime.now():%H:%M:%S} {message}\n")
    except OSError:
        pass
