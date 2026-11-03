"""Refresh rehearsal: copy the v1 site, apply 5 known mutations, serve it, re-ingest with no code changes.

Pass = the diff report lists exactly those 5 changes and a quote for the discontinued item is refused.
usage: python eval/refresh_rehearsal.py SITE_DIR WORK_DIR [--port 8001]
Needs a promoted v1 snapshot in data/paperlane.db (it is copied, not modified).
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

from pl import db
from pl.diff import change_count
from pl.ingest import run_ingest
from pl.pricing import quote
from pl.search import Criteria, search

EXPECTED = {
    "price": ["PL-CP-A4-70: list 109.00 -> 112.00"],
    "tiers": ["PL-CP-A4-80: tiers [10+: 122.55, 50+: 116.10] -> [10+: 119.90, 50+: 116.10]"],
    "stock": ["PL-CP-A4-75: in_stock -> out_of_stock (back 2026-12-01)", "PL-CS-A4-160-AST: in_stock -> discontinued"],
    "new": ["PL-CP-A4-90-ECO PaperLane Essentials Recycled A4 90gsm @ 139.00 (in_stock)"],
}


def sub(path: Path, old: str, new: str):
    t = path.read_text()
    assert old in t, f"{old!r} not in {path}"
    path.write_text(t.replace(old, new, 1))


def mutate(site: Path):
    p = site / "product"
    sub(p / "pl-cp-a4-70.html", "฿109.00", "฿112.00")                                        # 1 list price
    sub(site / "api/pricing/PL-CP-A4-80.json", "122.55", "119.9")                             # 2 tier
    sub(p / "pl-cp-a4-75.html", '<span class="stock-in">In stock</span>',                    # 3 stock -> out
        '<span class="stock-out">Out of stock &mdash; expected back 1 December 2026</span>')
    new = (p / "pl-cp-a4-80-eco.html").read_text()                                            # 4 new product
    new = (new.replace("PL-CP-A4-80-ECO", "PL-CP-A4-90-ECO").replace("80gsm", "90gsm")
              .replace("80 gsm", "90 gsm").replace("฿125.00", "฿139.00"))
    new = new.replace("<span data-sku='PL-CP-A4-90-ECO'>Loading volume pricing&hellip;</span>", "none")
    (p / "pl-cp-a4-90-eco.html").write_text(new)
    sub(site / "category/copy-paper/page-2.html", "<div class='grid'>",
        "<div class='grid'><div class='card'><h3><a href='../../product/pl-cp-a4-90-eco.html'>"
        "PaperLane Essentials Recycled A4 90gsm</a></h3><div class='price'>฿139.00</div></div>")
    sub(p / "pl-cs-a4-160-ast.html", '<span class="stock-in">In stock</span>',               # 5 discontinued
        '<span class="stock-out">Discontinued</span>')


def mutate_round2(site: Path):
    """Run-level noise: wording change, a dead link, +16 SKUs (>20% swing). Should hold, then promote on accept."""
    sub(site / "product/pl-cp-a4-80-nusa.html", '<span class="stock-in">In stock</span>', '<span class="stock-in">Only 3 left</span>')
    sub(site / "index.html", "<a href=\"delivery.html\">", "<a href=\"promo/black-friday.html\">Sale</a><a href=\"delivery.html\">")
    tpl = (site / "product/pl-cs-a4-200-wh.html").read_text()
    cards = []
    for i in range(16):
        sku = f"PL-CS-A4-{300 + i}-WH"
        page = tpl.replace("PL-CS-A4-200-WH", sku).replace("200gsm", f"{300 + i}gsm").replace("200 gsm", f"{300 + i} gsm")
        page = page.replace("<span data-sku='" + sku + "'>Loading volume pricing&hellip;</span>", "none")
        (site / "product" / f"{sku.lower()}.html").write_text(page)
        cards.append(f"<div class='card'><h3><a href='../../product/{sku.lower()}.html'>Card {300 + i}gsm</a></h3></div>")
    sub(site / "category/card-photo/page-2.html", "<div class='grid'>", "<div class='grid'>" + "".join(cards))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("work")
    ap.add_argument("--port", type=int, default=8001)
    a = ap.parse_args()
    work = Path(a.work)
    if work.exists():
        shutil.rmtree(work)
    site = work / "www" / "paperlane"
    shutil.copytree(a.site, site)
    mutate(site)
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(a.port)], cwd=work / "www",
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://localhost:{a.port}/paperlane/"
        for _ in range(50):
            try:
                httpx.get(base + "index.html", timeout=1)
                break
            except httpx.HTTPError:
                time.sleep(0.2)
        shutil.copy(db.db_path(), work / "rehearsal.db")
        con = db.connect(work / "rehearsal.db")
        res = run_ingest(base, data_dir=work / "data", con=con)
        mutate_round2(site)
        res2 = run_ingest(base, data_dir=work / "data", con=con)
        held_live = db.current_run_id(con)
        db.promote(con, res2.run_id)
    finally:
        srv.terminate()
    _, live = db.load_current(con)
    new16 = [s for s in live if s.startswith("PL-CS-A4-3")]
    r2_ok = (res2.status == "held" and held_live == res.run_id
             and any("dead link" in w for w in res2.warnings) and any("SKU count" in w for w in res2.warnings)
             and live["PL-CP-A4-80-NUSA"].stock_status == "in_stock" and live["PL-CP-A4-80-NUSA"].quotable
             and len(new16) == 16 and all(live[s].quotable for s in new16))

    got = {k: v for k, v in res.changes.items() if v}
    diff_ok = got == EXPECTED and change_count(res.changes) == 5
    q = quote([("PL-CS-A4-160-AST", 2)], res.items)
    refused_ok = not q.lines and q.refused and "discontinued" in q.refused[0]["reason"]
    s = search(Criteria(product_type="paper", paper_kind="card", size="A4", weight_gsm=160, quantity={"value": 2}), res.items)
    offered = [m["sku"] for m in s.get("matches", []) + s.get("alternatives", [])]
    not_offered = "PL-CS-A4-160-AST" not in offered

    out = ["# Refresh rehearsal", "",
           f"Site copy mutated in `{site}` (5 changes), served on port {a.port}, re-ingested with the unchanged code.", "",
           f"- Snapshot status: **{res.status}** (run `{res.run_id}`)",
           f"- Diff lists exactly the 5 planted changes: **{'PASS' if diff_ok else 'FAIL'}**",
           f"- Quote for discontinued PL-CS-A4-160-AST refused: **{'PASS' if refused_ok else 'FAIL'}** ({q.refused})",
           f"- Discontinued item not offered by search (A4 160gsm card): **{'PASS' if not_offered else 'FAIL'}** (offered: {offered})",
           "", "## Round 2: 'Only 3 left' wording, a dead link, +16 SKUs",
           f"- First ingest status: **{res2.status}** (previous snapshot still live: {held_live == res.run_id}); "
           f"warnings: {res2.warnings}",
           f"- After `pl promote {res2.run_id}`: 'Only 3 left' item in stock and quotable, 16 new SKUs quotable: "
           f"**{'PASS' if r2_ok else 'FAIL'}** ({len(live)} SKUs live)",
           "", "## Expected", "", "```", *[f"{k}: {v}" for k, v in EXPECTED.items()], "```",
           "", "## Ingest report produced by the pipeline", "", res.report]
    Path("eval/refresh_rehearsal.md").write_text("\n".join(out) + "\n")
    print("\n".join(out[:12]))
    sys.exit(0 if res.status == "promoted" and diff_ok and refused_ok and not_offered and r2_ok else 1)


if __name__ == "__main__":
    main()
