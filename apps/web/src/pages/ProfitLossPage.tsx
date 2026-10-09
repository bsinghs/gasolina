// Profit & Loss for one month (owner). Sales come from approved days; purchases and expenses are typed here.
// All math happens in the API (books/math.py); this screen shows it and lets the owner type entries.

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { EntryCategory, LedgerEntry, PnlYear, ProfitAndLoss, Vendor } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { useViewOnly } from "../lib/access";
import { Notice } from "../components/Notice";
import { ReportTabs } from "../components/ReportTabs";
import { Statement, type Row } from "../components/Statement";
import { today, prettyDate } from "../lib/dates";
import { formatMoney, parseAmount, toCents } from "../lib/money";

const CATEGORY: Record<EntryCategory, string> = {
  fuel_purchase: "Fuel purchase",
  merchandise_purchase: "Merchandise purchase",
  expense: "Expense",
};
const VENDOR_FOR: Record<EntryCategory, Vendor["kind"]> = { fuel_purchase: "fuel", merchandise_purchase: "merchandise", expense: "expense" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const EMPTY_FORM = { id: "", category: "expense" as EntryCategory, description: "", vendor_id: "", amount: "", store_id: "" };

function margin(part: string, whole: string) {
  const w = toCents(whole);
  return w ? `${((toCents(part) / w) * 100).toFixed(1)}% of revenue` : "–";
}

export function ProfitLossPage() {
  const viewOnly = useViewOnly();
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const month = params.get("month") ?? today().slice(0, 7);
  const storeId = params.get("store") ?? "";
  const include = params.get("include") === "submitted" ? "submitted" : "approved";
  const countPaidOuts = params.get("paidouts") !== "off";
  const set = (patch: Record<string, string>) =>
    setParams(Object.fromEntries(Object.entries({ month, store: storeId, include, paidouts: countPaidOuts ? "" : "off", ...patch })
      .filter(([, v]) => v !== "" && v !== "approved")));

  const [pnl, setPnl] = useState<ProfitAndLoss | null>(null);
  const [year, setYear] = useState<PnlYear | null>(null);
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    const q = { store_id: storeId || undefined, include: include as "approved" | "submitted", count_paid_outs: countPaidOuts };
    const [p, y, e, v] = await Promise.all([
      api.books.pnl({ month, ...q }), api.books.pnlYear({ year: month.slice(0, 4), ...q }),
      api.books.entries(month, storeId || undefined), api.vendors.list(),
    ]);
    setPnl(p); setYear(y); setEntries(e); setVendors(v);
  }, [month, storeId, include, countPaidOuts]);

  useEffect(() => {
    load().catch((e) => setMessage({ kind: "error", text: e.message }));
  }, [load]);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    setMessage(null);
    try {
      await fn();
      await load();
      setMessage({ kind: "ok", text: ok });
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "Couldn't save" });
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const amount = parseAmount(form.amount);
    if (amount === null || toCents(amount) <= 0) {
      setMessage({ kind: "error", text: `“${form.amount}” isn't an amount. Type it like 1250.00` });
      return;
    }
    const body = {
      month, category: form.category, description: form.description, vendor_id: form.vendor_id || null,
      amount, store_id: (storeId || form.store_id) || null,
    };
    act(async () => {
      if (form.id) await api.books.updateEntry(form.id, body);
      else await api.books.addEntry(body);
      setForm({ ...EMPTY_FORM, category: form.category });
    }, form.id ? "Entry changed." : "Entry added.");
  };

  const statement: Row[] = pnl ? [
    { kind: "head", label: "Revenue" },
    { kind: "line", line: { label: "Fuel sales", amount: pnl.fuel_sales, source: "days", items: [] } },
    { kind: "line", line: { label: "Merchandise sales", amount: pnl.merchandise_sales, source: "days", items: [] } },
    { kind: "info", label: "of which taxable (tax ÷ rate)", amount: pnl.taxable },
    { kind: "info", label: "of which non-taxable", amount: pnl.non_taxable },
    { kind: "total", label: "Total revenue", amount: pnl.revenue },
    { kind: "head", label: "Cost of goods" },
    ...pnl.cost_lines.map((line) => ({ kind: "line" as const, line })),
    { kind: "total", label: "Total cost of goods", amount: pnl.cost_of_goods },
    { kind: "total", label: "Gross profit", amount: pnl.gross_profit, tone: "big" },
    { kind: "head", label: "Expenses" },
    ...pnl.expense_lines.map((line) => ({ kind: "line" as const, line })),
    { kind: "total", label: "Total expenses", amount: pnl.expenses },
    { kind: "line", line: { label: "Cash over / short", amount: pnl.over_short, source: "days", items: [] } },
    { kind: "total", label: toCents(pnl.net_profit) < 0 ? "Net loss" : "Net profit", amount: pnl.net_profit, tone: toCents(pnl.net_profit) < 0 ? "bad" : "good" },
  ] : [];

  const vendorChoices = vendors.filter((v) => v.active && v.kind === VENDOR_FOR[form.category]);
  const storeName = storeId ? me?.stores.find((s) => s.id === storeId)?.name ?? "1 store" : "All stores";

  return (
    <main className="page stack">
      <div className="page-head">
        <div>
          <h1>Profit &amp; Loss</h1>
          <div className="muted">{pnl?.label ?? "…"} · {storeName} · sales from {include === "approved" ? "approved" : "approved + waiting"} days ({pnl?.days ?? 0})</div>
        </div>
      </div>
      <ReportTabs />

      <div className="report-controls">
        <label className="label-stack">Month<input type="month" className="text" value={month} onChange={(e) => e.target.value && set({ month: e.target.value })} /></label>
        <label className="label-stack">Store<select value={storeId} onChange={(e) => set({ store: e.target.value })}>
          <option value="">All stores (incl. shared)</option>
          {me?.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select></label>
        <label className="check-inline"><input type="checkbox" checked={countPaidOuts} onChange={(e) => set({ paidouts: e.target.checked ? "" : "off" })} />
          Count paid outs from the daily sheets</label>
        <label className="check-inline"><input type="checkbox" checked={include === "submitted"} onChange={(e) => set({ include: e.target.checked ? "submitted" : "approved" })} />
          Include days waiting for review</label>
      </div>
      {!countPaidOuts && <Notice kind="warn">Paid outs are left out. Use this when the same payments are also typed below, so nothing counts twice.</Notice>}
      {message && <Notice kind={message.kind}>{message.text}</Notice>}

      {pnl && (
        <div className="stat-row">
          <div className="stat"><div className="muted">Revenue</div><div className="v">{formatMoney(toCents(pnl.revenue))}</div><div className="stat-hint">Fuel + merchandise (tax not included)</div></div>
          <div className="stat"><div className="muted">Gross profit</div><div className="v">{formatMoney(toCents(pnl.gross_profit))}</div><div className="stat-hint">{margin(pnl.gross_profit, pnl.revenue)}</div></div>
          <div className="stat"><div className="muted">Expenses</div><div className="v">{formatMoney(toCents(pnl.expenses))}</div><div className="stat-hint">Typed + paid outs</div></div>
          <div className="stat"><div className="muted">Net profit</div><div className={`v ${toCents(pnl.net_profit) < 0 ? "neg" : ""}`}>{formatMoney(toCents(pnl.net_profit))}</div><div className="stat-hint">{margin(pnl.net_profit, pnl.revenue)}</div></div>
        </div>
      )}

      <section className="card">
        <div className="card-head">What you paid in {pnl?.label ?? "this month"}</div>
        <div className="card-body stack">
          {!viewOnly && <form className="entry-form" onSubmit={submit}>
            <label className="label-stack">Type<select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as EntryCategory, vendor_id: "" })}>
              {(Object.keys(CATEGORY) as EntryCategory[]).map((c) => <option key={c} value={c}>{CATEGORY[c]}</option>)}</select></label>
            <label className="label-stack">What for<input className="text" required maxLength={200} placeholder={form.category === "expense" ? "e.g. Payroll, Rent, Utilities" : "e.g. Load on Oct 3"}
              value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
            <label className="label-stack">Vendor (optional)<select value={form.vendor_id} onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}>
              <option value="">—</option>{vendorChoices.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select></label>
            <label className="label-stack">Amount ($)<input className="text" required inputMode="decimal" placeholder="0.00" value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })} /></label>
            <div className="row-wrap" style={{ gap: 6 }}>
              <button className="btn btn-primary" type="submit">{form.id ? "Save" : "Add"}</button>
              {form.id && <button className="btn btn-ghost" type="button" onClick={() => setForm(EMPTY_FORM)}>Cancel</button>}
            </div>
            {!storeId && (
              <label className="label-stack span-2">For store<select value={form.store_id} onChange={(e) => setForm({ ...form, store_id: e.target.value })}>
                <option value="">All stores (shared, e.g. insurance)</option>
                {me?.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
            )}
          </form>}
          {!viewOnly && vendorChoices.length === 0 && <div className="muted">No {VENDOR_FOR[form.category] === "expense" ? "expense" : VENDOR_FOR[form.category]} vendors yet. Add them on the Vendors tab.</div>}

          <div className="table-wrap">
            <table style={{ minWidth: 640 }}>
              <thead><tr><th className="left">Type</th><th className="left">What for</th><th className="left">Vendor</th><th className="left">Store</th><th>Amount</th><th /></tr></thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id}>
                    <td className="left">{CATEGORY[e.category]}</td><td className="left">{e.description}
                      {e.gallons && <div className="stamp">{Number(e.gallons).toLocaleString("en-US")} gal into {e.tank}{e.entry_date ? ` on ${prettyDate(e.entry_date)}` : ""} (Inventory)</div>}
                      {!e.gallons && e.entry_date && <div className="stamp">{prettyDate(e.entry_date)}</div>}</td>
                    <td className="left">{e.vendor_name ?? "—"}</td><td className="left">{e.store_name ?? "All stores"}</td>
                    <td>{formatMoney(toCents(e.amount))}</td>
                    <td>
                      {viewOnly ? null : confirmDelete === e.id ? (
                        <span className="row-wrap" style={{ gap: 6, justifyContent: "flex-end" }}>
                          <button className="btn btn-danger btn-sm" onClick={() => { setConfirmDelete(null); act(() => api.books.removeEntry(e.id), "Entry removed. It's kept in the history log."); }}>Remove</button>
                          <button className="btn btn-ghost btn-sm" onClick={() => setConfirmDelete(null)}>Keep</button>
                        </span>
                      ) : (
                        <span className="row-wrap" style={{ gap: 12, justifyContent: "flex-end" }}>
                          <button className="link-btn" onClick={() => setForm({ id: e.id, category: e.category, description: e.description, vendor_id: e.vendor_id ?? "", amount: e.amount, store_id: e.store_id ?? "" })}>Edit</button>
                          <button className="link-btn" style={{ color: "var(--bad)" }} onClick={() => setConfirmDelete(e.id)}>Remove</button>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
                {entries.length === 0 && <tr><td colSpan={6} className="left muted" style={{ padding: 18 }}>Nothing typed for this month yet. Add fuel loads, merchandise orders, payroll, rent, utilities…</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {pnl && (
        <section className="stack" style={{ gap: 8 }}>
          <h2 className="report-h2">Statement</h2>
          <Statement rows={statement} />
          <p className="muted" style={{ margin: 0 }}>PA sales tax collected ({formatMoney(toCents(pnl.sales_tax))}) is owed to the state, so it isn't revenue. Tap a line with › to see what's behind it.</p>
        </section>
      )}

      {year && (
        <section className="stack" style={{ gap: 8 }}>
          <h2 className="report-h2">{year.year} at a glance</h2>
          <div className="table-wrap">
            <table style={{ minWidth: 560 }}>
              <thead><tr><th className="left">Month</th><th>Revenue</th><th>Cost of goods</th><th>Expenses</th><th>Over/(short)</th><th>Net profit</th></tr></thead>
              <tbody>
                {year.months.map((m) => {
                  const empty = !toCents(m.revenue) && !toCents(m.cost_of_goods) && !toCents(m.expenses);
                  const net = toCents(m.net_profit);
                  return (
                    <tr key={m.month} className={m.month === month ? "clickable row-on" : "clickable"} onClick={() => set({ month: m.month })}>
                      <td className="left"><a href="#" onClick={(e) => e.preventDefault()}>{MONTHS[Number(m.month.slice(5)) - 1]}</a></td>
                      {empty ? <td colSpan={5} className="muted">–</td> : <>
                        <td>{formatMoney(toCents(m.revenue))}</td><td>{formatMoney(toCents(m.cost_of_goods))}</td><td>{formatMoney(toCents(m.expenses))}</td>
                        <td>{formatMoney(toCents(m.over_short))}</td><td className={net < 0 ? "neg" : "pos"}>{formatMoney(net)}</td>
                      </>}
                    </tr>
                  );
                })}
              </tbody>
              <tfoot><tr><td className="left">Year</td><td>{formatMoney(toCents(year.totals.revenue))}</td><td>{formatMoney(toCents(year.totals.cost_of_goods))}</td>
                <td>{formatMoney(toCents(year.totals.expenses))}</td><td>{formatMoney(toCents(year.totals.over_short))}</td><td>{formatMoney(toCents(year.totals.net_profit))}</td></tr></tfoot>
            </table>
          </div>
          <p className="muted" style={{ margin: 0 }}>Tap a month to open it.</p>
        </section>
      )}
    </main>
  );
}
