// Admin Monitor: who's online, live traffic, usage and history. App admin only (docs/features/admin-monitor.md).
// Refreshes by itself while the tab is on screen: online + traffic every 15 s, usage every 30 s.
import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { ROLE_NAMES, type HistoryKind, type HistoryRow, type MonitorHistory, type MonitorLive, type MonitorPeriod, type MonitorUsage } from "../api/types";
import { Notice } from "../components/Notice";
import { prettyDate, prettyTime } from "../lib/dates";

const PERIODS: { id: MonitorPeriod; label: string }[] = [
  { id: "release", label: "Since last release" }, { id: "today", label: "Today" }, { id: "7d", label: "7 days" }, { id: "30d", label: "30 days" },
];
const KINDS: { id: HistoryKind | ""; label: string }[] = [
  { id: "", label: "Everything" }, { id: "worksheet", label: "Worksheets" }, { id: "vendor", label: "Vendors" },
  { id: "books", label: "Purchases, expenses, balances" }, { id: "person", label: "People" }, { id: "store", label: "Stores" },
  { id: "settings", label: "Settings" },
];

/** Runs `fn` now and every `ms` while the tab is visible (and again when it becomes visible). */
function usePolling(fn: () => void, ms: number) {
  useEffect(() => {
    const tick = () => { if (document.visibilityState === "visible") fn(); };
    fn();
    const t = window.setInterval(tick, ms);
    document.addEventListener("visibilitychange", tick);
    return () => { window.clearInterval(t); document.removeEventListener("visibilitychange", tick); };
  }, [fn, ms]);
}

export function MonitorPage() {
  const [includeMe, setIncludeMe] = useState(false);
  const [period, setPeriod] = useState<MonitorPeriod>("release");
  const [live, setLive] = useState<MonitorLive | null>(null);
  const [usage, setUsage] = useState<MonitorUsage | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadLive = useCallback(() => {
    api.monitor.live(includeMe).then((l) => { setLive(l); setUpdated(new Date()); setError(null); })
      .catch((e: Error) => setError(e.message));
  }, [includeMe]);
  const loadUsage = useCallback(() => {
    api.monitor.usage(period, includeMe).then(setUsage).catch((e: Error) => setError(e.message));
  }, [period, includeMe]);
  usePolling(loadLive, 15_000);
  usePolling(loadUsage, 30_000);

  return (
    <main className="page stack">
      <div className="page-head">
        <div>
          <h1>Monitor</h1>
          <div className="muted">App admin only · updates by itself every 15 s{updated ? ` · last ${updated.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" })}` : ""}</div>
        </div>
        <label className="check-inline">
          <input type="checkbox" checked={includeMe} onChange={(e) => setIncludeMe(e.target.checked)} /> Include me
        </label>
      </div>
      {error && <Notice kind="error">{error}</Notice>}

      <div className="grid-2">
        <OnlineNow live={live} />
        <Traffic live={live} />
      </div>

      <section className="card">
        <div className="card-head monitor-head">
          <span>Usage · {usage?.label ?? "…"}</span>
          <div className="segmented" role="tablist" aria-label="Period">
            {PERIODS.map((p) => (
              <button key={p.id} type="button" className={period === p.id ? "on" : ""} onClick={() => setPeriod(p.id)}>{p.label}</button>
            ))}
          </div>
        </div>
        <div className="card-body stack" style={{ paddingTop: 12 }}>
          {usage && <Usage usage={usage} />}
        </div>
      </section>

      <HistoryCard />
    </main>
  );
}

function ago(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s} s ago`;
  const m = Math.round(s / 60);
  return m < 60 ? `${m} min ago` : prettyTime(iso);
}

function OnlineNow({ live }: { live: MonitorLive | null }) {
  const online = live?.online ?? [];
  return (
    <section className="card">
      <div className="card-head">Online now · {live ? online.length : "…"}</div>
      <div className="card-body">
        <p className="muted" style={{ margin: "4px 0 10px" }}>Used the app in the last {live?.online_minutes ?? 2} minutes.</p>
        {live && online.length === 0 && <p className="muted">Nobody right now.</p>}
        {online.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Who</th><th className="left">Screen</th><th className="left">Device</th><th>Last</th></tr></thead>
              <tbody>
                {online.map((p) => (
                  <tr key={p.person_id}>
                    <td className="left"><span className="dot-online" aria-hidden /> <strong>{p.name}</strong>
                      <div className="muted">{ROLE_NAMES[p.role] ?? p.role}{p.viewing_as ? ` · viewing as ${p.viewing_as}` : ""}</div></td>
                    <td className="left">{p.page ?? "–"}</td>
                    <td className="left">{p.device ?? "–"}</td>
                    <td>{ago(p.last_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

function Traffic({ live }: { live: MonitorLive | null }) {
  const mins = live?.per_minute ?? [];
  const max = Math.max(1, ...mins.map((m) => m.requests));
  const total = mins.reduce((a, m) => a + m.requests, 0);
  const errors = mins.reduce((a, m) => a + m.errors, 0);
  return (
    <section className="card">
      <div className="card-head">Traffic · last 60 minutes</div>
      <div className="card-body">
        <p className="muted" style={{ margin: "4px 0 10px" }}>
          {total} requests{errors ? ` · ${errors} server errors` : " · no server errors"} (the once-a-minute "I'm here" pings aren't counted)
        </p>
        <div className="minute-bars" role="img" aria-label={`Requests per minute, last 60 minutes: ${total} in total`}>
          {mins.map((m) => (
            <div key={m.minute} className={`minute-bar${m.errors ? " has-error" : ""}`}
              style={{ height: `${m.requests ? Math.max(6, (m.requests / max) * 100) : 2}%` }}
              title={`${new Date(m.minute).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}: ${m.requests} requests${m.errors ? `, ${m.errors} errors` : ""}`} />
          ))}
        </div>
        <div className="minute-axis muted"><span>60 min ago</span><span>now</span></div>
      </div>
    </section>
  );
}

function Usage({ usage }: { usage: MonitorUsage }) {
  const t = usage.totals;
  return (
    <>
      <p className="muted" style={{ margin: 0 }}>From {prettyTime(usage.since)}. A visit = requests less than 30 minutes apart. Active minutes = minutes with the app open.</p>
      <div className="stat-row monitor-stats">
        <div className="stat"><div className="muted">People</div><div className="v">{t.people}</div></div>
        <div className="stat"><div className="muted">Requests</div><div className="v">{t.requests}</div></div>
        <div className={`stat${t.errors ? " stat-warn" : ""}`}><div className="muted">Server errors</div><div className="v">{t.errors}</div></div>
        <div className={`stat${t.slow ? " stat-warn" : ""}`}><div className="muted">Slow (over 2 s)</div><div className="v">{t.slow}</div></div>
      </div>

      <h3 className="monitor-sub">Who used it</h3>
      {usage.people.length === 0 ? <p className="muted">Nobody in this period.</p> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th className="left">Who</th><th>Visits</th><th>Active min</th><th>Requests</th><th>Errors</th>
              <th className="left">Screens used most</th><th className="left">Device</th><th className="left">Last seen</th></tr></thead>
            <tbody>
              {usage.people.map((p) => (
                <tr key={p.person_id}>
                  <td className="left"><strong>{p.name}</strong><div className="muted">{ROLE_NAMES[p.role] ?? p.role}</div></td>
                  <td>{p.visits}</td><td>{p.active_minutes}</td><td>{p.requests}</td>
                  <td className={p.errors ? "bad-text" : ""}>{p.errors}</td>
                  <td className="left">{p.screens.join(", ") || "–"}</td>
                  <td className="left">{p.device ?? "–"}</td>
                  <td className="left">{ago(p.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid-2">
        <div>
          <h3 className="monitor-sub">Per day</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Day</th><th>People</th><th>Requests</th><th>Errors</th></tr></thead>
              <tbody>
                {usage.days.map((d) => (
                  <tr key={d.day}><td className="left">{prettyDate(d.day)}</td><td>{d.people}</td><td>{d.requests}</td>
                    <td className={d.errors ? "bad-text" : ""}>{d.errors}</td></tr>
                ))}
                {usage.days.length === 0 && <tr><td colSpan={4} className="left muted">No use yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h3 className="monitor-sub">Slowest requests</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">What</th><th>Count</th><th>Avg</th><th>Max</th></tr></thead>
              <tbody>
                {usage.slowest.map((s) => (
                  <tr key={s.method + s.route}><td className="left"><code>{s.method} {s.route.replace("/api", "")}</code></td>
                    <td>{s.requests}</td><td>{ms(s.avg_ms)}</td><td>{ms(s.max_ms)}</td></tr>
                ))}
                {usage.slowest.length === 0 && <tr><td colSpan={4} className="left muted">No requests yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <h3 className="monitor-sub">Problems (latest 20)</h3>
      <p className="muted" style={{ margin: 0 }}>Server errors (5xx) and refused requests (4xx). "Sign-in expired" (401) is routine and left out.</p>
      {usage.problems.length === 0 ? <p className="muted">None. 👍</p> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th className="left">When</th><th className="left">Who</th><th className="left">What</th><th className="left">Screen</th><th>Status</th><th>Time</th></tr></thead>
            <tbody>
              {usage.problems.map((p, i) => (
                <tr key={i}>
                  <td className="left">{prettyTime(p.at)}</td><td className="left">{p.name ?? "signed out"}</td>
                  <td className="left"><code>{p.method} {p.route.replace("/api", "")}</code></td><td className="left">{p.page ?? "–"}</td>
                  <td className={p.status >= 500 ? "bad-text" : ""}>{p.status}</td><td>{ms(p.ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

const ms = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)} s` : `${n} ms`);

function HistoryCard() {
  const [person, setPerson] = useState("");
  const [kind, setKind] = useState<HistoryKind | "">("");
  const [data, setData] = useState<MonitorHistory | null>(null);
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.monitor.history({ person_id: person || undefined, kind: kind || undefined })
      .then((h) => { setData(h); setRows(h.rows); setError(null); }).catch((e: Error) => setError(e.message));
  }, [person, kind]);
  useEffect(load, [load]);

  const more = () => {
    if (!data?.next_before) return;
    api.monitor.history({ person_id: person || undefined, kind: kind || undefined, before: data.next_before })
      .then((h) => { setData(h); setRows((r) => [...r, ...h.rows]); }).catch((e: Error) => setError(e.message));
  };

  return (
    <section className="card">
      <div className="card-head monitor-head">
        <span>History · everything people did</span>
        <button type="button" className="btn btn-sm" onClick={load}>Refresh</button>
      </div>
      <div className="card-body stack" style={{ paddingTop: 12 }}>
        <div className="row-wrap">
          <label className="field"><span>Person</span>
            <select value={person} onChange={(e) => setPerson(e.target.value)}>
              <option value="">Everyone</option>
              {(data?.people ?? []).map((p) => <option key={p.id} value={p.id}>{p.name} ({ROLE_NAMES[p.role] ?? p.role})</option>)}
            </select>
          </label>
          <label className="field"><span>Kind</span>
            <select value={kind} onChange={(e) => setKind(e.target.value as HistoryKind | "")}>
              {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
            </select>
          </label>
        </div>
        {error && <Notice kind="error">{error}</Notice>}
        <div className="table-wrap">
          <table className="history-table">
            <thead><tr><th className="left">When</th><th className="left">Who</th><th className="left">What</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="left">{prettyTime(r.at)}</td>
                  <td className="left">{r.who ?? "–"}{r.role ? <div className="muted">{ROLE_NAMES[r.role] ?? r.role}</div> : null}</td>
                  <td className="left wrap">{describe(r)}</td>
                </tr>
              ))}
              {data && rows.length === 0 && <tr><td colSpan={3} className="left muted">Nothing yet.</td></tr>}
            </tbody>
          </table>
        </div>
        {data?.next_before && <div><button type="button" className="btn" onClick={more}>Show more</button></div>}
      </div>
    </section>
  );
}

const WORKSHEET_VERBS: Record<string, string> = {
  created: "Started", saved: "Saved", submitted: "Submitted", returned: "Sent back", approved: "Approved",
  reopened: "Reopened", exported: "Exported to QuickBooks",
};
const SETTING_NAMES: Record<string, string> = {
  qb_accounts: "QuickBooks accounts", over_short_alert: "over/short alert", sales_tax_rate: "sales tax rate",
  reorder_percent: '"Order soon" %',
};
type D = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const money = (v: unknown) => (v === undefined || v === null ? "" : ` $${Number(v).toFixed(2)}`);

/** One history row in plain words */
export function describe(r: HistoryRow): string {
  const d = r.details as D;
  if (r.report_id || WORKSHEET_VERBS[r.action]) {
    const where = [r.store, r.business_date ? prettyDate(r.business_date) : null].filter(Boolean).join(" · ");
    const note = d?.note || d?.reason ? `: "${d.note ?? d.reason}"` : "";
    return `${WORKSHEET_VERBS[r.action] ?? r.action} worksheet${where ? ` · ${where}` : ""}${note}`;
  }
  switch (r.action) {
    case "vendor.added": return `Added vendor ${d.name} (${d.kind})`;
    case "vendor.deleted": return `Removed vendor ${d.name}`;
    case "vendor.changed": {
      const b = d.before ?? {}, a = d.after ?? {};
      const parts = [b.name !== a.name && `renamed ${b.name} → ${a.name}`, b.kind !== a.kind && `type ${b.kind} → ${a.kind}`,
        b.active !== a.active && (a.active ? "reactivated" : "deactivated")].filter(Boolean);
      return `Vendor ${a.name}: ${parts.join(", ") || "saved"}`;
    }
    case "ledger.added": return `Added ${label(d.category)}: ${d.vendor_name || d.description || ""}${money(d.amount)}`;
    case "ledger.changed": return `Changed ${label(d.after?.category ?? d.category)}: ${d.after?.vendor_name || d.after?.description || ""}${money(d.after?.amount)}`;
    case "ledger.deleted": return `Removed ${label(d.category)}: ${d.vendor_name || d.description || ""}${money(d.amount)}`;
    case "balance.saved": return `Saved balance sheet for ${d.month}`;
    case "balance.copied": return `Copied balance sheet ${d.from} → ${d.month}`;
    case "person.invited": return `Added ${d.name} (${roleName(d.role)})${d.stores?.length ? ` · ${d.stores.join(", ")}` : ""}`;
    case "person.removed": return `Removed ${d.name} (${roleName(d.role)})`;
    case "person.changed": {
      const b = d.before ?? {}, a = d.after ?? {};
      const parts = [
        b.name !== a.name && `name ${b.name} → ${a.name}`, b.email !== a.email && `email changed`,
        b.role !== a.role && `${roleName(b.role)} → ${roleName(a.role)}`,
        b.active !== a.active && (a.active ? "reactivated" : "deactivated"),
        JSON.stringify(b.stores) !== JSON.stringify(a.stores) && `stores: ${(a.stores ?? []).join(", ") || "none"}`,
      ].filter(Boolean);
      return `Changed ${a.name}: ${parts.join(", ") || "saved, no change"}`;
    }
    case "store.added": return `Added store ${d.name}`;
    case "store.removed": return `Removed store ${d.name}`;
    case "store.changed": {
      const b = d.before ?? {}, a = d.after ?? {};
      const parts = [b.name !== a.name && `renamed ${b.name} → ${a.name}`, b.qb_location !== a.qb_location && "QuickBooks location",
        b.active !== a.active && (a.active ? "reactivated" : "deactivated"),
        JSON.stringify(b.tanks) !== JSON.stringify(a.tanks) && "tanks",
        JSON.stringify(b.tank_specs) !== JSON.stringify(a.tank_specs) && "tank sizes / fuel types"].filter(Boolean);
      return `Store ${a.name}: ${parts.join(", ") || "saved, no change"}`;
    }
    case "settings.saved": return `Changed settings: ${Object.keys(d.changed ?? {}).map((k) => SETTING_NAMES[k] ?? k).join(", ")}`;
    case "test_data.reset": return "Reset test data";
    default: return r.action;
  }
}
const label = (c?: string) => ({ fuel_purchase: "fuel delivery", merchandise_purchase: "merchandise purchase", expense: "expense" }[c ?? ""] ?? "entry");
const roleName = (r?: string) => (r ? (ROLE_NAMES as Record<string, string>)[r] ?? r : "");
