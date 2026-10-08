// Money helpers. Math is done in whole cents so 0.1 + 0.2 problems can't happen.

export function toCents(value: string | number | null | undefined): number {
  const n = typeof value === "number" ? value : parseFloat(String(value ?? "").replace(/[$,\s]/g, ""));
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
}

export function formatMoney(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  return sign + "$" + (Math.abs(cents) / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Accounting style: shortages in parentheses, e.g. ($9.50) */
export function formatOverShort(cents: number): string {
  return cents < 0 ? `(${formatMoney(-cents)})` : formatMoney(cents);
}

export function money(value: string | number | null | undefined): string {
  return formatMoney(toCents(value));
}

/** "1,234.5" or "$40" -> "1234.50" for sending to the API */
export function toApiAmount(value: string): string {
  return (toCents(value) / 100).toFixed(2);
}

/** Strict reading of a typed amount for the books: "$1,234.50" → "1234.50", "(500)" or "-500" → "-500.00".
 *  Returns null when it isn't a number, so the screen can say so instead of saving 0.00. */
export function parseAmount(value: string): string | null {
  let t = value.trim().replace(/[$,\s]/g, "");
  if (t === "") return "0.00";
  let negative = false;
  if (/^\(.*\)$/.test(t)) { negative = true; t = t.slice(1, -1); }
  if (t.startsWith("-")) { negative = !negative; t = t.slice(1); }
  if (!/^(\d+\.?\d*|\.\d+)$/.test(t)) return null;
  const cents = Math.round(parseFloat(t) * 100);
  return ((negative ? -cents : cents) / 100).toFixed(2);
}
