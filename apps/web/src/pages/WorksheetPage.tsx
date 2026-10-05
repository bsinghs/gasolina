// The daily worksheet: the employee's main screen. Layout follows the owner's "GGS Daily Sales Worksheet".
// Drafts save automatically a moment after typing stops.

import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { PaidOut, Report } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Notice } from "../components/Notice";
import { PaidOutLines } from "../components/PaidOutLines";
import { StatusChip } from "../components/StatusChip";
import { prettyTime, today } from "../lib/dates";
import { formatMoney, formatOverShort, toApiAmount, toCents } from "../lib/money";
import { calculate } from "../lib/reconciliation";

const TWO_COLS = { "--cols": 2 } as CSSProperties;
const MONEY_FIELDS = ["fuel_sale", "merch_sale", "sales_tax", "credit", "debit", "ebt", "cash_drop"] as const;

interface Form {
  fuel_sale: string;
  merch_sale: string;
  sales_tax: string;
  gallons: string;
  credit: string;
  debit: string;
  ebt: string;
  cash_drop: string;
  employee_note: string;
  paid_outs: PaidOut[];
}

const EMPTY: Form = {
  fuel_sale: "", merch_sale: "", sales_tax: "", gallons: "", credit: "", debit: "", ebt: "", cash_drop: "",
  employee_note: "", paid_outs: [],
};

function blankIfZero(v: string) {
  return toCents(v) === 0 ? "" : v;
}

function formFromReport(r: Report): Form {
  return {
    ...Object.fromEntries(MONEY_FIELDS.map((k) => [k, blankIfZero(r[k])])),
    gallons: parseFloat(r.gallons) ? r.gallons : "",
    employee_note: r.employee_note ?? "",
    paid_outs: r.paid_outs,
  } as Form;
}

export function WorksheetPage() {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const storeId = params.get("store") ?? me?.stores[0]?.id ?? "";
  const date = params.get("date") ?? today();

  const [form, setForm] = useState<Form>(EMPTY);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmOver, setConfirmOver] = useState(false);
  const saveTimer = useRef<number>();

  const isOwner = me?.role === "owner";
  const status = report?.status ?? "draft";
  const editable = status === "draft" || status === "returned" || (isOwner && status === "submitted");
  const totals = calculate(form);
  const threshold = toCents(me?.over_short_alert ?? "20");
  const unnamedLine = form.paid_outs.some((p) => toCents(p.amount) > 0 && !p.payee.trim());

  // Load the worksheet for the chosen store + date
  useEffect(() => {
    if (!storeId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.reports.lookup(storeId, date)
      .then((r) => {
        if (cancelled) return;
        setReport(r);
        setForm(r ? formFromReport(r) : EMPTY);
        setDirty(false);
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [storeId, date]);

  const save = useCallback(async (): Promise<Report | null> => {
    if (unnamedLine) return null;
    setSaving(true);
    setError(null);
    try {
      const saved = await api.reports.save({
        store_id: storeId,
        business_date: date,
        ...Object.fromEntries(MONEY_FIELDS.map((k) => [k, toApiAmount(form[k])])),
        gallons: (parseFloat(form.gallons.replace(/,/g, "")) || 0).toFixed(1),
        employee_note: form.employee_note.trim() || null,
        paid_outs: form.paid_outs
          .filter((p) => p.payee.trim() || toCents(p.amount) > 0)
          .map((p) => ({ ...p, payee: p.payee.trim(), amount: toApiAmount(p.amount), check_no: p.check_no?.trim() || null })),
        field_sources: {},
      } as never);
      setReport(saved);
      setDirty(false);
      return saved;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save");
      return null;
    } finally {
      setSaving(false);
    }
  }, [form, storeId, date, unnamedLine]);

  // Autosave 1.5 s after the last change
  useEffect(() => {
    if (!dirty || !editable) return;
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(save, 1500);
    return () => window.clearTimeout(saveTimer.current);
  }, [dirty, editable, save]);

  const change = (patch: Partial<Form>) => {
    setForm((f) => ({ ...f, ...patch }));
    setDirty(true);
    setConfirmOver(false);
  };

  const submit = async () => {
    const needsNote = Math.abs(totals.overShort) > threshold && !form.employee_note.trim();
    if (needsNote && !confirmOver) {
      setConfirmOver(true);
      return;
    }
    window.clearTimeout(saveTimer.current);
    const saved = await save();
    if (!saved) return;
    try {
      setReport(await api.reports.submit(saved.id));
      setConfirmOver(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't submit");
    }
  };

  if (!me?.stores.length) {
    return (
      <main className="page narrow">
        {isOwner ? (
          <Notice kind="info">
            No stores yet. Add your first store in <Link to="/settings">Settings</Link>, then come back here.
          </Notice>
        ) : (
          <Notice kind="warn">You're not assigned to a store yet. Ask the owner to add you to one.</Notice>
        )}
      </main>
    );
  }

  const moneyField = (key: (typeof MONEY_FIELDS)[number], label: string, hint?: string) => (
    <div className="field">
      <label htmlFor={key}>{label} ($)</label>
      <input id={key} className="num" inputMode="decimal" placeholder="0.00" value={form[key]}
        disabled={!editable} onChange={(e) => change({ [key]: e.target.value } as Partial<Form>)} />
      {hint && <span className="hint">{hint}</span>}
    </div>
  );

  const cashLines = form.paid_outs.filter((p) => p.kind === "cash");
  const checkLines = form.paid_outs.filter((p) => p.kind === "check");
  const gallons = parseFloat(form.gallons.replace(/,/g, "")) || 0;
  const avgPrice = gallons > 0 ? toCents(form.fuel_sale) / 100 / gallons : 0;
  const hasCashDrop = form.cash_drop.trim() !== "";
  const os = totals.overShort;
  const osKind = !hasCashDrop || os === 0 ? "" : os < 0 ? "danger" : "success";
  const osText = !hasCashDrop ? "Enter the cash drop to reconcile" : os === 0 ? "Balanced" : os < 0 ? `Short by ${formatMoney(-os)}` : `Over by ${formatMoney(os)}`;
  const statusText = loading ? "Loading…" : saving ? "Saving…" : dirty ? "Unsaved changes" : report ? `Saved ${prettyTime(report.updated_at)}` : "New worksheet";
  const storeName = me.stores.find((s) => s.id === storeId)?.name ?? "";

  return (
    <main className="page sheet stack">
      {report?.status === "returned" && report.review_note && (
        <Notice kind="error"><strong>Sent back by the owner:</strong> “{report.review_note}” Fix it and submit again.</Notice>
      )}
      {report && !editable && (
        <Notice kind="info">This day is {status}. It can't be changed{isOwner ? " unless you reopen it from the review screen" : ""}.</Notice>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {unnamedLine && <Notice kind="warn">Add who each paid-out was paid to, so it can be saved.</Notice>}

      <div className="sheet-card">
        <header className="sheet-header">
          <h1>Daily Sales Worksheet</h1>
          <div className="meta">
            <select aria-label="Store" value={storeId} onChange={(e) => setParams({ store: e.target.value, date })}>
              {me.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <input type="date" aria-label="Business date" value={date} max={today()}
              onChange={(e) => e.target.value && setParams({ store: storeId, date: e.target.value })} />
          </div>
        </header>

        <div className="sheet-toolbar no-print">
          <span className="status"><StatusChip status={status} /> {statusText}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => window.print()}>Print / PDF</button>
        </div>
        <div className="sheet-toolbar print-only">
          {storeName} · {date} · {me.name}
        </div>

        <section className="section">
          <h2 className="section-title">Sales</h2>
          <div className="fields">
            {moneyField("fuel_sale", "Fuel Sales")}
            {moneyField("merch_sale", "Merchandise Sales")}
            {moneyField("sales_tax", "Tax Collected")}
          </div>
          <div className="calc-box">
            <span className="calc-label">Total Sales <small>Fuel + Merchandise + Tax</small></span>
            <span className="calc-value">{formatMoney(totals.totalSales)}</span>
          </div>
        </section>

        <section className="section">
          <h2 className="section-title">Payments Received (non-cash)</h2>
          <div className="fields">
            {moneyField("credit", "Credit Cards")}
            {moneyField("debit", "Debit Cards")}
            {moneyField("ebt", "Food Stamps / EBT")}
          </div>
          <div className="calc-box">
            <span className="calc-label">Total Non-Cash</span>
            <span className="calc-value">{formatMoney(totals.nonCash)}</span>
          </div>
        </section>

        <section className="section">
          <h2 className="section-title">Paid Outs</h2>
          <div className="grid-2">
            <PaidOutLines kind="cash" lines={cashLines} disabled={!editable}
              onChange={(lines) => change({ paid_outs: [...lines, ...checkLines] })} />
            <PaidOutLines kind="check" lines={checkLines} disabled={!editable}
              onChange={(lines) => change({ paid_outs: [...cashLines, ...lines] })} />
          </div>
          <div className="calc-box">
            <span className="calc-label">Cash Paid Out <small>Checks don't come out of the drawer</small></span>
            <span className="calc-value">{formatMoney(totals.cashPaidOut)}</span>
          </div>
        </section>

        <section className="section">
          <h2 className="section-title">Cash Management</h2>
          <div className="fields" style={TWO_COLS}>
            {moneyField("cash_drop", "Cash Drop / Actual Cash")}
            <div className="field">
              <label htmlFor="expected">Expected Cash</label>
              <input id="expected" readOnly value={formatMoney(totals.expectedCash)} tabIndex={-1} />
              <span className="hint">Total sales − non-cash − cash paid out</span>
            </div>
          </div>
          <div className={`calc-box ${osKind}`} aria-live="polite">
            <span className="calc-label">Over / Short <small>{osText}</small></span>
            <span className="calc-value">{hasCashDrop ? formatOverShort(os) : "–"}</span>
          </div>
        </section>

        <section className="section">
          <h2 className="section-title">Gallons Sold</h2>
          <div className="fields" style={TWO_COLS}>
            <div className="field">
              <label htmlFor="gallons">Total Gallons</label>
              <input id="gallons" className="num" inputMode="decimal" placeholder="0.0" value={form.gallons}
                disabled={!editable} onChange={(e) => change({ gallons: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="avg">Avg. Price / Gallon</label>
              <input id="avg" readOnly tabIndex={-1} value={avgPrice ? `$${avgPrice.toFixed(3)}` : "–"} />
            </div>
          </div>
        </section>

        <section className="section">
          <h2 className="section-title">Notes / Comments</h2>
          <div className="field">
            <textarea aria-label="Notes" rows={3} placeholder="Any discrepancies, special notes, or comments…"
              value={form.employee_note} disabled={!editable} onChange={(e) => change({ employee_note: e.target.value })} />
          </div>
        </section>

        {(editable && status !== "submitted") || (status === "submitted" && !isOwner) ? (
          <div className="sheet-footer no-print">
            {editable && status !== "submitted" && (
              <>
                {confirmOver && (
                  <div style={{ marginBottom: 10 }}>
                    <Notice kind="warn">This day is off by more than {formatMoney(threshold)}. Add a note explaining why, or submit anyway.</Notice>
                  </div>
                )}
                <button className="btn btn-success btn-block" disabled={saving || loading || unnamedLine} onClick={submit}>
                  {confirmOver ? "Submit anyway" : "Submit for approval"}
                </button>
                <p className="muted" style={{ textAlign: "center", margin: "8px 0 0" }}>Saves automatically as you type.</p>
              </>
            )}
            {status === "submitted" && !isOwner && (
              <p className="muted" style={{ textAlign: "center", margin: 0 }}>Submitted. The owner will review it.</p>
            )}
          </div>
        ) : null}
      </div>
    </main>
  );
}
