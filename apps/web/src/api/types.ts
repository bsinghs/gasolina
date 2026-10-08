// Shapes returned by the API. Money comes back as strings like "1234.50" to avoid rounding errors.

export type Role = "employee" | "manager" | "owner" | "admin";

/** Owner powers: the business owner, or the app admin (support). */
export const hasOwnerAccess = (role: Role | string | undefined) => role === "owner" || role === "admin";
export type Status = "draft" | "submitted" | "returned" | "approved" | "exported";
export type PaidOutKind = "cash" | "check";

export interface Me {
  id: string;
  email: string;
  name: string;
  role: Role;
  stores: { id: string; name: string; tracking_since: string; tanks: string[] }[];
  over_short_alert: string;
  sales_tax_rate: string;
  view_as_options?: { id: string; name: string; role: Role }[] | null; // app admin only
  viewed_by_name?: string | null; // set while the admin is viewing as this person (read-only)
}

export interface Store {
  id: string;
  name: string;
  qb_location: string | null;
  active: boolean;
  tanks: string[]; // underground fuel tanks, in reading order
}

export interface Person {
  id: string;
  email: string;
  name: string;
  role: Role;
  active: boolean;
  store_ids: string[];
  has_signed_in: boolean;
}

export interface PaidOut {
  id?: string;
  kind: PaidOutKind;
  check_no: string | null;
  payee: string;
  amount: string;
  gl_account: string | null;
}

export interface WorksheetInput {
  store_id: string;
  business_date: string;
  fuel_sale: string;
  merch_sale: string;
  sales_tax: string;
  gallons: string;
  credit: string;
  debit: string;
  ebt: string;
  cash_drop: string;
  employee_note: string | null;
  paid_outs: PaidOut[];
  tank_inventory: TankReading[]; // ending gallons per tank
  field_sources: Record<string, "typed" | "ai" | "ai_corrected">;
}

export interface TankReading {
  tank: string;
  gallons: string;
}

export interface HistoryEntry {
  action: string;
  actor_name: string | null;
  details: Record<string, unknown>;
  at: string;
}

export interface Report extends WorksheetInput {
  taxable_sale: string; // calculated by the API: sales tax / rate
  nontaxable_sale: string; // calculated: merchandise - taxable
  id: string;
  store_name: string;
  status: Status;
  total_sales: string;
  total_non_cash: string;
  cash_paid_out: string;
  expected_cash: string;
  over_short: string;
  submitted_by_name: string | null;
  submitted_at: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  exported_at: string | null;
  updated_at: string;
  history: HistoryEntry[];
}

export interface ReportSummary {
  id: string;
  store_id: string;
  store_name: string;
  business_date: string;
  status: Status;
  total_sales: string;
  expected_cash: string;
  over_short: string;
  submitted_by_name: string | null;
  submitted_at: string | null;
  review_note: string | null;
  has_ai_values: boolean;
}

export interface JournalLine {
  account: string;
  debit: string;
  credit: string;
  description: string;
}

export interface QbAccounts {
  cash: string;
  cards: string;
  ebt: string;
  fuel_sales: string;
  merch_sales: string;
  sales_tax: string;
  over_short: string;
  default_expense: string;
}

export interface AppSettings {
  over_short_alert: string;
  sales_tax_rate: string;
  qb_accounts: QbAccounts;
}

// ---------- Reports (month / quarter / year totals; amounts are exact strings) ----------
export type Period = "month" | "quarter" | "year";

export interface PeriodSums {
  days: number;
  days_short: number;
  days_unreviewed: number;
  fuel_sale: string;
  merch_sale: string;
  taxable_sale: string;
  nontaxable_sale: string;
  sales_tax: string;
  total_sales: string;
  gallons: string;
  credit: string;
  debit: string;
  ebt: string;
  total_non_cash: string;
  cash_paid_out: string;
  expected_cash: string;
  cash_drop: string;
  over_short: string;
}

export interface PeriodRow extends PeriodSums {
  key: string; // a date (month view) or "YYYY-MM" (quarter / year view)
  report_id?: string;
  store_id?: string;
  store_name?: string;
  status?: Status;
}

export interface PeriodSummary {
  period: Period;
  value: string;
  label: string;
  date_from: string;
  date_to: string;
  include: "approved" | "submitted";
  totals: PeriodSums;
  stores: (PeriodSums & { store_id: string; store_name: string })[];
  rows: PeriodRow[];
  missing: { store_id: string; store_name: string; days: number }[];
}

// ---------- The owner's books (amounts are exact strings) ----------
export type VendorKind = "fuel" | "merchandise" | "expense"; // fuel / merchandise = cost of goods
export interface Vendor { id: string; name: string; kind: VendorKind; active: boolean; used: boolean }

export type EntryCategory = "fuel_purchase" | "merchandise_purchase" | "expense";
export interface LedgerEntry {
  id: string;
  month: string; // first day, e.g. 2026-10-01
  store_id: string | null; // null = All stores (shared)
  store_name: string | null;
  category: EntryCategory;
  description: string;
  vendor_id: string | null;
  vendor_name: string | null;
  amount: string;
}
export interface EntryInput {
  month: string; // 2026-10
  store_id: string | null;
  category: EntryCategory;
  description: string;
  vendor_id: string | null;
  amount: string;
}

export interface BookLine { label: string; amount: string; source: "typed" | "paid_outs" | "days" | "auto"; items: { what?: string; vendor?: string | null; amount: string }[] }
export interface ProfitAndLoss {
  month: string; label: string; days: number;
  fuel_sales: string; merchandise_sales: string; taxable: string; non_taxable: string; sales_tax: string;
  revenue: string; cost_lines: BookLine[]; cost_of_goods: string; gross_profit: string;
  expense_lines: BookLine[]; expenses: string; over_short: string; net_profit: string; count_paid_outs: boolean;
}
export interface PnlYear {
  year: string;
  months: { month: string; revenue: string; cost_of_goods: string; expenses: string; over_short: string; net_profit: string }[];
  totals: { revenue: string; cost_of_goods: string; expenses: string; over_short: string; net_profit: string };
}

export type BalanceSection = "asset" | "liability" | "equity";
export interface BalanceLineInput { section: BalanceSection; name: string; amount: string }
export interface BalanceSheet {
  month: string; label: string; store_id: string | null;
  typed_lines: BalanceLineInput[];
  assets: BookLine[]; liabilities: BookLine[]; equity: BookLine[];
  total_assets: string; total_liabilities: string; total_equity: string; difference: string; balanced: boolean;
}

export interface VendorSpending {
  label: string; total: string;
  vendors: { vendor: string; on_list: boolean; cost_of_goods: string; expense: string; not_on_list: string; total: string; share: string;
             items: { date: string; what: string; amount: string; source: "typed" | "paid_out" }[] }[];
}
