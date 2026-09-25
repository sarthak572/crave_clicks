# CafePOS - Bug Tracker

## Critical

None.

---

## High Priority

### BUG-001
Title: Billing window has no Back button

Status: Closed

Description:
Billing opens in a separate window.
User cannot return to Dashboard without closing the window.

Expected:
- Back button.
- If cart is empty:
  Return immediately.
- If cart contains items:
  Show:

  Discard current order?

  Yes / No

---

### BUG-002
Title: Multiple top-level windows

Status: Closed

Description:
Dashboard, Billing, Reports and Menu Management each open as separate windows.

Expected:
Single MainWindow using QStackedWidget.

Pages:
- Dashboard
- Billing
- Reports
- Menu Management

---

## Medium Priority

### BUG-003
Title: macOS text fields unreadable

Status: Closed

Description:
Input widgets render black text on black background.

Affected:
- QLineEdit
- QComboBox
- Numeric fields
- Internal Notes

Expected:
Black text on white background.

---

### BUG-004
Title: Numeric inputs start with 0.00

Status: Closed

Description:
User must delete 0.00 before entering value.

Expected:
Blank field
OR
Automatically select existing value on focus.

---

## Low Priority

### BUG-005
Improve spacing in dialogs

Status: Closed

Description:
Dialogs feel cramped.

Expected:
8–12 px consistent spacing.

---

### BUG-006
Improve alignment in Order Details

Status: Closed

Description:
Information is centered.

Expected:
Left-aligned label/value layout.

---

### BUG-007
Improve payment breakdown formatting

Status: Closed

Current:

Cash: ₹20.00

Expected:

Cash ₹20

---

### BUG-008
Improve button layout

Status: Closed

Buttons:
- Void Order
- Reprint
- Close

Should appear in a clean horizontal row.
