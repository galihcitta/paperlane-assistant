"""Live LLM-fallback exercise: one product page rewritten into a layout the parser doesn't know.

usage (needs ANTHROPIC_API_KEY): mkdir -p W/www && cp -R ../paperlane W/www/ && cp data/paperlane.db W/fb.db
       python eval/llm_fallback_run.py W
"""
import json, subprocess, sys, time
from pathlib import Path
import httpx
from pl import db
from pl.ingest import run_ingest
work = Path(sys.argv[1]); page = work / "www/paperlane/product/pl-cp-a4-70.html"
t = page.read_text()
old = t[t.index("<table class='specs'>"):t.index("</table>") + len("</table>")]
new = ("<ul class='facts'><li>Product reference &mdash; PL-CP-A4-70</li><li>Made by: Siam Office</li>"
       "<li>Sheet format &mdash; A4, 210 by 297 millimetres</li><li>Grammage &mdash; 70 g/m&sup2;</li>"
       "<li>Shade &mdash; bright white</li><li>Surface &mdash; uncoated</li><li>Contents &mdash; 500 sheets</li></ul>")
page.write_text(t.replace(old, new))
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8002"], cwd=work / "www", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try: httpx.get("http://localhost:8002/paperlane/index.html", timeout=1); break
        except httpx.HTTPError: time.sleep(0.2)
    con = db.connect(work / "fb.db")
    res = run_ingest("http://localhost:8002/paperlane/", data_dir=work / "data", con=con, log=lambda *_: None)
finally:
    srv.terminate()
it = res.items["PL-CP-A4-70"]
print("status", res.status, "| changes", {k: v for k, v in res.changes.items() if v})
print(json.dumps(it.model_dump(mode="json", include={"sku","extraction","product_name","brand","size_code","weight_gsm","colour","finish","sheets_per_pack","pack_unit","list_price_satang","stock_status","tiers","quotable","quarantine_reason"}), ensure_ascii=False))
print(res.report.split("## ")[0][-600:])
