-- 007: the owner's books (Oct 8): vendors, typed purchases / expenses, balance-sheet lines.
-- ADD-ONLY: three new tables; nothing existing is changed.
-- store_id null = "All stores (shared)", e.g. insurance for the whole group.

create table vendors (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    kind        text not null check (kind in ('fuel', 'merchandise', 'expense')),  -- fuel/merchandise = cost of goods
    active      boolean not null default true,
    created_at  timestamptz not null default now()
);
create unique index vendors_name_idx on vendors (lower(name));

-- Purchases and expenses the owner types in for a month (his P&L "What you paid this month")
create table ledger_entries (
    id           uuid primary key default gen_random_uuid(),
    month        date not null check (extract(day from month) = 1),     -- first day of the month
    store_id     uuid references stores(id),
    category     text not null check (category in ('fuel_purchase', 'merchandise_purchase', 'expense')),
    description  text not null,
    vendor_id    uuid references vendors(id),
    amount       numeric(12,2) not null check (amount >= 0),
    created_by   uuid references people(id),
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);
create index ledger_entries_month_idx on ledger_entries (month, store_id);

-- Balance sheet lines the owner types for the end of a month
create table balance_lines (
    id        uuid primary key default gen_random_uuid(),
    month     date not null check (extract(day from month) = 1),
    store_id  uuid references stores(id),
    section   text not null check (section in ('asset', 'liability', 'equity')),
    name      text not null,
    amount    numeric(14,2) not null,                                     -- equity can be negative (owner draws)
    position  int not null default 0
);
create index balance_lines_month_idx on balance_lines (month, store_id);

-- Same lock as every other table (see 002): only our API can reach them.
alter table vendors        enable row level security;
alter table ledger_entries enable row level security;
alter table balance_lines  enable row level security;
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    revoke all on vendors, ledger_entries, balance_lines from anon, authenticated;
  end if;
end $$;
