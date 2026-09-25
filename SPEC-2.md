# CafePOS Specification

**Version:** 1.0

------------------------------------------------------------------------

# 1. Purpose

CafePOS is an offline-first Windows desktop Point of Sale (POS)
application built for a single café.

The software is designed to be:

-   Reliable
-   Fast
-   Easy to learn
-   Easy to maintain

The objective is to replace subscription-based POS software with a
simple desktop application that performs billing efficiently without
requiring an internet connection.

------------------------------------------------------------------------

# 2. Technology

-   Python 3.12
-   PySide6
-   SQLite
-   SQLAlchemy
-   PyInstaller

------------------------------------------------------------------------

# 3. Users

The application is intended for:

-   Owner
-   Cashier
-   Café Staff

There are no user accounts or login screens.

------------------------------------------------------------------------

# 4. Scope

## Included

-   Dashboard
-   Billing
-   Cart
-   Menu Management
-   Reports
-   Receipt Printing
-   Excel Export
-   GST Rate (single owner-set rate, CGST/SGST split)
-   WhatsApp online orders (optional, off by default; needs internet and the relay service in relay/)

## Excluded

-   Inventory
-   Customer Accounts
-   Loyalty Programs
-   Coupons
-   QR Ordering
-   Barcode Scanner
-   Kitchen Display
-   Cloud Sync
-   Online Payments
-   Multi-user Login
-   Multi-branch Support

------------------------------------------------------------------------

# 5. General Behaviour

-   Runs completely offline.
-   Stores all data locally.
-   Replacing CafePOS.exe must never delete data.
-   Data is stored in SQLite.
-   Menu prices are before GST.
-   The owner sets one GST rate in Settings. GST is added on top of the amount
    after any discount. Every new bill stores that rate and its split: half
    CGST, half SGST. The total is the amount after discount plus CGST and SGST.
-   A complete Excel copy of all data (CafePOS_Data.xlsx) is refreshed
    automatically every 2 hours, at start-up and when the app is closed.
-   Bill numbers reset every day.
-   Internal database IDs remain unique forever.

Application folder:

CafePOS/ CafePOS.exe cafepos.db config.json CafePOS_Data.xlsx logs/

------------------------------------------------------------------------

# 6. Dashboard

The application opens to the Dashboard.

Dashboard contains:

-   New Order
-   Reports
-   Menu Management

------------------------------------------------------------------------

# 7. New Order

Only one unfinished cart may exist.

If a cashier starts another order while a cart already exists:

Display:

"Discard current order?"

Options:

Yes - Delete unfinished cart - Start new order

No - Return to current order

------------------------------------------------------------------------

# 8. Billing

Workflow:

Dashboard

↓

New Order

↓

Search or choose category

↓

Click menu item

↓

Item added to cart

↓

Adjust quantity using + or -

↓

Apply optional discount

↓

Choose payment method

↓

Done

↓

Complete Order?

↓

Order saved

↓

Print Receipt?

↓

New empty order

Rules:

-   Clicking an item already present in the cart does nothing.
-   Quantity changes only with + and -.
-   Quantity reaching zero removes the item.
-   Cart automatically scrolls to newly added items when required.
-   Done button remains disabled while the cart is empty.

------------------------------------------------------------------------

# 9. Menu

Each menu item contains:

-   Name
-   Category
-   Price

Rules:

-   Search by name only.
-   Categories sorted alphabetically.
-   Items sorted alphabetically.
-   Category field is editable.
-   Typing a new category automatically creates it.
-   Deleting the last item in a category removes that category
    automatically.
-   Deleting a menu item removes it from the UI while preserving
    historical orders.

------------------------------------------------------------------------

# 10. Discounts

Supported:

-   Flat Amount
-   Percentage

Applicable to:

-   Entire Bill
-   Individual Item

Rules:

-   Only one discount per order.
-   Negative discounts are not allowed.
-   Discount cannot exceed the bill value.

------------------------------------------------------------------------

# 11. Payments

Supported payment methods:

-   Cash
-   UPI
-   Split Payment

The application records payments only.

It does not:

-   Process payments
-   Calculate change

Split payments store the exact amount paid by each payment method.

------------------------------------------------------------------------

# 12. Orders

An order remains editable until completed.

Completing an order:

-   Assigns bill number
-   Saves the order
-   Makes it immutable

Completed orders cannot be edited.

Mistakes are corrected by:

1.  Void existing order.
2.  Create a new order.

------------------------------------------------------------------------

# 13. Printing

After an order is completed:

Display:

"Print Receipt?"

Yes - Print receipt - Show "Bill Printed"

No - Skip printing

If printing fails:

Show:

"Receipt could not be printed."

The order remains saved and may be reprinted later.

Support:

-   80 mm thermal receipts
-   A4 printing

------------------------------------------------------------------------

# 14. Reports

Tabs:

-   Today
-   Weekly
-   Monthly

Summary:

-   Number of Orders
-   Total Revenue
-   Most Sold Item

Order table:

-   Bill Number
-   Order Value
-   Time
-   Payment Method

Selecting an order opens a popup displaying:

-   Items
-   Quantities
-   Prices
-   Discount
-   Service Type
-   Payment Breakdown
-   Bill Time

Buttons:

-   Reprint
-   Void Order
-   Close

Voided orders remain searchable but are excluded from revenue totals.

------------------------------------------------------------------------

# 15. Historical Data

Every completed order stores its own copy of:

-   Item Name
-   Item Price
-   Quantity
-   Internal Note

Changing or deleting menu items never changes historical orders.

------------------------------------------------------------------------

# 16. First Launch

If config.json does not exist:

Display a setup dialog asking for:

-   Cafe Name
-   Receipt Footer

Create config.json after saving.

The printer is selected the first time a receipt is printed and
remembered automatically.

------------------------------------------------------------------------

# 17. Future Scope

Possible future additions:

-   Inventory
-   Customer Accounts
-   Loyalty
-   QR Ordering
-   Cloud Backup
-   Multi-user Support
