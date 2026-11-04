"""Post-check on the model's final reply against THIS turn's tool results. It guarantees that:

- every money figure (currency-marked, two-decimal, or a bare amount of 3+ digits that isn't a quantity)
  appears in this turn's tool results or the customer's own message this turn (or is a fixed policy figure);
- a figure on a line that names one SKU belongs to that SKU's tool data (or is a quote total);
- a line labelled "Total" / "Subtotal" (the breakdown line) states a quote's total / subtotal;
- every SKU and every catalog product name in the reply appears in this turn's tool results;
- no sentence claims a total excludes delivery (every total the tools return includes it).

Apart from that delivery claim it cannot tell whether prose claims (e.g. "matte finish") are right, and it misses
paraphrased product names.
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
# The breakdown line: "Total: 1,546.15", "- Subtotal 1,295.00", "**Total incl. VAT**: ...". Not "the total would rise".
_TOTAL = re.compile(r"^\s*(?:[-*•]\s*)?(?:\*\*)?(sub)?total\b", re.I)
POLICY = {Decimal("3000"), Decimal("150")}   # free-delivery threshold and fee, stated in the system prompt
# Claims that a total leaves delivery out. Subtotals, line totals and unit prices really do exclude it, so they don't count.
_D = r"(?:delivery|shipping)"
_NOT_TOTAL = re.compile(r"\b(?:line|item|goods|product)\s+totals?\b|\btotals?\s+budget\b", re.I)
_TOTAL_WORD = re.compile(r"\btotals?\b", re.I)
_LEAVES_OUT = re.compile(
    rf"\btotals?\b.{{0,120}}?(?:(?:exclud\w*|(?:not|n['’]t)\s+(?:yet\s+)?(?:includ\w*|count\w*))\s+(?:\S+\s+){{0,3}}?{_D}"
    rf"|without\s+(?:the\s+)?{_D}|(?:but\s+|and\s+|,\s*)not\s+(?:the\s+)?{_D})", re.I)
_D_LEFT_OUT = re.compile(rf"{_D}\W+(?:\S+\s+){{0,2}}?(?:(?:not|\w*n['’]t)\s+(?:yet\s+)?includ|exclud)|{_D}.{{0,40}}?\bon top of\b", re.I)
_RISES = r"(?:higher|more|increase\w*|go(?:es)? up|rises?)\b(?!\s+than\b)"     # "higher than your budget" is about the budget
_HIGHER_ONCE = re.compile(rf"\btotals?\b.{{0,100}}?\b{_RISES}.{{0,50}}?\b(?:once|when|after)\b.{{0,40}}?{_D}"
                          rf"|\b(?:once|when|after)\b.{{0,30}}?{_D}.{{0,40}}?\b(?:added|included)\b.{{0,80}}?\btotals?\b.{{0,40}}?\b{_RISES}", re.I)
_HIGHER_IT = re.compile(rf"\btotals?\b.{{0,100}}?\b{_RISES}.{{0,50}}?\b(?:once|when|after)\s+it['’]?s?\s+(?:is\s+)?(?:added|included)", re.I)
_LEAVES_OUT_TH = re.compile(r"(?:ยอดรวม|ราคารวม|รวมทั้งหมด|ยอดสุทธิ).{0,60}?ไม่รวมค่า(?:จัด)?ส่ง")


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


def false_delivery_claim(reply: str) -> str | None:
    """The first sentence saying a total excludes delivery. "Could be higher once delivery is confirmed" is honest
    (delivery outside the service area needs the sales team), so it doesn't count."""
    for line in reply.splitlines():
        for s in re.split(r"(?<=[.!?])\s+", line):
            t = _NOT_TOTAL.sub(" ", s)
            if _LEAVES_OUT.search(t) or _LEAVES_OUT_TH.search(t) or (_TOTAL_WORD.search(t) and _D_LEFT_OUT.search(t)):
                return s
            if "confirm" not in t.lower() and (_HIGHER_ONCE.search(t) or (re.search(_D, line, re.I) and _HIGHER_IT.search(t))):
                return s
    return None


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
    q_level = allowed_numbers(*(json.dumps({k: v for k, v in q.items() if k != "lines"}, ensure_ascii=False)
                                for q in quotes))   # subtotal, delivery, VAT, total, insights (e.g. free-delivery tip)
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
            ok = per_sku.get(sku, set()) | q_level | allowed_numbers(customer) | POLICY
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
    if (claim := false_delivery_claim(reply)):
        problems.append(f"a claim that a total leaves out delivery ({claim!r}), but every total already includes delivery and VAT")
    return problems
