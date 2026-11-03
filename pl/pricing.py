"""Deterministic pricing (PR1-PR8). Pure: takes the catalog snapshot as an argument, no I/O, no model.

All money is integer satang. The only rounding is VAT (PR5): 7% of (subtotal + delivery), half-up to the satang.
"""
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .models import Item
from .normalise import satang_to_str as fmt

VAT_RATE = Decimal("0.07")
FREE_DELIVERY_FROM = 300_000   # THB 3,000.00
DELIVERY_FEE = 15_000          # THB 150.00


def unit_price(it: Item, qty: int) -> tuple[int, str]:
    """(unit price in satang, rule) at this quantity. PR3: sale beats everything; PR2: highest met tier; else list."""
    if it.sale_price_satang is not None:
        return it.sale_price_satang, "sale"
    met = [t for t in it.tiers if qty >= t.min_qty]
    if met:
        t = max(met, key=lambda t: t.min_qty)
        return t.unit_price_satang, f"tier:{t.min_qty}"
    return it.list_price_satang, "list"


def delivery_for(subtotal: int) -> int:
    return 0 if subtotal >= FREE_DELIVERY_FROM else DELIVERY_FEE


def vat_for(amount: int) -> int:
    return int((Decimal(amount) * VAT_RATE).quantize(Decimal(1), ROUND_HALF_UP))


@dataclass
class Line:
    sku: str
    product_name: str
    qty: int
    pack_unit: str
    sheets_per_pack: int
    unit_price_satang: int
    rule: str
    line_total_satang: int
    list_price_satang: int
    source_url: str
    crawled_at: str
    tiers_url: str | None


@dataclass
class Quote:
    lines: list[Line] = field(default_factory=list)
    refused: list[dict] = field(default_factory=list)
    subtotal_satang: int = 0
    delivery_satang: int = 0
    vat_satang: int = 0
    total_satang: int = 0
    insights: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.refused and bool(self.lines)

    def to_dict(self) -> dict:
        """Tool-facing view: amounts as THB strings so the model copies, never computes."""
        return {
            "currency": "THB", "prices_exclude_vat": True, "ok": self.ok,
            "lines": [{"sku": l.sku, "product_name": l.product_name, "qty_packs": l.qty,
                       "pack": f"{l.pack_unit} of {l.sheets_per_pack} sheets",
                       "unit_price": fmt(l.unit_price_satang), "price_rule": l.rule,
                       "list_price": fmt(l.list_price_satang), "line_total": fmt(l.line_total_satang),
                       "source_url": l.source_url, "crawled_at": l.crawled_at} for l in self.lines],
            "refused": self.refused,
            "subtotal": fmt(self.subtotal_satang), "delivery": fmt(self.delivery_satang),
            "vat_7pct": fmt(self.vat_satang), "total_incl_vat": fmt(self.total_satang),
            "insights": self.insights,
        }

    def raw(self) -> dict:
        return asdict(self) | {"ok": self.ok}


def _totals(lines: list[tuple[Item, int]]) -> tuple[int, int, int, int]:
    sub = sum(unit_price(it, q)[0] * q for it, q in lines)
    dl = delivery_for(sub)
    vat = vat_for(sub + dl)
    return sub, dl, vat, sub + dl + vat


def quote(req: list[tuple[str, int]], items: dict[str, Item], insights: bool = True) -> Quote:
    q = Quote()
    priced: list[tuple[Item, int]] = []
    merged: dict[str, int] = {}
    for sku, qty in req:
        merged[sku] = merged.get(sku, 0) + int(qty)   # PR2 counts packs per item, so same SKU twice = one line
    for sku, qty in merged.items():
        it = items.get(sku)
        if it is None:
            q.refused.append({"sku": sku, "reason": "unknown SKU (not in the current catalog)"})
        elif qty < 1:
            q.refused.append({"sku": sku, "reason": f"quantity must be at least 1 pack (got {qty})"})
        elif it.stock_status != "in_stock":
            reason = it.stock_status.replace("_", " ")
            if it.back_in_stock:
                reason += f", expected back {it.back_in_stock.isoformat()}"
            q.refused.append({"sku": sku, "reason": reason})
        else:
            priced.append((it, qty))
    for it, qty in priced:
        u, rule = unit_price(it, qty)
        q.lines.append(Line(it.sku, it.product_name, qty, it.pack_unit, it.sheets_per_pack, u, rule, u * qty,
                            it.list_price_satang, it.source_url, it.crawled_at, it.tiers_url))
    if priced:
        q.subtotal_satang, q.delivery_satang, q.vat_satang, q.total_satang = _totals(priced)
        if insights:
            q.insights = _insights(priced, q)
    return q


def _insights(priced: list[tuple[Item, int]], q: Quote) -> list[str]:
    """Salesperson hints, all computed here so every figure is checkable."""
    out = []
    if q.delivery_satang:
        gap = FREE_DELIVERY_FROM - q.subtotal_satang
        best = None
        for i, (it, qty) in enumerate(priced):
            for extra in range(1, 4):
                trial = [(x, n + extra if j == i else n) for j, (x, n) in enumerate(priced)]
                t = _totals(trial)
                if t[1] == 0:
                    if best is None or t[3] < best[2]:
                        best = (it.sku, extra, t[3])
                    break
        out.append(f"Subtotal is {fmt(gap)} below the free-delivery threshold of 3,000.00.")
        if best:
            sku, extra, total = best
            delta = total - q.total_satang
            out.append(f"Adding {extra} more pack(s) of {sku} makes delivery free; the new total would be "
                       f"{fmt(total)} ({'+' if delta >= 0 else ''}{fmt(delta)} vs this quote).")
    for it, qty in priced:
        if it.sale_price_satang is not None:
            continue
        nxt = sorted((t for t in it.tiers if t.min_qty > qty), key=lambda t: t.min_qty)
        if nxt and nxt[0].min_qty - qty <= max(2, qty // 4):
            t = nxt[0]
            out.append(f"{it.sku}: ordering {t.min_qty} packs (+{t.min_qty - qty}) drops the unit price to "
                       f"{fmt(t.unit_price_satang)}.")
    return out
