// Owner's review queue. The boxes on top are counts AND filters: click one to see those days.
// "Missing" = a past day (not today) in the date range where a store has no worksheet at all,
// counted only from the day the store was added (or its first worksheet).

import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { ReportSummary, Status } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Notice } from "../components/Notice";
import { StatusChip } from "../components/StatusChip";
import { dateRange, daysAgo, prettyDate, today } from "../lib/dates";
import { formatMoney, formatOverShort, toCents } from "../lib/money";

const MISSING = "missing";

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "submitted", label: "Needs review" },
  { value: "approved", label: "Approved, not exported" },
  { value: MISSING, label: "Missing days" },
  { value: "returned", label: "Sent back" },
  { value: "draft", label: "Drafts (not submitted)" },
  { value: "exported", label: "Exported" },
  { value: "", label: "All worksheets" },
];

export function ReviewPage() {
  const { me } = useAuth();
  const navigate = useNavigate();
  const [storeId, setStoreId] = useState("");
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState(searchParams.get("show") ?? "submitted"); // ?show=missing from Reports
  const [dateFrom, setDateFrom] = useState(daysAgo(13));
  const [dateTo, setDateTo] = useState(today());
  const [all, setAll] = useState<ReportSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  // One request for the whole range; the boxes and the table filter it on screen.
  useEffect(() => {
    let current = true;
    api.reports.list({ store_id: storeId || undefined, date_from: dateFrom, date_to: dateTo })
      .then((everything) => {
        if (!current) return;
        setAll(everything);
        setError(null);
      })
      .catch((e) => current && setError(e.message));
    return () => {
      current = false;
    };
  }, [storeId, dateFrom, dateTo]);

  // Missing days, grouped by store: past days only (today isn't over), never before the store started.
  const missingByStore = useMemo(() => {
    const yesterday = daysAgo(1);
    const have = new Set(all.map((r) => `${r.store_id}|${r.business_date}`));
    return (me?.stores ?? [])
      .filter((s) => !storeId || s.id === storeId)
      .map((s) => {
        const since = s.tracking_since ?? dateFrom; // older API: no start date yet
        const from = dateFrom > since ? dateFrom : since;
        const to = dateTo < yesterday ? dateTo : yesterday;
        const dates = from <= to ? dateRange(from, to).reverse().filter((d) => !have.has(`${s.id}|${d}`)) : [];
        return { store: s, dates };
      })
      .filter((g) => g.dates.length > 0);
  }, [all, me, storeId, dateFrom, dateTo]);

  const missingCount = missingByStore.reduce((n, g) => n + g.dates.length, 0);
  const waiting = all.filter((r) => r.status === "submitted").length;
  const unexported = all.filter((r) => r.status === "approved").length;
  const sentBack = all.filter((r) => r.status === "returned").length;
  const netOverShort = all.filter((r) => r.status !== "draft").reduce((s, r) => s + toCents(r.over_short), 0);
  const rows = status === MISSING ? [] : all.filter((r) => !status || r.status === status);

  const tile = (value: string, label: string, count: number, hint: string) => (
    <button type="button" className={`stat stat-btn${status === value ? " active" : ""}${count > 0 && value !== "approved" ? " attention" : ""}`}
      onClick={() => setStatus(value)} aria-pressed={status === value}>
      <div className="muted">{label}</div>
      <div className="v">{count}</div>
      <div className="stat-hint">{hint}</div>
    </button>
  );

  const currentLabel = STATUS_FILTERS.find((f) => f.value === status)?.label ?? "";

  return (
    <main className="page stack">
      <div className="page-head">
        <div>
          <h1>Review queue</h1>
          <div className="muted">{prettyDate(dateFrom)} – {prettyDate(dateTo)} · click a box to filter</div>
        </div>
        <div className="row-wrap">
          <label className="label-stack">Store
            <select value={storeId} onChange={(e) => setStoreId(e.target.value)}>
              <option value="">All stores</option>
              {me?.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label className="label-stack">Show
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUS_FILTERS.map((f) => <option key={f.label} value={f.value}>{f.label}</option>)}
            </select>
          </label>
          <label className="label-stack">From<input type="date" className="text" value={dateFrom} max={dateTo} onChange={(e) => e.target.value && setDateFrom(e.target.value)} /></label>
          <label className="label-stack">To<input type="date" className="text" value={dateTo} min={dateFrom} onChange={(e) => e.target.value && setDateTo(e.target.value)} /></label>
        </div>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      <div className="stat-row">
        {tile("submitted", "Needs your review", waiting, "Submitted by staff, waiting for approve / send back")}
        {tile("approved", "Approved, not exported", unexported, "Ready for the QuickBooks export")}
        {tile(MISSING, "Missing days", missingCount, "Past days with no worksheet started")}
        {tile("returned", "Sent back", sentBack, "Waiting for staff to fix")}
        <div className="stat">
          <div className="muted">Net over/short</div>
          <div className={`v ${netOverShort < 0 ? "neg" : ""}`}>{formatOverShort(netOverShort)}</div>
          <div className="stat-hint">Submitted + approved days in range</div>
        </div>
      </div>

      {status === MISSING ? (
        <section className="card">
          <div className="card-head">Missing days <span className="muted">· click a day to open its worksheet</span></div>
          <div className="card-body stack">
            {missingByStore.length === 0 && <div className="muted">Every store has a worksheet for every past day in this range.</div>}
            {missingByStore.map(({ store, dates }) => (
              <div key={store.id} className="missing-store">
                <div className="missing-store-head">
                  <strong>{store.name}</strong>
                  <span className="muted">{dates.length} day{dates.length === 1 ? "" : "s"}</span>
                </div>
                <div className="date-chips">
                  {dates.map((d) => (
                    <button key={d} type="button" className="date-chip" title="Open this day's worksheet"
                      onClick={() => navigate(`/worksheet?store=${store.id}&date=${d}`)}>{prettyDate(d)}</button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : (
        <div className="table-wrap">
          <table style={{ minWidth: 760 }}>
            <thead>
              <tr>
                <th className="left">Date</th><th className="left">Store</th><th>Total sales</th><th>Expected cash</th>
                <th>Over/(short)</th><th className="left">Submitted by</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const os = toCents(r.over_short);
                return (
                  <tr key={r.id} className="clickable" onClick={() => navigate(`/days/${r.id}`)}>
                    <td className="left"><a href={`/days/${r.id}`} onClick={(e) => e.preventDefault()}>{prettyDate(r.business_date)}</a></td>
                    <td className="left">{r.store_name}</td>
                    <td>{formatMoney(toCents(r.total_sales))}</td>
                    <td>{formatMoney(toCents(r.expected_cash))}</td>
                    <td className={os < 0 ? "neg" : os > 0 ? "pos" : ""}>{formatOverShort(os)}</td>
                    <td className="left">{r.submitted_by_name ?? "—"}</td>
                    <td><StatusChip status={r.status as Status} /></td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr><td colSpan={7} className="left muted" style={{ padding: 24 }}>
                  No worksheets in “{currentLabel}” for these dates.
                  {status === "submitted" && " You're all caught up."}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
