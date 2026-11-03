"""Label-driven parsers for PaperLane product pages.

The site shows the same facts in four layouts (variant table, spec table, spec <dl>, prose).
We never parse by position: every value is found through its label (via SYNONYMS), so a
reordered column or a renamed-but-known label still parses. An unknown label, or a record
that fails validation, sends the page to the LLM fallback instead of guessing.
"""
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from . import normalise as N
from .models import Item

SYNONYMS = {
    "sku": ["item code", "sku", "product code", "code", "item no", "item number"],
    "brand": ["brand", "manufacturer", "maker", "made by"],
    "size": ["size", "paper size", "format", "sheet size"],
    "dims": ["dimensions", "measurements"],
    "weight": ["weight", "basis weight", "paper weight", "grammage"],
    "colour": ["colour", "color", "shade", "paper colour", "paper color"],
    "finish": ["finish", "surface", "coating", "paper finish"],
    "pack": ["sheets per pack", "pack contents", "pack size", "sheets", "pack", "contents"],
    "printing": ["printing", "print", "sides", "print sides"],
    "price": ["price"],
    "volume": ["volume pricing", "volume price", "bulk pricing"],
    "availability": ["availability", "stock", "in stock", "status"],
}
_LABEL = {syn: key for key, syns in SYNONYMS.items() for syn in syns}

# Values in a "Colour" column that describe print colour, not paper colour.
_PRINT_COLOUR = re.compile(r"cmyk|full colou?r|black and white|black & white|mono|greyscale|grayscale|b&w|black only|"
                           r"single colou?r|one colou?r|\b1\s*-?\s*colou?r|^\s*colou?r\s*$", re.I)
_AMT = r"(฿\s*[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s*(?:THB|baht))"
_WAS_NOW = re.compile(r"\bwas\s*:?\s*" + _AMT + r"\W*\bnow\s*:?\s*" + _AMT, re.I)


def label_key(label: str) -> str | None:
    t = re.sub(r"\s+", " ", label.strip().lower()).rstrip(":")
    if t in _LABEL:
        return _LABEL[t]
    if t.startswith("price"):  # "Price per pack of 100"
        return "price"
    return None


@dataclass
class PageResult:
    url: str
    is_product: bool
    items: list[Item] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)  # (sku, text), untrusted
    tier_skus: list[str] = field(default_factory=list)          # data-sku without data-sale
    sale_skus: list[str] = field(default_factory=list)          # data-sale='1': must have a sale price
    errors: list[str] = field(default_factory=list)
    main_text: str = ""


def _text(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _price_from(el: Tag) -> tuple[int | None, int | None]:
    """(list, sale) from a cell/box. <del>/<s>/span.was old</del> new, or "Was old now new" => list=old, sale=new."""
    d = el.find(["del", "s"]) or el.select_one(".was")
    if d:
        list_p = N.money_to_satang(_text(d))
        clone = BeautifulSoup(str(el), "lxml")
        for x in clone.find_all(["del", "s"]) + clone.select(".was, .sale"):
            x.decompose()
        return list_p, N.money_to_satang(_text(clone.select_one(".big") or clone))
    m = _WAS_NOW.search(_text(el))
    if m:
        return N.money_to_satang(m.group(1)), N.money_to_satang(m.group(2))
    big = el.select_one(".big") if el.name != "td" else None
    return N.money_to_satang(_text(big or el)), None


def _stock_from(el: Tag) -> tuple[str, object, str]:
    s = el.find(class_=re.compile(r"^stock"))
    raw = _text(s) if s else _text(el)
    status, back = N.parse_stock(raw, (s.get("class") or [None])[0] if s else None)
    return status, back, raw


def _category(soup: BeautifulSoup, url: str) -> str | None:
    a = soup.select_one("main a[href*='category/']")
    if not a:
        return None
    m = re.search(r"category/([^/]+)/", urljoin(url, a["href"]))
    return m.group(1) if m else None


def _finish_from_title(title: str) -> str | None:
    m = re.search(r"[–—-]\s*([A-Za-z ]+)$", title)
    return m.group(1).strip() if m else None


def parse_page(html: str, url: str, crawled_at: str) -> PageResult:
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main") or soup.body
    notes_el = main.select(".notes") if main else []
    note_texts = [_text(p) for n in notes_el for p in (n.find_all("p") or [n])]
    for n in notes_el:
        n.extract()  # untrusted; never part of what we (or the LLM fallback) parse
    main_text = _text(main)
    tier_skus = [e["data-sku"] for e in main.select("[data-sku]") if e.get("data-sale") != "1"]
    is_product = bool(main.select("[data-sku]") or main.select(".pricebox")
                      or re.search(r"\b(item code|sku)\b", main_text, re.I))
    sale_skus = [e["data-sku"] for e in main.select("[data-sku]") if e.get("data-sale") == "1"]
    res = PageResult(url=url, is_product=is_product, tier_skus=tier_skus, sale_skus=sale_skus, main_text=main_text)
    if not is_product:
        return res

    title = _text(main.find("h1"))
    category = _category(soup, url)
    common = dict(product_url=url, source_url=url, crawled_at=crawled_at, category=category)

    variant_table = None
    for t in main.find_all("table"):
        first = t.find("tr")
        if first and len(first.find_all("th")) > 1 and not first.find("td"):
            variant_table = t
            break

    try:
        if variant_table is not None:
            res.items = _parse_variant_table(variant_table, title, main_text, common, res.errors)
        elif main.select_one("table.specs, dl.specs") or main.find("dl") or main.find("table"):
            res.items = [_parse_spec_block(main, title, common, res.errors)]
        elif main.select_one(".description"):
            res.items = [_parse_prose(main, title, common, res.errors)]
        else:
            res.errors.append("no known layout")
    except Exception as e:  # malformed page: hand it to the fallback, don't crash the run
        res.errors.append(f"parser exception: {e!r}")
        res.items = []

    if not res.items and not res.errors:
        res.errors.append("product page but no items parsed")
    for it in res.items:
        res.errors += [f"{it.sku}: {e}" for e in it.validation_errors()]
    res.notes = [(it.sku, t) for it in res.items for t in note_texts]
    return res


def _parse_variant_table(table: Tag, title: str, page_text: str, common: dict, errors: list) -> list[Item]:
    rows = table.find_all("tr")
    headers = [_text(th) for th in rows[0].find_all("th")]
    keys = [label_key(h) for h in headers]
    for h, k in zip(headers, keys):
        if k is None:
            errors.append(f"unknown column label {h!r}")
    price_header = next((h for h, k in zip(headers, keys) if k == "price"), "")
    pack_unit, sheets = N.parse_pack(price_header)
    if sheets is None:
        pack_unit, sheets = N.parse_pack(page_text)
    size_code, w, h = N.parse_size(title)
    finish_raw = _finish_from_title(title)
    items = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if not cells:
            continue
        v = {}
        for k, td in zip(keys, cells):
            if k:
                v[k] = td
        sku = _text(v.get("sku"))
        price_list, price_sale = _price_from(v["price"]) if "price" in v else (None, None)
        gsm, lb, wsrc = N.parse_weight(_text(v.get("weight")))
        colour_txt = _text(v.get("colour"))
        colour_mode_txt = colour_txt if _PRINT_COLOUR.search(colour_txt or "") else None
        paper_colour_txt = None if colour_mode_txt else (colour_txt or None)
        printing = _text(v.get("printing"))
        status, back, raw = _stock_from(v["availability"]) if "availability" in v else ("unknown", None, None)
        is_print = bool(printing or colour_mode_txt)
        items.append(Item(
            sku=sku, product_name=title,
            product_type="printed_flyer" if is_print else "paper",
            brand=_text(v.get("brand")) or None,
            size_code=size_code, width_mm=w, height_mm=h,
            weight_gsm=gsm, weight_lb_stated=lb, weight_source=wsrc,
            colour=N.parse_colour(paper_colour_txt), colour_raw=paper_colour_txt,
            finish=N.parse_finish(finish_raw), finish_raw=finish_raw,
            sides=N.parse_sides(printing), colour_mode=N.parse_colour_mode(colour_mode_txt),
            pack_unit=pack_unit or "pack", sheets_per_pack=sheets,
            list_price_satang=price_list, sale_price_satang=price_sale,
            stock_status=status, stock_raw=raw, back_in_stock=back, **common,
        ))
    return items


def _spec_pairs(main: Tag) -> list[tuple[str, str]]:
    pairs = []
    for tr in main.select("table tr"):
        th, td = tr.find("th"), tr.find("td")
        if th and td:
            pairs.append((_text(th), _text(td)))
    for dl in main.find_all("dl"):
        for dt in dl.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                pairs.append((_text(dt), _text(dd)))
    return pairs


def _pricebox(main: Tag, common: dict) -> dict:
    box = main.select_one(".pricebox") or main
    list_p, sale_p = _price_from(box)
    status, back, raw = _stock_from(box)
    unit, sheets = N.parse_pack(_text(box))
    if unit is None:
        m = re.search(r"/\s*(ream|pack)\b", _text(box), re.I)
        unit = m.group(1).lower() if m else None
    return dict(list_price_satang=list_p, sale_price_satang=sale_p, stock_status=status,
                back_in_stock=back, stock_raw=raw, _unit=unit, _sheets=sheets)


def _parse_spec_block(main: Tag, title: str, common: dict, errors: list) -> Item:
    v: dict[str, str] = {}
    for label, value in _spec_pairs(main):
        k = label_key(label)
        if k is None:
            errors.append(f"unknown spec label {label!r}")
            continue
        v.setdefault(k, value)
    pb = _pricebox(main, common)
    unit, sheets = pb.pop("_unit"), pb.pop("_sheets")
    _, spec_sheets = N.parse_pack(v.get("pack"))
    size_code, w, h = N.parse_size(v.get("size"), v.get("dims"))
    gsm, lb, wsrc = N.parse_weight(v.get("weight"))
    printing = v.get("printing")
    mode_txt = v.get("colour") if printing and _PRINT_COLOUR.search(v.get("colour") or "") else None
    if mode_txt:
        v.pop("colour")
    return Item(
        sku=v.get("sku", ""), product_name=title,
        product_type="printed_flyer" if printing else "paper",
        brand=v.get("brand"), size_code=size_code, width_mm=w, height_mm=h,
        weight_gsm=gsm, weight_lb_stated=lb, weight_source=wsrc,
        colour=N.parse_colour(v.get("colour")), colour_raw=v.get("colour"),
        finish=N.parse_finish(v.get("finish")), finish_raw=v.get("finish"),
        sides=N.parse_sides(printing), colour_mode=N.parse_colour_mode(mode_txt),
        pack_unit=unit or "pack", sheets_per_pack=spec_sheets or sheets, **pb, **common,
    )


_PROSE = {
    "pack": re.compile(r"supplied as an? ((?:ream|pack|box) of \d+ sheets)", re.I),
    "size": re.compile(r"Each sheet is (.+?) and weighs", re.I),
    "weight": re.compile(r"weighs ([\d.]+\s*(?:gsm|g/m²|g/m2|lb[^.,]*?)(?:\s*\([^)]*\))?)(?=[.,]|\s+and|\s*$)", re.I),
    "colour_finish": re.compile(r"The ([\w\s-]+?) sheets have an? ([\w\s-]+?) (?:surface|finish)", re.I),
    "sku": re.compile(r"(?:Item code|SKU)\s*:\s*([A-Z0-9-]+)", re.I),
    "brand": re.compile(r" from (.+?) is supplied", re.I),
}


def _parse_prose(main: Tag, title: str, common: dict, errors: list) -> Item:
    text = _text(main.select_one(".description"))
    g = {k: rx.search(text) for k, rx in _PROSE.items()}
    pb = _pricebox(main, common)
    unit, sheets = pb.pop("_unit"), pb.pop("_sheets")
    p_unit, p_sheets = N.parse_pack(g["pack"].group(1)) if g["pack"] else (None, None)
    size_code, w, h = N.parse_size(g["size"].group(1) if g["size"] else None)
    gsm, lb, wsrc = N.parse_weight(g["weight"].group(1) if g["weight"] else None)
    colour_raw = g["colour_finish"].group(1) if g["colour_finish"] else None
    finish_raw = g["colour_finish"].group(2) if g["colour_finish"] else None
    return Item(
        sku=g["sku"].group(1) if g["sku"] else "", product_name=title, product_type="paper",
        brand=g["brand"].group(1) if g["brand"] else None,
        size_code=size_code, width_mm=w, height_mm=h,
        weight_gsm=gsm, weight_lb_stated=lb, weight_source=wsrc,
        colour=N.parse_colour(colour_raw), colour_raw=colour_raw,
        finish=N.parse_finish(finish_raw), finish_raw=finish_raw,
        pack_unit=p_unit or unit or "pack", sheets_per_pack=p_sheets or sheets, **pb, **common,
    )


def links(html: str, url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    return [urljoin(url, a["href"]) for a in soup.find_all("a", href=True)]
