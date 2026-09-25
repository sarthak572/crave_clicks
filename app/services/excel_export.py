"""Create Excel workbooks for the completed-order reports."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile

from app.models import Order
from app.services.reports import ReportSummary


def export_report_to_xlsx(
    destination: Path,
    title: str,
    start_date: date,
    end_date: date,
    summary: ReportSummary,
    orders: Iterable[Order],
) -> None:
    """Write one report period to a self-contained Excel workbook.

    The workbook intentionally mirrors the report tab: its summary excludes
    voided orders, while the order list retains them for audit purposes.
    """
    rows = [
        [title],
        ["Period", _period_label(start_date, end_date)],
        [],
        ["Orders", summary.order_count],
        ["Revenue", summary.total_revenue],
        ["Most Sold Item", summary.most_sold_item or "No sales"],
        [],
        ["Bill Number", "Order Value", "Time", "Payment Method"],
    ]
    for order in orders:
        bill_number = str(order.bill_number)
        if order.is_void:
            bill_number = f"{bill_number} (VOIDED)"
        rows.append([bill_number, order.total, order.order_time, order.payment_mode])

    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _root_relationships_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml())
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships_xml())
        archive.writestr("xl/styles.xml", _styles_xml())
        archive.writestr("xl/worksheets/sheet1.xml", _worksheet_xml(rows))


def _period_label(start_date: date, end_date: date) -> str:
    if start_date == end_date:
        return start_date.isoformat()
    return f"{start_date.isoformat()} to {end_date.isoformat()}"


def _worksheet_xml(rows: list[list[object]]) -> bytes:
    worksheet = Element(
        "worksheet",
        {"xmlns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"},
    )
    SubElement(
        worksheet,
        "dimension",
        {"ref": f"A1:D{max(len(rows), 1)}"},
    )
    columns = SubElement(worksheet, "cols")
    for index, width in enumerate((24, 18, 18, 22), start=1):
        SubElement(
            columns,
            "col",
            {"min": str(index), "max": str(index), "width": str(width), "customWidth": "1"},
        )

    sheet_data = SubElement(worksheet, "sheetData")
    for row_index, values in enumerate(rows, start=1):
        row = SubElement(sheet_data, "row", {"r": str(row_index)})
        for column_index, value in enumerate(values, start=1):
            if value == "":
                continue
            cell_reference = f"{_column_name(column_index)}{row_index}"
            attributes = {"r": cell_reference}
            if column_index == 2 and (row_index == 5 or row_index > 8):
                attributes["s"] = "4"
            elif row_index == 1:
                attributes["s"] = "1"
            elif row_index in (4, 5, 6):
                attributes["s"] = "2"
            elif row_index == 8:
                attributes["s"] = "3"

            cell = SubElement(row, "c", attributes)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                SubElement(cell, "v").text = str(value)
            else:
                cell.set("t", "inlineStr")
                inline_string = SubElement(cell, "is")
                SubElement(inline_string, "t").text = str(value)

    SubElement(
        worksheet,
        "autoFilter",
        {"ref": f"A8:D{max(len(rows), 8)}"},
    )
    return tostring(worksheet, encoding="utf-8", xml_declaration=True)


def _column_name(column_index: int) -> str:
    """Return the Excel column label for a one-based column index."""
    label = ""
    while column_index:
        column_index, remainder = divmod(column_index - 1, 26)
        label = chr(65 + remainder) + label
    return label


def _content_types_xml() -> bytes:
    return _xml(
        "Types",
        "http://schemas.openxmlformats.org/package/2006/content-types",
        (
            ("Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"}),
            ("Default", {"Extension": "xml", "ContentType": "application/xml"}),
            ("Override", {"PartName": "/xl/workbook.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"}),
            ("Override", {"PartName": "/xl/worksheets/sheet1.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"}),
            ("Override", {"PartName": "/xl/styles.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"}),
        ),
    )


def _root_relationships_xml() -> bytes:
    return _xml(
        "Relationships",
        "http://schemas.openxmlformats.org/package/2006/relationships",
        (("Relationship", {"Id": "rId1", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "Target": "xl/workbook.xml"}),),
    )


def _workbook_xml() -> bytes:
    workbook = Element(
        "workbook",
        {
            "xmlns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "xmlns:r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        },
    )
    sheets = SubElement(workbook, "sheets")
    SubElement(sheets, "sheet", {"name": "Report", "sheetId": "1", "r:id": "rId1"})
    return tostring(workbook, encoding="utf-8", xml_declaration=True)


def _workbook_relationships_xml() -> bytes:
    return _xml(
        "Relationships",
        "http://schemas.openxmlformats.org/package/2006/relationships",
        (
            ("Relationship", {"Id": "rId1", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", "Target": "worksheets/sheet1.xml"}),
            ("Relationship", {"Id": "rId2", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "Target": "styles.xml"}),
        ),
    )


def _styles_xml() -> bytes:
    style_sheet = Element(
        "styleSheet",
        {"xmlns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"},
    )
    number_formats = SubElement(style_sheet, "numFmts", {"count": "1"})
    SubElement(number_formats, "numFmt", {"numFmtId": "164", "formatCode": '"₹"#,##0.00'})
    fonts = SubElement(style_sheet, "fonts", {"count": "2"})
    SubElement(fonts, "font")
    bold_font = SubElement(fonts, "font")
    SubElement(bold_font, "b")
    fills = SubElement(style_sheet, "fills", {"count": "2"})
    SubElement(fills, "fill").append(Element("patternFill", {"patternType": "none"}))
    SubElement(fills, "fill").append(Element("patternFill", {"patternType": "gray125"}))
    borders = SubElement(style_sheet, "borders", {"count": "1"})
    SubElement(borders, "border")
    cell_style_xfs = SubElement(style_sheet, "cellStyleXfs", {"count": "1"})
    SubElement(cell_style_xfs, "xf", {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"})
    cell_xfs = SubElement(style_sheet, "cellXfs", {"count": "5"})
    for number_format, font_id in (("0", "0"), ("0", "1"), ("0", "1"), ("0", "1"), ("164", "0")):
        SubElement(
            cell_xfs,
            "xf",
            {"numFmtId": number_format, "fontId": font_id, "fillId": "0", "borderId": "0", "xfId": "0", "applyNumberFormat": "1"},
        )
    return tostring(style_sheet, encoding="utf-8", xml_declaration=True)


def _xml(root_name: str, namespace: str, children: tuple[tuple[str, dict[str, str]], ...]) -> bytes:
    root = Element(root_name, {"xmlns": namespace})
    for child_name, attributes in children:
        SubElement(root, child_name, attributes)
    return tostring(root, encoding="utf-8", xml_declaration=True)
