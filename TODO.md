# CafePOS - Remaining Work

---

# Phase 1 — Complete Functionality

## Module 7

### Excel Export

Status:
Not Started

Tasks:

- Export Today report
- Export Weekly report
- Export Monthly report
- Export as XLSX
- Filename:
  CafePOS_Report_YYYY-MM-DD.xlsx
- Success dialog
- Error handling

---

## Module 8

### Configuration

Status:
Not Started

Tasks:

- config.json
- First launch setup
- Cafe name
- Receipt footer
- Default printer
- Printer persistence

---

## Module 9

### Packaging

Status:
Not Started

Tasks:

- PyInstaller
- Windows executable
- External database
- External config
- Logs folder

Target layout:

CafePOS/

    CafePOS.exe

    cafepos.db

    config.json

    logs/

---

# Phase 2 — UX Improvements

## Navigation

- Replace multiple windows with one MainWindow.
- Use QStackedWidget.
- Add Back button.
- Confirm before discarding cart.

---

## UI Improvements

- Better spacing
- Better typography
- Better alignment
- Better tables
- Better dialogs
- Better icons
- Consistent margins

---

## Forms

- Fix numeric inputs
- Fix macOS palette
- Better placeholders

---

# Phase 3 — Polish

- Toast notifications
- Consistent colors
- Windows 11 style
- Segoe UI
- Rounded buttons
- Remove visual inconsistencies

No gradients.
No animations.
No unnecessary decorations.

---

# Phase 4 — Testing

Billing

- Cash
- UPI
- Split Payment

Discounts

- Flat
- Percentage
- Item
- Invalid values

Reports

- Revenue
- Most Sold Item
- Voiding
- Reprint

Printing

- Thermal
- A4

Persistence

- Restart application
- Verify data

Windows

- Fresh install
- Replace executable
- Preserve database

---

# Release Checklist

- All modules complete
- All BUGS.md items resolved
- No crashes
- Packaging complete
- Windows tested
- Cafe owner acceptance testing