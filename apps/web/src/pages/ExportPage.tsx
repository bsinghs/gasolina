// Download approved days for QuickBooks, plus check paid-outs and raw data.

import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ReportSummary } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Notice } from "../components/Notice";
import { useViewOnly } from "../lib/access";
import { daysAgo, prettyDate, today } from "../lib/dates";
import { formatMoney, toCents } from "../lib/money";

export function ExportPage() {
  const { me } = useAuth();
  const viewOnly = useViewOnly(); // co-owner: sees the days and the read-only downloads, can't mark days exported
  const [dateFrom, setDateFrom] = useState(daysAgo(7));
  const [dateTo, setDateTo] = useState(today());
  const [storeId, setStoreId] = useState("");
  const [includeExported, setIncludeExported] = useState(false);
  const [ready, setReady] = useState<ReportSummary[]>([]);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    api.reports
      .list({ date_from: dateFrom, date_to: dateTo, store_id: storeId || undefined, status: includeExported ? "approved,exported" : "approved" })
      .then(setReady)
      .catch((e) => setMessage({ kind: "error", text: e.message }));
  }, [dateFrom, dateTo, storeId, includeExported, reloadKey]);

  const run = async (fn: () => Promise<void>, done: string) => {
    setMessage(null);
    try {
      await fn();
      setMessage({ kind: "ok", text: done });
      setReloadKey((k) => k + 1);
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "Export failed" });
    }
  };

  return (
    <main className="page narrow stack">
      <div className="page-head"><h1>Export</h1></div>
      <div className="card card-pad stack">
        <div className="row-wrap">
          <label className="label-stack">From<input type="date" className="text" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></label>
          <label className="label-stack">To<input type="date" className="text" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></label>
          <label className="label-stack">Store
            <select value={storeId} onChange={(e) => setStoreId(e.target.value)}>
              <option value="">All stores</option>
              {me?.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        </div>
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
          <input type="checkbox" checked={includeExported} onChange={(e) => setIncludeExported(e.target.checked)} />
          Include days already exported (re-download)
        </label>
      </div>

      {message && <Notice kind={message.kind}>{message.text}</Notice>}

      <section className="card">
        <div className="card-head">QuickBooks journal entries · {ready.length} day{ready.length === 1 ? "" : "s"} ready</div>
        <div className="card-body">
          {ready.map((r) => (
            <div key={r.id} className="field-row" style={{ fontSize: 13 }}>
              <span>{prettyDate(r.business_date)} · {r.store_name}</span><span>{formatMoney(toCents(r.total_sales))}</span>
            </div>
          ))}
          {ready.length === 0 && <p className="muted">No approved days in this range.</p>}
        </div>
        <div className="card-pad stack" style={{ gap: 8 }}>
          {viewOnly ? <span className="muted">View only: the owner downloads the QuickBooks file (it marks these days as exported).</span> : <>
          <button className="btn btn-primary btn-block" disabled={ready.length === 0}
            onClick={() => run(() => api.exports.quickbooks({ date_from: dateFrom, date_to: dateTo, store_id: storeId || undefined, include_already_exported: includeExported }),
              "Downloaded. Those days are now marked Exported. In QuickBooks: Settings ⚙ → Import data → Journal entries.")}>
            Download QuickBooks CSV
          </button>
          <span className="muted">Turn off account numbers in QuickBooks before importing, and make sure the account names in Settings match your chart of accounts.</span>
          </>}
        </div>
      </section>

      <section className="card card-pad stack" style={{ gap: 10 }}>
        <div className="sans" style={{ fontWeight: 700 }}>Other downloads</div>
        <div className="row-wrap">
          <button className="btn btn-ghost" onClick={() => run(() => api.exports.checkPaidOuts(dateFrom, dateTo), "Check paid-outs downloaded.")}>Check paid-outs CSV</button>
          <button className="btn btn-ghost" onClick={() => run(() => api.exports.raw(dateFrom, dateTo), "Raw data downloaded.")}>All worksheet data (Excel CSV)</button>
        </div>
      </section>
    </main>
  );
}
