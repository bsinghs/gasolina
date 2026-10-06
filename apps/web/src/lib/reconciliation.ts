// Live preview of the worksheet math while typing.
// The API recalculates on save (services/api/app/modules/reports/reconciliation.py) and its numbers win.

import { toCents } from "./money";

export interface WorksheetNumbers {
  fuel_sale: string;
  merch_sale: string;
  sales_tax: string;
  credit: string;
  debit: string;
  ebt: string;
  cash_drop: string;
  paid_outs: { kind: "cash" | "check"; amount: string }[];
}

// taxable = sales tax / rate (PA 6%), non-taxable = merchandise - taxable. Part of merchandise, not extra sales.
export function calculate(w: WorksheetNumbers, taxRate = 0.06) {
  const totalSales = toCents(w.fuel_sale) + toCents(w.merch_sale) + toCents(w.sales_tax);
  const taxable = taxRate > 0 ? Math.round(toCents(w.sales_tax) / taxRate) : 0;
  const nonTaxable = toCents(w.merch_sale) - taxable;
  const nonCash = toCents(w.credit) + toCents(w.debit) + toCents(w.ebt);
  const cashPaidOut = w.paid_outs.filter((p) => p.kind === "cash").reduce((sum, p) => sum + toCents(p.amount), 0);
  const expectedCash = totalSales - nonCash - cashPaidOut;
  const overShort = toCents(w.cash_drop) - expectedCash;
  return { totalSales, taxable, nonTaxable, nonCash, cashPaidOut, expectedCash, overShort };
}
