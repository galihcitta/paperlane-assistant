"""Post-check on the model's final reply against THIS turn's tool results. It guarantees that:

- every money figure (currency-marked, two-decimal, or a bare amount of 3+ digits that isn't a quantity)
  appears in this turn's tool results or the customer's own message this turn (or is a fixed policy figure);
- a figure on a line that names one SKU belongs to that SKU's tool data (or is a quote total);
- a "total" / "subtotal" on a line that names no product equals a quote's total / subtotal;
- every SKU and every catalog product name in the reply appears in this turn's tool results.

It cannot tell whether prose claims (e.g. "matte finish") are right, and it misses paraphrased product names.
"""
import json
import re
from decimal import Decimal, InvalidOperation

_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_CCY = r"(?:฿|THB|Baht|baht|บาท)"
_UNIT_AFTER = (r"(?!\s*(?:sheets?|gsm|g/m|g\b|lb|packs?|reams?|boxes|box|mm|cm|pcs|pieces|copies|flyers|cards"
               r"|x\b|×|%|in\b|inch|\"|days?|-\d|/))")
# Money = currency marker, exactly two decimals, or a bare amount with 3+ integer digits that isn't a quantity.
_MONEY = re.compile(
    rf"{_CCY}\s*({_NUM})"
    rf"|({_NUM})\s*{_CCY}"
    rf"|(?<![\d.,])(\d{{1,3}}(?:,\d{{3}})+\.\d{{2}}|\d+\.\d{{2}})(?![\d])"
    rf"|(?<![\d.,/-])(\d{{1,3}}(?:,\d{{3}})+|\d{{3,}})(?![\d.,]){_UNIT_AFTER}"
)
_ANY_NUM = re.compile(_NUM)
_SKU = re.compile(r"\bPL-[A-Z0-9]+(?:-[A-Z0-9]+)+\b")
_TOTAL = re.compile(r"(?<!line )\b(sub)?total\b", re.I)
POLICY = {Decimal("3000"), Decimal("150")}   # free-delivery threshold and fee, stated in the system prompt


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", ""))
    except InvalidOperation:
        return None


def money_figures(text: str) -> list[Decimal]:
    out = []
    for m in _MONEY.finditer(_SKU.sub(" ", text)):
        v = _dec(next(g for g in m.groups() if g))
        if v is not None:
            out.append(v)
    return out


def allowed_numbers(*texts: str) -> set[Decimal]:
    return {d for t in texts for m in _ANY_NUM.findall(t) if (d := _dec(m)) is not None}


def _walk(x, per_sku: dict, quotes: list):
    if isinstance(x, dict):
        if "total_incl_vat" in x and "subtotal" in x:
            quotes.append(x)
        if isinstance(x.get("sku"), str):
            per_sku.setdefault(x["sku"], set()).update(allowed_numbers(json.dumps(x, ensure_ascii=False)))
        for v in x.values():
            _walk(v, per_sku, quotes)
    elif isinstance(x, list):
        for v in x:
            _walk(v, per_sku, quotes)


def check(reply: str, results: list[str], customer: str = "", catalog_names=()) -> list[str]:
    """Problems found (empty = pass). `results` = this turn's tool result JSON strings."""
    joined = "\n".join(results)
    allowed = allowed_numbers(joined, customer) | POLICY
    per_sku: dict[str, set] = {}
    quotes: list[dict] = []
    for r in results:
        try:
            _walk(json.loads(r), per_sku, quotes)
        except ValueError:
            pass
    q_totals = {_dec(q["total_incl_vat"]) for q in quotes}
    q_subs = {_dec(q["subtotal"]) for q in quotes}
    names = {n for n in catalog_names if n and n.lower() in reply.lower()}

    problems = []
    for v in money_figures(reply):
        if v not in allowed:
            problems.append(f"THB figure {v} does not appear in this turn's tool results")
    for sku in sorted(set(_SKU.findall(reply))):
        if sku not in joined:
            problems.append(f"SKU {sku} does not appear in this turn's tool results")
    for n in sorted(names):
        if n not in joined:
            problems.append(f"product {n!r} does not appear in this turn's tool results")

    for line in reply.splitlines():
        skus = set(_SKU.findall(line))
        if len(skus) == 1:
            sku = skus.pop()
            ok = per_sku.get(sku, set()) | q_totals | q_subs | allowed_numbers(customer) | POLICY
            for v in money_figures(line):
                if v not in ok and v in allowed:
                    problems.append(f"{v} is stated for {sku} but is not that SKU's figure")
        elif not skus and not any(n.lower() in line.lower() for n in names):
            for m in _TOTAL.finditer(line):
                figs, want = money_figures(line[m.end():]), (q_subs if m.group(1) else q_totals)
                v = figs[0] if figs else None
                if want and v is not None and v not in want and v not in POLICY:   # "free from a 3,000 subtotal"
                    label = "subtotal" if m.group(1) else "total"
                    problems.append(f"stated {label} {v} does not match the quote ({', '.join(map(str, sorted(want)))})")
    return problems
