-- 009 (Oct 9): release log. ADD-ONLY: one new table.
-- The API writes a row when it starts with a new version or commit (see app/core/release.py).
create table releases (
    id           bigserial primary key,
    env          text not null,                 -- test | production | demo
    version      text not null,                 -- from the VERSION file, e.g. 2026.10.3
    git_commit   text not null,                 -- short commit the API was built from
    deployed_by  text,                          -- from deploy.sh (the Google account that ran it)
    started_at   timestamptz not null default now()
);
create index releases_env_idx on releases (env, started_at desc);

alter table releases enable row level security;
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    revoke all on releases from anon, authenticated;
  end if;
end $$;
