"""Queries behind the admin Monitor page: who's online, traffic, usage and history.

"Online" = any request or ping in the last 2 minutes. A visit = requests less than 30 minutes apart.
Active minutes = distinct minutes with a request or ping. Pings (/api/me/ping) never count as traffic.
"""

from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg import Connection

from app.core import db
from app.core.config import get_settings
from app.core.dates import business_today
from app.modules.monitor.log import PING_ROUTE

ONLINE_MINUTES = 2
VISIT_GAP = "30 minutes"
PERIODS = {"release", "today", "7d", "30d"}
HISTORY_KINDS = {
    "worksheet": "a.report_id is not null",
    "vendor": "a.action like 'vendor.%%'",
    "books": "(a.action like 'ledger.%%' or a.action like 'balance.%%')",
    "person": "a.action like 'person.%%'",
    "store": "a.action like 'store.%%'",
    "settings": "(a.action like 'settings.%%' or a.action like 'test_data.%%')",
}

# Rows from the chosen period, without the admin's own unless asked
_SCOPE = """at >= %(since)s and person_id is not null
            and (%(hide)s::uuid is null or person_id <> %(hide)s::uuid)"""


def period_start(conn: Connection, period: str) -> tuple[datetime, str]:
    now = datetime.now(timezone.utc)
    if period == "release":
        row = db.fetch_one(
            conn, "select version, started_at from releases where env = %s order by started_at desc, id desc limit 1",
            [get_settings().app_env],
        )
        if row:
            return row["started_at"], f"since release {row['version']}"
        period = "7d"
    if period == "today":
        tz = ZoneInfo(get_settings().business_timezone)
        return datetime.combine(business_today(), time.min, tzinfo=tz), "today"
    days = 30 if period == "30d" else 7
    return now - timedelta(days=days), f"last {days} days"


def live(conn: Connection, hide: UUID | None) -> dict:
    p = {"hide": hide, "ping": PING_ROUTE, "mins": ONLINE_MINUTES}
    online = db.fetch_all(
        conn,
        """select distinct on (r.person_id) r.person_id, p.name, p.role, r.page, r.device, r.at as last_at,
                  v.name as viewing_as
           from api_requests r join people p on p.id = r.person_id
           left join people v on v.id = r.viewed_as
           where r.at > now() - make_interval(mins => %(mins)s)
             and (%(hide)s::uuid is null or r.person_id <> %(hide)s::uuid)
           order by r.person_id, r.at desc""",
        p,
    )
    online.sort(key=lambda r: r["last_at"], reverse=True)
    per_minute = db.fetch_all(
        conn,
        """select m.minute,
                  count(r.id) filter (where r.route <> %(ping)s) as requests,
                  count(r.id) filter (where r.status >= 500) as errors
           from generate_series(date_trunc('minute', now()) - interval '59 minutes', date_trunc('minute', now()),
                                interval '1 minute') as m(minute)
           left join api_requests r on date_trunc('minute', r.at) = m.minute
                and (%(hide)s::uuid is null or r.person_id is distinct from %(hide)s::uuid)
           group by m.minute order by m.minute""",
        p,
    )
    return {"online": online, "per_minute": per_minute, "online_minutes": ONLINE_MINUTES}


def usage(conn: Connection, period: str, hide: UUID | None) -> dict:
    since, label = period_start(conn, period)
    p = {"since": since, "hide": hide, "ping": PING_ROUTE, "tz": get_settings().business_timezone}
    totals = db.fetch_one(
        conn,
        f"""select count(*) filter (where route <> %(ping)s) as requests,
                   count(distinct person_id) as people,
                   count(*) filter (where status >= 500) as errors,
                   count(*) filter (where ms > 2000 and route <> %(ping)s) as slow
            from api_requests where {_SCOPE}""",
        p,
    )
    people = db.fetch_all(
        conn,
        f"""with r as (
                select person_id, at, route, device, status,
                       case when at - lag(at) over (partition by person_id order by at) <= interval '{VISIT_GAP}'
                            then 0 else 1 end as new_visit
                from api_requests where {_SCOPE})
            select p.id as person_id, p.name, p.role,
                   sum(r.new_visit)::int as visits,
                   count(distinct date_trunc('minute', r.at))::int as active_minutes,
                   (count(*) filter (where r.route <> %(ping)s))::int as requests,
                   (count(*) filter (where r.status >= 500))::int as errors,
                   min(r.at) as first_seen, max(r.at) as last_seen,
                   mode() within group (order by r.device) as device
            from r join people p on p.id = r.person_id
            group by p.id order by max(r.at) desc""",
        p,
    )
    screens = db.fetch_all(
        conn,
        f"""select person_id, page, count(*) as n from api_requests
            where {_SCOPE} and page is not null group by person_id, page order by person_id, n desc""",
        p,
    )
    top: dict[UUID, list[str]] = {}
    for s in screens:
        top.setdefault(s["person_id"], [])
        if len(top[s["person_id"]]) < 3:
            top[s["person_id"]].append(s["page"])
    for person in people:
        person["screens"] = top.get(person["person_id"], [])
    days = db.fetch_all(
        conn,
        f"""select (at at time zone %(tz)s)::date as day,
                   count(distinct person_id) as people,
                   count(*) filter (where route <> %(ping)s) as requests,
                   count(*) filter (where status >= 500) as errors
            from api_requests where {_SCOPE} group by 1 order by 1 desc""",
        p,
    )
    # Problems: server errors and refusals, not "sign-in expired" (401, routine)
    problems = db.fetch_all(
        conn,
        """select r.at, p.name, r.method, r.route, r.page, r.status, r.ms
           from api_requests r left join people p on p.id = r.person_id
           where r.at >= %(since)s and r.status >= 400 and r.status <> 401
             and (%(hide)s::uuid is null or r.person_id is distinct from %(hide)s::uuid)
           order by r.at desc limit 20""",
        p,
    )
    slowest = db.fetch_all(
        conn,
        f"""select method, route, count(*) as requests, round(avg(ms))::int as avg_ms, max(ms) as max_ms
            from api_requests where {_SCOPE} and route <> %(ping)s
            group by method, route order by avg(ms) desc limit 8""",
        p,
    )
    return {"period": period, "label": label, "since": since, "totals": totals, "people": people,
            "days": days, "problems": problems, "slowest": slowest}


def history(conn: Connection, person_id: UUID | None, kind: str | None, before: int | None, limit: int) -> dict:
    where = ["true"]
    params: dict = {"limit": limit + 1}
    if person_id:
        where.append("a.actor_id = %(person)s")
        params["person"] = person_id
    if kind:
        where.append(HISTORY_KINDS[kind])
    if before:  # "Show more": rows older than the last one shown (time first, id breaks ties)
        where.append("(a.at, a.id) < (select b.at, b.id from audit_log b where b.id = %(before)s)")
        params["before"] = before
    rows = db.fetch_all(
        conn,
        f"""select a.id, a.at, a.action, a.details, a.report_id, p.name as who, p.role,
                   d.business_date, s.name as store
            from audit_log a
            left join people p on p.id = a.actor_id
            left join daily_reports d on d.id = a.report_id
            left join stores s on s.id = d.store_id
            where {' and '.join(where)}
            order by a.at desc, a.id desc limit %(limit)s""",
        params,
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return {"rows": rows, "next_before": rows[-1]["id"] if more else None}
