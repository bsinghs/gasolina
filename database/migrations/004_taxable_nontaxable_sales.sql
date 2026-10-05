-- Owner's worksheet (Oct 5): Taxable and Non-taxable amounts are their own sales lines.
-- Total sales = fuel + merchandise + taxable + non-taxable + sales tax
alter table daily_reports
    add column if not exists taxable_sale    numeric(12,2) not null default 0,
    add column if not exists nontaxable_sale numeric(12,2) not null default 0;
