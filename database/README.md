# database

Plain SQL migrations, applied in file-name order.

- `migrations/001_initial_schema.sql` creates every table.
- Add a change as a new file (`002_add_something.sql`). Never edit a migration that has already run.

Apply them with:

```bash
cd services/api
python -m scripts.migrate        # reads DATABASE_URL from .env
```

The script records applied files in a `schema_migrations` table, so running it twice is safe.

| Table | What it holds |
| --- | --- |
| `stores` | Gas stations |
| `people` | Everyone allowed to sign in (invite list) and their role |
| `store_members` | Which stores each person works at |
| `daily_reports` | One worksheet per store per day, plus its workflow status |
| `paid_outs` | Cash and check paid-out lines for a worksheet |
| `attachments` | Shift-report photos (pointer to file storage) |
| `report_uploads` | AI extractions of register reports (next step) |
| `audit_log` | Who did what, when |
| `settings` | QuickBooks account names, over/short alert threshold |
