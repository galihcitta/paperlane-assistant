"""Layered evaluation: (a) ingest completeness, (b) criteria extraction, (c) product selection,
(d) totals to the satang, (e) decision type. Each request runs N times to measure stability."""
import json
import re
import time
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from . import db, llm, replycheck
from .agent import Agent
from .replycheck import allowed_numbers
from .search import Criteria, search

ROOT = Path("eval")
# Scorer only, deliberately wider than replycheck.false_delivery_claim: the reply check rewrites whatever that function
# catches, so sharing it would make this score unable to fail. Any sentence naming a total and delivery with wording
# that delivery is outside the total.
_D_OUTSIDE = re.compile(r"exclud|\bnot\b|n['’]t\b|without|separate|extra|additional|on top|\bbefore\b|higher(?!\s+than)|(?:will|would|to) be added", re.I)
# "total including delivery and VAT is not within budget" is about the budget.
_D_INSIDE = re.compile(r"(?<!not )(?<!n['’]t )\b(?:includ\w*|incl\.?|with)\s+(?:(?!(?:not?|but)\b)\S+\s+){0,3}?(?:delivery|shipping)"
                       r"|(?:delivery|shipping)(?:\s+and\s+VAT)?\s+included", re.I)


def delivery_outside_total(reply: str) -> str | None:
    if (claim := replycheck.false_delivery_claim(reply)):
        return claim
    for s in re.split(r"(?<=[.!?])\s+|\n", reply):
        if re.search(r"(?<!sub)(?<!line )\btotals?\b", s, re.I) and re.search(r"delivery|shipping", s, re.I) \
                and _D_OUTSIDE.search(s) and "confirm" not in s.lower() and not _D_INSIDE.search(s):
            return s
    return None


def _with_date_forms(wanted: list[str]) -> list[str]:
    """Scorer only: an ISO date in reply_has_any also accepts '12 Nov', '12 November', 'Nov 12', 'November 12'."""
    out = list(wanted)
    for s in wanted:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            d = date.fromisoformat(s)
            for m in (d.strftime("%b"), d.strftime("%B")):
                out += [f"{d.day} {m}", f"{m} {d.day}"]
    return out


def ingest_layer(con) -> dict:
    run_id, items = db.load_current(con)
    raw = Path("data/raw") / run_id
    skus = set()
    for f in raw.rglob("*.html"):
        t = f.read_text()
        skus |= set(re.findall(r"<td>(PL-[A-Z0-9-]+)</td>", t)) | set(re.findall(r"<dd>(PL-[A-Z0-9-]+)</dd>", t))
        skus |= set(re.findall(r"Item code: (PL-[A-Z0-9-]+)", t))
    missing = [s for s, it in items.items() if it.missing_required()]
    pricing_files = {f.stem for f in (raw / "api" / "pricing").glob("*.json")} if (raw / "api" / "pricing").exists() else set()
    tiers_ok = all(items[s].tiers for s in pricing_files if s in items)
    return {"snapshot": run_id, "skus_in_db": len(items), "skus_in_source": len(skus), "missing_required": len(missing),
            "db_equals_source": set(items) == skus, "pricing_files": len(pricing_files), "all_tiers_attached": tiers_ok}


def _subset(expected: dict, got: dict) -> tuple[int, int, list[str]]:
    hit, misses = 0, []
    for k, v in expected.items():
        g = got.get(k)
        if isinstance(v, dict):
            ok = isinstance(g, dict) and all(g.get(kk) == vv for kk, vv in v.items())
        else:
            ok = g == v
        hit += ok
        if not ok:
            misses.append(f"{k}: expected {v!r}, got {g!r}")
    return hit, len(expected), misses


def score(case: dict, out: dict) -> dict:
    r = {"checks": {}, "notes": []}
    exp_dec = case["decision"] if isinstance(case["decision"], list) else [case["decision"]]
    r["checks"]["decision"] = out["decision"] in exp_dec
    if not r["checks"]["decision"]:
        r["notes"].append(f"decision {out['decision']} (expected {exp_dec})")
    if "criteria" in case:
        got = out["criteria"].get("item1") or (next(iter(out["criteria"].values())) if out["criteria"] else {})
        h, n, miss = _subset(case["criteria"], got)
        r["criteria_hits"], r["criteria_total"] = h, n
        r["checks"]["criteria"] = h == n
        r["notes"] += [f"criteria {m}" for m in miss]
    sel = []
    if "top1" in case:
        ok = bool(out["items"]) and out["items"][0] == case["top1"]
        sel.append(ok)
        if not ok:
            r["notes"].append(f"top1 {out['items'][:1]} (expected {case['top1']})")
    quoted = [l["sku"] for l in (out["quote"] or {}).get("lines", [])]
    for a in case.get("absent", []):
        ok = a not in out["items"] and a not in quoted
        sel.append(ok)
        if not ok:
            r["notes"].append(f"{a} offered/quoted but must not be")
    for u in case.get("unavailable", []):
        ok = u in out.get("unavailable", [])
        sel.append(ok)
        if not ok:
            r["notes"].append(f"{u} not reported as unavailable")
    if sel:
        r["checks"]["selection"] = all(sel)
    if "total" in case:
        exp = Decimal(case["total"])
        got = (out["quote"] or {}).get("total_incl_vat")
        tool_ok = got is not None and Decimal(got.replace(",", "")) == exp
        reply_ok = exp in allowed_numbers(out["reply"])
        r["checks"]["total"] = tool_ok and reply_ok
        if not tool_ok:
            r["notes"].append(f"quote total {got} (expected {case['total']})")
        elif not reply_ok:
            r["notes"].append(f"reply does not state the total {case['total']}")
    if "delivery_flag" in case:
        da = out.get("delivery_area")
        flagged = bool(da) and da["in_service_area"] is False
        ok = flagged == case["delivery_flag"] and (case["delivery_flag"] is False or da is not None)
        r["checks"]["delivery"] = ok
        if not ok:
            r["notes"].append(f"delivery flag {da} (expected flagged={case['delivery_flag']})")
    reply_checks = []
    if "reply_has_any" in case:
        ok = any(re.search(rf"(?<!\d){re.escape(s)}(?!\d)", out["reply"], re.I) for s in _with_date_forms(case["reply_has_any"]))
        reply_checks.append(ok)
        if not ok:
            r["notes"].append(f"reply lacks any of {case['reply_has_any']}")
    if "reply_not_regex" in case:
        m = re.search(case["reply_not_regex"], out["reply"])
        reply_checks.append(m is None)
        if m:
            r["notes"].append(f"reply contains forbidden text {m.group(0)!r}")
    if reply_checks:
        r["checks"]["reply"] = all(reply_checks)
    claim = delivery_outside_total(out["reply"])
    r["checks"]["delivery_wording"] = claim is None
    if claim:
        r["notes"].append(f"reply says delivery is outside a total: {claim!r}")
    r["checks"]["reply_check"] = out["reply_check_passed"]
    if not out["reply_check_passed"]:
        r["notes"].append("reply post-check failed" + (" -> template reply sent" if out["template_used"] else ""))
    r["pass"] = all(v for k, v in r["checks"].items() if k != "reply_check")
    return r


def score_replycheck(case: dict, items: dict) -> dict:
    """Offline case: run the search tool, then the reply check on a scripted reply; it must flag expect_problem."""
    rc = case["replycheck"]
    res = search(Criteria(**rc["criteria"]), items)
    probs = replycheck.check(rc["reply"], [json.dumps(res, ensure_ascii=False, default=str)], "",
                             [i.product_name for i in items.values()])
    ok = any(re.search(rc["expect_problem"], p) for p in probs)
    return {"checks": {"reply_check_catches": ok}, "pass": ok, "reply": rc["reply"], "decision": res["decision"],
            "notes": [] if ok else [f"reply check did not flag {rc['expect_problem']!r} (problems: {probs})"]}


def main(runs: int = 3, only: list[str] | None = None, cases_path: Path | None = None) -> int:
    """cases_path: an alternative cases file (e.g. a case exported from /ops); its results go next to it."""
    if not llm.available():
        print("ANTHROPIC_API_KEY is not set; the eval needs the model.")
        return 2
    con = db.connect()
    cases = yaml.safe_load((cases_path or ROOT / "requests.yaml").read_text())
    out_json, out_md = ((cases_path.with_suffix(".results.json"), cases_path.with_suffix(".results.md")) if cases_path
                        else (ROOT / "results.json", ROOT / "results.md"))
    eval_run = "eval-" + time.strftime("%Y%m%dT%H%M%S", time.gmtime())   # tags this run's request-log records
    if only:
        cases = [c for c in cases if any(c["id"].startswith(o) for o in only)]
    agent = Agent(con=con)
    ing = ingest_layer(con)
    results = defaultdict(list)
    for run in range(runs):
        for c in cases:
            sid = f"eval-{c['id']}-{run}-{int(time.time())}"
            t0 = time.monotonic()
            if c.get("offline"):
                s = score_replycheck(c, agent.items) | {"run": run, "latency_s": 0.0, "items": [], "criteria": {},
                                                        "total": None, "template_used": False, "regenerated": False, "error": None}
                results[c["id"]].append(s)
                print(f"run {run} {c['id']}: {'PASS' if s['pass'] else 'FAIL'} {'; '.join(s['notes'])}", flush=True)
                continue
            outs = [agent.chat(sid, msg, traffic="eval", eval_run=eval_run) for msg in c["turns"]]
            # the conversation passes the reply check / avoids the template only if every turn does
            out = outs[-1] | {"reply_check_passed": all(o["reply_check_passed"] for o in outs),
                              "template_used": any(o["template_used"] for o in outs)}
            s = score(c, out)
            s |= {"run": run, "latency_s": round(time.monotonic() - t0, 1), "reply": out["reply"],
                  "decision": out["decision"], "items": out["items"], "criteria": out["criteria"],
                  "total": (out["quote"] or {}).get("total_incl_vat"), "template_used": out["template_used"],
                  "regenerated": out["regenerated"], "error": out["error"],
                  "cost_usd": round(sum(o["est_cost_usd"] for o in outs), 6), "request_ids": [o["request_id"] for o in outs]}
            results[c["id"]].append(s)
            print(f"run {run} {c['id']}: {'PASS' if s['pass'] else 'FAIL'} {'; '.join(s['notes'])}", flush=True)
    spend = round(sum(r.get("cost_usd", 0) for rs in results.values() for r in rs), 4)
    out_json.write_text(json.dumps({"eval_run": eval_run, "spend_usd": spend, "ingest": ing, "results": results},
                                   indent=1, ensure_ascii=False, default=str))
    md = report(cases, results, ing, runs) + f"\nEval run `{eval_run}` (tag in the request log); spend ${spend:.2f}.\n"
    out_md.write_text(md)
    print(md)
    return 0


def report(cases, results, ing, runs) -> str:
    allr = [r for rs in results.values() for r in rs]
    def rate(key):
        xs = [r["checks"][key] for r in allr if key in r["checks"]]
        return f"{sum(xs)}/{len(xs)} ({100 * sum(xs) / len(xs):.0f}%)" if xs else "n/a"
    ch = sum(r.get("criteria_hits", 0) for r in allr)
    ct = sum(r.get("criteria_total", 0) for r in allr)
    lat = sorted(r["latency_s"] for r in allr)
    lines = [
        "# Evaluation results", "",
        f"Model `{llm.model()}`, effort `{llm.effort()}`, catalog snapshot `{ing['snapshot']}`, "
        f"{len(cases)} requests x {runs} runs = {len(allr)} conversations.", "",
        "## Layers", "",
        "| Layer | Result |", "|---|---|",
        f"| (a) Ingest completeness | {ing['skus_in_db']} SKUs in DB vs {ing['skus_in_source']} counted independently in the crawled HTML "
        f"(sets equal: {ing['db_equals_source']}); {ing['missing_required']} missing required fields; "
        f"{ing['pricing_files']} pricing files, all attached: {ing['all_tiers_attached']} |",
        f"| (b) Criteria extraction | {ch}/{ct} expected fields ({100 * ch / max(ct, 1):.0f}%); cases fully right: {rate('criteria')} |",
        f"| (c) Product selection | {rate('selection')} |",
        f"| (d) Totals exact (tool quote and reply text) | {rate('total')} |",
        f"| (e) Decision type | {rate('decision')} |",
        f"| Reply content checks | {rate('reply')} |",
        f"| Delivery-area flag | {rate('delivery')} |",
        f"| No false claim that a total leaves out delivery | {rate('delivery_wording')} |",
        f"| Reply post-check passed first or second try | {rate('reply_check')} |",
        f"| Reply check catches a planted wrong total (offline) | {rate('reply_check_catches')} |",
        f"| **Overall pass** | {sum(r['pass'] for r in allr)}/{len(allr)} |", "",
        f"Latency per conversation: median {lat[len(lat) // 2]}s, max {lat[-1]}s.", "",
        "## Per request (stability over runs)", "", "| Request | Passes | Notes (failed runs) |", "|---|---|---|",
    ]
    for c in cases:
        rs = results[c["id"]]
        notes = "; ".join(sorted({n for r in rs if not r["pass"] for n in r["notes"]})) or ""
        lines.append(f"| {c['id']} | {sum(r['pass'] for r in rs)}/{len(rs)} | {notes} |")
    fails = [(cid, r) for cid, rs in results.items() for r in rs if not r["pass"] or not r["checks"].get("reply_check", True)]
    lines += ["", "## Failures (every failing run)", ""]
    if not fails:
        lines.append("None.")
    for cid, r in fails:
        lines += [f"### {cid} run {r['run']}", "", f"- Checks: {r['checks']}", f"- Notes: {'; '.join(r['notes'])}",
                  f"- Decision `{r['decision']}`, items {r['items']}, total {r['total']}, criteria {json.dumps(r['criteria'])}",
                  "- Reply:", "", "> " + r["reply"].replace("\n", "\n> "), ""]
    return "\n".join(lines) + "\n"
