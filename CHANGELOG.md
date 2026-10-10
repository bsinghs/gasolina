# Changelog

What changed in each production release, in plain words. Newest first.
Version = year.month.release-in-month (`VERSION` file). Each release has a git tag `v<version>`.
How to release: [docs/DEPLOY.md](docs/DEPLOY.md#releasing).

## 2026.10.3 (Oct 9, 2026)
- **Inventory** is the owner's new home page: gallons on hand and % full per tank, deliveries, gallons used, days left, an "Order soon" flag, pumps vs tanks check, sell price vs cost per gallon. Merchandise bought vs sold. Fuel deliveries typed here also count as fuel purchases on the P&L.
- **Co-owner** role: sees every page the owner sees, changes nothing (no change buttons).
- **Paid outs**: employees pick the vendor from the owner's list (searchable), or "Miscellaneous" with a note. The owner sees those notes on Reports → Vendors to add new vendors.
- **My days** (employees, managers): fuel and merchandise sales per day, month totals, "Show 30 more days", and the time each day was submitted. Review shows submit times too.
- Settings: fuel type and size for each tank; "Order soon" %.
- Versions: the version is shown at the bottom of every page; Settings → Versions & releases lists what was released when.

## 2026.10.2 (Oct 8, 2026)
- Worksheet follows the owner's Oct 8 form: TRUTH logo, ending inventory per tank, vendor names on paid outs.
- **Reports**: sales totals for a month, quarter or year, per store or all stores, with an Excel download.
- **Books**: vendor list, Profit & Loss, Balance Sheet.

## 2026.10.1 (Oct 5, 2026)
- Taxable / non-taxable merchandise calculated from the PA sales tax.
- Review queue: count boxes filter the list; missing days grouped per store.
- App admin "View as": see the app as any owner, manager or employee (read-only).
- A separate **test** copy of the app with its own data.

## 2026.10.0 (Oct 4, 2026)
- First live release at shift-close.pages.dev: daily sales worksheet on the phone, owner review (approve / send back), QuickBooks journal-entry export, people and stores, Google sign-in.
