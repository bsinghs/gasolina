// The daily worksheet: the employee's main screen. Same fields and math as the original prototype.
// Drafts save automatically a moment after typing stops.

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { PaidOut, Report } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Notice } from "../components/Notice";
import { OverShortGauge } from "../components/OverShortGauge";
import { PaidOutLines } from "../components/PaidOutLines";
import { StatusChip } from "../components/StatusChip";
import { prettyTime, today } from "../lib/dates";
import { formatMoney, toApiAmount, toCents } from "../lib/money";
import { calculate } from "../lib/reconciliation";

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
        <Notice kind="warn">You're not assigned to a store yet. Ask the owner to add you to one.</Notice>
      </main>
    );
  }

  const moneyRow = (key: (typeof MONEY_FIELDS)[number], label: string) => (
    <div className="field-row">
      <label htmlFor={key}>{label}<span className="unit">$</span></label>
      <input id={key} className="num" inputMode="decimal" placeholder="0.00" value={form[key]}
        disabled={!editable} onChange={(e) => change({ [key]: e.target.value } as Partial<Form>)} />
    </div>
  );

  const cashLines = form.paid_outs.filter((p) => p.kind === "cash");
  const checkLines = form.paid_outs.filter((p) => p.kind === "check");
  const gallons = parseFloat(form.gallons.replace(/,/g, "")) || 0;
  const avgPrice = gallons > 0 ? toCents(form.fuel_sale) / 100 / gallons : 0;

  return (
    <main className="page narrow stack">
      <section className="card card-pad stack" style={{ background: "var(--ink)", color: "#fff", border: "none" }}>
        <div className="row-wrap">
          <label className="label-stack" style={{ color: "#9fb2b7", flex: 1, minWidth: 160 }}>
            Store
            <select value={storeId} onChange={(e) => setParams({ store: e.target.value, date })}>
              {me.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label className="label-stack" style={{ color: "#9fb2b7", flex: 1, minWidth: 140 }}>
            Business date
            <input type="date" className="text" value={date} max={today()}
              onChange={(e) => e.target.value && setParams({ store: storeId, date: e.target.value })} />
          </label>
        </div>
        <div className="muted" style={{ color: "#9fb2b7", display: "flex", gap: 10, alignItems: "center" }}>
          <StatusChip status={status} />
          {loading ? "Loading…" : saving ? "Saving…" : dirty ? "Unsaved changes" : report ? `Saved ${prettyTime(report.updated_at)}` : "New worksheet"}
        </div>
      </section>

      {report?.status === "returned" && report.review_note && (
        <Notice kind="error"><strong>Sent back by the owner:</strong> “{report.review_note}” Fix it and submit again.</Notice>
      )}
      {report && !editable && (
        <Notice kind="info">This day is {status}. It can't be changed{isOwner ? " unless you reopen it from the review screen" : ""}.</Notice>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {unnamedLine && <Notice kind="warn">Add who each paid-out was paid to, so it can be saved.</Notice>}

      <section className="card">
        <div className="card-head">Sales</div>
        <div className="card-body">
          {moneyRow("fuel_sale", "Fuel sale")}
          {moneyRow("merch_sale", "Merchant sale")}
          {moneyRow("sales_tax", "Sales tax collected")}
        </div>
        <div className="total-row"><span>Total sales</span><span>{formatMoney(totals.totalSales)}</span></div>
      </section>

      <section className="card">
        <div className="card-head">Fuel volume</div>
        <div className="card-body">
          <div className="field-row">
            <label htmlFor="gallons">Fuel gallons sold<span className="unit">gal</span></label>
            <input id="gallons" className="num" inputMode="decimal" placeholder="0.0" value={form.gallons}
              disabled={!editable} onChange={(e) => change({ gallons: e.target.value })} />
          </div>
          <div className="sub-row"><span>Avg. price / gallon</span><strong>{avgPrice ? `$${avgPrice.toFixed(2)}` : "–"}</strong></div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">Electronic &amp; food stamp tender</div>
        <div className="card-body">
          {moneyRow("credit", "Credit card")}
          {moneyRow("debit", "Debit card")}
          {moneyRow("ebt", "Food stamp / EBT")}
        </div>
        <div className="total-row"><span>Total non-cash tender</span><span>{formatMoney(totals.nonCash)}</span></div>
      </section>

      <section className="card">
        <div className="card-head">Paid outs</div>
        <div className="card-body">
          <PaidOutLines kind="cash" lines={cashLines} disabled={!editable}
            onChange={(lines) => change({ paid_outs: [...lines, ...checkLines] })} />
          <PaidOutLines kind="check" lines={checkLines} disabled={!editable}
            onChange={(lines) => change({ paid_outs: [...cashLines, ...lines] })} />
        </div>
        <div className="total-row">
          <span>Total paid out <span className="muted">(cash only, checks not deducted)</span></span>
          <span>{formatMoney(totals.cashPaidOut)}</span>
        </div>
      </section>

      <section className="card">
        <div className="card-head">Cash drop</div>
        <div className="card-body">{moneyRow("cash_drop", "Cash drop / actual count")}</div>
      </section>

      <section className="card">
        <div className="card-head">Note to owner</div>
        <div className="card-body" style={{ paddingTop: 12 }}>
          <textarea aria-label="Note to owner" rows={2} style={{ width: "100%" }} placeholder="Optional, e.g. pump 4 down after 3pm"
            value={form.employee_note} disabled={!editable} onChange={(e) => change({ employee_note: e.target.value })} />
        </div>
      </section>

      <section className="summary">
        <h2>RECONCILIATION</h2>
        <div className="sum-line"><span>Total sales</span><strong>{formatMoney(totals.totalSales)}</strong></div>
        <div className="sum-line"><span>Less non-cash tender</span><strong>{formatMoney(totals.nonCash)}</strong></div>
        <div className="sum-line"><span>Less paid outs (cash only)</span><strong>{formatMoney(totals.cashPaidOut)}</strong></div>
        <div className="sum-line"><span>Expected cash</span><strong>{formatMoney(totals.expectedCash)}</strong></div>
        <OverShortGauge cents={totals.overShort} hasCashDrop={form.cash_drop.trim() !== ""} />
        {editable && status !== "submitted" && (
          <div style={{ marginTop: 14 }}>
            {confirmOver && (
              <div style={{ marginBottom: 10 }}>
                <Notice kind="warn">This day is off by more than {formatMoney(threshold)}. Add a note explaining why, or submit anyway.</Notice>
              </div>
            )}
            <button className="btn btn-primary btn-block" disabled={saving || loading || unnamedLine} onClick={submit}>
              {confirmOver ? "Submit anyway" : "Submit for approval"}
            </button>
          </div>
        )}
        {status === "submitted" && !isOwner && (
          <p style={{ textAlign: "center", color: "#9fb2b7", fontSize: 12.5, marginBottom: 0 }}>
            Submitted. The owner will review it.
          </p>
        )}
      </section>
    </main>
  );
}
