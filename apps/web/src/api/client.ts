// The only place the web app talks to the backend. Every call goes through the API, never the database.

import type {
  AppSettings, JournalLine, Me, Person, Report, ReportSummary, Store, WorksheetInput,
  Period, PeriodSummary, Vendor, VendorKind, LedgerEntry, EntryInput, ProfitAndLoss, PnlYear, BalanceSheet,
  BalanceLineInput, VendorSpending, History, Inventory, TankSpec, Health, Release, VendorName, MiscPaidOut,
  MonitorLive, MonitorUsage, MonitorHistory, MonitorPeriod, HistoryKind,
} from "./types";

/** Tanks / tank_specs left out = keep the store's tanks as they are */
type StoreInput = Pick<Store, "name" | "qb_location" | "active"> & { tanks?: string[]; tank_specs?: TankSpec[] };

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "") + "/api";

// Set by the AuthProvider so every request carries the signed-in user's identity.
let getAuthHeaders: () => Promise<Record<string, string>> = async () => ({});
export function setAuthHeaderSource(fn: () => Promise<Record<string, string>>) {
  getAuthHeaders = fn;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const OFFLINE_MESSAGE = "Couldn't reach the server. Check your internet connection and try again.";

// fetch() itself fails (TypeError "Failed to fetch" / "Load failed") when the request never got an answer:
// a wifi/cell blip, the phone waking up, a browser extension. Reads are retried once; saves are not
// retried automatically, so nothing is ever sent twice.
async function send(path: string, options: { method?: string; body?: unknown }): Promise<Response> {
  const method = options.method ?? "GET";
  for (let attempt = 1; ; attempt++) {
    try {
      return await fetch(BASE + path, {
        method,
        // X-Page: which screen asked (for the admin Monitor; ids are stripped by the API)
        headers: { "Content-Type": "application/json", "X-Page": window.location.pathname, ...(await getAuthHeaders()) },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
      });
    } catch (err) {
      if (method === "GET" && attempt < 2) {
        await new Promise((r) => setTimeout(r, 800));
        continue;
      }
      throw new ApiError(0, err instanceof TypeError ? OFFLINE_MESSAGE : String(err));
    }
  }
}

async function request<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await send(path, options);
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  return (await res.json()) as T;
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    /* not JSON */
  }
  return `Something went wrong (${res.status})`;
}

// Downloads a CSV from the API and saves it with the file name the server suggests.
async function download(path: string, options: { method?: string; body?: unknown } = {}) {
  const res = await send(path, options);
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? "export.csv";
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function query(params: Record<string, string | boolean | undefined>) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && q.set(k, String(v)));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const api = {
  me: () => request<Me>("/me"),
  health: () => request<Health>("/health"),
  releases: () => request<Release[]>("/releases"),
  /** Once a minute while the app is open: shows the person as online on the admin Monitor */
  ping: () => request<{ ok: boolean }>("/me/ping"),

  monitor: {
    live: (includeMe: boolean) => request<MonitorLive>(`/monitor/live${query({ include_me: includeMe })}`),
    usage: (period: MonitorPeriod, includeMe: boolean) =>
      request<MonitorUsage>(`/monitor/usage${query({ period, include_me: includeMe })}`),
    history: (q: { person_id?: string; kind?: HistoryKind; before?: number }) =>
      request<MonitorHistory>(`/monitor/history${query({ ...q, before: q.before ? String(q.before) : undefined })}`),
  },

  admin: {
    resetTestData: () => request<{ ok: boolean; removed: Record<string, number> }>("/admin/reset-test-data", { method: "POST" }),
  },
  stores: {
    list: () => request<Store[]>("/stores"),
    create: (data: StoreInput) => request<Store>("/stores", { method: "POST", body: data }),
    update: (id: string, data: StoreInput) => request<Store>(`/stores/${id}`, { method: "PATCH", body: data }),
    remove: (id: string) => request<{ ok: boolean }>(`/stores/${id}`, { method: "DELETE" }),
  },

  people: {
    list: () => request<Person[]>("/people"),
    invite: (data: Omit<Person, "id" | "has_signed_in">) => request<Person>("/people", { method: "POST", body: data }),
    update: (id: string, data: Omit<Person, "id" | "has_signed_in">) =>
      request<Person>(`/people/${id}`, { method: "PATCH", body: data }),
    remove: (id: string) => request<{ ok: boolean }>(`/people/${id}`, { method: "DELETE" }),
  },

  reports: {
    list: (filters: { store_id?: string; status?: string; date_from?: string; date_to?: string; mine?: boolean }) =>
      request<ReportSummary[]>(`/reports${query(filters)}`),
    lookup: (store_id: string, business_date: string) =>
      request<Report | null>(`/reports/lookup${query({ store_id, business_date })}`),
    get: (id: string) => request<Report>(`/reports/${id}`),
    history: (until: string, days = 30) => request<History>(`/reports/history${query({ until, days: String(days) })}`),
    payees: (store_id: string) => request<string[]>(`/reports/payees${query({ store_id })}`),
    save: (data: WorksheetInput) => request<Report>("/reports", { method: "PUT", body: data }),
    submit: (id: string) => request<Report>(`/reports/${id}/submit`, { method: "POST" }),
    sendBack: (id: string, note: string) => request<Report>(`/reports/${id}/return`, { method: "POST", body: { note } }),
    approve: (id: string, gl_accounts: Record<string, string>) =>
      request<Report>(`/reports/${id}/approve`, { method: "POST", body: { gl_accounts } }),
    reopen: (id: string) => request<Report>(`/reports/${id}/reopen`, { method: "POST" }),
  },

  exports: {
    journalPreview: (reportId: string) => request<JournalLine[]>(`/exports/journal-entry/${reportId}`),
    quickbooks: (body: { date_from: string; date_to: string; store_id?: string; include_already_exported: boolean }) =>
      download("/exports/quickbooks", { method: "POST", body }),
    checkPaidOuts: (date_from: string, date_to: string) =>
      download(`/exports/check-paid-outs.csv${query({ date_from, date_to })}`),
    raw: (date_from: string, date_to: string) => download(`/exports/raw.csv${query({ date_from, date_to })}`),
  },

  summaries: {
    get: (q: { period: Period; value: string; store_id?: string; include: "approved" | "submitted" }) =>
      request<PeriodSummary>(`/summaries${query(q)}`),
    csv: (q: { period: Period; value: string; store_id?: string; include: "approved" | "submitted" }) =>
      download(`/summaries/csv${query(q)}`),
  },

  vendors: {
    list: () => request<Vendor[]>("/vendors"),
    add: (data: { name: string; kind: VendorKind; active?: boolean }) => request<Vendor>("/vendors", { method: "POST", body: data }),
    update: (id: string, data: { name: string; kind: VendorKind; active: boolean }) =>
      request<Vendor>(`/vendors/${id}`, { method: "PATCH", body: data }),
    remove: (id: string) => request<{ ok: boolean }>(`/vendors/${id}`, { method: "DELETE" }),
    names: () => request<VendorName[]>("/vendors/names"),
    miscellaneous: (days = 90) => request<MiscPaidOut[]>(`/vendors/miscellaneous${query({ days: String(days) })}`),
    spending: (q: { period: "month" | "year"; value: string; store_id?: string; include: "approved" | "submitted" }) =>
      request<VendorSpending>(`/vendors/spending${query(q)}`),
  },

  inventory: (q: { month: string; store_id?: string; include?: "approved" | "submitted" }) =>
    request<Inventory>(`/inventory${query(q)}`),
  books: {
    entries: (month: string, store_id?: string) => request<LedgerEntry[]>(`/books/entries${query({ month, store_id })}`),
    addEntry: (data: EntryInput) => request<LedgerEntry>("/books/entries", { method: "POST", body: data }),
    updateEntry: (id: string, data: EntryInput) => request<LedgerEntry>(`/books/entries/${id}`, { method: "PATCH", body: data }),
    removeEntry: (id: string) => request<{ ok: boolean }>(`/books/entries/${id}`, { method: "DELETE" }),
    pnl: (q: { month: string; store_id?: string; include: "approved" | "submitted"; count_paid_outs: boolean }) =>
      request<ProfitAndLoss>(`/books/pnl${query(q)}`),
    pnlYear: (q: { year: string; store_id?: string; include: "approved" | "submitted"; count_paid_outs: boolean }) =>
      request<PnlYear>(`/books/pnl-year${query(q)}`),
    balance: (month: string, store_id?: string, count_paid_outs = true) =>
      request<BalanceSheet>(`/books/balance${query({ month, store_id, count_paid_outs })}`),
    saveBalance: (data: { month: string; store_id: string | null; lines: BalanceLineInput[] }) =>
      request<BalanceSheet>("/books/balance", { method: "PUT", body: data }),
    copyPrevious: (month: string, store_id?: string) =>
      request<BalanceSheet & { copied: number }>(`/books/balance/copy-previous${query({ month, store_id })}`, { method: "POST" }),
  },

  settings: {
    get: () => request<AppSettings>("/settings"),
    save: (data: AppSettings) => request<AppSettings>("/settings", { method: "PUT", body: data }),
  },
};
