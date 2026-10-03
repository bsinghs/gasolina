// Owner settings: stores, QuickBooks account names, and the over/short alert.

import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { AppSettings, QbAccounts, Store } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
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
  const { refresh } = useAuth();
  const [stores, setStores] = useState<Store[]>([]);
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
              <span style={s.active ? undefined : { opacity: 0.5 }}>{s.name}{s.qb_location ? <span className="muted"> · QB location: {s.qb_location}</span> : null}</span>
              <button className="link-btn" onClick={() => guard(() => api.stores.update(s.id, { ...s, active: !s.active }), s.active ? "Store deactivated." : "Store reactivated.")}>
                {s.active ? "Deactivate" : "Reactivate"}
              </button>
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
