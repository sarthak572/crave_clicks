# CafePOS Business Rules

## 1. General

-   Application works completely offline.
-   Billing must never require an internet connection.
-   Prices entered in the menu are before GST.
-   The owner sets one GST rate in Settings. GST is added on top of the amount
    after any discount. Each bill shows the taxable value, CGST (half the rate)
    and SGST (half the rate), and the total includes them.
-   A bill keeps the GST rate it was made with; changing the rate affects new
    bills only.
-   The bill total is rounded to the nearest whole rupee (exactly 50 paise
    rounds up) because paise cannot be paid. The difference is shown on the
    bill as Round Off, and a split payment must add up to the rounded total.
-   Only completed orders are stored.

------------------------------------------------------------------------

## 2. Cart

-   Only one active cart may exist.
-   Starting a new order while a cart exists asks: "Discard current
    order?"
-   Selecting **Yes** clears the cart.
-   Selecting **No** returns to the current order.
-   Done is disabled when the cart is empty.

------------------------------------------------------------------------

## 3. Menu Items

-   Clicking a menu item adds it to the cart only if it is not already
    present.
-   Clicking an item already in the cart does nothing.
-   Quantity changes only through + and - buttons.
-   Quantity reaching zero removes the item.
-   New items automatically scroll into view.

------------------------------------------------------------------------

## 4. Menu Management

-   Name is required.
-   Category is required.
-   Price must be greater than zero.
-   Search is by item name only.
-   Categories and items are displayed alphabetically.
-   Typing a new category creates it automatically.
-   Deleting the last item in a category removes the category.
-   Deleting a menu item removes it from the UI immediately.

------------------------------------------------------------------------

## 5. Discounts

Supported: - Flat Amount - Percentage

Applicable to: - Whole Bill - Individual Item

Rules: - Only one discount per order. - Negative discounts are not
allowed. - Discount cannot exceed the subtotal.

------------------------------------------------------------------------

## 6. Payments

Supported: - Cash - UPI - Split

Rules: - Application records payments only. - No payment gateway
integration. - No change calculation. - Split payment amounts must equal
the final payable amount.

------------------------------------------------------------------------

## 7. Orders

-   Orders remain editable until completed.
-   Completing an order assigns a bill number.
-   Completed orders cannot be edited.
-   Corrections are made by voiding the order and creating a new one.

------------------------------------------------------------------------

## 8. Printing

After saving an order, ask:

"Print receipt?"

Yes: - Print receipt. - Show "Bill Printed".

No: - Skip printing.

If printing fails: - Show "Receipt could not be printed." - Order
remains saved.

Supports: - 80 mm thermal - A4

------------------------------------------------------------------------

## 9. Reports

Tabs: - Today - Weekly - Monthly

Voided orders: - Remain searchable. - Are excluded from revenue totals.

Empty reports display:

"No orders today."

------------------------------------------------------------------------

## 10. Voiding

Only completed orders can be voided.

Voiding: - Requires confirmation. - Cannot be undone. - Preserves the
original order. - Prevents further editing. - Reprinting a voided order
is not allowed.

------------------------------------------------------------------------

## 11. Historical Data

Completed orders store: - Item name - Unit price - Quantity - Internal
note

Changing or deleting menu items never changes historical orders.

------------------------------------------------------------------------

## 12. First Launch

If config.json does not exist: - Ask for Cafe Name. - Ask for Receipt
Footer. - Create config.json.

Default printer is chosen the first time a receipt is printed and
remembered.

------------------------------------------------------------------------

## 13. Errors

Show an error dialog for: - Payment mismatch - Invalid discount -
Receipt printing failure - Unexpected application error

Unexpected errors are logged.

------------------------------------------------------------------------

## 14. Success Messages

Display brief notifications for: - Menu Updated - Bill Printed - Export
Successful
