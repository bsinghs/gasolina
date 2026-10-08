// The owner's Reports area: one menu item, four sections.
import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/reports", label: "Sales", end: true },
  { to: "/reports/pnl", label: "Profit & Loss" },
  { to: "/reports/balance", label: "Balance Sheet" },
  { to: "/reports/vendors", label: "Vendors" },
];

export function ReportTabs() {
  return (
    <nav className="report-tabs" aria-label="Reports">
      {TABS.map((t) => (
        <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => (isActive ? "on" : "")}>{t.label}</NavLink>
      ))}
    </nav>
  );
}
