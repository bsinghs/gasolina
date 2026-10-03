-- 002: Nobody reaches these tables except our API.
-- Supabase publishes every table in "public" through its Data API, which anyone holding the
-- public (anon) key can call. Our web app never uses that path, so we switch on row-level
-- security with NO policies: the Data API sees nothing. Our API connects as the database
-- owner, which is not affected by row-level security, so the app keeps working.

alter table stores          enable row level security;
alter table people          enable row level security;
alter table store_members   enable row level security;
alter table daily_reports   enable row level security;
alter table paid_outs       enable row level security;
alter table attachments     enable row level security;
alter table report_uploads  enable row level security;
alter table audit_log       enable row level security;
alter table settings        enable row level security;

-- Belt and braces: take away the Data API roles' table rights too (they only exist on Supabase).
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    revoke all on all tables in schema public from anon, authenticated;
    revoke all on all sequences in schema public from anon, authenticated;
  end if;
end $$;
