# CafePOS Acceptance Tests

## First Launch

-   [ ] Welcome setup appears when config.json is missing.
-   [ ] Cafe Name is required.
-   [ ] Receipt Footer is saved.
-   [ ] config.json is created.
-   [ ] Dashboard opens after setup.

------------------------------------------------------------------------

## Dashboard

-   [ ] Application opens to Dashboard.
-   [ ] New Order opens Billing.
-   [ ] Reports opens Reports.
-   [ ] Menu Management opens Menu Management.

------------------------------------------------------------------------

## Billing

-   [ ] First category is selected automatically.
-   [ ] Search filters menu items by name.
-   [ ] Clicking an item adds it to the cart.
-   [ ] Clicking the same item again does not change quantity.
-   [ ] + increases quantity.
-   [ ] - decreases quantity.
-   [ ] Quantity reaching zero removes the item.
-   [ ] Newly added item scrolls into view.
-   [ ] Done is disabled when the cart is empty.

------------------------------------------------------------------------

## Discounts

-   [ ] Flat discount works.
-   [ ] Percentage discount works.
-   [ ] Negative discount is rejected.
-   [ ] Discount greater than subtotal is rejected.
-   [ ] Only one discount can exist per order.

------------------------------------------------------------------------

## Payments

-   [ ] Cash payment works.
-   [ ] UPI payment works.
-   [ ] Split payment works.
-   [ ] Split payment mismatch shows an error.

------------------------------------------------------------------------

## Orders

-   [ ] Order can be completed.
-   [ ] Bill number is assigned.
-   [ ] Bill number increments correctly.
-   [ ] New day starts bill numbering from 1.
-   [ ] New empty order opens after completion.
-   [ ] Unfinished cart prompts before discard.

------------------------------------------------------------------------

## Printing

-   [ ] Print prompt appears after saving.
-   [ ] Thermal receipt prints.
-   [ ] A4 receipt prints.
-   [ ] Printer selection is remembered.
-   [ ] Printing failure shows an error.
-   [ ] Reprint works.

------------------------------------------------------------------------

## Menu Management

-   [ ] Add item.
-   [ ] Edit item.
-   [ ] Delete item.
-   [ ] Deleted item disappears from the menu.
-   [ ] New category is created automatically.
-   [ ] Empty category disappears.
-   [ ] Search works.

------------------------------------------------------------------------

## Reports

-   [ ] Today report displays correctly.
-   [ ] Weekly report displays correctly.
-   [ ] Monthly report displays correctly.
-   [ ] Order details popup opens.
-   [ ] Excel export works.
-   [ ] Empty reports display "No orders today."

------------------------------------------------------------------------

## Void Orders

-   [ ] Void confirmation appears.
-   [ ] Order is marked VOIDED.
-   [ ] Voided order remains searchable.
-   [ ] Revenue excludes voided orders.
-   [ ] Voided order cannot be reprinted.

------------------------------------------------------------------------

## Historical Data

-   [ ] Price changes do not affect previous orders.
-   [ ] Deleted menu items do not affect previous orders.
-   [ ] Item names remain unchanged in historical orders.

------------------------------------------------------------------------

## Persistence

-   [ ] Orders remain after application restart.
-   [ ] Menu remains after application restart.
-   [ ] config.json is preserved.
-   [ ] Replacing CafePOS.exe does not affect data.

------------------------------------------------------------------------

## Error Handling

-   [ ] Payment mismatch dialog appears.
-   [ ] Invalid discount dialog appears.
-   [ ] Receipt printing error appears.
-   [ ] Unexpected errors are logged without crashing the application.
