// Balance Sheet at the end of a month (owner). The owner types what the business has and owes;
// the API adds PA tax owed and profit to date, and checks Assets = Liabilities + Equity.
// Edits stay on screen until "Save balances", so a half-typed sheet never overwrites the saved one.

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { BalanceLineInput, BalanceSection, BalanceSheet } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { useViewOnly } from "../lib/access";
import { Notice } from "../components/Notice";
import { ReportTabs } from "../components/ReportTabs";
import { Statement, type Row } from "../components/Statement";
import { today } from "../lib/dates";
import { formatMoney, parseAmount, toCents } from "../lib/money";

const SECTIONS: { key: BalanceSection; title: string; hint: string; starter: string[] }[] = [
  { key: "asset", title: "Assets (what you own)", hint: "Bank balance from the statement, cash on hand, inventory at cost, equipment.",
    starter: ["Cash in bank", "Cash on hand", "Fuel inventory", "Merchandise inventory", "Equipment & fixtures"] },
  { key: "liability", title: "Liabilities (what you owe)", hint: "PA sales tax collected this month is added automatically.",
    starter: ["Accounts payable", "Loans", "Credit card balance"] },
  { key: "equity", title: "Equity (owner's share)", hint: "Enter owner draws as a negative number. Profit to date is added automatically.",
    starter: ["Owner's investment", "Owner draws", "Opening retained earnings"] },
];

type EditLine = BalanceLineInput & { key: number };
let nextKey = 1;
const withKeys = (lines: BalanceLineInput[]): EditLine[] => lines.map((l) => ({ ...l, key: nextKey++ }));

export function BalanceSheetPage() {
  const viewOnly = useViewOnly();
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const month = params.get("month") ?? today().slice(0, 7);
  const storeId = params.get("store") ?? "";
  const countPaidOuts = params.get("paidouts") !== "off";
  const set = (patch: Record<string, string>) =>
    setParams(Object.fromEntries(Object.entries({ month, store: storeId, paidouts: countPaidOuts ? "" : "off", ...patch }).filter(([, v]) => v !== "")));

  const [sheet, setSheet] = useState<BalanceSheet | null>(null);
  const [lines, setLines] = useState<EditLine[]>([]);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const show = (b: BalanceSheet) => { setSheet(b); setLines(withKeys(b.typed_lines)); setDirty(false); };
  const load = useCallback(() => api.books.balance(month, storeId || undefined, countPaidOuts).then(show), [month, storeId, countPaidOuts]);
  useEffect(() => { setMessage(null); load().catch((e) => setMessage({ kind: "error", text: e.message })); }, [load]);

  const edit = (key: number, patch: Partial<EditLine>) => { setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l))); setDirty(true); };
  const add = (section: BalanceSection, name = "") => { setLines((ls) => [...ls, { key: nextKey++, section, name, amount: "" }]); setDirty(true); };
  const remove = (key: number) => { setLines((ls) => ls.filter((l) => l.key !== key)); setDirty(true); };

  const run = async (fn: () => Promise<BalanceSheet>, ok: string) => {
    setMessage(null);
    try {
      show(await fn());
      setMessage({ kind: "ok", text: ok });
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "Couldn't save" });
    }
  };
  const save = () => {
    const unnamed = lines.some((l) => !l.name.trim() && toCents(l.amount) !== 0);
    if (unnamed) { setMessage({ kind: "error", text: "Give every line with an amount a name." }); return; }
    const bad = lines.find((l) => parseAmount(l.amount) === null);
    if (bad) { setMessage({ kind: "error", text: `“${bad.amount}” for ${bad.name || "a line"} isn't an amount. Type it like 1250.00, or (500.00) / -500 for a minus.` }); return; }
    const clean = lines.filter((l) => l.name.trim()).map((l) => ({ section: l.section, name: l.name.trim(), amount: parseAmount(l.amount) as string }));
    run(async () => { await api.books.saveBalance({ month, store_id: storeId || null, lines: clean }); return api.books.balance(month, storeId || undefined, countPaidOuts); }, "Balances saved.");
  };

  const statement: Row[] = sheet ? [
    { kind: "head", label: "Assets" }, ...sheet.assets.map((line) => ({ kind: "line" as const, line })),
    { kind: "total", label: "Total assets", amount: sheet.total_assets, tone: "big" },
    { kind: "head", label: "Liabilities" }, ...sheet.liabilities.map((line) => ({ kind: "line" as const, line })),
    { kind: "total", label: "Total liabilities", amount: sheet.total_liabilities },
    { kind: "head", label: "Equity" }, ...sheet.equity.map((line) => ({ kind: "line" as const, line })),
    { kind: "total", label: "Total equity", amount: sheet.total_equity },
    { kind: "total", label: "Total liabilities + equity", amount: ((toCents(sheet.total_liabilities) + toCents(sheet.total_equity)) / 100).toFixed(2), tone: "big" },
    { kind: "total", label: sheet.balanced ? "Balanced ✓" : "Off by (assets − liabilities − equity)", amount: sheet.difference, tone: sheet.balanced ? "good" : "bad" },
  ] : [];
  const empty = sheet && sheet.typed_lines.length === 0 && lines.length === 0;
  const storeName = storeId ? me?.stores.find((s) => s.id === storeId)?.name ?? "1 store" : "The whole business (shared)";

  return (
    <main className="page stack">
      <div className="page-head">
        <div>
          <h1>Balance Sheet</h1>
          <div className="muted">End of {sheet?.label ?? "…"} · {storeName}</div>
        </div>
      </div>
      <ReportTabs />

      <div className="report-controls">
        <label className="label-stack">As of the end of<input type="month" className="text" value={month}
          disabled={dirty} title={dirty ? "Save or undo your changes first" : undefined}
          onChange={(e) => e.target.value && set({ month: e.target.value })} /></label>
        <label className="label-stack">For<select value={storeId} onChange={(e) => set({ store: e.target.value })} disabled={dirty} title={dirty ? "Save or undo your changes first" : undefined}>
          <option value="">The whole business (shared)</option>
          {me?.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select></label>
        <label className="check-inline"><input type="checkbox" checked={countPaidOuts} disabled={dirty} onChange={(e) => set({ paidouts: e.target.checked ? "" : "off" })} />
          Profit to date counts daily paid outs</label>
      </div>
      {!storeId && <div className="muted">This view adds up the shared lines below and each store's own lines (shown with the store's name in the statement). Pick a store to type that store's lines.</div>}
      {message && <Notice kind={message.kind}>{message.text}</Notice>}

      {sheet && (
        <div className="stat-row">
          <div className="stat"><div className="muted">Total assets</div><div className="v">{formatMoney(toCents(sheet.total_assets))}</div></div>
          <div className="stat"><div className="muted">Total liabilities</div><div className="v">{formatMoney(toCents(sheet.total_liabilities))}</div></div>
          <div className="stat"><div className="muted">Total equity</div><div className="v">{formatMoney(toCents(sheet.total_equity))}</div></div>
          <div className="stat"><div className="muted">Check</div><div className={`v ${sheet.balanced ? "pos" : "neg"}`}>{sheet.balanced ? "Balanced" : `Off ${formatMoney(toCents(sheet.difference))}`}</div>
            <div className="stat-hint">Assets = liabilities + equity</div></div>
        </div>
      )}

      {!viewOnly && <section className="card">
        <div className="card-head">Balances at the end of {sheet?.label ?? "the month"}</div>
        <div className="card-body stack">
          {empty && (
            <div className="row-wrap" style={{ gap: 8 }}>
              <button className="btn btn-ghost" onClick={() => run(async () => { await api.books.copyPrevious(month, storeId || undefined); return api.books.balance(month, storeId || undefined, countPaidOuts); }, "Copied last month's lines. Update the amounts and save.")}>Copy last month's lines</button>
              <button className="btn btn-ghost" onClick={() => { SECTIONS.forEach((s) => s.starter.forEach((n) => add(s.key, n))); }}>Start with common lines</button>
            </div>
          )}
          {SECTIONS.map((s) => (
            <div key={s.key}>
              <div className="lines-head">{s.title}</div>
              <div className="muted" style={{ marginBottom: 6 }}>{s.hint}</div>
              {lines.filter((l) => l.section === s.key).map((l) => (
                <div className="bs-line" key={l.key}>
                  <input aria-label={`${s.title} line name`} value={l.name} placeholder="Name" maxLength={120} onChange={(e) => edit(l.key, { name: e.target.value })} />
                  <input className="amt" aria-label={`${l.name || "line"} amount`} inputMode="decimal" placeholder="0.00" value={l.amount} onChange={(e) => edit(l.key, { amount: e.target.value })} />
                  <button type="button" className="icon-btn" aria-label={`Remove ${l.name || "line"}`} onClick={() => remove(l.key)}>✕</button>
                </div>
              ))}
              <button type="button" className="link-btn" onClick={() => add(s.key)}>+ Add line</button>
            </div>
          ))}
        </div>
      </section>}

      {dirty && !viewOnly && (
        <div className="save-bar" role="status">
          <span>You have changes that aren't saved yet.</span>
          <span className="row-wrap" style={{ gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => sheet && show(sheet)}>Undo changes</button>
            <button className="btn btn-primary btn-sm" onClick={save}>Save balances</button>
          </span>
        </div>
      )}

      {sheet && (
        <section className="stack" style={{ gap: 8 }}>
          <h2 className="report-h2">Statement (saved)</h2>
          <Statement rows={statement} />
          <p className="muted" style={{ margin: 0 }}>
            Profit to date adds up every month's net profit from the Profit &amp; Loss{storeId ? " for this store" : ""}. Type bank balances from the bank statement.
          </p>
        </section>
      )}
    </main>
  );
}
