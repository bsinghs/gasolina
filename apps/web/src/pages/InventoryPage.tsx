// Inventory (owner / co-owner home): per station, fuel tanks (on hand, % full, delivered, used, days left,
// pump vs tank check, price vs cost per gallon) and merchandise (sold vs bought). All numbers come from the API.
// Fuel deliveries and merchandise purchases typed here are entries in the books, so the P&L counts them once.

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Inventory, StoreInventory, TankStatus, Vendor } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { useViewOnly } from "../lib/access";
import { Notice } from "../components/Notice";
import { prettyDate, today } from "../lib/dates";
import { money, parseAmount } from "../lib/money";

const gal = (v: string | null) => (v === null ? "–" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 1 }));
const perGal = (v: string | null) => (v === null ? "–" : `$${Number(v).toFixed(3)}`);
const lastDayOf = (month: string) => {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m, 0).getDate();
};

function FullBar({ percent, warn }: { percent: string | null; warn: boolean }) {
  if (percent === null) return <span className="muted">size not set</span>;
  const p = Math.max(0, Math.min(100, Number(percent)));
  return (
    <span className="fullbar-wrap" title={`${percent}% full`}>
      <span className="fullbar"><span className={`fullbar-fill${warn ? " warn" : ""}`} style={{ width: `${p}%` }} /></span>
      <span className={`fullbar-label${warn ? " warn" : ""}`}>{Number(percent).toFixed(0)}% full</span>
    </span>
  );
}

type Form =
  | { kind: "fuel"; store_id: string; date: string; tank: string; gallons: string; amount: string; vendor_id: string; note: string }
  | { kind: "merch"; store_id: string; date: string; amount: string; vendor_id: string; note: string };

export function InventoryPage() {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const month = /^20\d{2}-(0[1-9]|1[0-2])$/.test(params.get("month") ?? "") ? params.get("month")! : today().slice(0, 7);
  const storeId = params.get("store") ?? "";
  const include = params.get("include") === "submitted" ? "submitted" : "approved";
  const set = (patch: Record<string, string>) =>
    setParams(Object.fromEntries(Object.entries({ month, store: storeId, include, ...patch }).filter(([, v]) => v !== "" && v !== "approved")));

  const [data, setData] = useState<Inventory | null>(null);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [form, setForm] = useState<Form | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const readOnly = useViewOnly();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [inv, v] = await Promise.all([api.inventory({ month, store_id: storeId || undefined, include }), api.vendors.list()]);
      setData(inv);
      setVendors(v.filter((x) => x.active));
    } finally {
      setLoading(false);
    }
  }, [month, storeId, include]);
  useEffect(() => { load().catch((e) => setMessage({ kind: "error", text: e.message })); }, [load]);

  const stores = me?.stores ?? [];
  const defaultDate = today().startsWith(month) ? today() : `${month}-${String(lastDayOf(month)).padStart(2, "0")}`;
  const firstStore = storeId || stores[0]?.id || "";
  const tanksOf = (id: string) => stores.find((s) => s.id === id)?.tanks ?? [];

  const openFuel = (store = firstStore) =>
    setForm({ kind: "fuel", store_id: store, date: defaultDate, tank: tanksOf(store)[0] ?? "", gallons: "", amount: "", vendor_id: vendors.find((v) => v.kind === "fuel")?.id ?? "", note: "" });
  const openMerch = (store = firstStore) =>
    setForm({ kind: "merch", store_id: store, date: defaultDate, amount: "", vendor_id: vendors.find((v) => v.kind === "merchandise")?.id ?? "", note: "" });

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setMessage(null);
    const amount = parseAmount(form.amount || "0");
    if (amount === null || Number(amount) < 0) return setMessage({ kind: "error", text: "Cost must be an amount like 10,250.00 (or leave it blank)." });
    const vendor = vendors.find((v) => v.id === form.vendor_id);
    try {
      if (form.kind === "fuel") {
        const gallons = Number(form.gallons.replace(/,/g, ""));
        if (!(gallons > 0)) return setMessage({ kind: "error", text: "Enter the gallons delivered." });
        await api.books.addEntry({
          store_id: form.store_id, category: "fuel_purchase", entry_date: form.date, tank: form.tank, gallons: gallons.toFixed(1),
          amount, vendor_id: form.vendor_id || null,
          description: [`${vendor?.name ?? "Fuel"} delivery`, form.note.trim()].filter(Boolean).join(" · "),
        });
      } else {
        await api.books.addEntry({
          store_id: form.store_id, category: "merchandise_purchase", entry_date: form.date, amount, vendor_id: form.vendor_id || null,
          description: [`${vendor?.name ?? "Merchandise"} purchase`, form.note.trim()].filter(Boolean).join(" · "),
        });
      }
      const what = form.kind === "fuel" ? "Delivery added. It's also a fuel purchase on the Profit & Loss." : "Purchase added. It's also on the Profit & Loss.";
      setForm(null);
      if (!form.date.startsWith(month)) set({ month: form.date.slice(0, 7) });
      await load();
      setMessage({ kind: "ok", text: what });
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Couldn't save" });
    }
  };

  const removeDelivery = async (id: string) => {
    setMessage(null);
    try { await api.books.removeEntry(id); await load(); setMessage({ kind: "ok", text: "Delivery removed (it's kept in the history log)." }); }
    catch (err) { setMessage({ kind: "error", text: err instanceof Error ? err.message : "Couldn't remove" }); }
  };

  return (
    <main className="page stack">
      <div className="page-head">
        <div>
          <h1>Inventory</h1>
          <div className="muted">{data?.label ?? "…"} · fuel tanks and merchandise, bought vs used / sold</div>
        </div>
        {!readOnly && (
          <div className="row-wrap" style={{ gap: 8 }}>
            <button className="btn btn-primary" onClick={() => openFuel()} disabled={!stores.length}>+ Fuel delivery</button>
            <button className="btn btn-ghost" onClick={() => openMerch()} disabled={!stores.length}>+ Merchandise purchase</button>
          </div>
        )}
      </div>

      <div className="report-controls">
        <label className="label-stack">Month<input type="month" className="text" value={month} max={today().slice(0, 7)}
          onChange={(e) => e.target.value && set({ month: e.target.value })} /></label>
        <label className="label-stack">Store<select value={storeId} onChange={(e) => set({ store: e.target.value })}>
          <option value="">All stores</option>
          {stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select></label>
        <label className="check-inline">
          <input type="checkbox" checked={include === "submitted"} onChange={(e) => set({ include: e.target.checked ? "submitted" : "approved" })} />
          Include days waiting for review (sales)
        </label>
      </div>

      {message && <Notice kind={message.kind}>{message.text}</Notice>}

      {form && (
        <form className="card card-pad stack" onSubmit={save}>
          <strong>{form.kind === "fuel" ? "Fuel delivery" : "Merchandise purchase"}</strong>
          <div className="row-wrap">
            <label className="label-stack">Store
              <select value={form.store_id} onChange={(e) => {
                const id = e.target.value;
                setForm(form.kind === "fuel" ? { ...form, store_id: id, tank: tanksOf(id)[0] ?? "" } : { ...form, store_id: id });
              }}>
                {stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select></label>
            <label className="label-stack">Date<input type="date" className="text" required value={form.date} max={today()}
              onChange={(e) => setForm({ ...form, date: e.target.value })} /></label>
            {form.kind === "fuel" && (
              <>
                <label className="label-stack">Tank<select value={form.tank} onChange={(e) => setForm({ ...form, tank: e.target.value })}>
                  {tanksOf(form.store_id).map((t) => <option key={t}>{t}</option>)}</select></label>
                <label className="label-stack">Gallons<input className="num" inputMode="decimal" required placeholder="0" value={form.gallons}
                  onChange={(e) => setForm({ ...form, gallons: e.target.value })} /></label>
              </>
            )}
            <label className="label-stack">{form.kind === "fuel" ? "Cost (blank if invoice later)" : "Amount"}
              <input className="num" inputMode="decimal" placeholder="0.00" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></label>
            <label className="label-stack">Vendor<select value={form.vendor_id} onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}>
              <option value="">(none)</option>
              {vendors.filter((v) => v.kind === (form.kind === "fuel" ? "fuel" : "merchandise")).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select></label>
            <label className="label-stack" style={{ flex: 1, minWidth: 180 }}>Note / invoice #
              <input className="text" maxLength={150} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
          </div>
          <div className="row-wrap">
            <button className="btn btn-primary" type="submit">Add</button>
            <button className="btn btn-ghost" type="button" onClick={() => setForm(null)}>Cancel</button>
            <span className="muted">Vendors missing? Add them on <Link to="/reports/vendors">Reports → Vendors</Link>.</span>
          </div>
        </form>
      )}

      {loading && !data && <p className="muted">Loading…</p>}
      {data?.stores.length === 0 && <Notice kind="info">No active stores yet. Add one in Settings.</Notice>}
      {data?.stores.map((s) => (
        <StoreCard key={s.store_id} s={s} reorder={data.reorder_percent} asOf={data.as_of} readOnly={readOnly}
          onDelivery={() => openFuel(s.store_id)} onPurchase={() => openMerch(s.store_id)} onRemove={removeDelivery} />
      ))}
    </main>
  );
}

function StoreCard({ s, reorder, asOf, readOnly, onDelivery, onPurchase, onRemove }: {
  s: StoreInventory; reorder: number; asOf: string; readOnly: boolean;
  onDelivery: () => void; onPurchase: () => void; onRemove: (id: string) => void;
}) {
  const f = s.fuel;
  const m = s.merchandise;
  const [confirm, setConfirm] = useState<string | null>(null);
  const noReadings = f.tanks.every((t) => t.latest === null);
  const check = f.pump_check;
  const checkPct = check?.difference_percent ? Number(check.difference_percent) : 0;

  return (
    <section className="card">
      <div className="card-head">{s.store_name}</div>
      <div className="card-body stack" style={{ paddingTop: 12 }}>
        <h2 className="report-h2">Fuel</h2>
        {noReadings && <Notice kind="info">No tank readings yet. Employees enter the gallons left in each tank at closing on the worksheet.</Notice>}

        <div className="stat-row">
          {f.grades.map((g) => (
            <div key={g.grade} className={`stat${g.order_soon ? " stat-warn" : ""}`}>
              <div className="muted">{g.grade}{g.tanks > 1 ? ` · ${g.tanks} tanks` : ""}{g.order_soon && <span className="chip chip-missing" style={{ marginLeft: 6 }}>Order soon</span>}</div>
              <div className="v">{gal(g.on_hand)} <span style={{ fontSize: 14 }}>gal</span></div>
              <FullBar percent={g.percent_full} warn={g.order_soon} />
              <div className="stat-hint">Delivered {gal(g.delivered)} · used {gal(g.used)} gal this month</div>
            </div>
          ))}
        </div>

        <div className="table-wrap">
          <table style={{ minWidth: 760 }}>
            <thead><tr><th className="left">Tank</th><th className="left">On hand</th><th className="left">% full</th><th>Delivered</th><th>Used</th><th>Avg / day</th><th>Days left</th></tr></thead>
            <tbody>
              {f.tanks.map((t: TankStatus) => (
                <tr key={t.name}>
                  <td className="left">{t.name}<div className="muted small">{t.grade}{t.capacity ? ` · ${gal(t.capacity)} gal tank` : ""}</div></td>
                  <td className="left">{gal(t.on_hand)} gal{t.latest_day && <div className="stamp">read {prettyDate(t.latest_day)}{Number(t.delivered_since_reading) > 0 ? ` + ${gal(t.delivered_since_reading)} delivered since` : ""}</div>}</td>
                  <td className="left"><FullBar percent={t.percent_full} warn={t.order_soon} />{t.order_soon && <div><span className="chip chip-missing">Order soon</span></div>}</td>
                  <td>{gal(t.delivered)}</td>
                  <td>{t.used === null ? <span className="muted" title="Needs two readings">–</span> : gal(t.used)}
                    {t.opening_day && t.closing_day && <div className="stamp">{prettyDate(t.opening_day)} → {prettyDate(t.closing_day)}</div>}</td>
                  <td>{gal(t.average_per_day)}</td>
                  <td>{t.days_left ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small" style={{ margin: 0 }}>
          On hand = latest reading + deliveries since. Used = reading before + deliveries − latest reading. &quot;Order soon&quot; when a tank is under {reorder}% full (Settings) or about 3 days or less are left.
          Readings from submitted and approved days.
        </p>

        {check && (
          <Notice kind={checkPct > 1 && !check.days_missing ? "warn" : "info"}>
            {prettyDate(check.first_day)} – {prettyDate(check.last_day)}: pumps sold <strong>{gal(check.pump_gallons)} gal</strong>, tanks went down{" "}
            <strong>{gal(check.tank_gallons)} gal</strong>.{" "}
            {check.days_missing > 0 ? null : Number(check.difference) === 0 ? "They match."
              : Math.abs(checkPct) <= 1 ? <>A {gal(String(Math.abs(Number(check.difference))))} gal ({Math.abs(checkPct).toFixed(1)}%) difference: within 1%, normal for meter and temperature differences.</>
              : Number(check.difference) > 0
              ? <>Tanks lost <strong>{gal(check.difference)} gal ({check.difference_percent}%)</strong> more than was sold. Check readings, deliveries, or for a leak.</>
              : <>Tanks went down {gal(String(-Number(check.difference)))} gal ({Math.abs(checkPct).toFixed(1)}%) less than was sold. Check the readings.</>}
            {check.days_missing > 0 && <><strong>Can&apos;t compare yet:</strong> {check.days_missing} day{check.days_missing === 1 ? " has" : "s have"} no
              submitted worksheet (missing or sent back), so the pump total is short. Pick a month with every day in.</>}
          </Notice>
        )}

        <div className="stat-row">
          <div className="stat"><div className="muted">Fuel sales</div><div className="v">{money(f.money.sales)}</div>
            <div className="stat-hint">{gal(f.money.gallons_sold)} gal sold</div></div>
          <div className="stat"><div className="muted">Avg sell price</div><div className="v">{perGal(f.money.price_per_gallon)}</div><div className="stat-hint">per gallon</div></div>
          <div className="stat"><div className="muted">Avg cost</div><div className="v">{perGal(f.money.cost_per_gallon)}</div>
            <div className="stat-hint">{money(f.money.delivered_cost)} for {gal(f.money.gallons_costed)} gal delivered</div></div>
          <div className="stat"><div className="muted">Margin</div><div className={`v${f.money.margin_per_gallon && Number(f.money.margin_per_gallon) < 0 ? " neg" : ""}`}>{perGal(f.money.margin_per_gallon)}</div>
            <div className="stat-hint">per gallon, sell − cost</div></div>
        </div>

        <div className="row-wrap" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <strong style={{ fontSize: 14 }}>Deliveries this month</strong>
          {!readOnly && <button className="link-btn" onClick={onDelivery}>+ Add delivery</button>}
        </div>
        {f.deliveries.length === 0 ? <p className="muted" style={{ margin: 0 }}>None typed in yet.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Date</th><th className="left">Tank</th><th>Gallons</th><th>Cost</th><th className="left">Vendor / note</th><th></th></tr></thead>
              <tbody>
                {f.deliveries.map((d) => (
                  <tr key={d.id}>
                    <td className="left">{prettyDate(d.entry_date)}</td><td className="left">{d.tank}</td><td>{gal(d.gallons)}</td>
                    <td>{Number(d.amount) ? money(d.amount) : <span className="muted">invoice to come</span>}</td>
                    <td className="left">{d.description}</td>
                    <td>{readOnly ? null : confirm === d.id ? (
                      <span className="row-wrap" style={{ gap: 6 }}>
                        <button className="btn btn-danger btn-sm" onClick={() => { setConfirm(null); onRemove(d.id); }}>Remove</button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setConfirm(null)}>Keep</button>
                      </span>
                    ) : <button className="link-btn" style={{ color: "var(--bad)" }} onClick={() => setConfirm(d.id)}>Remove</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <h2 className="report-h2" style={{ marginTop: 12 }}>Merchandise</h2>
        <div className="stat-row">
          <div className="stat"><div className="muted">Sold</div><div className="v">{money(m.sold)}</div><div className="stat-hint">merchandise sales this month</div></div>
          <div className="stat"><div className="muted">Bought</div><div className="v">{money(m.bought)}</div>
            <div className="stat-hint">{money(m.bought_typed)} typed in + {money(m.bought_paid_outs)} paid outs</div></div>
          <div className="stat"><div className="muted">Bought as % of sales</div>
            <div className="v">{m.bought_percent_of_sales === null ? "–" : `${m.bought_percent_of_sales}%`}</div>
            <div className="stat-hint">Over 100% = bought more than was sold (stocking up)</div></div>
        </div>
        <div className="row-wrap" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <strong style={{ fontSize: 14 }}>By vendor</strong>
          {!readOnly && <button className="link-btn" onClick={onPurchase}>+ Add purchase</button>}
        </div>
        {m.vendors.length === 0 ? <p className="muted" style={{ margin: 0 }}>No merchandise vendors yet. Add them on <Link to="/reports/vendors">Reports → Vendors</Link>.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Vendor</th><th>Bought this month</th><th className="left">Last purchase</th><th>Days since</th></tr></thead>
              <tbody>
                {m.vendors.map((v) => (
                  <tr key={v.vendor}>
                    <td className="left">{v.vendor}</td>
                    <td>{money(v.amount)}{v.purchases > 1 && <div className="stamp">{v.purchases} purchases</div>}</td>
                    <td className="left">{v.last_day ? prettyDate(v.last_day) : <span className="muted">none yet</span>}</td>
                    <td>{v.days_since ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted small" style={{ margin: 0 }}>
          Bought = merchandise purchases typed in + paid outs to merchandise vendors on the daily sheets. Days since are counted to {prettyDate(asOf)}.
          Item-by-item stock comes later, from invoice files.
        </p>
      </div>
    </section>
  );
}
