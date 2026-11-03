"""What changed between two catalog snapshots. Feeds the per-run report a human reviews before trusting a refresh."""
from .models import Item
from .normalise import satang_to_str as s

_OTHER = ["product_name", "size_code", "weight_gsm", "colour", "finish", "sides", "colour_mode",
          "sheets_per_pack", "pack_unit", "brand", "category", "product_type"]


def _tiers(it: Item) -> str:
    return ", ".join(f"{t.min_qty}+: {s(t.unit_price_satang)}" for t in it.tiers) or "none"


def diff(old: dict[str, Item], new: dict[str, Item]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {k: [] for k in ["new", "removed", "price", "sale", "tiers", "stock", "quotable", "other"]}
    for sku in sorted(new.keys() - old.keys()):
        it = new[sku]
        out["new"].append(f"{sku} {it.product_name} @ {s(it.list_price_satang)} ({it.stock_status})")
    for sku in sorted(old.keys() - new.keys()):
        out["removed"].append(f"{sku} {old[sku].product_name}")
    for sku in sorted(old.keys() & new.keys()):
        a, b = old[sku], new[sku]
        if a.list_price_satang != b.list_price_satang:
            out["price"].append(f"{sku}: list {s(a.list_price_satang)} -> {s(b.list_price_satang)}")
        if a.sale_price_satang != b.sale_price_satang:
            fa = s(a.sale_price_satang) if a.sale_price_satang else "none"
            fb = s(b.sale_price_satang) if b.sale_price_satang else "none"
            out["sale"].append(f"{sku}: sale {fa} -> {fb}")
        if _tiers(a) != _tiers(b):
            out["tiers"].append(f"{sku}: tiers [{_tiers(a)}] -> [{_tiers(b)}]")
        if (a.stock_status, a.back_in_stock) != (b.stock_status, b.back_in_stock):
            out["stock"].append(f"{sku}: {a.stock_status} -> {b.stock_status}"
                                + (f" (back {b.back_in_stock})" if b.back_in_stock else ""))
        if a.quotable != b.quotable:
            out["quotable"].append(f"{sku}: " + ("now quotable" if b.quotable else f"NOT quotable ({b.quarantine_reason})"))
        for f in _OTHER:
            if getattr(a, f) != getattr(b, f):
                out["other"].append(f"{sku}: {f} {getattr(a, f)!r} -> {getattr(b, f)!r}")
    return out


def change_count(d: dict[str, list[str]]) -> int:
    return sum(len(v) for v in d.values())
