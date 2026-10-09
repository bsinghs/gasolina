"""Inventory math worked by hand (no database). Same numbers as the API test in test_oct9.py."""

from datetime import date
from decimal import Decimal as D

from app.modules.inventory.math import (
    Delivery, Purchase, Reading, by_grade, common_window, fuel_money, merchandise, pump_check, tank_usage,
)

SEP1, SEP30 = date(2026, 9, 1), date(2026, 9, 30)


def regular(**over):
    args = dict(name="Tank 1 – Regular", grade="Regular", capacity=D("10000"), before=Reading(date(2026, 8, 31), D("6000")),
                readings=[Reading(date(2026, 9, 1), D("5000")), Reading(date(2026, 9, 3), D("7100")), Reading(date(2026, 9, 2), D("8000"))],
                deliveries=[Delivery(date(2026, 9, 2), D("4000"), D("10000.00"))], first=SEP1, last=SEP30, reorder_percent=25)
    return tank_usage(**(args | over))


def premium(**over):
    args = dict(name="Tank 2 – Premium", grade="Premium", capacity=D("5000"), before=Reading(date(2026, 8, 31), D("3000")),
                readings=[Reading(date(2026, 9, 1), D("2800")), Reading(date(2026, 9, 2), D("2600")), Reading(date(2026, 9, 3), D("2450"))],
                deliveries=[], first=SEP1, last=SEP30, reorder_percent=25)
    return tank_usage(**(args | over))


def test_tank_used_is_opening_plus_deliveries_minus_closing():
    t = regular()
    assert t.used == D("2900.0")                   # 6,000 + 4,000 - 7,100
    assert (t.opening_day, t.closing_day) == (date(2026, 8, 31), date(2026, 9, 3))
    assert t.average_per_day == D("966.7")         # 2,900 / 3 days
    assert t.latest == D("7100.0") and t.latest_day == date(2026, 9, 3) and t.on_hand == D("7100.0")
    assert t.percent_full == D("71.0")
    assert t.days_left == D("7.3")                 # 7,100 / 966.7
    assert t.delivered == D("4000.0") and t.delivered_cost == D("10000.00")
    assert not t.order_soon


def test_order_soon_when_below_the_setting_or_few_days_left():
    assert premium(reorder_percent=50).order_soon             # 49.0% < 50%
    assert not premium().order_soon                            # 49.0%, 13.4 days left
    assert premium(capacity=None, before=Reading(date(2026, 8, 31), D("2900"))).order_soon is False
    low = premium(readings=[Reading(date(2026, 9, 1), D("2800")), Reading(date(2026, 9, 3), D("500"))])
    assert low.days_left == D("0.6") and low.order_soon        # 500 / 833.3 a day


def test_first_reading_of_the_month_is_the_opening_when_none_before():
    t = regular(before=None)
    assert t.used == D("1900.0")                   # 5,000 + 4,000 (Sep 2) - 7,100
    assert t.opening_day == date(2026, 9, 1) and t.average_per_day == D("950.0")


def test_fewer_than_two_readings_means_use_unknown():
    one = regular(before=None, readings=[Reading(date(2026, 9, 1), D("5000"))])
    assert one.used is None and one.average_per_day is None and one.days_left is None
    assert one.latest == D("5000.0") and one.on_hand == D("9000.0") and one.percent_full == D("90.0")   # + Sep 2 delivery
    none = regular(before=None, readings=[])
    assert none.latest is None and none.percent_full is None and none.used is None and not none.order_soon
    only_before = regular(readings=[])
    assert only_before.latest == D("6000.0") and only_before.latest_day == date(2026, 8, 31) and only_before.used is None


def test_delivery_after_the_latest_reading_counts_on_hand():
    t = regular(deliveries=[Delivery(date(2026, 9, 2), D("4000"), D("1")), Delivery(date(2026, 9, 5), D("2000"), D("1"))])
    assert t.latest == D("7100.0") and t.delivered_since_reading == D("2000.0") and t.on_hand == D("9100.0")
    assert t.percent_full == D("91.0") and t.used == D("2900.0") and t.delivered == D("6000.0")
    assert t.days_left == D("9.4")                 # 9,100 / 966.7


def test_deliveries_outside_the_month_and_unknown_capacity():
    t = regular(deliveries=[Delivery(date(2026, 8, 30), D("999"), D("1")), Delivery(date(2026, 9, 2), D("4000"), D("10000.00")),
                            Delivery(date(2026, 10, 1), D("500"), D("1"))], capacity=None)
    assert t.delivered == D("4000.0") and t.used == D("2900.0") and t.percent_full is None


def test_grades_and_pump_check():
    tanks = [regular(), premium(), regular(name="Tank 3 – Regular", capacity=None)]
    g = {x.grade: x for x in by_grade(tanks)}
    assert g["Regular"].tanks == 2 and g["Regular"].used == D("5800.0") and g["Regular"].capacity is None
    assert g["Premium"].percent_full == D("49.0") and g["Premium"].used == D("550.0")

    two = [regular(), premium()]
    window = common_window(two)
    assert window == (date(2026, 8, 31), date(2026, 9, 3))
    c = pump_check(window, date(2026, 9, 1), D("3350.0"), two)
    assert (c.tank_gallons, c.pump_gallons, c.difference, c.difference_percent) == (D("3450.0"), D("3350.0"), D("100.0"), D("3.0"))
    assert c.days_missing == 0 and pump_check(window, date(2026, 9, 1), D("2000"), two, days_missing=1).days_missing == 1
    # different reading days → no comparison
    assert common_window([regular(), premium(before=None)]) is None
    assert common_window([regular(before=None, readings=[])]) is None


def test_fuel_money_leaves_out_deliveries_without_a_cost():
    m = fuel_money(D("10100.00"), D("3350.0"), [Delivery(SEP1, D("4000"), D("10000.00")), Delivery(SEP1, D("1000"), D("0"))])
    assert (m.price_per_gallon, m.cost_per_gallon, m.margin_per_gallon) == (D("3.015"), D("2.500"), D("0.515"))
    assert m.gallons_costed == D("4000.0")
    empty = fuel_money(D("0"), D("0"), [])
    assert empty.price_per_gallon is None and empty.cost_per_gallon is None and empty.margin_per_gallon is None


def test_merchandise_bought_vs_sold():
    kinds = {"pepsi": "merchandise", "mclane": "merchandise", "coke": "merchandise", "ice co": "expense"}
    m = merchandise(
        sold=D("1500.00"),
        purchases=[Purchase("McLane", D("300.00"), date(2026, 9, 2), "typed"),
                   Purchase(" pepsi", D("50.00"), date(2026, 9, 1), "paid_out"),
                   Purchase("Ice Co", D("20.00"), date(2026, 9, 1), "paid_out"),      # expense: not merchandise
                   Purchase("Bob's", D("5.00"), date(2026, 9, 1), "paid_out")],       # not on the list: not counted
        earlier_last_days={"coke": date(2026, 8, 31), "pepsi": date(2026, 8, 31)},
        vendor_names=["Coke", "McLane", "Pepsi"], kinds=kinds, as_of=SEP30)
    assert (m.bought_typed, m.bought_paid_outs, m.bought, m.bought_percent_of_sales) == (D("300.00"), D("50.00"), D("350.00"), D("23.3"))
    rows = [(v.vendor, v.amount, v.purchases, v.last_day, v.days_since) for v in m.vendors]
    assert rows == [("McLane", D("300.00"), 1, date(2026, 9, 2), 28), ("Pepsi", D("50.00"), 1, date(2026, 9, 1), 29),
                    ("Coke", D("0"), 0, date(2026, 8, 31), 30)]
    assert merchandise(sold=D("0"), purchases=[], earlier_last_days={}, vendor_names=[], kinds={}, as_of=SEP30).bought_percent_of_sales is None
