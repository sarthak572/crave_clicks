# CafePOS Database Specification

## Database

Engine: SQLite

Database File:

cafepos.db

All timestamps use the local system time.

------------------------------------------------------------------------

# Table: menu_items

Stores the current café menu.

  Column       Type                                Notes
  ------------ ----------------------------------- ---------------------
  id           INTEGER PRIMARY KEY AUTOINCREMENT   Internal ID
  name         TEXT NOT NULL                       Menu item name
  category     TEXT NOT NULL                       Category name
  price        REAL NOT NULL                       Price before GST
  is_deleted   INTEGER NOT NULL DEFAULT 0          Soft delete flag

Rules

-   Name is required.
-   Category is required.
-   Price must be greater than 0.
-   Deleted items are hidden from the UI.

------------------------------------------------------------------------

# Table: orders

Stores completed orders only.

  Column           Type
  ---------------- -----------------------------------
  id               INTEGER PRIMARY KEY AUTOINCREMENT
  bill_number      INTEGER NOT NULL
  order_date       TEXT NOT NULL
  order_time       TEXT NOT NULL
  service_type     TEXT NOT NULL
  payment_mode     TEXT NOT NULL
  subtotal         REAL NOT NULL
  discount_type    TEXT
  discount_value   REAL
  discount_scope   TEXT
  discount_menu_item_id INTEGER
  total            REAL NOT NULL
  gst_rate         REAL
  taxable_amount   REAL
  cgst             REAL
  sgst             REAL
  is_void          INTEGER NOT NULL DEFAULT 0

Rules

-   One row per completed order.
-   Bill numbers restart from 1 each day.
-   id never resets.
-   `gst_rate`, `taxable_amount`, `cgst` and `sgst` are copied onto the order
    when it is completed and never change afterwards. They are NULL when no GST
    rate was set (including all bills made before GST support).
-   GST is added on top of the discounted amount, so `total` includes it:
    `taxable_amount = subtotal - discount`,
    `cgst = sgst = round(taxable_amount * rate / 200, 2)` and
    `total = taxable_amount + cgst + sgst`. With no GST rate, `total` equals
    `taxable_amount`. Bills made while GST was still included in menu prices
    keep their old figures.
-   `discount_scope` is `order` or `item` when a discount is applied.
-   `discount_menu_item_id` identifies the discounted historical order item
    when the scope is `item`.

------------------------------------------------------------------------

# Table: order_items

Stores every item sold.

  Column         Type
  -------------- -----------------------------------
  id             INTEGER PRIMARY KEY AUTOINCREMENT
  order_id       INTEGER NOT NULL
  menu_item_id   INTEGER
  item_name      TEXT NOT NULL
  quantity       INTEGER NOT NULL
  unit_price     REAL NOT NULL
  note           TEXT

Foreign Key

order_id -\> orders.id

Rules

-   item_name and unit_price are copied from the menu when the order is
    completed.
-   Historical orders never change.

------------------------------------------------------------------------

# Table: split_payments

Only used when payment mode is Split.

  Column         Type
  -------------- -----------------------------------
  id             INTEGER PRIMARY KEY AUTOINCREMENT
  order_id       INTEGER NOT NULL
  payment_mode   TEXT NOT NULL
  amount         REAL NOT NULL

Foreign Key

order_id -\> orders.id

Example

Cash 120

UPI 80

------------------------------------------------------------------------

# Relationships

orders

└── order_items

└── split_payments

------------------------------------------------------------------------

# Bill Number Logic

When an order is completed:

1.  Read today's date.
2.  Find the largest bill number for today.
3.  Assign next number.
4.  Save order.

Example

2026-08-03

1 2 3 4

Next order

5

On a new day

Bill numbering starts again from 1.

------------------------------------------------------------------------

# Deleting Menu Items

Deleting a menu item:

-   Sets is_deleted = 1.
-   Removes it from the UI.
-   Does not affect historical orders.

------------------------------------------------------------------------

# Configuration

Application settings are stored in:

config.json

Contains:

-   Cafe Name
-   Receipt Footer
-   Default Printer
-   GST Rate (percentage; 0 or missing means no GST is shown)

------------------------------------------------------------------------

# Log Files

Unexpected errors are written to:

logs/YYYY-MM-DD.log

------------------------------------------------------------------------

# Excel Data File

File: CafePOS_Data.xlsx (beside cafepos.db)

A complete, human-readable copy of the database. SQLite remains the live
store; the workbook is rebuilt from it in a background thread after every
committed change to orders or the menu, and once at every start-up (so an
existing database is back-filled).

Sheets

-   Read Me
-   Orders (one row per bill, including voided bills)
-   Order Items (one row per item sold)
-   Daily Summary (orders, revenue, cash/UPI, discounts; voided excluded)
-   Item Sales (quantity and sales per item; voided excluded)
-   Menu (active items, plus removed items marked Removed)

Rules

-   The workbook is derived data. Edits made in Excel are overwritten and
    never reach the POS.
-   It is written to a temporary file and swapped in, so it is never half
    written.
-   If Excel has the file open, the POS retries every 15 seconds and on exit
    makes a final attempt; failures are written to logs/YYYY-MM-DD.log.
-   If the file is deleted, it is recreated on the next start-up.

------------------------------------------------------------------------

# Default Menu

default_menu.json holds a `version` number and the `items` list.

-   A new database is seeded from it.
-   When its `version` is higher than the database's `PRAGMA user_version`,
    the current menu items are soft-deleted (historical orders untouched) and
    replaced by the file's items, once. Edits made afterwards in Menu
    Management are never overwritten until the version is raised again.

------------------------------------------------------------------------

# Backup

Backing up the application only requires:

CafePOS.exe

cafepos.db

config.json

CafePOS_Data.xlsx (optional: rebuilt from cafepos.db)

logs/ (optional)
