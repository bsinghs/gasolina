// Vendors (owner): the list of who the stores pay, and spending by vendor for a month or a year.
// Paid outs on the daily sheets are matched to this list by name, which decides where they land in the P&L.

import { Fragment, useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { MISCELLANEOUS, type MiscPaidOut, type Vendor, type VendorKind, type VendorSpending } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { useViewOnly } from "../lib/access";
import { Notice } from "../components/Notice";
import { ReportTabs } from "../components/ReportTabs";
import { prettyDate, today } from "../lib/dates";
import { formatMoney, toCents } from "../lib/money";

const KIND: Record<VendorKind, string> = { fuel: "Cost of goods: fuel", merchandise: "Cost of goods: merchandise", expense: "Expense" };

export function VendorsPage() {
  const viewOnly = useViewOnly();
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const period = params.get("period") === "year" ? "year" : "month";
  const value = params.get("value") ?? (period === "year" ? today().slice(0, 4) : today().slice(0, 7));
  const storeId = params.get("store") ?? "";
  const set = (patch: Record<string, string>) =>
    setParams(Object.fromEntries(Object.entries({ period, value, store: storeId, ...patch }).filter(([, v]) => v !== "")));

  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [spending, setSpending] = useState<VendorSpending | null>(null);
  const [misc, setMisc] = useState<MiscPaidOut[]>([]);
  const [form, setForm] = useState<{ name: string; kind: VendorKind }>({ name: "", kind: "merchandise" });
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    const [v, s, m] = await Promise.all([api.vendors.list(), api.vendors.spending({ period, value, store_id: storeId || undefined, include: "approved" }),
      api.vendors.miscellaneous(90)]);
    setVendors(v); setSpending(s); setMisc(m);
  }, [period, value, storeId]);
  useEffect(() => { load().catch((e) => setMessage({ kind: "error", text: e.message })); }, [load]);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    setMessage(null);
    try { await fn(); await load(); setMessage({ kind: "ok", text: ok }); }
    catch (e) { setMessage({ kind: "error", text: e instanceof Error ? e.message : "Couldn't save" }); }
  };
  const addVendor = (e: FormEvent, name = form.name, kind = form.kind) => {
    e.preventDefault();
    act(async () => { await api.vendors.add({ name, kind }); setForm({ ...form, name: "" }); }, `${name.trim()} added to the list.`);
  };

  const top = spending?.vendors[0];
  const notOnList = spending?.vendors.filter((v) => !v.on_list && v.vendor.toLowerCase() !== MISCELLANEOUS.toLowerCase()) ?? [];

  return (
    <main className="page stack">
      <div className="page-head"><div><h1>Vendors</h1><div className="muted">Who you pay, and how much</div></div></div>
      <ReportTabs />
      {message && <Notice kind={message.kind}>{message.text}</Notice>}

      <section className="card">
        <div className="card-head">Vendor list</div>
        <div className="card-body stack">
          <p className="muted" style={{ margin: 0 }}>
            Mark each vendor as <strong>cost of goods</strong> (fuel or merchandise you buy to sell) or <strong>expense</strong> (everything else).
            Paid outs on the daily sheets are matched by name and land in the right place on the Profit &amp; Loss.
          </p>
          {!viewOnly && <form className="row-wrap" onSubmit={(e) => addVendor(e)}>
            <label className="label-stack" style={{ flex: 2, minWidth: 180 }}>Vendor name
              <input className="text" required maxLength={120} placeholder="e.g. Sunoco Fuel" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <label className="label-stack" style={{ flex: 1, minWidth: 180 }}>Type
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as VendorKind })}>
                {(Object.keys(KIND) as VendorKind[]).map((k) => <option key={k} value={k}>{KIND[k]}</option>)}</select></label>
            <button className="btn btn-dark" type="submit">Add vendor</button>
          </form>}
          <div className="table-wrap">
            <table style={{ minWidth: 520 }}>
              <thead><tr><th className="left">Vendor</th><th className="left">Type</th><th /></tr></thead>
              <tbody>
                {vendors.map((v) => (
                  <tr key={v.id} style={v.active ? undefined : { opacity: 0.55 }}>
                    <td className="left">{v.name}{!v.active && <span className="muted"> (inactive)</span>}</td>
                    <td className="left">
                      <select aria-label={`Type for ${v.name}`} value={v.kind} disabled={viewOnly} onChange={(e) => act(() => api.vendors.update(v.id, { name: v.name, kind: e.target.value as VendorKind, active: v.active }), `${v.name} changed.`)}>
                        {(Object.keys(KIND) as VendorKind[]).map((k) => <option key={k} value={k}>{KIND[k]}</option>)}</select>
                    </td>
                    <td>
                      {viewOnly ? null : confirmDelete === v.id ? (
                        <span className="row-wrap" style={{ gap: 6, justifyContent: "flex-end" }}>
                          <button className="btn btn-danger btn-sm" onClick={() => { setConfirmDelete(null); act(() => api.vendors.remove(v.id), `${v.name} removed.`); }}>Remove</button>
                          <button className="btn btn-ghost btn-sm" onClick={() => setConfirmDelete(null)}>Keep</button>
                        </span>
                      ) : (
                        <span className="row-wrap" style={{ gap: 12, justifyContent: "flex-end" }}>
                          <button className="link-btn" onClick={() => act(() => api.vendors.update(v.id, { name: v.name, kind: v.kind, active: !v.active }), v.active ? `${v.name} deactivated.` : `${v.name} active again.`)}>
                            {v.active ? "Deactivate" : "Reactivate"}</button>
                          {!v.used && <button className="link-btn" style={{ color: "var(--bad)" }} onClick={() => setConfirmDelete(v.id)}>Remove</button>}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
                {vendors.length === 0 && <tr><td colSpan={3} className="left muted" style={{ padding: 18 }}>No vendors yet. Add the ones you pay most: fuel supplier, distributors, ice, repairs…</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">Miscellaneous paid outs to sort out (last 90 days)</div>
        <div className="card-body stack" style={{ paddingTop: 12 }}>
          <p className="muted" style={{ margin: 0 }}>
            Employees pick a vendor from the list on each paid out. When it isn&apos;t there, they choose <strong>{MISCELLANEOUS}</strong> and write what it was.
            Add the vendor here so they can pick it next time.
          </p>
          {misc.length === 0 ? <p className="muted" style={{ margin: 0 }}>Nothing to sort out.</p> : (
            <div className="table-wrap">
              <table style={{ minWidth: 560 }}>
                <thead><tr><th className="left">Day</th><th className="left">Store</th><th>Amount</th><th className="left">Their note</th><th /></tr></thead>
                <tbody>
                  {misc.map((m) => (
                    <tr key={m.id}>
                      <td className="left"><Link to={`/days/${m.report_id}`}>{prettyDate(m.business_date)}</Link>
                        {m.submitted_by_name && <div className="stamp">{m.submitted_by_name}</div>}</td>
                      <td className="left">{m.store_name}</td>
                      <td>{formatMoney(toCents(m.amount))}<div className="stamp">{m.kind}</div></td>
                      <td className="left">{m.note ?? <span className="muted">no note</span>}</td>
                      <td>{!viewOnly && <button className="link-btn" onClick={() => { setForm({ ...form, name: (m.note ?? "").slice(0, 120) }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                        Add as vendor…</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <section className="stack" style={{ gap: 10 }}>
        <h2 className="report-h2">Spending by vendor</h2>
        <div className="report-controls">
          <div className="segmented" role="tablist" aria-label="Period">
            {(["month", "year"] as const).map((p) => (
              <button key={p} type="button" role="tab" aria-selected={period === p} className={period === p ? "on" : ""}
                onClick={() => set({ period: p, value: p === "year" ? value.slice(0, 4) : `${value.slice(0, 4)}-${today().slice(5, 7)}` })}>{p === "month" ? "Month" : "Year"}</button>
            ))}
          </div>
          {period === "month"
            ? <label className="label-stack">Month<input type="month" className="text" value={value} onChange={(e) => e.target.value && set({ value: e.target.value })} /></label>
            : <label className="label-stack">Year<select value={value} onChange={(e) => set({ value: e.target.value })}>
                {Array.from({ length: 6 }, (_, i) => String(Number(today().slice(0, 4)) - i)).map((y) => <option key={y}>{y}</option>)}</select></label>}
          <label className="label-stack">Store<select value={storeId} onChange={(e) => set({ store: e.target.value })}>
            <option value="">All stores</option>{me?.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        </div>

        {spending && (
          <div className="stat-row">
            <div className="stat"><div className="muted">Total paid</div><div className="v">{formatMoney(toCents(spending.total))}</div><div className="stat-hint">{spending.label}</div></div>
            <div className="stat"><div className="muted">Vendors</div><div className="v">{spending.vendors.length}</div><div className="stat-hint">{notOnList.length} not on the list</div></div>
            <div className="stat"><div className="muted">Largest</div><div className="v">{top ? formatMoney(toCents(top.total)) : "–"}</div><div className="stat-hint">{top ? `${top.vendor} · ${top.share}%` : "–"}</div></div>
          </div>
        )}

        {notOnList.length > 0 && !viewOnly && (
          <Notice kind="warn">
            Paid out to vendors that aren't on the list: {notOnList.map((v) => v.vendor).join(", ")}. Add them so their payments land in the right place:
            <span className="row-wrap" style={{ gap: 6, marginTop: 8 }}>
              {notOnList.slice(0, 6).map((v) => (
                <span key={v.vendor} className="row-wrap" style={{ gap: 4 }}>
                  <strong>{v.vendor}</strong>
                  {(["merchandise", "expense"] as VendorKind[]).map((k) => (
                    <button key={k} className="btn btn-ghost btn-sm" onClick={(e) => addVendor(e as unknown as FormEvent, v.vendor, k)}>
                      as {k === "expense" ? "expense" : "merchandise"}</button>))}
                </span>
              ))}
            </span>
          </Notice>
        )}

        <div className="table-wrap">
          <table style={{ minWidth: 640 }}>
            <thead><tr><th className="left">Vendor</th><th>Cost of goods</th><th>Expenses</th><th>Not on list</th><th>Total</th><th>Share</th></tr></thead>
            <tbody>
              {spending?.vendors.map((v) => (
                <Fragment key={v.vendor}>
                  <tr className="clickable" onClick={() => setOpenRow(openRow === v.vendor ? null : v.vendor)} aria-expanded={openRow === v.vendor}>
                    <td className="left"><a href="#" onClick={(e) => e.preventDefault()}>{v.vendor}</a> <span className="muted">{openRow === v.vendor ? "▾" : "›"}</span></td>
                    <td>{toCents(v.cost_of_goods) ? formatMoney(toCents(v.cost_of_goods)) : "–"}</td>
                    <td>{toCents(v.expense) ? formatMoney(toCents(v.expense)) : "–"}</td>
                    <td className={toCents(v.not_on_list) ? "neg" : ""}>{toCents(v.not_on_list) ? formatMoney(toCents(v.not_on_list)) : "–"}</td>
                    <td><strong>{formatMoney(toCents(v.total))}</strong></td><td>{v.share}%</td>
                  </tr>
                  {openRow === v.vendor && v.items.map((it, i) => (
                    <tr key={i} className="detail-row">
                      <td className="left muted" colSpan={4}>{it.source === "typed" ? `Typed · ${it.date.slice(0, 7)}` : prettyDate(it.date)} · {it.what}</td>
                      <td>{formatMoney(toCents(it.amount))}</td><td />
                    </tr>
                  ))}
                </Fragment>
              ))}
              {spending && spending.vendors.length === 0 && <tr><td colSpan={6} className="left muted" style={{ padding: 18 }}>No payments in this period yet. They come from typed purchases / expenses (Profit &amp; Loss) and the daily paid outs.</td></tr>}
            </tbody>
            {spending && spending.vendors.length > 0 && <tfoot><tr><td className="left">Total</td><td colSpan={3} /><td>{formatMoney(toCents(spending.total))}</td><td>100%</td></tr></tfoot>}
          </table>
        </div>
        <p className="muted" style={{ margin: 0 }}>Counts typed purchases and expenses, and paid outs on approved days. Tap a vendor to see each payment.</p>
      </section>
    </main>
  );
}
