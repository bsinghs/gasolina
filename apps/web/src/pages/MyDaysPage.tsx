// An employee's recent worksheets, newest first. Sent-back days are shown at the top with the owner's note.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ReportSummary } from "../api/types";
import { Notice } from "../components/Notice";
import { StatusChip } from "../components/StatusChip";
import { daysAgo, prettyDate } from "../lib/dates";
import { formatOverShort, toCents } from "../lib/money";

export function MyDaysPage() {
  const [rows, setRows] = useState<ReportSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.reports.list({ date_from: daysAgo(30) }).then(setRows).catch((e) => setError(e.message));
  }, []);

  const returned = rows?.filter((r) => r.status === "returned") ?? [];
  const others = rows?.filter((r) => r.status !== "returned") ?? [];
  const link = (r: ReportSummary) => `/worksheet?store=${r.store_id}&date=${r.business_date}`;

  return (
    <main className="page narrow stack">
      <div className="page-head"><h1>My days</h1><span className="muted">Last 30 days</span></div>
      {error && <Notice kind="error">{error}</Notice>}
      {rows?.length === 0 && <Notice kind="info">Nothing yet. Your submitted worksheets will show up here.</Notice>}

      {returned.map((r) => (
        <div key={r.id} className="notice notice-error stack" style={{ gap: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <strong>{prettyDate(r.business_date)} · {r.store_name}</strong><StatusChip status="returned" />
          </div>
          <span>“{r.review_note}”</span>
          <Link className="btn btn-dark" to={link(r)} style={{ alignSelf: "flex-start" }}>Fix and resend</Link>
        </div>
      ))}

      {others.length > 0 && (
        <div className="table-wrap">
          <table>
            <tbody>
              {others.map((r) => {
                const os = toCents(r.over_short);
                return (
                  <tr key={r.id}>
                    <td className="left"><Link to={link(r)}>{prettyDate(r.business_date)}</Link><div className="muted">{r.store_name}</div></td>
                    <td className={os < 0 ? "neg" : os > 0 ? "pos" : ""}>{os === 0 ? "Balanced" : formatOverShort(os)}</td>
                    <td><StatusChip status={r.status} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
