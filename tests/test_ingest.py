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


def test_reject_keeps_previous_snapshot(site_copy, con, tmp_path):
    first = run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(site_copy))
    for f in list((site_copy / "product").glob("pl-c*.html")):   # remove most single-SKU pages
        f.unlink()
    second = run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(site_copy))
    assert second.status == "rejected"
    from pl import db
    assert db.current_run_id(con) == first.run_id


def test_diff_detects_changes(site_copy, con, tmp_path):
    run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(site_copy))
    p = site_copy / "product" / "pl-cp-a4-70.html"
    p.write_text(p.read_text().replace("฿109.00", "฿112.00"))
    res = run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(site_copy))
    assert res.status == "promoted"
    assert res.changes["price"] == ["PL-CP-A4-70: list 109.00 -> 112.00"]
    assert sum(len(v) for v in res.changes.values()) == 1
