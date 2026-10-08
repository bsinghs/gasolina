// A money statement (Profit & Loss, Balance Sheet): headings, lines, totals.
// Lines with something behind them (paid outs, typed entries) open on tap to show the detail.
import { Fragment, useState } from "react";
import type { BookLine } from "../api/types";
import { formatMoney, toCents } from "../lib/money";

export type Row =
  | { kind: "head"; label: string }
  | { kind: "line"; line: BookLine; indent?: boolean }
  | { kind: "info"; label: string; amount: string }
  | { kind: "total"; label: string; amount: string; tone?: "good" | "bad" | "big" };

const SOURCE: Record<BookLine["source"], string> = { typed: "typed", paid_outs: "paid outs", days: "from the days", auto: "automatic" };

export function Statement({ rows }: { rows: Row[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="table-wrap">
      <table className="statement">
        <tbody>
          {rows.map((r, i) => {
            if (r.kind === "head") return <tr key={i} className="st-head"><td colSpan={2}>{r.label}</td></tr>;
            if (r.kind === "info") return <tr key={i} className="st-info"><td>{r.label}</td><td>{formatMoney(toCents(r.amount))}</td></tr>;
            if (r.kind === "total") {
              return <tr key={i} className={`st-total ${r.tone ?? ""}`}><td>{r.label}</td><td>{formatMoney(toCents(r.amount))}</td></tr>;
            }
            const key = `${i}-${r.line.label}`;
            const canOpen = r.line.items.length > 0;
            return (
              <Fragment key={key}>
                <tr className={canOpen ? "st-line clickable" : "st-line"} onClick={() => canOpen && setOpen(open === key ? null : key)}
                  aria-expanded={canOpen ? open === key : undefined}>
                  <td>
                    {r.line.label} <span className="pill">{SOURCE[r.line.source]}</span>
                    {canOpen && <span className="muted"> {open === key ? "▾" : "›"}</span>}
                  </td>
                  <td>{formatMoney(toCents(r.line.amount))}</td>
                </tr>
                {open === key && r.line.items.map((it, j) => (
                  <tr key={`${key}-${j}`} className="st-detail">
                    <td>{[it.what, it.vendor].filter(Boolean).join(" · ") || "—"}</td>
                    <td>{formatMoney(toCents(it.amount))}</td>
                  </tr>
                ))}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
