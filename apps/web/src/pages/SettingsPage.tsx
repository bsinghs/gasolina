// Owner settings: stores, QuickBooks account names, and the over/short alert.

import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { AppSettings, QbAccounts, Store } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { IS_TEST } from "../lib/env";
import { Notice } from "../components/Notice";

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
  const [confirmReset, setConfirmReset] = useState(false);
  const [stores, setStores] = useState<Store[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [newStore, setNewStore] = useState({ name: "", qb_location: "" });
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const load = () => Promise.all([api.stores.list(), api.settings.get()]).then(([s, st]) => { setStores(s); setSettings(st); });
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
    if (settings) guard(() => api.settings.save(settings), "Settings saved.");
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
              <span style={s.active ? undefined : { opacity: 0.5 }}>{s.name}{!s.active && <span className="muted"> (deactivated)</span>}{s.qb_location ? <span className="muted"> · QB location: {s.qb_location}</span> : null}</span>
              {confirmDelete === s.id ? (
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
          <form onSubmit={addStore} className="row-wrap" style={{ paddingTop: 12 }}>
            <label className="label-stack" style={{ flex: 2, minWidth: 180 }}>New store name
              <input className="text" required value={newStore.name} onChange={(e) => setNewStore({ ...newStore, name: e.target.value })} /></label>
            <label className="label-stack" style={{ flex: 1, minWidth: 140 }}>QuickBooks location (optional)
              <input className="text" value={newStore.qb_location} onChange={(e) => setNewStore({ ...newStore, qb_location: e.target.value })} /></label>
            <button className="btn btn-dark" type="submit">Add store</button>
          </form>
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
          <div className="card-body">
            <p className="muted">Use the exact account names from your QuickBooks chart of accounts (sub-accounts as Parent:Sub).</p>
            {(Object.keys(ACCOUNT_LABELS) as (keyof QbAccounts)[]).map((key) => (
              <div key={key} className="field-row">
                <label htmlFor={`acct-${key}`}>{ACCOUNT_LABELS[key]}</label>
                <input id={`acct-${key}`} className="text" style={{ width: 240 }} value={settings.qb_accounts[key]}
                  onChange={(e) => setSettings({ ...settings, qb_accounts: { ...settings.qb_accounts, [key]: e.target.value } })} />
              </div>
            ))}
            <div className="field-row">
              <label htmlFor="threshold">Warn when over/short is more than<span className="unit">$</span></label>
              <input id="threshold" className="num" inputMode="decimal" value={settings.over_short_alert}
                onChange={(e) => setSettings({ ...settings, over_short_alert: e.target.value })} />
            </div>
          </div>
          <div className="card-pad"><button className="btn btn-primary" type="submit">Save settings</button></div>
        </form>
      )}
    </main>
  );
}
