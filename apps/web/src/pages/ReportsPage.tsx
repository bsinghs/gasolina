// Owner reports: totals for a month, a quarter or a year, for one store or all of them.
// Read-only: the API adds up saved worksheets (approved days by default); nothing is changed here.
// The choices live in the address (?period=quarter&value=2026-Q4…) so Back and refresh keep them.

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Period, PeriodRow, PeriodSums, PeriodSummary, Status } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Notice } from "../components/Notice";
import { StatusChip } from "../components/StatusChip";
import { prettyDate, today } from "../lib/dates";
import { formatMoney, formatOverShort, toCents } from "../lib/money";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function defaultValue(period: Period): string {
  const t = today();
  if (period === "month") return t.slice(0, 7);
  if (period === "quarter") return `${t.slice(0, 4)}-Q${Math.floor((Number(t.slice(5, 7)) - 1) / 3) + 1}`;
  return t.slice(0, 4);
}

const gal = (v: string) => Number(v).toLocaleString("en-US", { maximumFractionDigits: 1 });
const monthName = (key: string) => MONTHS[Number(key.slice(5, 7)) - 1];

export function ReportsPage() {
  const { me } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const period = (["month", "quarter", "year"].includes(params.get("period") ?? "") ? params.get("period") : "month") as Period;
  const value = params.get("value") ?? defaultValue(period);
  const storeId = params.get("store") ?? "";
  const include = params.get("include") === "submitted" ? "submitted" : "approved";

  const [data, setData] = useState<PeriodSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const set = (patch: Record<string, string>) => {
    const next = { period, value, store: storeId, include, ...patch };
    setParams(Object.fromEntries(Object.entries(next).filter(([, v]) => v !== "" && v !== "approved")));
  };

  useEffect(() => {
    let current = true;
    setLoading(true);
    api.summaries.get({ period, value, store_id: storeId || undefined, include })
      .then((d) => { if (current) { setData(d); setError(null); } })
      .catch((e) => current && setError(e.message))
      .finally(() => current && setLoading(false));
    return () => { current = false; };
  }, [period, value, storeId, include]);

  const year = value.slice(0, 4);
  const years = Array.from({ length: 6 }, (_, i) => String(Number(today().slice(0, 4)) - i));
  const t = data?.totals;
  const osCents = t ? toCents(t.over_short) : 0;
  const avgPrice = t && Number(t.gallons) > 0 ? toCents(t.fuel_sale) / 100 / Number(t.gallons) : 0;

  return (
    <main className="page stack">
      <div className="page-head">
        <div>
          <h1>Reports</h1>
          <div className="muted">{data ? data.label : "…"} · {storeId ? me?.stores.find((s) => s.id === storeId)?.name ?? "1 store" : "All stores"} · {include === "approved" ? "approved days" : "approved + waiting for review"}</div>
        </div>
        <button type="button" className="btn btn-ghost" disabled={!data || data.totals.days === 0}
          onClick={() => api.summaries.csv({ period, value, store_id: storeId || undefined, include }).catch((e) => setError(e.message))}>
          Download for Excel
        </button>
      </div>

      <div className="report-controls">
        <div className="segmented" role="tablist" aria-label="Period">
          {(["month", "quarter", "year"] as Period[]).map((p) => (
            <button key={p} type="button" role="tab" aria-selected={period === p} className={period === p ? "on" : ""}
              onClick={() => set({ period: p, value: p === "month" && period !== "month" ? defaultValue("month") : p === "quarter" ? `${year}-Q${period === "month" ? Math.floor((Number(value.slice(5, 7)) - 1) / 3) + 1 : 1}` : p === "year" ? year : value })}>
              {p === "month" ? "Month" : p === "quarter" ? "Quarter" : "Year"}
            </button>
          ))}
        </div>
        {period === "month" && (
          <label className="label-stack">Month<input type="month" className="text" value={value} max={today().slice(0, 7)}
            onChange={(e) => e.target.value && set({ value: e.target.value })} /></label>
        )}
        {period === "quarter" && (
          <>
            <label className="label-stack">Year<select value={year} onChange={(e) => set({ value: `${e.target.value}-${value.slice(5)}` })}>
              {years.map((y) => <option key={y}>{y}</option>)}</select></label>
            <label className="label-stack">Quarter<select value={value.slice(5)} onChange={(e) => set({ value: `${year}-${e.target.value}` })}>
              {["Q1", "Q2", "Q3", "Q4"].map((q, i) => <option key={q} value={q}>{q} ({MONTHS[i * 3].slice(0, 3)}–{MONTHS[i * 3 + 2].slice(0, 3)})</option>)}</select></label>
          </>
        )}
        {period === "year" && (
          <label className="label-stack">Year<select value={value} onChange={(e) => set({ value: e.target.value })}>
            {years.map((y) => <option key={y}>{y}</option>)}</select></label>
        )}
        <label className="label-stack">Store<select value={storeId} onChange={(e) => set({ store: e.target.value })}>
          <option value="">All stores</option>
          {me?.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select></label>
        <label className="check-inline">
          <input type="checkbox" checked={include === "submitted"} onChange={(e) => set({ include: e.target.checked ? "submitted" : "approved" })} />
          Include days waiting for review
        </label>
      </div>

      {error && <Notice kind="error">{error}</Notice>}
      {data && data.missing.length > 0 && (
        <Notice kind="warn">
          No worksheet yet for {data.missing.map((m) => `${m.store_name}: ${m.days} day${m.days === 1 ? "" : "s"}`).join(" · ")} in this period.{" "}
          <button type="button" className="link-btn" style={{ padding: 0, minHeight: 0 }}
            onClick={() => navigate(`/review?show=missing`)}>See which days</button>
        </Notice>
      )}

      {t && (
        <div className={`stat-row${loading ? " is-loading" : ""}`}>
          <div className="stat"><div className="muted">Total sales</div><div className="v">{formatMoney(toCents(t.total_sales))}</div>
            <div className="stat-hint">{t.days} day{t.days === 1 ? "" : "s"}{t.days_unreviewed ? ` · ${t.days_unreviewed} not reviewed yet` : ""}</div></div>
          <div className="stat"><div className="muted">Fuel sales</div><div className="v">{formatMoney(toCents(t.fuel_sale))}</div>
            <div className="stat-hint">{gal(t.gallons)} gal{avgPrice ? ` · avg $${avgPrice.toFixed(3)}/gal` : ""}</div></div>
          <div className="stat"><div className="muted">Merchandise sales</div><div className="v">{formatMoney(toCents(t.merch_sale))}</div>
            <div className="stat-hint">Taxable {formatMoney(toCents(t.taxable_sale))} · non-taxable {formatMoney(toCents(t.nontaxable_sale))}</div></div>
          <div className="stat"><div className="muted">PA sales tax</div><div className="v">{formatMoney(toCents(t.sales_tax))}</div>
            <div className="stat-hint">Collected, owed to the state</div></div>
          <div className="stat"><div className="muted">Net over / short</div><div className={`v ${osCents < 0 ? "neg" : ""}`}>{formatOverShort(osCents)}</div>
            <div className="stat-hint">{t.days_short} day{t.days_short === 1 ? "" : "s"} short</div></div>
        </div>
      )}

      {data && data.stores.length > 1 && !storeId && (
        <section className="stack" style={{ gap: 8 }}>
          <h2 className="report-h2">By store</h2>
          <SumsTable
            first="Store"
            rows={data.stores.map((s) => ({ ...s, key: s.store_id, label: s.store_name }))}
            onOpen={(r) => set({ store: r.key })}
            total={data.totals}
          />
        </section>
      )}

      {data && (
        <section className="stack" style={{ gap: 8 }}>
          <h2 className="report-h2">{period === "month" ? "Day by day" : "Month by month"}</h2>
          {period === "month" ? (
            <DayTable rows={data.rows} total={data.totals} onOpen={(r) => r.report_id && navigate(`/days/${r.report_id}`)} />
          ) : (
            <SumsTable
              first="Month"
              rows={data.rows.map((r) => ({ ...r, label: monthName(r.key) }))}
              onOpen={(r) => set({ period: "month", value: r.key })}
              total={data.totals}
            />
          )}
          <p className="muted" style={{ margin: 0 }}>
            {period === "month" ? "Tap a day to open its worksheet." : "Tap a month to see its days."} Drafts and days sent back aren't counted.
          </p>
        </section>
      )}
    </main>
  );
}

type Labeled = PeriodSums & { key: string; label: string };

function SumsTable({ first, rows, total, onOpen }: { first: string; rows: Labeled[]; total: PeriodSums; onOpen: (r: Labeled) => void }) {
  return (
    <div className="table-wrap">
      <table style={{ minWidth: 820 }}>
        <thead>
          <tr><th className="left">{first}</th><th>Days</th><th>Fuel</th><th>Merch</th><th>Taxable</th><th>Non-taxable</th><th>Tax</th><th>Total sales</th><th>Gallons</th><th>Over/(short)</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className={r.days ? "clickable" : "empty-row"} onClick={() => r.days && onOpen(r)}>
              <td className="left">{r.days ? <a href="#" onClick={(e) => e.preventDefault()}>{r.label}</a> : r.label}</td>
              <td>{r.days || "–"}</td>
              {r.days ? <SumCells r={r} /> : <td colSpan={8} className="muted">No days counted</td>}
            </tr>
          ))}
        </tbody>
        <tfoot><tr><td className="left">Total</td><td>{total.days}</td><SumCells r={total} /></tr></tfoot>
      </table>
    </div>
  );
}

function SumCells({ r }: { r: PeriodSums }) {
  const os = toCents(r.over_short);
  return (
    <>
      <td>{formatMoney(toCents(r.fuel_sale))}</td><td>{formatMoney(toCents(r.merch_sale))}</td>
      <td>{formatMoney(toCents(r.taxable_sale))}</td><td>{formatMoney(toCents(r.nontaxable_sale))}</td>
      <td>{formatMoney(toCents(r.sales_tax))}</td><td><strong>{formatMoney(toCents(r.total_sales))}</strong></td>
      <td>{gal(r.gallons)}</td><td className={os < 0 ? "neg" : os > 0 ? "pos" : ""}>{formatOverShort(os)}</td>
    </>
  );
}

function DayTable({ rows, total, onOpen }: { rows: PeriodRow[]; total: PeriodSums; onOpen: (r: PeriodRow) => void }) {
  return (
    <div className="table-wrap">
      <table style={{ minWidth: 900 }}>
        <thead>
          <tr><th className="left">Date</th><th className="left">Store</th><th>Fuel</th><th>Merch</th><th>Taxable</th><th>Non-taxable</th><th>Tax</th><th>Total sales</th><th>Gallons</th><th>Over/(short)</th><th>Status</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.report_id} className="clickable" onClick={() => onOpen(r)}>
              <td className="left"><a href="#" onClick={(e) => e.preventDefault()}>{prettyDate(r.key)}</a></td>
              <td className="left">{r.store_name}</td>
              <SumCells r={r} />
              <td><StatusChip status={r.status as Status} /></td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={11} className="left muted" style={{ padding: 24 }}>No days counted in this period yet.</td></tr>}
        </tbody>
        {rows.length > 0 && <tfoot><tr><td className="left" colSpan={2}>Total ({total.days} days)</td><SumCells r={total} /><td /></tr></tfoot>}
      </table>
    </div>
  );
}
