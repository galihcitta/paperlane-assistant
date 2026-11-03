import json
from types import SimpleNamespace

from pl import agent as agent_mod
from pl.replycheck import check, money_figures


def test_figures_detected():
    assert [str(x) for x in money_figures("Total ฿4,237.20, unit 198.00 THB, 20 packs, 7% VAT, 3000 baht")] == \
        ["4237.20", "198.00", "3000"]


def test_check_flags_invented_price_and_sku():
    src = [json.dumps({"total": "4,237.20", "sku": "PL-PR-LTR-MT-100-40"}), "under 250 a pack"]
    assert check("PL-PR-LTR-MT-100-40 costs ฿4,237.20, under your ฿250 limit", src) == []
    probs = check("Total ฿4,200.00 for PL-PR-LTR-XX-1", src)
    assert len(probs) == 2


class FakeClient:
    """Scripted stand-in for the Anthropic client to test the loop's guard rails (not model quality)."""

    def __init__(self, script):
        self.script = list(script)
        self.messages = self
        self.beta = SimpleNamespace(messages=self)

    def create(self, **kw):
        return self.script.pop(0)


def _resp(blocks, stop):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage)


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool(name, inp):
    return SimpleNamespace(type="tool_use", id="t1", name=name, input=inp)


def test_bad_figures_regenerate_then_template(monkeypatch, tmp_path, v1_items):
    from conftest import BASE, SITE, FileFetcher
    from pl import db
    from pl.ingest import run_ingest
    con = db.connect(tmp_path / "a.db")
    run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(SITE))
    crit = {"product_type": "printed_flyer", "size": "letter", "sides": "one side", "colour_mode": "colour",
            "max_unit_price": 250, "quantity": {"value": 20}}
    fake = FakeClient([_resp([_tool("search_products", crit)], "tool_use"),
                       _resp([_text("Best: ฿4,000.00 total")], "end_turn"),
                       _resp([_text("Sorry, ฿3,999.99 then")], "end_turn")])
    monkeypatch.setattr(agent_mod.llm, "client", lambda: fake)
    monkeypatch.setattr(agent_mod, "LOG_PATH", tmp_path / "log.jsonl")
    a = agent_mod.Agent(con=con)
    out = a.chat("s1", "letter flyers one side colour under 250, 20 packs")
    assert out["regenerated"] and out["template_used"] and not out["reply_check_passed"]
    assert "4,237.20" in out["reply"] and "PL-PR-LTR-MT-100-40" in out["reply"]
    assert out["decision"] == "matches"
    assert json.loads((tmp_path / "log.jsonl").read_text().splitlines()[-1])["template_used"] is True


def test_quote_tool_sheets_and_delivery(monkeypatch, tmp_path):
    from conftest import BASE, SITE, FileFetcher
    from pl import db
    from pl.ingest import run_ingest
    con = db.connect(tmp_path / "q.db")
    run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(SITE))
    a = agent_mod.Agent(con=con)
    s = agent_mod.Session()
    turn = {"decision": None, "criteria": {}, "skus": [], "quote": None, "last_search": None, "delivery_area": None}
    out, err = a._run_tool(s, "quote", {"lines": [{"sku": "PL-CP-A4-70", "qty_sheets": 1200}],
                                        "delivery_location": "Chiang Mai"}, turn)
    assert not err and out["lines"][0]["qty_packs"] == 3 and out["total_incl_vat"] == "510.39"
    assert "rounded up to 3 reams" in out["rounding_notes"][0]
    assert out["delivery_area"]["in_service_area"] is False and turn["delivery_area"] == out["delivery_area"]
