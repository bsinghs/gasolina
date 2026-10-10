// Owner settings: stores, QuickBooks account names, and the over/short alert.

import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import { GRADES, type Health, type Release, type AppSettings, type Grade, type QbAccounts, type Store, type TankSpec } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { IS_TEST } from "../lib/env";
import { Notice } from "../components/Notice";
import { useViewOnly } from "../lib/access";
import { SCREENS_COMMIT, SCREENS_VERSION } from "../components/VersionFooter";
import { prettyTime } from "../lib/dates";

const ACCOUNT_LABELS: Record<keyof QbAccounts, string> = {
  cash: "Cash drop goes to",
  cards: "Credit + debit cards",
  ebt: "Food stamp / EBT",
  fuel_sales: "Fuel sales",
  merch_sales: "Merchandise sales",
  sales_tax: "Sales tax collected",
  over_short: "Cash over/short",
  default_expense: "Default paid-out expense",
};

export function SettingsPage() {
  const { refresh, me } = useAuth();
  const viewOnly = useViewOnly(); // co-owner: sees stores, tanks and settings; no change buttons
  const [confirmReset, setConfirmReset] = useState(false);
  const [stores, setStores] = useState<Store[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [editTanks, setEditTanks] = useState<{ id: string; tanks: TankSpec[] } | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [taxPct, setTaxPct] = useState("6");
  const [newStore, setNewStore] = useState({ name: "", qb_location: "" });
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const [health, setHealth] = useState<Health | null>(null);
  const [releases, setReleases] = useState<Release[]>([]);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.releases().then(setReleases).catch(() => setReleases([]));
  }, []);

  const load = () => Promise.all([api.stores.list(), api.settings.get()]).then(([s, st]) => { setStores(s); setSettings(st); setTaxPct(String(+(parseFloat(st.sales_tax_rate) * 100).toFixed(2))); });
  useEffect(() => { load().catch((e) => setMessage({ kind: "error", text: e.message })); }, []);

  const guard = async (fn: () => Promise<unknown>, ok: string) => {
    setMessage(null);
    try {
      await fn();
      await load();
      await refresh(); // store list in the header and worksheet
      setMessage({ kind: "ok", text: ok });
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "Couldn't save" });
    }
  };

  const addStore = (e: FormEvent) => {
    e.preventDefault();
    guard(async () => {
      await api.stores.create({ name: newStore.name, qb_location: newStore.qb_location || null, active: true });
      setNewStore({ name: "", qb_location: "" });
    }, "Store added.");
  };

  const saveSettings = (e: FormEvent) => {
    e.preventDefault();
    const rate = parseFloat(taxPct) / 100;
    if (settings && !(settings.reorder_percent >= 1 && settings.reorder_percent <= 90)) {
      setMessage({ kind: "error", text: "\"Order soon\" must be between 1 and 90 % full." });
      return;
    }
    if (settings) guard(() => api.settings.save({ ...settings, sales_tax_rate: rate.toFixed(4) }), "Settings saved.");
  };

  return (
    <main className="page narrow stack">
      <div className="page-head"><h1>Settings</h1></div>
      {message && <Notice kind={message.kind}>{message.text}</Notice>}

      <section className="card">
        <div className="card-head">Stores</div>
        <div className="card-body">
          {stores.map((s) => (
            <div key={s.id} className="field-row">
              <span style={s.active ? undefined : { opacity: 0.5 }}>
                {s.name}{!s.active && <span className="muted"> (deactivated)</span>}{s.qb_location ? <span className="muted"> · QB location: {s.qb_location}</span> : null}
                {editTanks?.id === s.id ? (
                  <TankEditor store={s.name} tanks={editTanks.tanks} onChange={(tanks) => setEditTanks({ id: s.id, tanks })}
                    onCancel={() => setEditTanks(null)}
                    onSave={() => {
                      const tank_specs = editTanks.tanks.map((t) => ({ ...t, name: t.name.trim(), capacity: t.capacity?.trim() || null })).filter((t) => t.name);
                      // previous_name was set when the row was loaded: a renamed tank keeps its readings and deliveries
                      setEditTanks(null);
                      guard(() => api.stores.update(s.id, { name: s.name, qb_location: s.qb_location, active: s.active, tank_specs }),
                        "Tanks saved. Past days keep the tank names they were entered with.");
                    }} />
                ) : (
                  <span className="muted" style={{ display: "block", fontSize: 12 }}>
                    Tanks: {(s.tank_specs ?? []).map((t) => `${t.name} (${t.grade}${t.capacity ? `, ${Number(t.capacity).toLocaleString("en-US")} gal` : ""})`).join(" · ") || "–"}{" "}
                    {!viewOnly && <button className="link-btn" style={{ padding: 0, minHeight: 0, fontSize: 12 }} onClick={() => setEditTanks({ id: s.id, tanks: s.tank_specs.map((t) => ({ ...t, previous_name: t.name })) })}>Change</button>}
                  </span>
                )}
              </span>
              {viewOnly ? null : confirmDelete === s.id ? (
                <span className="row-wrap" style={{ gap: 8, alignItems: "center" }}>
                  <span className="muted">Delete permanently?</span>
                  <button className="btn btn-danger btn-sm" onClick={() => { setConfirmDelete(null); guard(() => api.stores.remove(s.id), "Store deleted."); }}>Yes, delete</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setConfirmDelete(null)}>Cancel</button>
                </span>
              ) : (
                <span className="row-wrap" style={{ gap: 14 }}>
                  <button className="link-btn" title={s.active ? "Closed or sold: hides it, keeps its history" : undefined}
                    onClick={() => guard(() => api.stores.update(s.id, { ...s, active: !s.active }), s.active ? "Store deactivated. Its past days stay in Review and Export." : "Store reactivated.")}>
                    {s.active ? "Deactivate" : "Reactivate"}
                  </button>
                  <button className="link-btn" style={{ color: "var(--bad)" }} title="Only for stores added by mistake (no worksheets yet)"
                    onClick={() => setConfirmDelete(s.id)}>Delete</button>
                </span>
              )}
            </div>
          ))}
          {!viewOnly && <form onSubmit={addStore} className="row-wrap" style={{ paddingTop: 12 }}>
            <label className="label-stack" style={{ flex: 2, minWidth: 180 }}>New store name
              <input className="text" required value={newStore.name} onChange={(e) => setNewStore({ ...newStore, name: e.target.value })} /></label>
            <label className="label-stack" style={{ flex: 1, minWidth: 140 }}>QuickBooks location (optional)
              <input className="text" value={newStore.qb_location} onChange={(e) => setNewStore({ ...newStore, qb_location: e.target.value })} /></label>
            <button className="btn btn-dark" type="submit">Add store</button>
          </form>}
        </div>
      </section>

      {IS_TEST && me?.role === "admin" && (
        <section className="card" style={{ borderColor: "#dd6b20" }}>
          <div className="card-head" style={{ color: "#9c4221" }}>Test data (test environment only)</div>
          <div className="card-body stack" style={{ paddingTop: 12 }}>
            <p className="muted" style={{ margin: 0 }}>
              Deletes every store, person (except app admins), worksheet and history entry in this <strong>test</strong> copy.
              QuickBooks account names are kept. This button doesn't exist in the real app.
            </p>
            {confirmReset ? (
              <div className="row-wrap" style={{ alignItems: "center" }}>
                <span className="muted">Wipe all test data?</span>
                <button className="btn btn-danger btn-sm" onClick={() => {
                  setConfirmReset(false);
                  guard(async () => { await api.admin.resetTestData(); }, "Test data reset. Start fresh: add a store, then people.");
                }}>Yes, wipe it</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setConfirmReset(false)}>Cancel</button>
              </div>
            ) : (
              <div><button className="btn btn-danger" onClick={() => setConfirmReset(true)}>Reset test data</button></div>
            )}
          </div>
        </section>
      )}

      {settings && (
        <form className="card" onSubmit={saveSettings}>
          <div className="card-head">QuickBooks accounts &amp; alerts</div>
          <fieldset disabled={viewOnly} className="card-body" style={{ border: "none", margin: 0, minWidth: 0 }}>
            <p className="muted">Use the exact account names from your QuickBooks chart of accounts (sub-accounts as Parent:Sub).</p>
            {(Object.keys(ACCOUNT_LABELS) as (keyof QbAccounts)[]).map((key) => (
              <div key={key} className="field-row">
                <label htmlFor={`acct-${key}`}>{ACCOUNT_LABELS[key]}</label>
                <input id={`acct-${key}`} className="text" style={{ width: 240 }} value={settings.qb_accounts[key]}
                  onChange={(e) => setSettings({ ...settings, qb_accounts: { ...settings.qb_accounts, [key]: e.target.value } })} />
              </div>
            ))}
            <div className="field-row">
              <label htmlFor="taxrate">Sales tax rate (splits merchandise into taxable / non-taxable)<span className="unit">%</span></label>
              <input id="taxrate" className="num" inputMode="decimal" value={taxPct}
                onChange={(e) => setTaxPct(e.target.value)} />
            </div>
            <div className="field-row">
              <label htmlFor="reorder">Inventory: flag a fuel tank &quot;Order soon&quot; below<span className="unit">% full</span></label>
              <input id="reorder" className="num" inputMode="numeric" value={settings.reorder_percent}
                onChange={(e) => setSettings({ ...settings, reorder_percent: Number(e.target.value.replace(/\D/g, "")) || 0 })} />
            </div>
            <div className="field-row">
              <label htmlFor="threshold">Warn when over/short is more than<span className="unit">$</span></label>
              <input id="threshold" className="num" inputMode="decimal" value={settings.over_short_alert}
                onChange={(e) => setSettings({ ...settings, over_short_alert: e.target.value })} />
            </div>
          </fieldset>
          {!viewOnly && <div className="card-pad"><button className="btn btn-primary" type="submit">Save settings</button></div>}
        </form>
      )}
      <section className="card">
        <div className="card-head">Versions &amp; releases</div>
        <div className="card-body stack" style={{ paddingTop: 12 }}>
          <div className="field-row"><span>Screens (this website)</span><span>{SCREENS_VERSION} · {SCREENS_COMMIT}</span></div>
          <div className="field-row"><span>API ({health?.env ?? "…"})</span><span>{health ? `${health.version} · ${health.commit}` : "…"}</span></div>
          <p className="muted" style={{ margin: 0 }}>
            Each time this copy's API starts with a new version, it's recorded below. What changed in each version is in CHANGELOG.md.
          </p>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">When</th><th className="left">Copy</th><th className="left">Version</th><th className="left">Commit</th><th className="left">By</th></tr></thead>
              <tbody>
                {releases.map((r, i) => (
                  <tr key={i}><td className="left">{prettyTime(r.started_at)}</td><td className="left">{r.env}</td><td className="left">{r.version}</td>
                    <td className="left">{r.git_commit}</td><td className="left">{r.deployed_by ?? "–"}</td></tr>
                ))}
                {releases.length === 0 && <tr><td colSpan={5} className="left muted">No releases recorded yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>
  );
}

/** One row per underground tank: name (as on the worksheet), fuel type, size in gallons (for % full on Inventory). */
function TankEditor({ store, tanks, onChange, onSave, onCancel }: {
  store: string; tanks: TankSpec[]; onChange: (t: TankSpec[]) => void; onSave: () => void; onCancel: () => void;
}) {
  const set = (i: number, patch: Partial<TankSpec>) => onChange(tanks.map((t, j) => (j === i ? { ...t, ...patch } : t)));
  return (
    <span className="stack" style={{ gap: 6, marginTop: 6, display: "flex" }}>
      {tanks.map((t, i) => (
        <span key={i} className="row-wrap" style={{ gap: 6 }}>
          <input className="text" style={{ flex: 2, minWidth: 150 }} aria-label={`${store} tank ${i + 1} name`} value={t.name}
            onChange={(e) => set(i, { name: e.target.value })} />
          <select aria-label={`${store} tank ${i + 1} fuel type`} value={t.grade} onChange={(e) => set(i, { grade: e.target.value as Grade })}>
            {GRADES.map((g) => <option key={g}>{g}</option>)}
          </select>
          <input className="num" style={{ width: 110 }} inputMode="numeric" placeholder="Size (gal)" aria-label={`${store} tank ${i + 1} size in gallons`}
            value={t.capacity ?? ""} onChange={(e) => set(i, { capacity: e.target.value.replace(/\D/g, "") || null })} />
          <button type="button" className="icon-btn" aria-label={`Remove ${store} tank ${i + 1}`} onClick={() => onChange(tanks.filter((_, j) => j !== i))}>✕</button>
        </span>
      ))}
      <span className="row-wrap" style={{ gap: 8 }}>
        {tanks.length < 10 && (
          <button type="button" className="link-btn" onClick={() => onChange([...tanks, { name: `Tank ${tanks.length + 1}`, grade: "Regular", capacity: null }])}>+ Add tank</button>
        )}
        <button type="button" className="btn btn-primary btn-sm" onClick={onSave}>Save tanks</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
      </span>
      <span className="muted" style={{ fontSize: 12 }}>Size is the tank&apos;s capacity in gallons (on the tank chart). Needed for &quot;% full&quot; on Inventory.</span>
    </span>
  );
}
