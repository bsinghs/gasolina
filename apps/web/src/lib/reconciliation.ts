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

export function calculate(w: WorksheetNumbers) {
  const totalSales = toCents(w.fuel_sale) + toCents(w.merch_sale) + toCents(w.sales_tax);
  const nonCash = toCents(w.credit) + toCents(w.debit) + toCents(w.ebt);
  const cashPaidOut = w.paid_outs.filter((p) => p.kind === "cash").reduce((sum, p) => sum + toCents(p.amount), 0);
  const expectedCash = totalSales - nonCash - cashPaidOut;
  const overShort = toCents(w.cash_drop) - expectedCash;
  return { totalSales, nonCash, cashPaidOut, expectedCash, overShort };
}
