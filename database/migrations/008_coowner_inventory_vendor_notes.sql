-- 008 (Oct 9): owner's call. ADD-ONLY: new columns and a wider role check; no existing row is changed.
-- Spec: docs/features/owner-call-oct9.md

-- Co-owner: same powers as the owner (only the owner manages owners / co-owners; checked in the API)
alter table people drop constraint if exists people_role_check;
alter table people add constraint people_role_check
    check (role in ('employee', 'manager', 'owner', 'coowner', 'admin'));

-- Fuel type and capacity per tank name: {"Tank 1 – Regular": {"grade": "Regular", "capacity": 10000}}
-- (stores.tanks stays the ordered list of names)
alter table stores add column if not exists tank_specs jsonb not null default '{}'::jsonb;

-- A fuel delivery = a fuel purchase with a date, a tank and gallons (so the P&L counts it once)
alter table ledger_entries add column if not exists entry_date date;
alter table ledger_entries add column if not exists tank text;
alter table ledger_entries add column if not exists gallons numeric(10,1) check (gallons is null or gallons > 0);
alter table ledger_entries drop constraint if exists ledger_entries_date_in_month;
alter table ledger_entries add constraint ledger_entries_date_in_month
    check (entry_date is null or date_trunc('month', entry_date)::date = month);
alter table ledger_entries drop constraint if exists ledger_entries_gallons_fuel_only;
alter table ledger_entries add constraint ledger_entries_gallons_fuel_only
    check (gallons is null or (category = 'fuel_purchase' and store_id is not null and entry_date is not null and tank is not null));
create index if not exists ledger_entries_delivery_idx on ledger_entries (store_id, entry_date) where gallons is not null;

-- Paid out to "Miscellaneous": what it was, so the owner can add the vendor
alter table paid_outs add column if not exists note text;
