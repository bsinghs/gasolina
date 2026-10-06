-- Owner (Oct 5): taxable / non-taxable are a SPLIT of merchandise, worked out from the PA sales tax:
--   taxable     = sales tax / 6%
--   non-taxable = merchandise - taxable
-- They are no longer typed by the employee or added to total sales (total sales = fuel + merch + tax).
-- Fill in the split for days already saved (totals are unchanged). The API recalculates it on every save,
-- using the rate in Settings.
update daily_reports
set taxable_sale    = round(sales_tax / 0.06, 2),
    nontaxable_sale = merch_sale - round(sales_tax / 0.06, 2);
