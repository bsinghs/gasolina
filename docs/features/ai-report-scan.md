# Feature spec: AI report scan

_Status: **draft, not started** · Written Oct 4, 2026 · Owner of this spec: Bhajan_

## 1. Problem

At close, the employee copies about 10 numbers from the register's printed report into the worksheet by hand. It's slow, and a mistyped digit only shows up later as an unexplained over/short. The register report already holds every number we need, and it checks itself (its totals must add up).

**Goal:** the employee photographs the register report, and the worksheet fills itself in. The app checks the numbers add up and highlights anything doubtful. The employee confirms and submits as usual. The photo stays with the day, so the owner can compare.

**Not a goal:** removing the human. AI only ever fills a **draft**; a person always confirms, and the owner still approves.

## 2. Who and when

| Who | Where | Moment |
| --- | --- | --- |
| Employee | Phone, Worksheet page | End of shift, before submitting |
| Owner | Laptop, Day detail page | When reviewing a submitted day |

## 3. User flow

### Employee
1. Opens the day's worksheet and taps **Scan register report**.
2. Phone camera opens (or picks a photo/PDF). Takes the photo.
3. Sees "Reading the report…" (target: under 20 seconds).
4. Worksheet fields fill in. Each AI-filled field shows a small **AI** tag.
5. A banner sums up the checks:
   - all good: "Read 8 values. All checks add up."
   - or not: "1 check didn't add up: card + cash ≠ total on the slip. Please check Credit, Debit, EBT." The fields involved, and any low-confidence field, are **highlighted**.
6. Employee fixes anything highlighted. Editing an AI value marks it **ai_corrected**.
7. Still types what the report doesn't have: **cash drop**, **gallons**, check paid-outs, note.
8. Submits as today. Submitting is allowed even with a failed check (the banner shows on the owner's side too).

### Owner
1. Day detail shows a **Report photo** thumbnail (tap → full size) and a line like "AI-read 8 values · 1 corrected by employee · 1 check failed".
2. Corrected fields show the AI's value next to the submitted value.
3. Approve / send back as today.

### Manual path stays
Not scanning is always fine. Every field remains typeable, and nothing changes for a typed-only day.

## 4. What the report gives us

From the sample **Close Month Report** (store A6123, register 101, period ending 8/31/26):

| Report line | Worksheet field | Sample value |
| --- | --- | --- |
| Total fuel sales | `fuel_sale` | 156,968.05 |
| Total merch sales | `merch_sale` | 72,982.48 |
| Total taxes | `sales_tax` | 938.66 |
| MOP sales: Credit | `credit` | 136,071.25 |
| MOP sales: Debit | `debit` | 13,569.70 |
| MOP sales: EBT | `ebt` | 78.83 |
| Payment out: Pay out (+ In house) | cash paid-out lines | 158.70 + 3,666.77 |
| Header: report type, period end, store #, register | checks only (date and store match) | Close Month, 8/31/26 |
| MOP sales: Cash; Cancel/refunds: Cash; Net sales total; Totalizer; Total MOP sales | cross-checks only (kept in `raw_json`) | 82,244.41; 1,075.08; 230,889.19; ... |

**Not on the report → still typed:** cash drop (counted cash), gallons (needs a fuel/pump report later), check paid-outs, note.

**Important:** the sample is a **month** close. The worksheet is **daily**. We need a photo of the **daily shift-close report** from the owner before building (open question 1). The design below handles any report type as a config, so this doesn't block the plumbing.

## 5. Cross-checks (done in code, not by AI)

| # | Check | Sample result | If it fails |
| --- | --- | --- | --- |
| C1 | fuel + merch + taxes = net sales total | 230,889.19 ✓ | Highlight the 3 sales fields |
| C2 | net sales total = totalizer difference | ✓ | Highlight sales fields |
| C3 | total MOP sales − refunds = net sales total | 231,964.27 − 1,075.08 = 230,889.19 ✓ | Highlight payment fields |
| C4 | credit + debit + EBT + cash = total MOP sales | **231,964.19 vs 231,964.27 ✗ ($0.08)** | Highlight credit, debit, EBT |
| C5 | pay-out lines = total payment out | ✓ | Highlight paid-outs |
| C6 | report date matches the worksheet's business date | | Warning: "This report is for 8/30, the worksheet is 8/31" |
| C7 | store / register number matches the store (once we store register IDs) | | Warning |

C4 shows why this matters: reading the sample photo, the four payment lines are **8 cents** off the printed total, so one digit was misread. The app must **flag, not guess**. Tolerance: exact to the cent (configurable).

**Low confidence:** any field the model rates below **0.90**, or where the model couldn't find the line, is highlighted even if checks pass.

## 6. Design

```
Phone (Worksheet)                API (Cloud Run)                        Outside
  │ photo (≤10 MB)  ───────────▶ POST /api/reports/{id}/scans
  │                               ├─ save file ───────────────────────▶ Supabase Storage (private bucket "report-photos")
  │                               ├─ attachments row
  │                               ├─ extract(file, report_type) ──────▶ Claude vision model (Anthropic API)
  │                               │     returns JSON: fields + confidence + text read
  │                               ├─ run checks C1-C7 (code)
  │                               ├─ report_uploads row (raw, fields, confidence, checks)
  │ ◀──── proposed values + checks + highlights
  │ fills form, field_sources = ai / ai_corrected
  │ PUT /api/reports/{id}  (existing save)
```

### Decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Where the AI code lives | New module `services/api/app/modules/scans/` with one boundary function `extract(file_bytes, content_type, report_type) -> Extraction` in `scans/extractor.py` | Simple to deploy (one service, still $0 hosting). The boundary means it can move to `services/ai` or switch model/provider without touching the rest |
| Model | Claude with vision, via the Anthropic API; model name in `AI_MODEL` env var | Reads photos of printed slips well; structured JSON output via a fixed schema |
| Report types | Config per type in `scans/report_types/<type>.py`: JSON schema for the model, field mapping, which checks apply | Daily shift report, month close, fuel report = new config, not new code |
| Photo storage | Supabase Storage, private bucket, API holds the key; photos shrunk in the browser to ~1600 px JPEG first | Already have Supabase; free tier storage is separate from the 500 MB database. ~300 KB per photo |
| Sync or background | **Synchronous** (request waits ~10-20 s) | Simplest. Cloud Run timeout raised from 60 s to 120 s. Move to background only if it's too slow |
| Who applies the values | The **screen** fills the form; the existing save stores them | No new "apply" endpoint; employee stays in control |
| Turn on/off | `AI_SCAN_ENABLED` env var (default **off**) | Lets us deploy safely and keep $0 until we choose to turn it on |

### API

| Method | Path | Who | Does |
| --- | --- | --- | --- |
| `POST` | `/api/reports/{report_id}/scans` | Employee of that store, or owner; report must be draft/returned | Multipart `file`, optional `report_type` (default from settings). Returns `{scan_id, attachment_id, fields, confidence, checks, highlights, report_date}` |
| `GET` | `/api/reports/{report_id}/scans` | Same | Past scans for this day (latest first) |
| `GET` | `/api/attachments/{attachment_id}/url` | Same | Short-lived signed link to view the photo |

Errors: 413 file too large; 415 not an image/PDF; 409 day not editable; 503 scanning turned off or AI provider down (the screen says "Couldn't read it, please type the numbers").

### Data (tables already exist from migration 001)

- `attachments`: one row per photo (`storage_path`, `content_type`, `uploaded_by`). **Migration 003** adds `sha256` (spot the same photo uploaded twice) and `size_bytes`.
- `report_uploads`: one row per scan. `report_type`; `model`; `raw_json` (everything the model read, including lines we don't use yet); `fields_json` (mapped worksheet values); `confidence_json`; `checks_json`; `status` (`pending` / `done` / `failed`).
- `daily_reports.field_sources`: already exists. Values `typed` / `ai` / `ai_corrected`.
- `audit_log`: new actions `scanned` (with scan id) and, on save, which fields were `ai_corrected` with old → new.
- `settings`: new keys `scan_default_report_type`, `scan_confidence_threshold` (0.90), `scan_check_tolerance` (0.00).

### New settings (env vars)

| Name | Secret? | Example |
| --- | --- | --- |
| `AI_SCAN_ENABLED` | no | `false` |
| `AI_MODEL` | no | `claude-sonnet-5-5` |
| `ANTHROPIC_API_KEY` | **yes** → Secret Manager | |
| `SUPABASE_SERVICE_KEY` | **yes** → Secret Manager | (secret key, Storage access only from the API) |
| `SCAN_BUCKET` | no | `report-photos` |

## 7. Privacy, safety, cost

- **What's in the photo:** sales totals, store/register numbers, cashier ID. No card numbers or customer names. Ask employees to photograph only the report.
- **Model provider:** images go to Anthropic over the API. API data isn't used for training by default; **confirm the current terms before go-live.**
- **Storage:** private bucket. Photos are only reachable through short-lived links from our API, after the same permission checks as the day itself.
- **Untrusted output:** the model's JSON is validated against the schema; numbers are parsed to `Decimal` in code; anything invalid = field left empty and highlighted. The model never writes to the database directly.
- **Cost:** this is the **first thing in the app that isn't free**. One model call per scan; expected to be a few cents per photo or less, to be **measured in story S2** and written here. A few stores × 1 scan a day stays a small monthly amount. Anthropic API needs prepaid credits. `AI_SCAN_ENABLED=false` keeps it at $0.

## 8. Acceptance criteria

- [ ] On a phone, an employee can photograph a report and see the worksheet filled in **under 20 s** (typical).
- [ ] On the sample report, all 6 mapped fields and the 2 pay-out lines match the slip, **and C4 is flagged** (the 8-cent case).
- [ ] Fields below the confidence threshold or in a failed check are highlighted; others aren't.
- [ ] Editing an AI value marks it `ai_corrected`; untouched AI values stay `ai`; typed values stay `typed`.
- [ ] A report dated differently from the worksheet shows the C6 warning.
- [ ] The owner sees the photo, the AI/corrected tags with the original AI value, and the check results on Day detail.
- [ ] Employees can't scan or view photos for stores they don't belong to (test).
- [ ] With `AI_SCAN_ENABLED=false`, the button is hidden and the endpoint returns 503; everything else works.
- [ ] AI provider down / bad photo → friendly message, worksheet unchanged, manual entry works.
- [ ] **Accuracy check:** on 10 real report photos from the owner (good, blurry, angled, crumpled), ≥ 95% of fields read correctly, and every misread is either highlighted or caught by a check. Results recorded in this doc.

## 9. Stories (build in this order)

| # | Story | Done when |
| --- | --- | --- |
| S1 | **Photo upload + storage**: bucket, migration 003, upload endpoint (store file + `attachments` row, no AI yet), signed-URL endpoint, browser shrinks the photo | Employee attaches a photo to a day; owner sees it on Day detail |
| S2 | **Extractor**: `extractor.py` with the model call + schema for the report type; fixture-based tests with a stubbed model; record real cost per scan | Running it on the sample photo returns the sample values |
| S3 | **Checks**: C1-C7 as pure functions in `scans/checks.py` with tests using the sample numbers (including the 8-cent failure) | Tests pass |
| S4 | **Scan endpoint**: ties S1-S3 together, saves `report_uploads`, permission tests, `AI_SCAN_ENABLED` flag | `POST /scans` returns proposed values + checks |
| S5 | **Worksheet UI**: Scan button, progress, fill + AI tags, highlights, banner, `ai_corrected` tracking | Click-through with `make demo` (stubbed extractor in demo mode) |
| S6 | **Owner view**: photo, AI/corrected tags with original value, checks summary on Day detail | Owner click-through |
| S7 | **Go live**: secrets in Secret Manager, `deploy.sh` passes the new settings, timeout 120 s, accuracy check on 10 real photos | Acceptance criteria all ticked |

`make demo` gets a **fake extractor** (returns the sample values after 2 s) so the whole flow can be shown without an API key or cost.

## 10. Open questions (for the owner)

1. **Can we get photos of the daily shift-close report** (5-10 different days, different stores)? The month report is only the sample.
2. Is there a separate **fuel / pump report** with gallons? (Would fill `gallons` later.)
3. One worksheet per **day** or per **shift**? (Affects which report is scanned.)
4. Do the paid-outs on the slip ("Pay out", "In house") always mean **cash** from the drawer?
5. Is a few cents per scan OK, or keep scanning **owner-only** at first?

## 11. Later (not in this feature)

- Fuel/pump report → gallons.
- Paste or forward a **text message** → draft worksheet.
- Owner-side AI flags for unusual days (over/short trend, sales far from normal).
- AI-suggested QuickBooks expense account from the payee name.
