import re

from conftest import BASE, SITE, FileFetcher
from pl.ingest import run_ingest
from pl.parse import parse_page


def _independent_sku_count():
    # Count item codes straight from the HTML source, without the parser.
    skus = set()
    for f in (SITE / "product").glob("*.html"):
        t = f.read_text()
        skus |= set(re.findall(r"<td>(PL-[A-Z0-9-]+)</td>", t))
        skus |= set(re.findall(r"<dd>(PL-[A-Z0-9-]+)</dd>", t))
        skus |= set(re.findall(r"Item code: (PL-[A-Z0-9-]+)", t))
    return len(skus)


def test_v1_complete(v1_items):
    assert len(v1_items) == _independent_sku_count() == 72
    assert all(not it.missing_required() for it in v1_items.values())
    with_tiers = {s for s, it in v1_items.items() if it.tiers}
    assert with_tiers == {p.stem for p in (SITE / "api" / "pricing").glob("*.json")}


def test_traps(v1_items):
    ltr24 = v1_items["PL-CP-LTR-24"]          # bare "24 lb"
    assert (ltr24.weight_gsm, ltr24.weight_source, ltr24.weight_lb_stated) == (90, "converted_from_lb", 24)
    lgl = v1_items["PL-CP-LGL-20"]            # "20 lb bond"
    assert (lgl.weight_gsm, lgl.size_code, lgl.width_mm, lgl.height_mm) == (75, "LEGAL", 216, 356)
    sale = v1_items["PL-PR-LTR-GL-170-40"]
    assert (sale.list_price_satang, sale.sale_price_satang, sale.tiers) == (29900, 25900, [])
    ivy = v1_items["PL-CL-A4-100-IVY"]
    assert ivy.stock_status == "out_of_stock" and str(ivy.back_in_stock) == "2026-11-20"
    a4 = v1_items["PL-CP-A4-70"]
    assert [(t.min_qty, t.unit_price_satang) for t in a4.tiers] == [(10, 10464), (50, 9810)]
    fl = v1_items["PL-PR-LTR-MT-100-40"]
    assert (fl.product_type, fl.sides, fl.colour_mode, fl.finish, fl.sheets_per_pack, fl.size_code) == \
        ("printed_flyer", 1, "cmyk", "matte", 100, "LETTER")
    assert v1_items["PL-PR-A4-MT-100-11"].colour_mode == "bw"
    assert v1_items["PL-CP-LTR-90-NUSA"].weight_gsm == 90   # "90 g/m²" in prose layout


def test_notes_are_quarantined():
    html = (SITE / "product" / "pl-ph-a4-230-mt.html").read_text()
    r = parse_page(html, "u", "t")
    assert any("AI shopping assistants" in t for _, t in r.notes)
    assert "AI shopping assistants" not in r.main_text      # never reaches parsers or the LLM fallback


def test_unknown_label_goes_to_fallback():
    html = (SITE / "product" / "pl-cp-a4-70.html").read_text().replace("<th>Finish</th>", "<th>Coating type</th>")
    r = parse_page(html, "u", "t")
    assert any("unknown spec label" in e for e in r.errors)


def test_relabelled_columns_still_parse():
    html = (SITE / "product" / "flyers-a4-matte.html").read_text()
    html = html.replace("<th>Paper weight</th>", "<th>Grammage</th>").replace("<th>Availability</th>", "<th>Stock</th>")
    r = parse_page(html, "u", "t")
    assert not r.errors and len(r.items) == 8


def _ingest(site, con, tmp_path, **kw):
    return run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(site), **kw)


def _edit(path, old, new):
    t = path.read_text()
    assert old in t
    path.write_text(t.replace(old, new))


def test_count_swing_and_dead_link_hold_until_accepted(site_copy, con, tmp_path):
    from pl import db
    first = _ingest(site_copy, con, tmp_path)
    for f in list((site_copy / "product").glob("pl-c*.html")):   # drop most single-SKU pages (> 20% swing)
        f.unlink()
    held = _ingest(site_copy, con, tmp_path)
    assert held.status == "held" and db.current_run_id(con) == first.run_id
    assert any("SKU count" in w for w in held.warnings) and any("dead link" in w for w in held.warnings)
    accepted = _ingest(site_copy, con, tmp_path, accept=True)
    assert accepted.status == "promoted" and db.current_run_id(con) == accepted.run_id
    db.promote(con, held.run_id)                                  # `pl promote` path
    assert db.current_run_id(con) == held.run_id


def test_bad_sku_quarantined_rest_promoted(site_copy, con, tmp_path):
    _ingest(site_copy, con, tmp_path)
    _edit(site_copy / "api/pricing/PL-CP-A4-70.json", '"vat_included": false', '"vat_included": true')
    _edit(site_copy / "api/pricing/PL-CP-A4-80.json", "122.55", "999.0")          # tier above list price
    _edit(site_copy / "product/pl-cp-a5-80.html", '<span class="stock-in">In stock</span>', "<span>Ask us</span>")  # unknown
    res = _ingest(site_copy, con, tmp_path)
    assert res.status == "promoted"
    assert set(res.quarantined) == {"PL-CP-A4-70", "PL-CP-A4-80", "PL-CP-A5-80"}
    assert "vat_included" in res.quarantined["PL-CP-A4-70"]
    assert sum(it.quotable for it in res.items.values()) == 69
    from pl.pricing import quote
    q = quote([("PL-CP-A4-70", 10)], res.items)
    assert not q.lines and "not quotable" in q.refused[0]["reason"]
    assert "NOT quotable" in res.report


def test_unparseable_page_keeps_last_known_rows_unquotable(site_copy, con, tmp_path):
    _ingest(site_copy, con, tmp_path)
    _edit(site_copy / "product/flyers-a5-matte.html", "<th>Printing</th>", "<th>Print process</th>")
    res = _ingest(site_copy, con, tmp_path)                       # no API key -> no LLM fallback
    assert res.status == "promoted" and len(res.items) == 72
    a5 = [s for s in res.quarantined if s.startswith("PL-PR-A5-MT")]
    assert len(a5) == 8 and all("failed to parse" in res.quarantined[s] for s in a5)


def test_low_stock_wording_is_in_stock(site_copy, con, tmp_path):
    _edit(site_copy / "product/pl-cp-a4-75.html", '<span class="stock-in">In stock</span>', '<span class="stock-in">Low stock</span>')
    _edit(site_copy / "product/pl-cp-a4-70.html", '<span class="stock-in">In stock</span>', '<span class="stock-in">Only 3 left</span>')
    res = _ingest(site_copy, con, tmp_path)
    assert res.items["PL-CP-A4-75"].stock_status == res.items["PL-CP-A4-70"].stock_status == "in_stock"
    from pl.normalise import parse_stock
    assert parse_stock("Only 3 left")[0] == "in_stock"          # LLM fallback path has no CSS class


def test_rejected_only_when_nothing_usable(site_copy, con, tmp_path):
    for f in (site_copy / "product").glob("*.html"):
        f.write_text("<html><body><main><h1>Moved</h1><div class='pricebox'>See our new shop</div></main></body></html>")
    res = _ingest(site_copy, con, tmp_path)
    assert res.status == "rejected"


def test_diff_detects_changes(site_copy, con, tmp_path):
    run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(site_copy))
    p = site_copy / "product" / "pl-cp-a4-70.html"
    p.write_text(p.read_text().replace("฿109.00", "฿112.00"))
    res = run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(site_copy))
    assert res.status == "promoted"
    assert res.changes["price"] == ["PL-CP-A4-70: list 109.00 -> 112.00"]
    assert sum(len(v) for v in res.changes.values()) == 1


def test_print_wordings():
    from pl.normalise import parse_colour_mode, parse_sides
    assert [parse_sides(t) for t in ["1-sided", "2-sided", "1 side", "Front & back", "front and back"]] == [1, 2, 1, 2, 2]
    assert [parse_colour_mode(t) for t in ["Colour", "Black only", "Single colour (black)", "1 colour"]] == \
        ["cmyk", "bw", "bw", "bw"]


def test_sale_markups_detected():
    from bs4 import BeautifulSoup
    from pl.parse import _price_from
    for html in ["<td><s>฿299.00</s> ฿259.00</td>", "<td><span class='was'>฿299.00</span> ฿259.00</td>",
                 "<td>Was ฿299.00, now ฿259.00</td>"]:
        assert _price_from(BeautifulSoup(html, "lxml").td) == (29900, 25900), html


def test_flyer_without_sides_quarantined(site_copy, con, tmp_path):
    p = site_copy / "product/flyers-ltr-gloss.html"
    _edit(p, "<td>Single-sided</td><td>Full colour (CMYK)</td><td>฿235.00</td>", "<td></td><td>Full colour (CMYK)</td><td>฿235.00</td>")
    res = _ingest(site_copy, con, tmp_path)
    assert res.status == "promoted" and "missing sides" in res.quarantined["PL-PR-LTR-GL-100-40"]
    assert res.items["PL-PR-LTR-MT-100-40"].quotable     # other pages unaffected (this page goes to the fallback)


def test_sale_flag_without_sale_price_quarantined(site_copy, con, tmp_path):
    _edit(site_copy / "product/flyers-ltr-gloss.html", "<del>฿299.00</del> ฿259.00<span class='sale'>Sale</span>", "฿299.00")
    res = _ingest(site_copy, con, tmp_path)
    assert "no sale price" in res.quarantined["PL-PR-LTR-GL-170-40"]


def test_tier_coverage_drop_quarantines_affected_skus(site_copy, con, tmp_path):
    assert _ingest(site_copy, con, tmp_path).status == "promoted"
    for f in (site_copy / "product").glob("*.html"):     # tier placeholders gone, e.g. endpoint renamed in JS
        f.write_text(f.read_text().replace("data-sku=", "data-item="))
    res = _ingest(site_copy, con, tmp_path)
    hit = [s for s, r in res.quarantined.items() if "volume pricing missing" in r]
    assert len(hit) == 59 and res.items["PL-CP-A4-70"].quotable is False
