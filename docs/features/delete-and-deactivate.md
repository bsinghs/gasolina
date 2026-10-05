# Feature spec: delete vs deactivate (stores and people)

_Status: **done** · Oct 4, 2026 · Asked for by Bhajan after trying the live app_

## Problem

1. **Bug:** a deactivated store can still be ticked when adding or editing a person.
2. Mistakes can't be undone: a store or person added by mistake can only be deactivated, so it stays in lists forever.
3. Real life needs a clear path for a **closed store** and a **terminated employee**.

## Rules

| Situation | Action | What happens |
| --- | --- | --- |
| Added by mistake, never used | **Delete** | Gone everywhere (and their store links). Allowed only if nothing refers to it |
| Store closed / sold | **Deactivate** | Hidden from worksheets and the People store picker. Its past days stay in Review, Export and history. Can be reactivated |
| Employee left / terminated | **Deactivate** | Can't sign in. Their past worksheets and history keep their name. Can be reactivated |
| Store or person **has history** (any worksheet, or appears in the history log) | Delete **refused** | Message: "…has worksheets/history. Deactivate instead so the records stay." Financial records are never destroyed |

"Used" means:
- **Store:** has any `daily_reports` row.
- **Person:** created, submitted or reviewed any worksheet, appears as `actor_id` in `audit_log`, or uploaded an attachment.

## Guards

- A store that's inactive **can't be newly assigned** to someone (API + screen). Already-assigned inactive stores may stay assigned, so reactivating restores access.
- The People store picker shows **active stores only**, plus any inactive store the person already has (labelled "inactive").
- The owner can't delete themselves, and can't delete or edit the app admin.
- Deleting asks for a second click ("Delete permanently?" Yes / Cancel). No browser pop-ups.

## API

| Method | Path | Who | Result |
| --- | --- | --- | --- |
| `DELETE` | `/api/stores/{id}` | owner | `{ok:true}`; 409 if it has worksheets; 404 if not found |
| `DELETE` | `/api/people/{id}` | owner | `{ok:true}`; 409 if they have history; 400 self; 403 admin; 404 not found |
| `POST`/`PATCH` | `/api/people` | owner | 400 if a newly assigned store is inactive |

## Acceptance

- [x] Can't tick a deactivated store for a new person; API refuses it too.
- [x] Unused store / person: Delete removes it; it's gone from every list.
- [x] Used store / person: Delete refused with the clear message; Deactivate works and history stays.
- [x] Deactivated person can't sign in; reactivated can.
- [x] Tests for all of the above.

## Independent QA review (Oct 4)

A separate reviewer agent (spec + diff only) found 4 bugs, each proven by a failing test, all fixed:

| # | Severity | Bug | Fix |
| --- | --- | --- | --- |
| 1 | Medium | Same store twice in `store_ids` → 500 on edit, wrong "email exists" message on add | Duplicates removed in `PersonIn` |
| 2 | Medium | Deleting a store could leave an active employee with no store | Delete refused: "X only works at this store…" |
| 3 | Low | Changing an email to one already used → 500 | Clean 409 message |
| 4 | Low | Picker said "No stores yet" when all were deactivated; Delete shown on admin rows | Right message; no Delete for admin |

Their tests live on in `services/api/tests/test_people_edge_cases.py`.
