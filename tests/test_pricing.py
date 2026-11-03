from decimal import Decimal

import pytest
from hypothesis import given, strategies as st

from pl.models import Item, Tier
from pl.pricing import quote, unit_price

# Spec §6 golden quotes (recomputed by hand with Decimal from the v1 JSON/HTML, not by the engine).
GOLDEN = {
    "G1": ([("PL-PR-LTR-MT-100-40", 20)], "3960.00", "0.00", "277.20", "4237.20", ["tier:20"]),
    "G2": ([("PL-CP-A4-70", 9)], "981.00", "150.00", "79.17", "1210.17", ["list"]),
    "G3": ([("PL-CP-A4-70", 10)], "1046.40", "150.00", "83.75", "1280.15", ["tier:10"]),
    "G4": ([("PL-CP-A4-70", 50)], "4905.00", "0.00", "343.35", "5248.35", ["tier:50"]),
    "G5": ([("PL-PR-LTR-GL-170-40", 20)], "5180.00", "0.00", "362.60", "5542.60", ["sale"]),
    "G6": ([("PL-CP-LTR-20", 5)], "675.00", "150.00", "57.75", "882.75", ["list"]),
    "G7": ([("PL-PR-A5-MT-100-40", 20), ("PL-CP-A4-80", 10)], "3495.90", "0.00", "244.71", "3740.61", ["tier:20", "tier:10"]),
    "G8": ([("PL-PR-A4-MT-100-40", 15)], "2890.50", "150.00", "212.84", "3253.34", ["tier:5"]),
    "G9": ([("PL-PR-A4-MT-100-40", 16)], "3083.20", "0.00", "215.82", "3299.02", ["tier:5"]),
    "G10": ([("PL-CP-A4-80", 10)], "1225.50", "150.00", "96.29", "1471.79", ["tier:10"]),
}


def thb(satang):
    return f"{Decimal(satang) / 100:.2f}"


@pytest.mark.parametrize("gid", GOLDEN)
def test_golden(v1_items, gid):
    lines, sub, dl, vat, total, rules = GOLDEN[gid]
    q = quote(lines, v1_items)
    assert q.ok
    assert (thb(q.subtotal_satang), thb(q.delivery_satang), thb(q.vat_satang), thb(q.total_satang)) == (sub, dl, vat, total)
    assert [l.rule for l in q.lines] == rules
    assert all(l.source_url and l.crawled_at for l in q.lines)


def test_g8_insight_mentions_free_delivery(v1_items):
    q = quote([("PL-PR-A4-MT-100-40", 15)], v1_items)
    assert any("3,299.02" in s and "+45.68" in s for s in q.insights)


def test_out_of_stock_refused(v1_items):
    q = quote([("PL-CL-A4-100-IVY", 2), ("PL-CP-A4-70", 1)], v1_items)
    assert not q.ok and q.refused[0]["sku"] == "PL-CL-A4-100-IVY" and "2026-11-20" in q.refused[0]["reason"]
    assert [l.sku for l in q.lines] == ["PL-CP-A4-70"]


def test_discontinued_and_unknown_refused(v1_items):
    items = dict(v1_items)
    items["PL-CP-A4-75"] = items["PL-CP-A4-75"].model_copy(update={"stock_status": "discontinued"})
    q = quote([("PL-CP-A4-75", 5), ("NOPE-1", 1)], items)
    assert not q.lines and {r["sku"] for r in q.refused} == {"PL-CP-A4-75", "NOPE-1"}


def test_same_sku_twice_counts_packs_together(v1_items):
    q = quote([("PL-CP-A4-70", 5), ("PL-CP-A4-70", 5)], v1_items)
    assert len(q.lines) == 1 and q.lines[0].rule == "tier:10"


# ---- properties ----

def _item(list_p, tiers, sale=None):
    return Item(sku="X", product_url="u", product_name="x", product_type="paper", size_code="A4", weight_gsm=80,
                sheets_per_pack=500, list_price_satang=list_p, sale_price_satang=sale, stock_status="in_stock",
                source_url="u", crawled_at="t", tiers=[Tier(min_qty=m, unit_price_satang=p) for m, p in tiers])


@st.composite
def items(draw, with_sale=None):
    list_p = draw(st.integers(1_000, 100_000))
    mins = sorted(draw(st.sets(st.integers(2, 200), max_size=4)))
    prices, p = [], list_p
    for _ in mins:
        p = draw(st.integers(max(1, p // 2), p - 1)) if p > 1 else 1
        prices.append(p)
    tiers = [(m, pr) for m, pr in zip(mins, prices)]
    has_sale = draw(st.booleans()) if with_sale is None else with_sale
    sale = draw(st.integers(1, list_p - 1)) if has_sale else None
    return _item(list_p, tiers, sale)


@given(items(with_sale=True), st.integers(1, 500))
def test_sale_ignores_tiers(it, qty):
    assert unit_price(it, qty) == (it.sale_price_satang, "sale")


@given(items(), st.integers(1, 499))
def test_unit_price_non_increasing(it, qty):
    assert unit_price(it, qty + 1)[0] <= unit_price(it, qty)[0]


@given(items(), st.integers(1, 500))
def test_delivery_and_total_identity(it, qty):
    q = quote([("X", qty)], {"X": it}, insights=False)
    assert q.delivery_satang in (0, 15_000)
    assert (q.delivery_satang == 0) == (q.subtotal_satang >= 300_000)
    assert q.total_satang == q.subtotal_satang + q.delivery_satang + q.vat_satang
    exact = (Decimal(q.subtotal_satang + q.delivery_satang) * Decimal("0.07"))
    assert abs(Decimal(q.vat_satang) - exact) <= Decimal("0.5")


def test_delivery_flips_exactly_at_3000():
    below = quote([("X", 1)], {"X": _item(299_999, [])}, insights=False)
    at = quote([("X", 1)], {"X": _item(300_000, [])}, insights=False)
    assert (below.delivery_satang, at.delivery_satang) == (15_000, 0)


def test_free_delivery_suggestion_only_when_cheap(v1_items):
    q = quote([("PL-PR-A4-MT-100-40", 15)], v1_items)          # G8: +45.68 for one more pack
    assert q.lines[0].qty == 15 and any("Suggestion only" in i and "+45.68" in i for i in q.insights)
    q = quote([("PL-CP-A4-70", 9)], v1_items)                  # far below 3,000: no suggestion
    assert not any("Suggestion" in i for i in q.insights)
