"""Inventory math: fuel tanks and merchandise. Pure functions, no database, easy to test.

Fuel, per tank, for a period (first … last):
    Latest reading = gallons at the latest reading up to `last`
    On hand        = latest reading + deliveries after it (up to `last`), so a delivery shows before the next reading
    % full         = on hand / capacity
    Delivered      = gallons delivered to the tank in the period
    Used           = opening reading + deliveries after it (up to the closing reading) - closing reading
                     opening = last reading before the period, else the first one in it
                     closing = last reading in the period          (needs two readings)
    Average / day  = used / days between the opening and closing readings
    Days left      ~ on hand / average per day
    Order soon     = % full below the owner's setting, or about 3 days or less left

A reading is the gallons left at closing on that day, so a delivery on day D is in D's reading.

Merchandise, per store, for a period:
    Bought             = typed merchandise purchases + paid outs to merchandise vendors
    Bought % of sales  = bought / merchandise sales
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.modules.books.math import vendor_key
from app.modules.reports.reconciliation import money

ZERO = Decimal("0")
DAYS_LEFT_ALERT = Decimal("3")


def gal(v: Decimal) -> Decimal:
    return Decimal(v).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def pct(part: Decimal, whole: Decimal) -> Decimal | None:
    """part / whole as a percent with one decimal, or None when whole is zero."""
    if not whole:
        return None
    return (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Reading:
    day: date
    gallons: Decimal


@dataclass(frozen=True)
class Delivery:
    day: date
    gallons: Decimal
    cost: Decimal = ZERO


@dataclass
class TankResult:
    name: str
    grade: str
    capacity: Decimal | None
    latest: Decimal | None          # gallons at the latest reading
    latest_day: date | None
    delivered_since_reading: Decimal  # deliveries after the latest reading (not in it yet)
    on_hand: Decimal | None         # latest reading + deliveries since
    percent_full: Decimal | None
    delivered: Decimal              # gallons delivered in the period
    delivered_cost: Decimal
    used: Decimal | None            # None = fewer than two readings
    opening_day: date | None
    closing_day: date | None
    average_per_day: Decimal | None
    days_left: Decimal | None
    order_soon: bool


def tank_usage(*, name: str, grade: str, capacity: Decimal | None, before: Reading | None,
               readings: list[Reading], deliveries: list[Delivery], first: date, last: date,
               reorder_percent: int) -> TankResult:
    """`before` = the last reading before `first`; `readings` = readings from first to last (any order)."""
    inside = sorted((r for r in readings if first <= r.day <= last), key=lambda r: r.day)
    in_period = [d for d in deliveries if first <= d.day <= last]
    delivered = gal(sum((d.gallons for d in in_period), ZERO))
    delivered_cost = money(sum((d.cost for d in in_period), ZERO))

    opening = before or (inside[0] if inside else None)
    closing = inside[-1] if inside else None
    used = average = None
    if opening and closing and closing.day > opening.day:
        added = sum((d.gallons for d in deliveries if opening.day < d.day <= closing.day), ZERO)
        used = gal(opening.gallons + added - closing.gallons)
        span = (closing.day - opening.day).days
        if used > 0:
            average = gal(used / span)

    latest_reading = inside[-1] if inside else before
    latest = gal(latest_reading.gallons) if latest_reading else None
    since = gal(sum((d.gallons for d in deliveries if latest_reading and latest_reading.day < d.day <= last), ZERO))
    on_hand = gal(latest + since) if latest is not None else None
    percent_full = pct(on_hand, capacity) if on_hand is not None and capacity else None
    days_left = (on_hand / average).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if on_hand is not None and average else None
    order_soon = bool((percent_full is not None and percent_full < reorder_percent)
                      or (days_left is not None and days_left <= DAYS_LEFT_ALERT))
    return TankResult(
        name=name, grade=grade, capacity=capacity, latest=latest,
        latest_day=latest_reading.day if latest_reading else None, delivered_since_reading=since, on_hand=on_hand,
        percent_full=percent_full,
        delivered=delivered, delivered_cost=delivered_cost, used=used,
        opening_day=opening.day if used is not None else None, closing_day=closing.day if used is not None else None,
        average_per_day=average, days_left=days_left, order_soon=order_soon,
    )


@dataclass
class GradeTotal:
    grade: str
    tanks: int
    capacity: Decimal | None        # None if any tank's size is unknown
    on_hand: Decimal | None
    percent_full: Decimal | None
    delivered: Decimal
    used: Decimal | None            # None if any tank's use is unknown
    order_soon: bool


def by_grade(tanks: list[TankResult]) -> list[GradeTotal]:
    """Two Regular tanks show as one Regular line."""
    groups: "OrderedDict[str, list[TankResult]]" = OrderedDict()
    for t in tanks:
        groups.setdefault(t.grade, []).append(t)
    out = []
    for grade, ts in groups.items():
        capacity = None if any(t.capacity is None for t in ts) else sum((t.capacity for t in ts), ZERO)
        on_hand = None if any(t.on_hand is None for t in ts) else gal(sum((t.on_hand for t in ts), ZERO))
        used = None if any(t.used is None for t in ts) else gal(sum((t.used for t in ts), ZERO))
        out.append(GradeTotal(
            grade=grade, tanks=len(ts), capacity=capacity, on_hand=on_hand,
            percent_full=pct(on_hand, capacity) if on_hand is not None and capacity else None,
            delivered=gal(sum((t.delivered for t in ts), ZERO)), used=used, order_soon=any(t.order_soon for t in ts),
        ))
    return out


def common_window(tanks: list[TankResult]) -> tuple[date, date] | None:
    """The days to compare pump gallons with tank use: only when every tank was read on the same opening and
    closing days (otherwise the two numbers cover different days and the difference would mislead)."""
    if not tanks or any(t.used is None for t in tanks):
        return None
    windows = {(t.opening_day, t.closing_day) for t in tanks}
    return windows.pop() if len(windows) == 1 else None


@dataclass
class PumpCheck:
    first_day: date                 # first day counted (day after the opening reading)
    last_day: date
    pump_gallons: Decimal           # sold at the pump, from the worksheets
    tank_gallons: Decimal           # used by tank readings
    difference: Decimal             # tank - pump: more used than sold = possible loss
    difference_percent: Decimal | None


def pump_check(window: tuple[date, date], first_day: date, pump_gallons: Decimal, tanks: list[TankResult]) -> PumpCheck:
    tank_gallons = gal(sum((t.used for t in tanks), ZERO))
    pump = gal(pump_gallons)
    diff = gal(tank_gallons - pump)
    return PumpCheck(first_day=first_day, last_day=window[1], pump_gallons=pump, tank_gallons=tank_gallons,
                     difference=diff, difference_percent=pct(diff, pump))


@dataclass
class FuelMoney:
    sales: Decimal
    gallons_sold: Decimal
    price_per_gallon: Decimal | None      # average sell price
    delivered_cost: Decimal
    gallons_costed: Decimal               # deliveries with a cost typed in
    cost_per_gallon: Decimal | None
    margin_per_gallon: Decimal | None


def per_gallon(amount: Decimal, gallons: Decimal) -> Decimal | None:
    return (Decimal(amount) / Decimal(gallons)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP) if gallons else None


def fuel_money(sales: Decimal, gallons_sold: Decimal, deliveries: list[Delivery]) -> FuelMoney:
    """Average sell vs cost price per gallon. Deliveries with no cost yet (invoice to come) are left out of the cost."""
    costed = [d for d in deliveries if d.cost > 0]
    cost = money(sum((d.cost for d in costed), ZERO))
    costed_gal = gal(sum((d.gallons for d in costed), ZERO))
    price = per_gallon(sales, gallons_sold)
    unit_cost = per_gallon(cost, costed_gal)
    margin = (price - unit_cost) if price is not None and unit_cost is not None else None
    return FuelMoney(sales=money(sales), gallons_sold=gal(gallons_sold), price_per_gallon=price,
                     delivered_cost=cost, gallons_costed=costed_gal, cost_per_gallon=unit_cost, margin_per_gallon=margin)


# ---------- merchandise ----------

@dataclass(frozen=True)
class Purchase:
    """A merchandise purchase: typed in by the owner, or a paid out on a daily worksheet."""
    vendor: str | None
    amount: Decimal
    day: date | None                # None = typed without a date
    source: str                     # typed | paid_out


@dataclass
class VendorBought:
    vendor: str
    amount: Decimal                 # bought in the period
    purchases: int
    last_day: date | None           # latest purchase up to the period's end (any time)
    days_since: int | None


@dataclass
class Merchandise:
    sold: Decimal
    bought_typed: Decimal
    bought_paid_outs: Decimal
    bought: Decimal
    bought_percent_of_sales: Decimal | None
    vendors: list[VendorBought] = field(default_factory=list)


def merchandise(*, sold: Decimal, purchases: list[Purchase], earlier_last_days: dict[str, date],
                vendor_names: list[str], kinds: dict[str, str], as_of: date) -> Merchandise:
    """`purchases` = this period's typed purchases and paid outs (paid outs to any vendor: only merchandise
    vendors count); `earlier_last_days` = latest purchase day per vendor key before the period;
    `vendor_names` = active merchandise vendors (shown even with nothing bought)."""
    counted = [p for p in purchases if p.source == "typed" or kinds.get(vendor_key(p.vendor)) == "merchandise"]
    typed = money(sum((p.amount for p in counted if p.source == "typed"), ZERO))
    paid = money(sum((p.amount for p in counted if p.source == "paid_out"), ZERO))
    bought = money(typed + paid)

    rows: "OrderedDict[str, VendorBought]" = OrderedDict()
    for name in vendor_names:
        rows[vendor_key(name)] = VendorBought(name, ZERO, 0, earlier_last_days.get(vendor_key(name)), None)
    for p in counted:
        key = vendor_key(p.vendor) or "(no vendor)"
        row = rows.setdefault(key, VendorBought(p.vendor or "(no vendor)", ZERO, 0, earlier_last_days.get(key), None))
        row.amount = money(row.amount + p.amount)
        row.purchases += 1
        if p.day and (row.last_day is None or p.day > row.last_day):
            row.last_day = p.day
    for row in rows.values():
        row.days_since = (as_of - row.last_day).days if row.last_day else None
    vendors = sorted(rows.values(), key=lambda r: (-r.amount, r.vendor.lower()))
    return Merchandise(sold=money(sold), bought_typed=typed, bought_paid_outs=paid, bought=bought,
                       bought_percent_of_sales=pct(bought, sold), vendors=vendors)
