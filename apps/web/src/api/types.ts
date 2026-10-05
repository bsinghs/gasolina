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
  stores: { id: string; name: string }[];
  over_short_alert: string;
}

export interface Store {
  id: string;
  name: string;
  qb_location: string | null;
  active: boolean;
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
  field_sources: Record<string, "typed" | "ai" | "ai_corrected">;
}

export interface HistoryEntry {
  action: string;
  actor_name: string | null;
  details: Record<string, unknown>;
  at: string;
}

export interface Report extends WorksheetInput {
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
  qb_accounts: QbAccounts;
}
