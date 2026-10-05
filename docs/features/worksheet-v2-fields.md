# Feature spec: worksheet v2 (owner's GGS worksheet fields)

_Status: **waiting on the owner's answers** · Oct 4, 2026_

The owner shared a newer worksheet: [`docs/reference/owner-worksheet-ggs.html`](../reference/owner-worksheet-ggs.html).

**Done (Oct 4):** the app's **look and layout** now follow it: navy header, uppercase sections, labeled fields side by side on a laptop and stacked on a phone, shaded total boxes, green/red over/short box, and a **Print / PDF** button. Fields and math are unchanged.

**Not done:** his file has different **fields and math**. Changing them changes what's saved and what goes to QuickBooks, so we need his answers first.

## Confirmed so far

- **Taxable and non-taxable amounts: done (Oct 5).** His newer worksheet answered it: they are their own sales lines, not a split. **Total sales = Fuel + Merchandise + Taxable + Non-taxable + Tax.** Migration `004`, math + tests, worksheet (Fuel, Merch on one row; Taxable, Non-taxable, Tax on the next), owner Day detail, raw CSV, and QuickBooks: each gets its own credit line (accounts "Taxable Sales" / "Non-Taxable Sales", renamable in Settings).
- Field changes go in step by step after go-live.

## Differences

| His worksheet | Our app today | Question for the owner |
| --- | --- | --- |
| **Shift** (Day / Night / Mid) | One worksheet per store per **day** | One worksheet per **shift**? Then the owner reviews 2-3 per store per day |
| **Employee name** typed in | Comes from who's signed in | (No change needed) |
| Sales: Fuel, Merchandise, **Taxable, Non-taxable**, Tax. "Subtotal = Fuel + Merch + Taxable + Non-taxable + Tax" | **Same (done Oct 5)** | Answered |
| **Cash** received as a payment line | Cash is worked out: sales − cards − paid outs | Is "Cash" read from the register report? |
| **Checks received** (customers paying by check: #, name, amount) | Checks **paid out** (store paying vendors) | Does he need both? (Received = money in, paid out = money out) |
| **Starting cash / change fund**, **Safe drops**, **Actual cash in drawer** | One **Cash drop** field | Which number does he count at close? |
| Expected cash = starting + cash − paid out − drops; Over/short = actual − expected (drawer count) | Expected cash = sales − non-cash − paid out; Over/short = cash drop − expected (sales vs money) | **Which over/short does he want?** Could show both: "drawer" and "sales vs payments" |
| Gallons by grade: **Regular, Midgrade, Premium** | One total | Split by grade? |
| **Ending inventory** per tank (1 Regular, 2 Regular, 3 Premium) | Not tracked | Tanks per store (names) and units (gallons)? |
| Print / PDF | Added Oct 4 | |
| Saved in the browser only | Saved online, approval, QuickBooks | (Ours stays) |

## What it would take (once answered)

Migration (new columns, per-shift key if chosen), API schemas + math (`reconciliation.py`) + tests, worksheet screen, owner Day detail, QuickBooks mapping (checks received → Undeposited Funds, etc.), seed data. Roughly half a day to a day, depending on the shift question.
