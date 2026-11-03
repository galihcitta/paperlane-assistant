import json
from decimal import Decimal
from types import SimpleNamespace

from pl import agent as agent_mod
from pl.replycheck import check, money_figures


def test_figures_detected():
    assert [str(x) for x in money_figures("Total ฿4,237.20, unit 198.00 THB, 20 packs, 7% VAT, 3000 baht")] == \
        ["4237.20", "198.00", "3000"]


def test_check_flags_invented_price_and_sku():
    src = [json.dumps({"total": "4,237.20", "sku": "PL-PR-LTR-MT-100-40"})]
    assert check("PL-PR-LTR-MT-100-40 costs ฿4,237.20, under your ฿250 limit", src, "under 250 a pack") == []
    probs = check("Total ฿4,200.00 for PL-PR-LTR-XX-1", src)
    assert len(probs) == 2


_Q = {"lines": [{"sku": "PL-CP-A3-80", "product_name": "Copy A3", "unit_price": "289.00", "line_total": "1,445.00"}],
      "subtotal": "1,445.00", "delivery": "0.00", "vat_7pct": "101.15", "total_incl_vat": "1,546.15"}
_S = {"matches": [{"sku": "PL-CL-A3-80-PBL", "unit_price": "450.00", "line_total": "2,250.00"}], "best_quote": _Q}


def test_stated_total_must_equal_quote_total():
    res = [json.dumps(_S)]
    assert check("PL-CP-A3-80 x 5 @ 289.00 = 1,445.00\nVAT 7% 101.15\nTotal (incl. 7% VAT): ฿1,546.15", res) == []
    probs = check("PL-CP-A3-80 x 5 @ 289.00\nTotal: ฿2,250.00", res)    # a real figure, but not the quote's total
    assert any("stated total 2250.00" in p for p in probs)


def test_price_must_belong_to_its_sku():
    probs = check("PL-CP-A3-80: 450.00 per ream", [json.dumps(_S)])
    assert probs == ["450.00 is stated for PL-CP-A3-80 but is not that SKU's figure"]


def test_thai_baht_and_bare_amounts():
    assert money_figures("รวม 1546 บาท, 500 sheets, 80 gsm, 1200") == [Decimal("1546"), Decimal("1200")]
    assert check("Total 1546 บาท", [json.dumps(_S)])                    # 1546 is not 1546.15
    assert check("about 1,500 for 5 reams", [json.dumps(_S)])


def test_only_this_turns_results_and_known_names():
    assert check("PL-CP-A3-80 is ฿289.00", []) != []                     # no tool ran this turn
    probs = check("Try Lotus Bright Premium A4 80gsm", [json.dumps(_S)], catalog_names=["Lotus Bright Premium A4 80gsm"])
    assert probs and "Lotus Bright" in probs[0]


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


def test_chat_from_two_threads(monkeypatch, tmp_path):
    import threading
    from conftest import BASE, SITE, FileFetcher
    from pl import db
    from pl.ingest import run_ingest
    con = db.connect(tmp_path / "a.db")
    run_ingest(BASE, data_dir=tmp_path, con=con, log=lambda *_: None, fetcher=FileFetcher(SITE))
    fake = FakeClient([_resp([_text("Hello")], "end_turn") for _ in range(20)])
    monkeypatch.setattr(agent_mod.llm, "client", lambda: fake)
    monkeypatch.setattr(agent_mod, "LOG_PATH", tmp_path / "log.jsonl")
    a = agent_mod.Agent(con=con)     # created on this thread, used from others (as under uvicorn)
    errors = []

    def go(i):
        try:
            for _ in range(5):
                assert a.chat(f"s{i}", "hi")["reply"] == "Hello"
        except Exception as e:
            errors.append(e)
    ts = [threading.Thread(target=go, args=(i,)) for i in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert errors == []
