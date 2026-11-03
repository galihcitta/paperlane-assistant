from fastapi.testclient import TestClient

from conftest import BASE, SITE, FileFetcher
from pl.ingest import run_ingest


def test_quote_and_items(monkeypatch, tmp_path):
    monkeypatch.setenv("PL_DB", str(tmp_path / "api.db"))
    from pl import db
    run_ingest(BASE, data_dir=tmp_path, con=db.connect(), log=lambda *_: None, fetcher=FileFetcher(SITE))
    from pl.api import app
    c = TestClient(app)
    r = c.post("/quote", json={"lines": [{"sku": "PL-PR-A4-MT-100-40", "qty_packs": 16}]}).json()
    assert r["total_incl_vat"] == "3,299.02" and r["delivery"] == "0.00"
    assert c.post("/quote", json={"lines": [{"sku": "PL-CP-A4-70", "qty_packs": 0}]}).status_code == 422
    assert c.get("/items").json()["count"] == 72
    assert "PaperLane" in c.get("/").text
