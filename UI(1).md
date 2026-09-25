# CafePOS UI Specification

## General

-   Light theme only
-   Resizable main window
-   Clean layout with minimal icons
-   Enter = Confirm
-   Esc = Close dialog

------------------------------------------------------------------------

# 1. First Launch

Shown only if `config.json` does not exist.

## Dialog

Title: Welcome to CafePOS

Fields: - Cafe Name - Receipt Footer

Buttons: - Save

Validation: - Cafe Name is required.

After Save: - Create `config.json` - Open Dashboard

------------------------------------------------------------------------

# 2. Dashboard

Window Title: CafePOS

Three large tiles:

+---------------------------+
|       New Order           |
+---------------------------+

+---------------------------+
|        Reports            |
+---------------------------+

  ---------------------------
  Menu Management

  ---------------------------

Actions: - New Order -\> Billing - Reports -\> Reports Window - Menu
Management -\> Menu Window

------------------------------------------------------------------------

# 3. Billing

Layout:

  -------------------------------------------------------------
  Search

  -------------------------------------------------------------

+-----------+-----------------------------------+-------------+
| C         | Items                             | Cart        |
| ategories |                                   |             |
|           |                                   | Tea         |
|           |                                   | \[-\]\[+\]  |
|           |                                   |             |
|           |                                   | Coffee      |
+-----------+-----------------------------------+-------------+

Bottom of Cart: - Discount - Payment Method - Done

Behavior: - First category selected automatically. - Search filters by
item name. - Clicking an item adds it only if not already in cart. - New
item scrolls into view if needed. - Existing item click does nothing. -
+/- changes quantity. - Quantity 0 removes item. - Done disabled until
cart contains at least one item.

Payment: Radio buttons: - Cash - UPI - Split

Discount: Button opens popup.

------------------------------------------------------------------------

# 4. Discount Dialog

Options:

-   Flat Amount
-   Percentage

Buttons: - Apply - Cancel

Validation: - No negative values. - Cannot exceed bill.

------------------------------------------------------------------------

# 5. Complete Order Dialog

Message:

Complete Order?

Buttons:

Yes No

Yes: - Save order. - Ask to print.

No: - Return to Billing.

------------------------------------------------------------------------

# 6. Print Receipt Dialog

Message:

Print receipt?

Buttons:

Yes No

Yes: - Print. - If printer unknown, show Windows printer picker and
remember choice. - Return to new empty order.

No: - Return to new empty order.

Failure: Receipt could not be printed.

------------------------------------------------------------------------

# 7. Reports

Tabs: - Today - Weekly - Monthly

Top Summary: - Orders - Revenue - Most Sold Item

Table: - Bill No. - Amount - Time - Payment

Double-click row: Open Order Details.

Empty: No orders today.

Button: Export Excel

------------------------------------------------------------------------

# 8. Order Details Dialog

Shows: - Bill Number - Status - Items - Quantity - Price - Discount -
Service Type - Payment Breakdown - Bill Time

Buttons: - Reprint - Void Order - Close

If voided: Display "VOIDED".

Void Order: Confirmation dialog.

------------------------------------------------------------------------

# 9. Menu Management

Table: - Name - Category - Price

Buttons: - Add - Edit - Delete

Search: By name.

Delete: Immediate. No confirmation.

------------------------------------------------------------------------

# 10. Add/Edit Item Dialog

Fields: - Name - Category (editable dropdown) - Price

Buttons: - Save - Cancel

Validation: - Name required. - Category required. - Price \> 0.

------------------------------------------------------------------------

# 11. Toasts

-   Menu Updated
-   Bill Printed
-   Export Successful

------------------------------------------------------------------------

# 12. Error Dialogs

-   Payment mismatch.
-   Receipt could not be printed.
-   Unexpected error occurred.
