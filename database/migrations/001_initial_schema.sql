-- 001: initial schema for Gasolina (daily sales worksheet app)
-- Money is always numeric(12,2). Totals are calculated by the API (services/api/app/modules/reports/reconciliation.py)
-- and stored here so reports and exports never re-do the math differently.

create extension if not exists pgcrypto;

-- Gas stations / store locations
create table stores (
    id           uuid primary key default gen_random_uuid(),
    name         text not null unique,
    qb_location  text,                         -- QuickBooks Location/Class to tag entries with
    active       boolean not null default true,
    created_at   timestamptz not null default now()
);

-- People who may sign in. Nobody gets in unless they are listed here (invite-only).
create table people (
    id            uuid primary key default gen_random_uuid(),
    email         text not null,
    name          text not null,
    role          text not null check (role in ('employee', 'manager', 'owner')),
    active        boolean not null default true,
    auth_user_id  text unique,                 -- filled on first sign-in (Supabase Auth user id)
    created_at    timestamptz not null default now()
);
create unique index people_email_lower_idx on people (lower(email));

-- Which stores each person can submit for
create table store_members (
    person_id  uuid not null references people(id) on delete cascade,
    store_id   uuid not null references stores(id) on delete cascade,
    primary key (person_id, store_id)
);

-- One worksheet per store per business day
create table daily_reports (
    id              uuid primary key default gen_random_uuid(),
    store_id        uuid not null references stores(id),
    business_date   date not null,
    status          text not null default 'draft'
                    check (status in ('draft', 'submitted', 'returned', 'approved', 'exported')),

    -- what the employee enters
    fuel_sale       numeric(12,2) not null default 0,
    merch_sale      numeric(12,2) not null default 0,
    sales_tax       numeric(12,2) not null default 0,
    gallons         numeric(10,1) not null default 0,
    credit          numeric(12,2) not null default 0,
    debit           numeric(12,2) not null default 0,
    ebt             numeric(12,2) not null default 0,
    cash_drop       numeric(12,2) not null default 0,
    employee_note   text,

    -- calculated by the API on every save
    total_sales     numeric(12,2) not null default 0,
    total_non_cash  numeric(12,2) not null default 0,
    cash_paid_out   numeric(12,2) not null default 0,
    expected_cash   numeric(12,2) not null default 0,
    over_short      numeric(12,2) not null default 0,

    -- where each value came from: {"fuel_sale": "typed" | "ai" | "ai_corrected"}
    field_sources   jsonb not null default '{}'::jsonb,

    -- workflow
    created_by      uuid references people(id),
    submitted_by    uuid references people(id),
    submitted_at    timestamptz,
    reviewed_by     uuid references people(id),
    reviewed_at     timestamptz,
    review_note     text,
    exported_at     timestamptz,
    qb_txn_id       text,                      -- set when posted through the QuickBooks API (later)

    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    unique (store_id, business_date)
);
create index daily_reports_status_idx on daily_reports (status, business_date desc);

-- Paid-out line items (cash from the drawer, or checks)
create table paid_outs (
    id          uuid primary key default gen_random_uuid(),
    report_id   uuid not null references daily_reports(id) on delete cascade,
    kind        text not null check (kind in ('cash', 'check')),
    check_no    text,
    payee       text not null,
    amount      numeric(12,2) not null check (amount >= 0),
    gl_account  text,                          -- expense account the owner picks during review
    position    int not null default 0
);
create index paid_outs_report_idx on paid_outs (report_id);

-- Shift-report photos (file lives in object storage; this is the pointer)
create table attachments (
    id            uuid primary key default gen_random_uuid(),
    report_id     uuid references daily_reports(id) on delete cascade,
    storage_path  text not null,
    content_type  text,
    uploaded_by   uuid references people(id),
    created_at    timestamptz not null default now()
);

-- AI extractions of register reports (filled by the AI service, next step)
create table report_uploads (
    id               uuid primary key default gen_random_uuid(),
    attachment_id    uuid references attachments(id) on delete cascade,
    report_type      text not null,            -- e.g. 'close_month', 'shift_close'
    model            text,
    raw_json         jsonb,
    fields_json      jsonb,
    confidence_json  jsonb,
    checks_json      jsonb,
    status           text not null default 'pending'
                     check (status in ('pending', 'done', 'failed')),
    created_at       timestamptz not null default now()
);

-- Every important action, with what changed
create table audit_log (
    id          bigserial primary key,
    report_id   uuid references daily_reports(id) on delete cascade,
    actor_id    uuid references people(id),
    action      text not null,                 -- created, saved, submitted, returned, approved, reopened, exported
    details     jsonb not null default '{}'::jsonb,
    at          timestamptz not null default now()
);
create index audit_log_report_idx on audit_log (report_id, at);

-- Owner settings: QuickBooks account names, over/short alert threshold
create table settings (
    key    text primary key,
    value  jsonb not null
);

insert into settings (key, value) values
    ('over_short_alert', '20'),
    ('qb_accounts', '{
        "cash": "Undeposited Funds",
        "cards": "Credit Card Clearing",
        "ebt": "EBT Receivable",
        "fuel_sales": "Fuel Sales",
        "merch_sales": "Merchandise Sales",
        "sales_tax": "Sales Tax Payable",
        "over_short": "Cash Over/Short",
        "default_expense": "Miscellaneous Expense"
    }');
