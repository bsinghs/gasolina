// The only place the web app talks to the backend. Every call goes through the API, never the database.

import type {
  AppSettings, JournalLine, Me, Person, Report, ReportSummary, Store, WorksheetInput,
} from "./types";

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

async function request<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(BASE + path, {
    method: options.method ?? "GET",
    headers: { "Content-Type": "application/json", ...(await getAuthHeaders()) },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
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
  const res = await fetch(BASE + path, {
    method: options.method ?? "GET",
    headers: { "Content-Type": "application/json", ...(await getAuthHeaders()) },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
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

  stores: {
    list: () => request<Store[]>("/stores"),
    create: (data: Omit<Store, "id">) => request<Store>("/stores", { method: "POST", body: data }),
    update: (id: string, data: Omit<Store, "id">) => request<Store>(`/stores/${id}`, { method: "PATCH", body: data }),
  },

  people: {
    list: () => request<Person[]>("/people"),
    invite: (data: Omit<Person, "id" | "has_signed_in">) => request<Person>("/people", { method: "POST", body: data }),
    update: (id: string, data: Omit<Person, "id" | "has_signed_in">) =>
      request<Person>(`/people/${id}`, { method: "PATCH", body: data }),
  },

  reports: {
    list: (filters: { store_id?: string; status?: string; date_from?: string; date_to?: string; mine?: boolean }) =>
      request<ReportSummary[]>(`/reports${query(filters)}`),
    lookup: (store_id: string, business_date: string) =>
      request<Report | null>(`/reports/lookup${query({ store_id, business_date })}`),
    get: (id: string) => request<Report>(`/reports/${id}`),
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

  settings: {
    get: () => request<AppSettings>("/settings"),
    save: (data: AppSettings) => request<AppSettings>("/settings", { method: "PUT", body: data }),
  },
};
