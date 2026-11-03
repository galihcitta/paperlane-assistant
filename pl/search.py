"""Criteria validation and the search decision. All of this is code: the model fills Criteria,
this module decides clarify / matches / no_exact_match / not_sold and prices every candidate.
"""
import math
import re
from typing import Literal

from pydantic import BaseModel, Field

from . import normalise as N
from .models import Item
from .normalise import satang_to_str as fmt
from .pricing import delivery_for, quote, unit_price, vat_for


class Quantity(BaseModel):
    value: int = Field(gt=0)
    unit: Literal["packs", "sheets", "reams"] = Field(
        "packs", description="'500 flyers' or '2,000 sheets' -> sheets (a flyer pack is 100 printed sheets)")


class Budget(BaseModel):
    amount: float = Field(gt=0, description="THB")
    includes_vat: bool | None = Field(None, description="true only if the customer said the budget includes VAT ('incl. VAT', 'all-in', 'including tax')")


class Criteria(BaseModel):
    """What the customer asked for, in their words where possible; code normalises every field."""
    item_label: str = Field("item1", description="Use a different label per item in multi-item requests")
    new_request: bool = Field(False, description="true when this replaces (not refines) the previous request for this item_label")
    product_type: Literal["paper", "printed_flyer", "other"] | None = Field(
        None, description="'paper' = blank sheets; 'printed_flyer' = we print the customer's design; 'other' = anything PaperLane does not sell")
    requested_item: str | None = Field(None, description="for product_type 'other': what they asked for")
    paper_kind: Literal["copy", "coloured", "card", "photo"] | None = None
    size: str | None = Field(None, description="as said: 'A4', 'letter', '8.5x11', 'legal'...")
    sides: str | None = Field(None, description="as said: 'one side', '4/0', 'double-sided'...")
    colour_mode: str | None = Field(None, description="print colour as said: 'full colour', 'CMYK', 'B&W'...")
    paper_colour: str | None = Field(None, description="colour of the paper itself, as said")
    finish: str | None = Field(None, description="'matte', 'gloss', 'uncoated'...")
    weight_gsm: int | None = None
    weight_lb: int | None = None
    min_gsm: int | None = None
    max_gsm: int | None = None
    quantity: Quantity | None = None
    max_unit_price: float | None = Field(None, description="THB per pack, before VAT")
    budget_total: Budget | None = None
    keywords: list[str] = Field(default_factory=list, description="soft preferences: brand, 'recycled'...")
    delivery_location: str | None = Field(None, description="where the customer wants delivery, if they said")


_GENERIC_COLOUR = {"colour", "color", "coloured", "colored", "colourful", "colorful", "any colour", "any color", "coloured paper"}
REQUIRED = {"printed_flyer": ["size", "sides", "colour_mode", "quantity"], "paper": ["size", "quantity"]}
QUESTIONS = {
    "product_type": "Is this blank paper, or flyers that we print for you?",
    "size": "Which paper size do you need?",
    "sides": "Printed on one side or both sides?",
    "colour_mode": "Full colour or black and white printing?",
    "quantity": "How many packs do you need?",
    "paper_colour": "Do you mean coloured paper (which colour?), or white paper printed in full colour?",
    "weight": "Which weight (thickness) would you like?",
}


class Norm(BaseModel):
    """Criteria after code normalisation (what the filters use)."""
    product_type: str | None = None
    paper_kind: str | None = None
    size_code: str | None = None
    sides: int | None = None
    colour_mode: str | None = None
    paper_colour: str | None = None
    finish: str | None = None
    weight_gsm: int | None = None
    weight_converted_from_lb: int | None = None
    min_gsm: int | None = None
    max_gsm: int | None = None
    quantity: Quantity | None = None
    max_unit_price_satang: int | None = None
    budget_satang: int | None = None
    budget_includes_vat: bool = False
    budget_assumption: str | None = None
    keywords: list[str] = []
    ambiguous: list[str] = []
    size_raw: str | None = None


def merge(prev: Criteria | None, new: Criteria) -> Criteria:
    if prev is None or new.new_request:
        return new
    data = prev.model_dump()
    for k, v in new.model_dump(exclude_unset=True).items():
        if v is not None and v != [] and k != "new_request":
            data[k] = v
    return Criteria(**data)


def normalise(c: Criteria) -> tuple[Norm, list[str]]:
    errs: list[str] = []
    n = Norm(paper_kind=c.paper_kind, keywords=[k.lower() for k in c.keywords],
             min_gsm=c.min_gsm, max_gsm=c.max_gsm, quantity=c.quantity)
    if c.size:
        code, _, _ = N.parse_size(c.size)
        n.size_code = None if code is None else "CUSTOM" if code == "OTHER" else code   # None -> ask which size
        n.size_raw = c.size
    if c.sides:
        n.sides = N.parse_sides(c.sides) or ({"1": 1, "2": 2}.get(c.sides.strip()))
        if n.sides is None:
            errs.append(f"sides {c.sides!r} not recognised; allowed: one side (4/0), both sides (4/4)")
    if c.colour_mode:
        n.colour_mode = N.parse_colour_mode(c.colour_mode)
        if n.colour_mode is None:
            errs.append(f"colour_mode {c.colour_mode!r} not recognised; allowed: full colour (CMYK), black and white")
    if c.paper_colour:
        if c.paper_colour.strip().lower() in _GENERIC_COLOUR:
            if c.paper_kind != "coloured":  # "any coloured paper" is already said by paper_kind
                n.ambiguous.append("paper_colour")
        else:
            n.paper_colour = N.parse_colour(c.paper_colour)
    if c.finish:
        n.finish = N.parse_finish(c.finish)
    if c.weight_lb is not None:
        if c.weight_lb in N.LB_TO_GSM:
            n.weight_gsm, n.weight_converted_from_lb = N.LB_TO_GSM[c.weight_lb], c.weight_lb
        else:
            errs.append(f"weight {c.weight_lb} lb has no agreed gsm equivalent; allowed lb: {sorted(N.LB_TO_GSM)}")
    if c.weight_gsm is not None:
        n.weight_gsm = c.weight_gsm
    if c.max_unit_price is not None:
        n.max_unit_price_satang = N.money_to_satang(c.max_unit_price)
    if c.budget_total:
        n.budget_satang = N.money_to_satang(c.budget_total.amount)
        n.budget_includes_vat = bool(c.budget_total.includes_vat)
        n.budget_assumption = ("Budget treated as including 7% VAT (customer said so)." if n.budget_includes_vat else
                               "Budget assumed to exclude VAT (PaperLane default); compared with subtotal + delivery.")
    n.product_type = c.product_type
    if n.product_type is None and (n.sides or n.colour_mode):
        n.product_type = "printed_flyer"
    if n.product_type is None and (n.paper_kind or n.paper_colour or n.weight_converted_from_lb):
        n.product_type = "paper"
    return n, errs


def packs_for(it: Item, q: Quantity) -> tuple[int, str | None]:
    """Requested quantity in packs of this item, rounding up when sheets don't fill whole packs."""
    if q.unit == "packs" or (q.unit == "reams" and it.pack_unit == "ream"):
        return q.value, None
    sheets = q.value * 500 if q.unit == "reams" else q.value
    packs = math.ceil(sheets / it.sheets_per_pack)
    note = None
    if packs * it.sheets_per_pack != sheets:
        note = (f"{sheets:,} sheets is not a whole number of {it.pack_unit}s of {it.sheets_per_pack}; "
                f"rounded up to {packs} {it.pack_unit}s ({packs * it.sheets_per_pack:,} sheets).")
    return packs, note


def _kind(it: Item) -> str:
    name, cat = it.product_name.lower(), (it.category or "").lower()
    if "photo" in name:
        return "photo"
    if "card" in name:
        return "card"
    if "colour" in cat or "color" in cat or (it.colour not in (None, "white")):
        return "coloured"
    return "copy"


def _priced(it: Item, n: Norm) -> dict:
    packs, note = packs_for(it, n.quantity)
    u, rule = unit_price(it, packs)
    sub = u * packs
    dl = delivery_for(sub)
    vat = vat_for(sub + dl)
    return {"it": it, "packs": packs, "unit": u, "rule": rule, "sub": sub, "pre_vat": sub + dl,
            "total": sub + dl + vat, "rounding_note": note}


def _off_white(it: Item, n: Norm) -> int:
    """1 for a non-white paper when the customer named no colour (and didn't ask for coloured paper)."""
    return int(n.product_type == "paper" and n.paper_colour is None and n.paper_kind != "coloured"
               and it.colour not in (None, "white"))


def _view(p: dict, why: list[str] | None = None, differs: list[str] | None = None) -> dict:
    it = p["it"]
    d = {"sku": it.sku, "product_name": it.product_name, "size": it.size_code, "weight_gsm": it.weight_gsm,
         "finish": it.finish, "paper_colour": it.colour_raw, "sides": it.sides, "colour_mode": it.colour_mode,
         "pack": f"{it.pack_unit} of {it.sheets_per_pack} sheets", "qty_packs": p["packs"],
         "unit_price": fmt(p["unit"]), "price_rule": p["rule"], "list_price": fmt(it.list_price_satang),
         "line_total": fmt(p["sub"]), "total_incl_vat_if_ordered_alone": fmt(p["total"]),
         "stock": it.stock_status, "source_url": it.source_url}
    if it.weight_source == "converted_from_lb":
        d["weight_note"] = f"site states {it.weight_lb_stated} lb; {it.weight_gsm} gsm by the agreed table"
    if p.get("rounding_note"):
        d["rounding_note"] = p["rounding_note"]
    if why is not None:
        d["why"] = why
    if differs is not None:
        d["differs"] = differs
    return d


def _criteria_view(n: Norm) -> dict:
    return {k: v for k, v in n.model_dump().items() if v not in (None, [], False) and k != "ambiguous"}


def search(c: Criteria, items: dict[str, Item]) -> dict:
    n, errs = normalise(c)
    if errs:
        return {"error": "invalid criteria", "details": errs}
    base = {"criteria_used": _criteria_view(n)}
    if n.budget_assumption:
        base["budget_assumption"] = n.budget_assumption
    if c.delivery_location:
        base["delivery_area"] = delivery_area(c.delivery_location)

    if n.product_type == "other":
        types = sorted({(it.product_type, it.size_code) for it in items.values()})
        return base | {"decision": "not_sold", "requested_item": c.requested_item,
                       "message": "PaperLane does not list this. Do not suggest any product as if it were this item.",
                       "what_we_sell": {"paper": sorted({s for t, s in types if t == "paper"}),
                                        "printed_flyer": sorted({s for t, s in types if t == "printed_flyer"})}}

    pool = [it for it in items.values() if n.product_type is None or it.product_type == n.product_type]
    if n.paper_kind and n.product_type == "paper":
        pool = [it for it in pool if _kind(it) == n.paper_kind]

    def clarify(field: str, allowed: list) -> dict:
        missing = [f for f in REQUIRED.get(n.product_type or "", []) if _missing(n, f)]
        out = base | {"decision": "needs_clarification", "missing_or_ambiguous": field,
                      "question": QUESTIONS[field], "allowed_values": allowed,
                      "also_missing": [m for m in missing if m != field]}
        if field == "size" and n.size_raw:
            out["size_not_recognised"] = n.size_raw
        return out

    if n.product_type is None:
        return clarify("product_type", ["paper", "printed_flyer"])
    if "paper_colour" in n.ambiguous and n.product_type == "paper":
        colours = sorted({it.colour_raw for it in pool if it.colour and it.colour != "white"
                          and (not n.size_code or it.size_code == n.size_code)})
        return clarify("paper_colour", colours + ["white paper printed in full colour (flyer printing)"])
    for f in REQUIRED[n.product_type]:
        if _missing(n, f):
            return clarify(f, _allowed(pool, f))
    if n.paper_kind in ("card", "photo") and n.weight_gsm is None and n.min_gsm is None and n.max_gsm is None:
        weights = sorted({it.weight_gsm for it in pool if it.size_code == n.size_code})
        if len(weights) > 1:
            return clarify("weight", [f"{w} gsm" for w in weights])

    if n.size_code == "CUSTOM":
        return base | {"decision": "no_exact_match", "reason": f"size {n.size_raw!r} is not a size PaperLane lists; custom sizes are out of scope",
                       "alternatives": [], "unavailable": [], "sizes_we_sell": sorted({it.size_code for it in pool}),
                       "message": "Say custom sizes aren't offered; ask if one of the listed sizes would work."}
    sized = [it for it in pool if it.size_code == n.size_code]
    if not sized:
        return base | {"decision": "no_exact_match", "reason": f"no {n.product_type.replace('_', ' ')} in size {n.size_code}",
                       "alternatives": [], "unavailable": [],
                       "sizes_we_sell": sorted({it.size_code for it in pool}),
                       "message": "Size is never substituted automatically; ask if another size would work."}

    hard = [it for it in sized if _fixed_ok(it, n)]
    soft_ok = lambda it, n_: _soft_fail(it, n_) == []
    exact = [it for it in hard if soft_ok(it, n)]
    in_stock = [_priced(it, n) for it in exact if it.stock_status == "in_stock" and it.quotable]
    in_stock = [p for p in in_stock if _price_ok(p, n)]
    unavailable = [{"sku": it.sku, "product_name": it.product_name, "stock": it.stock_status,
                    "back_in_stock": it.back_in_stock.isoformat() if it.back_in_stock else None,
                    "note": ("price/details need confirmation by sales (catalog data problem)" if not it.quotable
                             else "no longer sold (discontinued)" if it.stock_status == "discontinued"
                             else "temporarily out of stock; cannot be quoted until it is back")}
                   for it in exact if it.stock_status != "in_stock" or not it.quotable]

    if in_stock:
        # Stated preferences first; with no paper colour given, white first; then the cheapest line total for the
        # requested quantity (converted to whole packs per item, so a 250-sheet pack is compared fairly with a ream).
        ranked = sorted(in_stock, key=lambda p: (-_kw_score(p["it"], n), _off_white(p["it"], n), p["sub"], p["unit"]))
        top = ranked[:3]
        best = top[0]
        q = quote([(best["it"].sku, best["packs"])], items)
        out = base | {"decision": "matches", "match_count": len(ranked),
                      "matches": [_view(p, _why(p, n)) for p in top],
                      "best_quote": q.to_dict()}
        if len(ranked) > 3:
            out["more_matches"] = [p["it"].sku for p in ranked[3:]]
        if unavailable:
            out["unavailable"] = unavailable
        nq = _narrowing_question(ranked, n)
        if nq:
            out["narrowing_question"] = nq
        return out

    # No exact in-stock match: relax in fixed order, never size/type/sides/colour mode.
    alts: list[dict] = []
    relaxed: list[str] = []
    seen: set[str] = set()
    n2 = n.model_copy()
    for step in ["price", "finish", "weight", "paper_colour"]:
        if step == "price":
            if n2.max_unit_price_satang is None and n2.budget_satang is None:
                continue
            n2.max_unit_price_satang = n2.budget_satang = None
        elif step == "finish":
            if n2.finish is None:
                continue
            n2.finish = None
        elif step == "weight":
            if n2.weight_gsm is None and n2.min_gsm is None and n2.max_gsm is None:
                continue
            n2.weight_gsm = n2.min_gsm = n2.max_gsm = None
        elif step == "paper_colour":
            if n2.paper_colour is None:
                continue
            n2.paper_colour = None
        relaxed.append(step)
        cands = [_priced(it, n2) for it in hard if soft_ok(it, n2) and it.stock_status == "in_stock" and it.quotable]
        cands = [p for p in cands if _price_ok(p, n2) and p["it"].sku not in seen]
        cands.sort(key=lambda p: (len(_differs(p, n)), _distance(p, n), _off_white(p["it"], n), p["sub"]))
        for p in cands[:3 - len(alts)]:
            seen.add(p["it"].sku)
            alts.append(_view(p, differs=_differs(p, n)))
        if len(alts) >= 3:
            break
    return base | {"decision": "no_exact_match",
                   "reason": "matching items are out of stock or unavailable" if unavailable and not relaxed
                   else "nothing in stock meets every requirement",
                   "unavailable": unavailable, "relaxed": relaxed, "alternatives": alts,
                   "never_relaxed": ["size", "product type", "sides", "colour mode"]}


def _missing(n: Norm, f: str) -> bool:
    return {"size": n.size_code, "sides": n.sides, "colour_mode": n.colour_mode, "quantity": n.quantity}[f] is None


def _allowed(pool: list[Item], f: str) -> list:
    if f == "size":
        return sorted({it.size_code for it in pool})
    if f == "sides":
        return ["one side (4/0)", "both sides (4/4)"]
    if f == "colour_mode":
        return ["full colour (CMYK)", "black and white"]
    return ["number of packs, or number of sheets"]


def _fixed_ok(it: Item, n: Norm) -> bool:
    if n.product_type == "printed_flyer":
        return it.sides == n.sides and it.colour_mode == n.colour_mode
    return True


def _soft_fail(it: Item, n: Norm) -> list[str]:
    fails = []
    if n.finish and it.finish != n.finish:
        fails.append("finish")
    if n.weight_gsm is not None and it.weight_gsm != n.weight_gsm:
        fails.append("weight")
    if n.min_gsm is not None and (it.weight_gsm or 0) < n.min_gsm:
        fails.append("weight")
    if n.max_gsm is not None and (it.weight_gsm or 0) > n.max_gsm:
        fails.append("weight")
    if n.paper_colour and it.colour != n.paper_colour and not (n.product_type == "printed_flyer" and n.paper_colour == "white"):
        fails.append("paper_colour")
    return fails


def _price_ok(p: dict, n: Norm) -> bool:
    if n.max_unit_price_satang is not None and p["unit"] > n.max_unit_price_satang:   # PR6: price at requested qty
        return False
    if n.budget_satang is not None:
        spend = p["total"] if n.budget_includes_vat else p["pre_vat"]
        if spend > n.budget_satang:
            return False
    return True


def _why(p: dict, n: Norm) -> list[str]:
    it, out = p["it"], []
    out.append(f"{it.product_type.replace('_', ' ')}, size {it.size_code}")
    if n.sides:
        out.append("one side" if it.sides == 1 else "both sides")
    if n.colour_mode:
        out.append("full colour" if it.colour_mode == "cmyk" else "black and white")
    if n.finish:
        out.append(f"{it.finish} finish")
    if n.weight_gsm or n.min_gsm or n.max_gsm:
        out.append(f"{it.weight_gsm} gsm")
    if n.paper_colour:
        out.append(f"colour {it.colour_raw}")
    if n.max_unit_price_satang is not None:
        out.append(f"unit price {fmt(p['unit'])} at {p['packs']} packs is within max {fmt(n.max_unit_price_satang)} ({p['rule']})")
    if n.budget_satang is not None:
        spend = p["total"] if n.budget_includes_vat else p["pre_vat"]
        out.append(f"{'total incl. VAT' if n.budget_includes_vat else 'subtotal + delivery'} {fmt(spend)} within budget {fmt(n.budget_satang)}")
    out.append("in stock")
    hits = [k for k in n.keywords if k in (it.product_name + " " + (it.brand or "")).lower()]
    if hits:
        out.append("matches preference: " + ", ".join(hits))
    return out


def _differs(p: dict, n: Norm) -> list[str]:
    it, out = p["it"], []
    if n.max_unit_price_satang is not None and p["unit"] > n.max_unit_price_satang:
        out.append(f"unit price {fmt(p['unit'])} is {fmt(p['unit'] - n.max_unit_price_satang)} over the max {fmt(n.max_unit_price_satang)}")
    if n.budget_satang is not None:
        spend = p["total"] if n.budget_includes_vat else p["pre_vat"]
        if spend > n.budget_satang:
            out.append(f"{'total incl. VAT' if n.budget_includes_vat else 'subtotal + delivery'} {fmt(spend)} is "
                       f"{fmt(spend - n.budget_satang)} over the budget {fmt(n.budget_satang)}")
    if n.finish and it.finish != n.finish:
        out.append(f"finish {it.finish} instead of {n.finish}")
    if n.weight_gsm is not None and it.weight_gsm != n.weight_gsm:
        d = it.weight_gsm - n.weight_gsm
        out.append(f"weight {it.weight_gsm} gsm instead of {n.weight_gsm} gsm ({'+' if d > 0 else ''}{d} gsm)")
    if (n.min_gsm is not None and it.weight_gsm < n.min_gsm) or (n.max_gsm is not None and it.weight_gsm > n.max_gsm):
        out.append(f"weight {it.weight_gsm} gsm is outside {n.min_gsm or 0}-{n.max_gsm or '∞'} gsm")
    if n.paper_colour and it.colour != n.paper_colour:
        out.append(f"colour {it.colour_raw} instead of {n.paper_colour}")
    return out


def _distance(p: dict, n: Norm) -> int:
    d = 0
    if n.weight_gsm is not None:
        d += abs(p["it"].weight_gsm - n.weight_gsm)
    if n.max_unit_price_satang is not None:
        d += max(0, p["unit"] - n.max_unit_price_satang) // 100
    if n.paper_colour and p["it"].colour != n.paper_colour:
        d += 0 if p["it"].colour in _NEAR_COLOURS.get(n.paper_colour, ()) else 1000
    return d


_NEAR_COLOURS = {"ivory": ("cream",), "cream": ("ivory",), "white": ("ivory", "cream")}


def _kw_score(it: Item, n: Norm) -> int:
    text = (it.product_name + " " + (it.brand or "") + " " + (it.colour_raw or "")).lower()
    return sum(1 for k in n.keywords if k in text)


def _narrowing_question(ranked: list[dict], n: Norm) -> str | None:
    # Only narrow among the products that fit what they named (e.g. a product name in keywords).
    top = max(_kw_score(p["it"], n) for p in ranked)
    its = [p["it"] for p in ranked if _kw_score(p["it"], n) == top]
    if len(its) < 2:
        return None
    if n.finish is None and len({i.finish for i in its}) > 1:
        return "Matte or gloss?" if {i.finish for i in its} <= {"matte", "gloss"} else \
            "Which finish do you prefer: " + ", ".join(sorted({i.finish for i in its})) + "?"
    if n.weight_gsm is None and len({i.weight_gsm for i in its}) > 1:
        return "Which paper weight: " + ", ".join(f"{w} gsm" for w in sorted({i.weight_gsm for i in its})) + "?"
    if n.paper_colour is None and len({i.colour for i in its}) > 1:
        return "White, or a coloured paper (" + ", ".join(sorted({i.colour for i in its} - {"white", None})) + ")?"
    if len({i.brand for i in its}) > 1:
        return "Any brand preference: " + ", ".join(sorted({i.brand for i in its if i.brand})) + "?"
    return None



# "Bangkok and vicinity" (site banner) = Bangkok plus the five adjoining provinces of the metropolitan region.
_IN_AREA = ["bangkok", "bkk", "krung thep", "nonthaburi", "pathum thani", "samut prakan", "samut sakhon",
            "nakhon pathom", "pak kret", "rangsit", "bang phli", "bang yai", "bang bua thong", "lam luk ka",
            "phra pradaeng", "suvarnabhumi", "sukhumvit", "silom", "sathorn", "sathon", "bang na", "chatuchak",
            "lat phrao", "ladprao", "ratchada", "bang kapi", "huai khwang", "pathum wan", "bang rak", "khlong toei",
            "watthana", "phaya thai", "ratchathewi", "din daeng", "don mueang", "lak si", "bang sue", "min buri",
            "lat krabang", "thon buri", "thonburi", "bang khen", "sai mai", "prawet", "suan luang", "phra khanong",
            "yan nawa", "bang kho laem", "rama 9", "ari", "thonglor", "thong lo", "ekkamai", "on nut", "asok", "siam"]


def delivery_area(location: str) -> dict:
    """Assumption 5: quote normally, but flag delivery outside (or not recognisably inside) Bangkok and vicinity."""
    t = location.lower()
    if any(re.search(rf"\b{re.escape(a)}\b", t) for a in _IN_AREA):
        return {"location": location, "in_service_area": True}
    return {"location": location, "in_service_area": False,
            "note": "PaperLane delivers in Bangkok and vicinity. Delivery to this location needs confirmation by "
                    "the sales team; the quote below uses standard delivery terms."}
