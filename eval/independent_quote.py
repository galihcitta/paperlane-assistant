"""Independent price calculator for eval expectations. Deliberately shares no code with pl/:
regexes over the raw site files + plain Decimal arithmetic, so a bug in the engine can't hide here.

usage: python eval/independent_quote.py SITE_DIR SKU:QTY [SKU:QTY ...]
"""
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


def prices(site: Path) -> dict[str, tuple[Decimal, Decimal | None]]:
    out = {}
    num = r"([\d,]+\.\d{2})"
    for f in (site / "product").glob("*.html"):
        t = f.read_text()
        for m in re.finditer(rf"<tr><td>(PL-[A-Z0-9-]+)</td>.*?<td>(?:<del>฿{num}</del> ฿{num}|฿{num})", t):
            sku, old, sale, plain = m.groups()
            out[sku] = (Decimal((old or plain).replace(",", "")), Decimal(sale.replace(",", "")) if sale else None)
        m = re.search(r"(?:<dd>|<td>|Item code: )(PL-[A-Z0-9-]+)<", t)
        p = re.search(rf"class='big'>(?:฿)?{num}", t)
        if m and p and m.group(1) not in out:
            out[m.group(1)] = (Decimal(p.group(1).replace(",", "")), None)
    return out


def unit(site: Path, sku: str, qty: int, table) -> Decimal:
    lst, sale = table[sku]
    if sale is not None:
        return sale
    f = site / "api" / "pricing" / f"{sku}.json"
    best = lst
    if f.exists():
        for t in sorted(json.loads(f.read_text())["tiers"], key=lambda t: t["min_qty"]):
            if qty >= t["min_qty"]:
                best = Decimal(str(t["unit_price"]))
    return best


def main(site: str, lines: list[str]):
    site = Path(site)
    table = prices(site)
    sub = sum(unit(site, s, int(q), table) * int(q) for s, q in (l.split(":") for l in lines))
    dl = Decimal(0) if sub >= 3000 else Decimal(150)
    vat = ((sub + dl) * Decimal("0.07")).quantize(Decimal("0.01"), ROUND_HALF_UP)
    print(json.dumps({"lines": lines, "subtotal": f"{sub:.2f}", "delivery": f"{dl:.2f}", "vat": f"{vat:.2f}",
                      "total": f"{sub + dl + vat:.2f}", "skus_on_site": len(table)}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
