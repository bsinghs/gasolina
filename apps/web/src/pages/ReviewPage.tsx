// Owner's review queue: every store x day, with missing days highlighted.

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ReportSummary, Status } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Notice } from "../components/Notice";
import { StatusChip } from "../components/StatusChip";
import { dateRange, daysAgo, prettyDate, today } from "../lib/dates";
import { formatMoney, formatOverShort, toCents } from "../lib/money";

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "submitted", label: "Needs review" },
  { value: "", label: "All" },
  { value: "draft", label: "Drafts" },
  { value: "returned", label: "Sent back" },
  { value: "approved", label: "Approved" },
  { value: "exported", label: "Exported" },
];

export function ReviewPage() {
  const { me } = useAuth();
  const navigate = useNavigate();
  const [storeId, setStoreId] = useState("");
  const [status, setStatus] = useState("submitted");
  const [dateFrom, setDateFrom] = useState(daysAgo(13));
  const [dateTo, setDateTo] = useState(today());
  const [rows, setRows] = useState<ReportSummary[]>([]);
  const [all, setAll] = useState<ReportSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const base = { store_id: storeId || undefined, date_from: dateFrom, date_to: dateTo };
    Promise.all([api.reports.list({ ...base, status: status || undefined }), api.reports.list(base)])
      .then(([filtered, everything]) => {
        setRows(filtered);
        setAll(everything);
      })
      .catch((e) => setError(e.message));
  }, [storeId, status, dateFrom, dateTo]);

  // Days in the last week (up to yesterday) where a store has no worksheet at all
  const missing = useMemo(() => {
    const stores = (me?.stores ?? []).filter((s) => !storeId || s.id === storeId);
    const have = new Set(all.map((r) => `${r.store_id}|${r.business_date}`));
    const from = dateFrom > daysAgo(7) ? dateFrom : daysAgo(7);
    const to = dateTo < daysAgo(1) ? dateTo : daysAgo(1);
    return dateRange(from, to)
      .reverse()
      .flatMap((d) => stores.filter((s) => !have.has(`${s.id}|${d}`)).map((s) => ({ date: d, store: s.name })));
  }, [all, me, storeId, dateFrom, dateTo]);

  const waiting = all.filter((r) => r.status === "submitted").length;
  const unexported = all.filter((r) => r.status === "approved").length;
  const netOverShort = all.filter((r) => r.status !== "draft").reduce((s, r) => s + toCents(r.over_short), 0);

  return (
    <main className="page stack">
      <div className="page-head">
        <div>
          <h1>Review queue</h1>
          <div className="muted">{waiting} waiting · {missing.length} missing day{missing.length === 1 ? "" : "s"} in the last week</div>
        </div>
        <div className="row-wrap">
          <label className="label-stack">Store
            <select value={storeId} onChange={(e) => setStoreId(e.target.value)}>
              <option value="">All stores</option>
              {me?.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label className="label-stack">Status
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUS_FILTERS.map((f) => <option key={f.label} value={f.value}>{f.label}</option>)}
            </select>
          </label>
          <label className="label-stack">From<input type="date" className="text" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></label>
          <label className="label-stack">To<input type="date" className="text" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></label>
        </div>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      <div className="row-wrap" style={{ alignItems: "stretch" }}>
        <div className="stat"><div className="muted">Waiting for you</div><div className="v">{waiting}</div></div>
        <div className="stat"><div className="muted">Approved, not exported</div><div className="v">{unexported}</div></div>
        <div className="stat"><div className="muted">Net over/short in range</div>
          <div className={`v ${netOverShort < 0 ? "neg" : ""}`}>{formatOverShort(netOverShort)}</div></div>
      </div>

      <div className="table-wrap">
        <table style={{ minWidth: 760 }}>
          <thead>
            <tr>
              <th className="left">Date</th><th className="left">Store</th><th>Total sales</th><th>Expected cash</th>
              <th>Over/(short)</th><th className="left">Submitted by</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {status === "" || status === "submitted"
              ? missing.map((m) => (
                  <tr key={`${m.store}-${m.date}`} className="missing">
                    <td className="left">{prettyDate(m.date)}</td><td className="left">{m.store}</td>
                    <td>—</td><td>—</td><td>—</td><td className="left">—</td><td><StatusChip status="missing" /></td>
                  </tr>
                ))
              : null}
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
            {rows.length === 0 && missing.length === 0 && (
              <tr><td colSpan={7} className="left muted" style={{ padding: 24 }}>Nothing here for these filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
