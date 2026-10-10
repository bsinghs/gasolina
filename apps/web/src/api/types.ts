// Shapes returned by the API. Money comes back as strings like "1234.50" to avoid rounding errors.

export type Role = "employee" | "manager" | "owner" | "coowner" | "admin";

/** Sees the owner's screens and every store: owner, co-owner (view only), app admin. Same as can(role, "see_all_stores") */
export const hasOwnerAccess = (role: Role | string | undefined) => role === "owner" || role === "coowner" || role === "admin";
/** Sees all stores (no store list needed): owner and co-owner */
export const isOwnerLevel = (role: Role | string | undefined) => role === "owner" || role === "coowner";
export const ROLE_NAMES: Record<Role, string> = {
  employee: "Employee", manager: "Manager", owner: "Owner", coowner: "Co-owner", admin: "App admin (support)",
};
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
  tank_specs: TankSpec[]; // same tanks with fuel type and capacity
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
  note?: string | null; // Miscellaneous: what it was and who was paid
}

/** Paid-out vendor when it's not on the owner's list (needs a note) */
export const MISCELLANEOUS = "Miscellaneous";

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
  fuel_sale: string;
  merch_sale: string;
  gallons: string;
  total_sales: string;
  expected_cash: string;
  over_short: string;
  submitted_by_name: string | null;
  submitted_at: string | null;
  review_note: string | null;
  has_ai_values: boolean;
}

/** Whole-month totals for one store on My days (submitted, approved and exported days) */
export interface MonthTotal {
  month: string; // 2026-10
  store_id: string;
  store_name: string;
  days: number;
  days_short: number;
  fuel_sale: string;
  merch_sale: string;
  gallons: string;
  over_short: string;
}

export interface History {
  days: ReportSummary[];
  months: MonthTotal[];
  next_until: string | null; // where the next (older) page ends; null = nothing older
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
  reorder_percent: number; // Inventory: tank below this % full = "Order soon"
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
  entry_date: string | null; // the day it was delivered / bought
  tank: string | null; // fuel deliveries only
  gallons: string | null;
}
export interface EntryInput {
  month?: string; // 2026-10 (may be left out when entry_date is given)
  store_id: string | null;
  category: EntryCategory;
  description: string;
  vendor_id: string | null;
  amount: string;
  // Only sent by the Inventory page; leaving them out keeps what's saved
  entry_date?: string;
  tank?: string;
  gallons?: string;
}

// ---------- Inventory (owner / co-owner) ----------
export type Grade = "Regular" | "Plus" | "Premium" | "Diesel" | "Other";
export const GRADES: Grade[] = ["Regular", "Plus", "Premium", "Diesel", "Other"];
export interface TankSpec {
  name: string; grade: Grade; capacity: string | null;
  aliases?: string[]; // older names (history is kept under them)
  previous_name?: string; // sent when renaming, so the tank keeps its history
}
export interface TankStatus {
  name: string; grade: Grade; capacity: string | null;
  latest: string | null; latest_day: string | null; delivered_since_reading: string; on_hand: string | null; percent_full: string | null;
  delivered: string; delivered_cost: string; used: string | null;
  opening_day: string | null; closing_day: string | null; average_per_day: string | null; days_left: string | null;
  order_soon: boolean;
}
export interface GradeTotal {
  grade: Grade; tanks: number; capacity: string | null; on_hand: string | null; percent_full: string | null;
  delivered: string; used: string | null; order_soon: boolean;
}
export interface FuelDelivery {
  id: string; entry_date: string; tank: string; gallons: string; amount: string; description: string;
  vendor_id: string | null; vendor_name: string | null;
}
export interface StoreInventory {
  store_id: string; store_name: string;
  fuel: {
    tanks: TankStatus[];
    grades: GradeTotal[];
    pump_check: { first_day: string; last_day: string; pump_gallons: string; tank_gallons: string; difference: string; difference_percent: string | null; days_missing: number } | null;
    money: { sales: string; gallons_sold: string; price_per_gallon: string | null; delivered_cost: string; gallons_costed: string;
             cost_per_gallon: string | null; margin_per_gallon: string | null };
    deliveries: FuelDelivery[];
  };
  merchandise: {
    sold: string; bought_typed: string; bought_paid_outs: string; bought: string; bought_percent_of_sales: string | null;
    vendors: { vendor: string; amount: string; purchases: number; last_day: string | null; days_since: number | null }[];
  };
}
export interface Inventory { month: string; label: string; reorder_percent: number; as_of: string; stores: StoreInventory[] }

export interface VendorName { name: string; kind: VendorKind }

// ---------- Versions ----------
export interface Health { ok: boolean; env: string; version: string; commit: string }
export interface Release { env: string; version: string; git_commit: string; started_at: string }
export interface MiscPaidOut {
  id: string; amount: string; kind: PaidOutKind; note: string | null; report_id: string; business_date: string;
  status: Status; store_name: string; submitted_by_name: string | null;
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

// ---------- Admin Monitor (app admin only, docs/features/admin-monitor.md) ----------
export type MonitorPeriod = "release" | "today" | "7d" | "30d";
export type HistoryKind = "worksheet" | "vendor" | "books" | "person" | "store" | "settings";
export interface OnlinePerson {
  person_id: string; name: string; role: Role; page: string | null; device: string | null; last_at: string; viewing_as: string | null;
}
export interface MonitorLive { online: OnlinePerson[]; per_minute: { minute: string; requests: number; errors: number }[]; online_minutes: number }
export interface UsagePerson {
  person_id: string; name: string; role: Role; visits: number; active_minutes: number; requests: number; errors: number;
  first_seen: string; last_seen: string; device: string | null; screens: string[];
}
export interface MonitorUsage {
  period: MonitorPeriod; label: string; since: string;
  totals: { requests: number; people: number; errors: number; slow: number };
  people: UsagePerson[];
  days: { day: string; people: number; requests: number; errors: number }[];
  problems: { at: string; name: string | null; method: string; route: string; page: string | null; status: number; ms: number }[];
  slowest: { method: string; route: string; requests: number; avg_ms: number; max_ms: number }[];
}
export interface HistoryRow {
  id: number; at: string; action: string; details: Record<string, unknown>; report_id: string | null;
  who: string | null; role: Role | null; business_date: string | null; store: string | null;
}
export interface MonitorHistory { rows: HistoryRow[]; next_before: number | null; people: { id: string; name: string; role: Role }[] }
