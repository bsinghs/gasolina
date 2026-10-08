// Owner's view of one day: the worksheet, the QuickBooks entry it will produce, and approve / send back.

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { JournalLine, Report } from "../api/types";
import { Notice } from "../components/Notice";
import { StatusChip } from "../components/StatusChip";
import { prettyDate, prettyTime } from "../lib/dates";
import { formatMoney, formatOverShort, toCents } from "../lib/money";

export function DayDetailPage() {
  const { id = "" } = useParams();
  const [report, setReport] = useState<Report | null>(null);
  const [journal, setJournal] = useState<JournalLine[]>([]);
  const [accounts, setAccounts] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [showReturn, setShowReturn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = (r: Report) => {
    setReport(r);
    setAccounts(Object.fromEntries(r.paid_outs.filter((p) => p.kind === "cash").map((p) => [p.id!, p.gl_account ?? ""])));
    api.exports.journalPreview(r.id).then(setJournal).catch(() => setJournal([]));
  };

  useEffect(() => {
    api.reports.get(id).then(load).catch((e) => setError(e.message));
  }, [id]);

  const act = async (fn: () => Promise<Report>) => {
    setBusy(true);
    setError(null);
    try {
      load(await fn());
      setShowReturn(false);
      setNote("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  if (!report) return <main className="page">{error ? <Notice kind="error">{error}</Notice> : <p className="muted">Loading…</p>}</main>;

  const os = toCents(report.over_short);
  const line = (label: string, value: string, strong = false) => (
    <div className="field-row" style={strong ? { fontWeight: 600 } : undefined}><span>{label}</span><span>{value}</span></div>
  );
  const debits = journal.reduce((s, l) => s + toCents(l.debit), 0);
  const credits = journal.reduce((s, l) => s + toCents(l.credit), 0);
  const cashLines = report.paid_outs.filter((p) => p.kind === "cash");
  const checkLines = report.paid_outs.filter((p) => p.kind === "check");

  return (
    <main className="page stack">
      <Link to="/review">← Review queue</Link>
      <div className="page-head">
        <div>
          <h1>{report.store_name} · {prettyDate(report.business_date)}</h1>
          <div className="muted" style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
            <StatusChip status={report.status} />
            {report.submitted_by_name ? `Submitted by ${report.submitted_by_name} ${prettyTime(report.submitted_at)}` : "Not submitted yet"}
          </div>
        </div>
        <div className="row-wrap">
          {(report.status === "submitted" || report.status === "draft" || report.status === "returned") && (
            <Link className="btn btn-ghost" to={`/worksheet?store=${report.store_id}&date=${report.business_date}`}>Edit</Link>
          )}
          {report.status === "submitted" && (
            <>
              <button className="btn btn-danger" disabled={busy} onClick={() => setShowReturn(true)}>Send back</button>
              <button className="btn btn-primary" disabled={busy}
                onClick={() => act(() => api.reports.approve(report.id, Object.fromEntries(Object.entries(accounts).filter(([, v]) => v.trim()))))}>
                Approve
              </button>
            </>
          )}
          {(report.status === "approved" || report.status === "exported") && (
            <button className="btn btn-ghost" disabled={busy} onClick={() => act(() => api.reports.reopen(report.id))}>Reopen</button>
          )}
        </div>
      </div>

      {error && <Notice kind="error">{error}</Notice>}
      {showReturn && (
        <div className="card card-pad stack" style={{ gap: 10 }}>
          <label className="label-stack" htmlFor="return-note">What needs fixing? The employee sees this note.</label>
          <textarea id="return-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Debit looks high vs the Z-report. Please recheck." />
          <div className="row-wrap">
            <button className="btn btn-danger" disabled={busy || !note.trim()} onClick={() => act(() => api.reports.sendBack(report.id, note))}>Send back</button>
            <button className="btn btn-ghost" onClick={() => setShowReturn(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="grid-2">
        <section className="card">
          <div className="card-head">Worksheet</div>
          <div className="card-body">
            {line("Fuel sale", formatMoney(toCents(report.fuel_sale)))}
            {line("Merchandise sale", formatMoney(toCents(report.merch_sale)))}
            {line("↳ Taxable (sales tax ÷ rate)", formatMoney(toCents(report.taxable_sale)))}
            {line("↳ Non-taxable (merchandise − taxable)", formatMoney(toCents(report.nontaxable_sale)))}
            {line("Sales tax", formatMoney(toCents(report.sales_tax)))}
            {line("Total sales", formatMoney(toCents(report.total_sales)), true)}
            {line("Gallons", `${report.gallons} gal`)}
            {(report.tank_inventory ?? []).map((t) => line(`↳ Ending: ${t.tank}`, `${t.gallons} gal`))}
            {line("Credit / debit", `${formatMoney(toCents(report.credit))} / ${formatMoney(toCents(report.debit))}`)}
            {line("EBT", formatMoney(toCents(report.ebt)))}
            {cashLines.map((p) => line(`Cash paid out: ${p.payee}`, formatMoney(toCents(p.amount))))}
            {checkLines.map((p) => line(`Check ${p.check_no ? "#" + p.check_no : ""}: ${p.payee}`, formatMoney(toCents(p.amount))))}
            {line("Expected cash", formatMoney(toCents(report.expected_cash)))}
            {line("Cash drop", formatMoney(toCents(report.cash_drop)))}
          </div>
          <div className="total-row" style={{ background: os < 0 ? "var(--bad-bg)" : os > 0 ? "#fff4e0" : "var(--good-bg)" }}>
            <span>Over / (short)</span><span className={os < 0 ? "neg" : ""}>{formatOverShort(os)}</span>
          </div>
          {report.employee_note && <p className="card-pad" style={{ margin: 0, fontSize: 13 }}>Note: “{report.employee_note}”</p>}
        </section>

        <section className="card">
          <div className="card-head">QuickBooks journal entry</div>
          <div className="card-body">
            {report.status === "submitted" && cashLines.length > 0 && (
              <div className="stack" style={{ gap: 8, padding: "10px 0" }}>
                <span className="muted">Expense account for each cash paid out (blank = default):</span>
                {cashLines.map((p) => (
                  <label key={p.id} className="label-stack">{p.payee}
                    <input className="text" value={accounts[p.id!] ?? ""} placeholder="e.g. Supplies"
                      onChange={(e) => setAccounts({ ...accounts, [p.id!]: e.target.value })} />
                  </label>
                ))}
              </div>
            )}
            <div style={{ overflowX: "auto" }}><table>
              <thead><tr><th className="left">Account</th><th>Debit</th><th>Credit</th></tr></thead>
              <tbody>
                {journal.map((l, i) => (
                  <tr key={i}>
                    <td className="left">{l.account}</td>
                    <td>{toCents(l.debit) ? formatMoney(toCents(l.debit)) : ""}</td>
                    <td>{toCents(l.credit) ? formatMoney(toCents(l.credit)) : ""}</td>
                  </tr>
                ))}
                <tr style={{ fontWeight: 600 }}><td className="left">Total</td><td>{formatMoney(debits)}</td><td>{formatMoney(credits)}</td></tr>
              </tbody>
            </table></div>
            <p className={debits === credits ? "pos" : "neg"} style={{ fontSize: 12.5 }}>{debits === credits ? "Balanced ✓" : "Not balanced"}</p>
            {checkLines.length > 0 && <p className="muted">Check paid-outs aren't in this entry. They're in the check paid-outs export.</p>}
          </div>
        </section>

        <section className="card">
          <div className="card-head">History</div>
          <div className="card-body">
            {report.history.map((h, i) => (
              <div key={i} className="field-row" style={{ fontSize: 12.5 }}>
                <span>{h.action}{h.actor_name ? ` · ${h.actor_name}` : ""}{typeof h.details.note === "string" ? ` · “${h.details.note}”` : ""}</span>
                <span className="muted">{prettyTime(h.at)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
