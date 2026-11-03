import pytest

from pl.search import Criteria, merge, search


def S(items, **kw):
    return search(Criteria(**kw), items)


def test_brief_example(v1_items):
    r = S(v1_items, product_type="printed_flyer", size="letter-size", sides="one side", colour_mode="colour",
          max_unit_price=250, quantity={"value": 20})
    assert r["decision"] == "matches" and r["match_count"] == 5
    all_skus = [m["sku"] for m in r["matches"]] + r["more_matches"]
    assert "PL-PR-LTR-MT-170-40" in all_skus          # 279 list, qualifies only via the 20-pack tier
    assert "PL-PR-LTR-GL-170-40" not in all_skus      # sale 259 > 250 (PR6), sale beats tiers (PR3)
    assert r["matches"][0]["sku"] == "PL-PR-LTR-MT-100-40"
    assert r["best_quote"]["total_incl_vat"] == "4,237.20"
    assert r["narrowing_question"] == "Matte or gloss?"


@pytest.mark.parametrize("size", ["8.5x11", "8½ × 11", "US letter", "Letter"])
def test_informal_letter(v1_items, size):
    r = S(v1_items, product_type="paper", size=size, weight_lb=20, quantity={"value": 5, "unit": "reams"})
    assert r["matches"][0]["sku"] == "PL-CP-LTR-20" and r["best_quote"]["total_incl_vat"] == "882.75"


def test_missing_required_asks_one_question(v1_items):
    r = S(v1_items, product_type="printed_flyer", size="A4", quantity={"value": 5})
    assert r["decision"] == "needs_clarification" and r["missing_or_ambiguous"] == "sides"
    assert r["also_missing"] == ["colour_mode"]


def test_colour_on_plain_paper_is_ambiguous(v1_items):
    r = S(v1_items, product_type="paper", size="A4", paper_colour="colour", quantity={"value": 5})
    assert r["decision"] == "needs_clarification" and r["missing_or_ambiguous"] == "paper_colour"


def test_card_without_weight(v1_items):
    r = S(v1_items, product_type="paper", paper_kind="card", size="A4", quantity={"value": 5})
    assert r["decision"] == "needs_clarification" and r["allowed_values"] == ["160 gsm", "200 gsm", "250 gsm"]


def test_out_of_stock_exact_match_never_offered(v1_items):
    r = S(v1_items, product_type="printed_flyer", size="A4", sides="double-sided", colour_mode="cmyk",
          finish="gloss", weight_gsm=170, quantity={"value": 10})
    assert r["decision"] == "no_exact_match"
    assert r["unavailable"][0]["sku"] == "PL-PR-A4-GL-170-44" and r["unavailable"][0]["back_in_stock"] == "2026-11-12"
    assert "PL-PR-A4-GL-170-44" not in [a["sku"] for a in r["alternatives"]]
    assert all(a["sides"] == 2 and a["colour_mode"] == "cmyk" and a["size"] == "A4" for a in r["alternatives"])


def test_size_never_relaxed(v1_items):
    r = S(v1_items, product_type="printed_flyer", size="A3", sides="one side", colour_mode="cmyk", quantity={"value": 5})
    assert r["decision"] == "no_exact_match" and r["alternatives"] == []


def test_sheets_round_up(v1_items):
    r = S(v1_items, product_type="paper", size="A4", weight_gsm=70, quantity={"value": 1250, "unit": "sheets"})
    m = r["matches"][0]
    assert m["qty_packs"] == 3 and "rounded up to 3 reams" in m["rounding_note"]


def test_budget_assumption_stated(v1_items):
    r = S(v1_items, product_type="paper", size="A4", weight_gsm=70, quantity={"value": 9}, budget_total={"amount": 1200})
    assert r["decision"] == "matches" and "exclude VAT" in r["budget_assumption"]   # 981 + 150 = 1131 <= 1200
    r = S(v1_items, product_type="paper", size="A4", weight_gsm=70, quantity={"value": 9},
          budget_total={"amount": 1200, "includes_vat": True})
    assert r["decision"] == "no_exact_match"                                         # 1210.17 > 1200


def test_not_sold(v1_items):
    assert S(v1_items, product_type="other", requested_item="envelopes")["decision"] == "not_sold"


def test_custom_size_is_out_of_scope(v1_items):
    r = S(v1_items, product_type="printed_flyer", size="DL 99x210mm", sides="one side", colour_mode="cmyk", quantity={"value": 5})
    assert r["decision"] == "no_exact_match" and "custom sizes" in r["reason"] and r["alternatives"] == []


def test_invalid_values_return_error(v1_items):
    r = S(v1_items, product_type="paper", size="A4", weight_lb=22, quantity={"value": 1})
    assert "22 lb" in r["details"][0]


def test_merge_follow_up():
    a = Criteria(product_type="printed_flyer", size="A4", quantity={"value": 5})
    b = Criteria(sides="one side", colour_mode="colour")
    m = merge(a, b)
    assert (m.size, m.sides, m.quantity.value) == ("A4", "one side", 5)
    assert merge(a, Criteria(product_type="paper", new_request=True)).size is None


def test_discontinued_is_named_not_offered(v1_items):
    items = dict(v1_items)
    items["PL-CP-A4-70"] = items["PL-CP-A4-70"].model_copy(update={"stock_status": "discontinued"})
    r = S(items, product_type="paper", size="A4", weight_gsm=70, quantity={"value": 5})
    assert r["decision"] == "no_exact_match" and "no longer sold" in r["unavailable"][0]["note"]
    assert r["alternatives"] and "PL-CP-A4-70" not in [a["sku"] for a in r["alternatives"]]


def test_ranked_by_cheapest_line_total(v1_items):
    r = S(v1_items, product_type="paper", size="A4", weight_gsm=80, quantity={"value": 10})
    totals = [float(m["line_total"].replace(",", "")) for m in r["matches"]]
    assert totals == sorted(totals)


def test_a3_reams_prefers_white_and_cheaper_total(v1_items):
    r = S(v1_items, product_type="paper", size="A3", quantity={"value": 5, "unit": "reams"})
    assert r["matches"][0]["sku"] == "PL-CP-A3-80" and r["best_quote"]["total_incl_vat"] == "1,546.15"


def test_coloured_sheets_cheapest_line_total(v1_items):
    r = S(v1_items, product_type="paper", paper_kind="coloured", paper_colour="coloured", size="A4",
          quantity={"value": 1000, "unit": "sheets"})
    assert r["decision"] == "matches" and r["matches"][0]["line_total"] == "390.00"


@pytest.mark.parametrize("loc,inside", [("Chiang Mai", False), ("Phuket", False), ("Nonthaburi", True),
                                        ("our office on Sukhumvit 21", True), ("Bangkok", True), ("Hua Hin", False)])
def test_delivery_area(v1_items, loc, inside):
    r = S(v1_items, product_type="paper", size="A4", weight_gsm=70, quantity={"value": 10}, delivery_location=loc)
    assert r["decision"] == "matches" and r["best_quote"]["total_incl_vat"] == "1,280.15"   # still quoted
    assert r["delivery_area"]["in_service_area"] is inside
    assert ("needs confirmation" in r["delivery_area"].get("note", "")) is (not inside)
