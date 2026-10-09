// Staff's recent worksheets, newest first, grouped by month: fuel and merchandise sales, over/short, when it
// was submitted, and each month's totals (calculated by the API). "Show 30 more days" goes further back.
// Days sent back are shown at the top with the owner's note.

import { Fragment, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { MonthTotal, ReportSummary } from "../api/types";
import { Notice } from "../components/Notice";
import { StatusChip } from "../components/StatusChip";
import { prettyDate, prettyTime, today } from "../lib/dates";
import { formatOverShort, money, toCents } from "../lib/money";

const monthLabel = (key: string) => {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
};
const gal = (v: string) => Number(v).toLocaleString("en-US", { maximumFractionDigits: 1 });

function OverShort({ value }: { value: string }) {
  const os = toCents(value);
  return <span className={os < 0 ? "neg" : os > 0 ? "pos" : ""}>{os === 0 ? "Balanced" : formatOverShort(os)}</span>;
}

/** Fuel and merchandise on two lines, so the table fits a phone */
function Sales({ fuel, merch, gallons }: { fuel: string; merch: string; gallons: string }) {
  return (
    <div className="sales-cell">
      <div><span className="muted small">Fuel</span> {money(fuel)}</div>
      <div className="stamp">{gal(gallons)} gal</div>
      <div><span className="muted small">Merch</span> {money(merch)}</div>
    </div>
  );
}

export function MyDaysPage() {
  const [days, setDays] = useState<ReportSummary[]>([]);
  const [months, setMonths] = useState<Record<string, MonthTotal>>({});
  const [nextUntil, setNextUntil] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((until: string) => {
    setLoading(true);
    api.reports.history(until, 30)
      .then((page) => {
        setDays((prev) => [...prev, ...page.days.filter((d) => !prev.some((p) => p.id === d.id))]);
        setMonths((prev) => ({ ...prev, ...Object.fromEntries(page.months.map((m) => [`${m.month}|${m.store_id}`, m])) }));
        setNextUntil(page.next_until);
        setLoaded(true);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => load(today()), [load]);

  const returned = days.filter((r) => r.status === "returned");
  const byMonth = new Map<string, ReportSummary[]>();
  days.forEach((d) => {
    const key = d.business_date.slice(0, 7);
    byMonth.set(key, [...(byMonth.get(key) ?? []), d]);
  });
  const manyStores = new Set(days.map((d) => d.store_id)).size > 1;
  const link = (r: ReportSummary) => `/worksheet?store=${r.store_id}&date=${r.business_date}`;

  return (
    <main className="page narrow stack">
      <div className="page-head"><h1>My days</h1><span className="muted">Newest first</span></div>
      {error && <Notice kind="error">{error}</Notice>}
      {loaded && days.length === 0 && !nextUntil && <Notice kind="info">Nothing yet. Your submitted worksheets will show up here.</Notice>}

      {returned.map((r) => (
        <div key={r.id} className="notice notice-error stack" style={{ gap: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <strong>{prettyDate(r.business_date)} · {r.store_name}</strong><StatusChip status="returned" />
          </div>
          <span>“{r.review_note}”</span>
          <Link className="btn btn-dark" to={link(r)} style={{ alignSelf: "flex-start" }}>Fix and resend</Link>
        </div>
      ))}

      {[...byMonth.entries()].map(([month, rows]) => {
        const totals = Object.values(months).filter((m) => m.month === month);
        return (
          <section key={month} className="stack" style={{ gap: 8 }}>
            <h2 className="report-h2">{monthLabel(month)}</h2>
            <div className="table-wrap">
              <table className="my-days">
                <thead><tr><th className="left">Day</th><th>Sales</th><th>Over / (short)</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td className="left">
                        <Link to={link(r)}>{prettyDate(r.business_date)}</Link>
                        {manyStores && <div className="muted small">{r.store_name}</div>}
                        <div className="stamp">{r.submitted_at ? `Submitted ${prettyTime(r.submitted_at)}` : "Not submitted yet"}</div>
                      </td>
                      <td><Sales fuel={r.fuel_sale} merch={r.merch_sale} gallons={r.gallons} /></td>
                      <td><OverShort value={r.over_short} /><div style={{ marginTop: 4 }}><StatusChip status={r.status} /></div></td>
                    </tr>
                  ))}
                </tbody>
                {totals.length > 0 && (
                  <tfoot>
                    {totals.map((t) => (
                      <Fragment key={t.store_id}>
                        <tr className="month-total">
                          <td className="left">
                            {monthLabel(month).split(" ")[0]} total{(manyStores || totals.length > 1) && <div className="muted small">{t.store_name}</div>}
                            <div className="stamp">{t.days} day{t.days === 1 ? "" : "s"} counted · {t.days_short} short</div>
                          </td>
                          <td><Sales fuel={t.fuel_sale} merch={t.merch_sale} gallons={t.gallons} /></td>
                          <td><OverShort value={t.over_short} /></td>
                        </tr>
                      </Fragment>
                    ))}
                  </tfoot>
                )}
              </table>
            </div>
          </section>
        );
      })}

      {loaded && (
        <p className="muted small" style={{ margin: 0 }}>
          Month totals count submitted and approved days for the whole month (not drafts or days sent back).
        </p>
      )}
      {nextUntil && (
        <button type="button" className="btn btn-ghost" disabled={loading} onClick={() => load(nextUntil)} style={{ alignSelf: "center" }}>
          {loading ? "Loading…" : "Show 30 more days"}
        </button>
      )}
      {loading && !loaded && <p className="muted">Loading…</p>}
    </main>
  );
}
