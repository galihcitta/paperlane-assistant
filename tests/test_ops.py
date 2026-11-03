import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from conftest import SITE
from pl import ops
from pl.trace import mask

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def _rec(i, **kw):
    r = {"request_id": f"req_{i:02d}", "ts": f"2026-11-04T10:{i:02d}:00+00:00", "traffic": "live",
         "session_id": f"s{i % 8}", "message": f"msg {i}", "decision": "matches", "latency_ms": (i + 1) * 1000,
         "est_cost_usd": 0.01, "regenerated": False, "template_used": False, "reply_check_passed": True,
         "check_problems": [[]], "reply": "ok", "criteria": {}, "spans": [], "skus": [], "total": None,
         "quote_lines": [], "snapshot": "v1", "error": None}
    return r | kw


def fixture_log() -> list[dict]:
    """20 requests, 8 conversations. Hand-computed expectations in test_fixture_metrics."""
    recs = [_rec(i) for i in range(20)]
    for i in (3, 7):
        recs[i] |= {"regenerated": True}
    recs[11] |= {"regenerated": True, "template_used": True, "reply_check_passed": False,
                 "check_problems": [["stated total 9.00 does not match the quote (8.00)"], ["empty reply"]]}
    for i in (1, 2, 5, 9):
        recs[i]["decision"] = "needs_clarification"
    for i in (4, 13, 17):
        recs[i]["decision"] = "no_exact_match"
    recs[19]["decision"] = "not_sold"
    for i in (0, 6, 12, 18):
        recs[i]["est_cost_usd"] = 0.02
    return recs


def test_fixture_metrics():
    m = ops.traffic_metrics(fixture_log())
    assert m["requests"] == 20 and m["conversations"] == 8
    assert m["check_fail_rate"] == 15.0          # 3 of 20 needed a rewrite
    assert m["template_rate"] == 5.0             # 1 of 20
    assert m["decision_mix"] == {"matches": 12, "needs_clarification": 4, "no_exact_match": 3, "not_sold": 1}
    assert (m["no_match_share"], m["not_sold_share"]) == (15.0, 5.0)
    assert (m["p50_latency_s"], m["p95_latency_s"]) == (10.0, 19.0)   # nearest rank over 1..20 s
    assert m["total_cost_usd"] == 0.24 and m["cost_per_conversation_usd"] == 0.03   # 16*0.01 + 4*0.02, / 8
    assert [ops.status(k, m[k]) for k in ("check_fail_rate", "template_rate", "p50_latency_s", "p95_latency_s",
                                          "cost_per_conversation_usd", "no_match_share", "not_sold_share")] == \
        ["alert", "alert", "alert", "alert", "ok", "ok", "ok"]


def _db(con, tmp_path, held: bool, age_days: int):
    rp = tmp_path / "report.md"
    rp.write_text("# Ingest report\n\n## Warnings (hold promotion until accepted)\n\n- dead link: http://x/promo.html: HTTP 404\n\n## Changes\n")
    old = f"2026-11-{4 - age_days:02d}T09:00:00+00:00" if age_days < 4 else "2026-10-25T09:00:00+00:00"
    con.execute("INSERT INTO runs (run_id, status, finished_at, promoted_at, report_path) VALUES (?,?,?,?,?)",
                ("r1", "promoted", old, old, ""))
    con.execute("INSERT INTO runs (run_id, status, finished_at, promoted_at, report_path) VALUES (?,?,?,?,?)",
                ("r2", "held" if held else "promoted", "2026-11-04T09:00:00+00:00",
                 None if held else "2026-11-04T09:00:00+00:00", str(rp)))
    con.commit()


def _page(tmp_path, con, recs, site=None):
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    d = ops.gather(log, con, tmp_path / "none.json", site_dir=site or SITE, now=NOW)
    return d, ops.render(d)


def _status(page: str, key: str) -> str:
    return page.split(f'data-metric="{key}" data-status="')[1].split('"')[0]


def test_healthy_page_is_green(con, tmp_path):
    _db(con, tmp_path, held=False, age_days=1)
    recs = [_rec(i, total="1,280.15", quote_lines=[["PL-CP-A4-70", 10]]) for i in range(3)]
    d, page = _page(tmp_path, con, recs)
    for k in ("template_rate", "check_fail_rate", "catalog_age_days", "last_ingest_not_promoted", "price_drift"):
        assert _status(page, k) == "ok", k


def test_injected_faults_turn_the_right_panel_red(con, tmp_path):
    _db(con, tmp_path, held=True, age_days=10)                     # held refresh + stale live snapshot
    site = tmp_path / "site"
    shutil.copytree(SITE, site)
    p = site / "api/pricing/PL-CP-A4-70.json"                       # drifted price: tier 10 104.64 -> 110.00
    p.write_text(p.read_text().replace("104.64", "110.00"))
    recs = [_rec(i) for i in range(10)]
    recs[4] |= {"regenerated": True, "template_used": True, "reply_check_passed": False,
                "check_problems": [["stated total 2407.50 does not match the quote (1546.15)"], ["empty reply"]]}
    recs[6] |= {"total": "1,280.15", "quote_lines": [["PL-CP-A4-70", 10]]}
    d, page = _page(tmp_path, con, recs, site)
    assert _status(page, "template_rate") == "alert"
    assert _status(page, "catalog_age_days") == "alert" and d["catalog"]["catalog_age_days"] == 10.1
    assert _status(page, "last_ingest_not_promoted") == "alert" and "dead link" in page
    assert _status(page, "price_drift") == "alert"
    assert d["drift"]["drifted"][0]["request_id"] == "req_06" and d["drift"]["drifted"][0]["now"] != "1280.15"
    t = ops.render_trace(recs, "req_04")                            # the cause is visible in the trace
    assert "template reply sent" in t and "stated total 2407.50" in t


def test_export_case_is_valid_eval_yaml():
    recs = fixture_log()
    case = yaml.safe_load(ops.export_case(recs, "req_08", expect="no_exact_match"))[0]
    assert case["id"] == "X-req_08" and case["decision"] == "no_exact_match"
    assert case["turns"] == ["msg 0", "msg 8"]                     # whole conversation s0 up to this request


def test_readme_renders_the_threshold_table():
    assert ops.threshold_table_md() in (Path(__file__).resolve().parents[1] / "README.md").read_text()


def test_mask_pii():
    assert mask("call 081-234-5678 or +66 81 234 5678, a@b.co; 1,000 sheets, 20 packs") == \
        "call [phone] or [phone], [email]; 1,000 sheets, 20 packs"
