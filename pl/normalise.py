"""Turn the site's free-text attribute values into typed, comparable fields.

Every function takes the raw string and returns the normalised value (or None when the
text does not say). The raw string is kept next to the value in the DB so each mapping
can be audited.
"""
import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

# Customer's agreed table (brief, "Weights"). Not a physics conversion: 20 lb bond is
# ~75.2 gsm, but PaperLane quotes these four values, so we use exactly these.
LB_TO_GSM = {20: 75, 24: 90, 28: 105, 32: 120}

# Canonical sizes in mm (portrait). Letter/Legal are rounded from inches.
SIZES = {
    "A3": (297, 420),
    "A4": (210, 297),
    "A5": (148, 210),
    "LETTER": (216, 279),
    "LEGAL": (216, 356),
}

_SIZE_WORDS = [
    (re.compile(r"\bA[-\s]?3\b", re.I), "A3"),
    (re.compile(r"\bA[-\s]?4\b", re.I), "A4"),
    (re.compile(r"\bA[-\s]?5\b", re.I), "A5"),
    (re.compile(r"\blegal\b", re.I), "LEGAL"),
    (re.compile(r"\bletter\b", re.I), "LETTER"),
]

_D = r"(\d+(?:\.\d+)?|\d*½)"
_U = r"(mm|cm|in\b|inch|inches|\"|'')?"
_DIMS = re.compile(_D + r"\s*" + _U + r"\s*(?:[×x*]|by)\s*" + _D + r"\s*" + _U, re.I)
_HALF = re.compile(r"(\d+)[\s-]+1/2\b")   # "8 1/2" / "8-1/2" -> "8.5"


def _num(s: str) -> float:
    s = s.strip()
    if s.endswith("½"):
        return float(s[:-1] or 0) + 0.5
    return float(s)


def parse_dims(text: str | None) -> tuple[int, int] | None:
    """'210 × 297 mm' -> (210, 297); '8.5 × 11 in' -> (216, 279). Returns portrait (w<=h)."""
    if not text:
        return None
    m = _DIMS.search(_HALF.sub(lambda h: h.group(1) + ".5", text))
    if not m:
        return None
    a, b, unit = _num(m.group(1)), _num(m.group(3)), (m.group(4) or m.group(2) or "").lower()
    if unit in ("in", "inch", "inches", '"', "''") or (not unit and max(a, b) < 30):
        a, b = a * 25.4, b * 25.4
    elif unit == "cm":
        a, b = a * 10, b * 10
    w, h = sorted((int(Decimal(a).quantize(0, ROUND_HALF_UP)), int(Decimal(b).quantize(0, ROUND_HALF_UP))))
    return w, h


def size_from_dims(dims: tuple[int, int] | None) -> str | None:
    if not dims:
        return None
    for code, (w, h) in SIZES.items():
        if abs(dims[0] - w) <= 2 and abs(dims[1] - h) <= 2:
            return code
    return "OTHER"


def parse_size(text: str | None, dims_text: str | None = None) -> tuple[str | None, int | None, int | None]:
    """Returns (size_code, width_mm, height_mm). Named size wins; dimensions fill mm and back it up."""
    dims = parse_dims(text) or parse_dims(dims_text)
    code = None
    for rx, c in _SIZE_WORDS:
        if text and rx.search(text):
            code = c
            break
    if code is None:
        code = size_from_dims(dims)
    if code and code != "OTHER" and not dims:
        dims = SIZES[code]
    return code, (dims[0] if dims else None), (dims[1] if dims else None)


_GSM = re.compile(r"(\d+(?:\.\d+)?)\s*(?:gsm|g/m²|g/m2|g\s*/\s*m2|g/sqm)", re.I)
_LB = re.compile(r"(\d+)\s*(?:lb|lbs|#)\b", re.I)


def parse_weight(text: str | None) -> tuple[int | None, int | None, str | None]:
    """Returns (weight_gsm, weight_lb_stated, weight_source).

    '24 lb (90 gsm)' -> (90, 24, 'stated'); '20 lb bond' -> (75, 20, 'converted_from_lb');
    an lb value outside the customer's table -> (None, lb, None) so validation flags it.
    """
    if not text:
        return None, None, None
    g = _GSM.search(text)
    lb = _LB.search(text)
    lb_val = int(lb.group(1)) if lb else None
    if g:
        return int(Decimal(g.group(1)).quantize(0, ROUND_HALF_UP)), lb_val, "stated"
    if lb_val is not None:
        gsm = LB_TO_GSM.get(lb_val)
        return gsm, lb_val, ("converted_from_lb" if gsm else None)
    return None, None, None


_MONEY_CCY = re.compile(r"(?:฿\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?)|(?:(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(?:THB|Baht))", re.I)
_MONEY = re.compile(r"(?:฿|THB|Baht)?\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(?:THB|Baht|฿)?", re.I)


def money_to_satang(text: str | float | Decimal | None) -> int | None:
    """'฿1,234.50' / '1234.50 THB' / 98.1 -> integer satang (123450). Half-up on stray 3rd decimal."""
    if text is None:
        return None
    if isinstance(text, (int, float, Decimal)):
        return int((Decimal(str(text)) * 100).quantize(0, ROUND_HALF_UP))
    m = _MONEY_CCY.search(text) or _MONEY.search(text)
    if not m:
        return None
    g = [x for x in m.groups()]
    whole, frac = (g[0], g[1]) if g[0] is not None else (g[2], g[3])
    whole = whole.replace(",", "")
    frac = (frac or "0").ljust(2, "0")
    return int(whole) * 100 + int(frac)


def satang_to_str(v: int) -> str:
    sign = "-" if v < 0 else ""
    v = abs(v)
    return f"{sign}{v // 100:,}.{v % 100:02d}"


_COLOUR_FAMILIES = ["white", "ivory", "cream", "black", "red", "pink", "yellow", "blue", "green",
                    "orange", "purple", "grey", "gray", "brown", "gold", "silver"]


def parse_colour(text: str | None) -> str | None:
    """Paper colour family: 'Bright white' -> white, 'Pastel pink' -> pink, 'Assorted brights' -> assorted."""
    if not text:
        return None
    t = text.lower()
    if "assorted" in t or "mixed" in t or "rainbow" in t:
        return "assorted"
    hits = [(t.rfind(c), c) for c in _COLOUR_FAMILIES if re.search(rf"\b{c}\b", t)]
    if not hits:
        return t.strip()
    c = max(hits)[1]
    return "grey" if c == "gray" else c


def parse_finish(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower()
    for key, val in [("gloss", "gloss"), ("matt", "matte"), ("silk", "silk"), ("satin", "silk"),
                     ("laid", "laid"), ("uncoated", "uncoated"), ("smooth", "smooth"), ("linen", "linen")]:
        if key in t:
            return val
    return t.strip()


def parse_sides(text: str | None) -> int | None:
    if not text:
        return None
    t = text.lower().strip()
    if t in ("1", "one", "single", "front", "front only"):
        return 1
    if t in ("2", "two", "both", "double"):
        return 2
    if re.search(r"double|both sides|two.sided|\b2\s*-?\s*sided|\b2 sides|front (?:&|and) back|duplex|4/4|1/1", t):
        return 2
    if re.search(r"single|one side|one.sided|\b1\s*-?\s*sided|\b1 side\b|simplex|4/0|1/0", t):
        return 1
    return None


def parse_colour_mode(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower()
    if re.search(r"black and white|black & white|b&w|b/w|mono|greyscale|grayscale|black only|"
                 r"single colou?r|one colou?r|\b1\s*-?\s*colou?r", t):
        return "bw"
    if re.search(r"cmyk|full colou?r|colou?r", t):
        return "cmyk"
    return None


_PACK = re.compile(r"(ream|pack|box|sleeve)\s+of\s+(\d+)", re.I)


def parse_pack(text: str | None) -> tuple[str | None, int | None]:
    """'per ream of 500 sheets' -> ('ream', 500); '500 sheets' -> (None, 500)."""
    if not text:
        return None, None
    m = _PACK.search(text)
    if m:
        unit = m.group(1).lower()
        return ("ream" if unit == "ream" else "pack"), int(m.group(2))
    m = re.search(r"(\d+)\s*(?:sheets)?", text)
    return None, (int(m.group(1)) if m else None)


def parse_stock(text: str | None, css_class: str | None = None) -> tuple[str, date | None]:
    """Returns (stock_status, back_in_stock). Anything not recognised is 'unknown' and gets flagged."""
    t = (text or "").lower()
    back = None
    m = re.search(r"(?:expected back|back in stock|available from|restock(?:ed)?)\s*(?:on\s*)?(\d{1,2} \w+ \d{4})", t)
    if m:
        try:
            back = datetime.strptime(m.group(1), "%d %B %Y").date()
        except ValueError:
            back = None
    if "discontinued" in t or "no longer" in t:
        return "discontinued", None
    if re.search(r"out of stock|sold out|not available|unavailable|back ?order", t) or css_class == "stock-out":
        return "out_of_stock", back
    if back is None and (css_class == "stock-in" or re.search(
            r"\bin stock\b|low stock|limited stock|only \d+ left|\d+ left|few left|last \d+|ready to ship|^\s*available\s*\.?$", t)):
        return "in_stock", None
    return "unknown", back
