-- 010 (Oct 10): request log for the admin Monitor page (docs/features/admin-monitor.md). ADD-ONLY: one new table.
-- One row per API request (not /api/health or OPTIONS), written after the answer was sent.
-- No ids from the URL, no query values, no request bodies, no IP address. Rows older than 90 days are removed on API start.
create table api_requests (
    id          bigserial primary key,
    at          timestamptz not null default now(),
    person_id   uuid references people(id) on delete set null,   -- who is signed in (the admin while using View as)
    viewed_as   uuid references people(id) on delete set null,   -- View as: whose app the admin was looking at
    method      text not null,
    route       text not null,                                   -- route template, e.g. /api/reports/{report_id}
    page        text,                                            -- screen the request came from (X-Page), ids replaced by :id
    status      int not null,
    ms          int not null,
    device      text                                             -- phone | tablet | computer
);
create index api_requests_at_idx on api_requests (at desc);
create index api_requests_person_idx on api_requests (person_id, at desc);

alter table api_requests enable row level security;
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    revoke all on api_requests from anon, authenticated;
  end if;
end $$;
