"""Post-check on the model's final reply: every THB figure and every SKU must come from tool output
(or the customer's own words). This is what stops an invented or miscalculated price reaching a customer.
"""
import re
from decimal import Decimal, InvalidOperation

_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
# A figure counts as money if it has a currency marker or exactly two decimals.
_MONEY = re.compile(
    rf"(?:฿|THB|Baht|baht)\s*({_NUM})"
    rf"|({_NUM})\s*(?:฿|THB|Baht|baht)"
    rf"|(?<![\d.,])(\d{{1,3}}(?:,\d{{3}})+\.\d{{2}}|\d+\.\d{{2}})(?![\d])"
)
_ANY_NUM = re.compile(_NUM)
_SKU = re.compile(r"\bPL-[A-Z0-9]+(?:-[A-Z0-9]+)+\b")


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", ""))
    except InvalidOperation:
        return None


def money_figures(text: str) -> list[Decimal]:
    out = []
    for m in _MONEY.finditer(text):
        v = _dec(next(g for g in m.groups() if g))
        if v is not None:
            out.append(v)
    return out


def allowed_numbers(*texts: str) -> set[Decimal]:
    return {d for t in texts for m in _ANY_NUM.findall(t) if (d := _dec(m)) is not None}


def check(reply: str, sources: list[str]) -> list[str]:
    """Returns the list of problems (empty = pass). `sources` = tool results JSON + customer messages."""
    allowed = allowed_numbers(*sources)
    joined = "\n".join(sources)
    problems = []
    for v in money_figures(reply):
        if v not in allowed:
            problems.append(f"THB figure {v} does not appear in any tool result")
    for sku in set(_SKU.findall(reply)):
        if sku not in joined:
            problems.append(f"SKU {sku} does not appear in any tool result")
    return problems
