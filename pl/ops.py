"""Operations view. Every number is a pure function of its inputs (request log records, runs rows, eval results),
and every panel compares it to a threshold from THRESHOLDS, which says what to do when it is crossed. The README
renders the same table (`threshold_table_md`), so the page and the docs can't disagree.
"""
import html
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# key: (label, unit, alert when value is ..., limit, action)
THRESHOLDS = {
    "check_fail_rate": ("Reply-check failure rate (first attempt)", "%", ">", 10.0,
                        "Open the failing traces. If the figure was right, the check has a false positive: fix it "
                        "narrowly in replycheck.py. If it was wrong, fix the prompt or tool output."),
    "template_rate": ("Template-reply rate", "%", ">", 2.0,
                      "Customers are getting the plain fallback. Open the traces: both attempts failed the check, "
                      "or the API errored (see error)."),
    "no_match_share": ("Decision mix: no exact match", "%", ">", 30.0,
                       "Many requests find nothing: check for a catalog gap or out-of-stock items in the traces."),
    "not_sold_share": ("Decision mix: not sold", "%", ">", 20.0,
                       "Customers ask for things PaperLane doesn't list: share with the owner as demand."),
    "p50_latency_s": ("Latency p50", "s", ">", 8.0, "Check tool rounds and rewrites in slow traces; check API status."),
    "p95_latency_s": ("Latency p95", "s", ">", 15.0, "Same as p50; slow tails usually mean a rewrite or 2+ tool rounds."),
    "cost_per_conversation_usd": ("Cost per conversation", "$", ">", 0.03,
                                  "Check cache reads in the traces (a cache miss costs ~10x), rewrites and tool rounds."),
    "catalog_age_days": ("Catalog age (live snapshot)", "days", ">", 7.0,
                         "Prices may be stale: run `pl ingest --base-url ...` and review the report."),
    "last_ingest_not_promoted": ("Last ingest held or rejected", "runs", ">", 0.0,
                                 "Read data/reports/<run>.md. If the warnings are expected, `pl promote <run>`; "
                                 "otherwise fix the site or the parser. The previous snapshot stays live."),
    "price_drift": ("Logged quotes that re-price differently", "quotes", ">", 0.0,
                    "A logged quote no longer matches the independent calculator on the live snapshot's raw pages: "
                    "if the site changed, re-ingest; if not, it's a pricing bug. Open the trace."),
}


def threshold_table_md() -> str:
    rows = ["| Metric | Alert when | Action |", "|---|---|---|"]
    for label, unit, op, limit, action in THRESHOLDS.values():
        lim = f"${limit:.2f}" if unit == "$" else f"{limit:g}{'%' if unit == '%' else ' ' + unit}"
        rows.append(f"| {label} | {op} {lim} | {action} |")
    return "\n".join(rows)


def status(key: str, value) -> str:
    if value is None:
        return "na"
    _, _, op, limit, _ = THRESHOLDS[key]
    return "alert" if (value > limit if op == ">" else value < limit) else "ok"


# ---------------------------------------------------------------- pure metrics

def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def percentile(xs: list[float], p: float) -> float | None:
    """Nearest-rank percentile (no interpolation)."""
    if not xs:
        return None
    s = sorted(xs)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)]


def traffic_metrics(records: list[dict]) -> dict:
    n = len(records)
    if not n:
        return {"requests": 0, "conversations": 0}
    convs: dict[str, float] = {}
    for r in records:
        convs[r["session_id"]] = convs.get(r["session_id"], 0.0) + r["est_cost_usd"]
    mix: dict[str, int] = {}
    for r in records:
        mix[r["decision"]] = mix.get(r["decision"], 0) + 1
    lat = [r["latency_ms"] / 1000 for r in records]
    pct = lambda k: round(100 * k / n, 1)
    return {
        "requests": n, "conversations": len(convs),
        "check_fail_rate": pct(sum(1 for r in records if r["regenerated"] or not r["reply_check_passed"])),
        "template_rate": pct(sum(1 for r in records if r["template_used"])),
        "decision_mix": dict(sorted(mix.items(), key=lambda kv: -kv[1])),
        "no_match_share": pct(mix.get("no_exact_match", 0)), "not_sold_share": pct(mix.get("not_sold", 0)),
        "p50_latency_s": percentile(lat, 50), "p95_latency_s": percentile(lat, 95),
        "cost_per_conversation_usd": round(sum(convs.values()) / len(convs), 4),
        "total_cost_usd": round(sum(convs.values()), 4),
    }


def catalog_metrics(runs: list[dict], now: datetime) -> dict:
    """runs: rows of the runs table (run_id, status, finished_at, promoted_at, counts, report_path)."""
    if not runs:
        return {"live_run": None, "catalog_age_days": None, "last_ingest_not_promoted": None}
    live = max((r for r in runs if r["status"] == "promoted"), key=lambda r: r["promoted_at"] or "", default=None)
    last = max(runs, key=lambda r: r["run_id"])
    age = None
    if live:
        t = datetime.fromisoformat(live["finished_at"].replace("Z", "+00:00"))
        age = round((now - (t if t.tzinfo else t.replace(tzinfo=timezone.utc))).total_seconds() / 86400, 1)
    warnings = []
    rp = Path(last.get("report_path") or "")
    if rp.is_file():
        sect = rp.read_text().split("## Warnings", 1)
        if len(sect) > 1:
            warnings = [l[2:] for l in sect[1].split("\n## ")[0].splitlines() if l.startswith("- ")]
    return {"live_run": live["run_id"] if live else None, "catalog_age_days": age,
            "last_run": last["run_id"], "last_status": last["status"], "last_warnings": warnings,
            "last_ingest_not_promoted": 0 if last["status"] == "promoted" else 1}


def price_drift(records: list[dict], reprice, sample: int = 10) -> dict:
    """Re-price the latest distinct logged quotes with `reprice(lines) -> total str`; list the ones that differ."""
    seen, checked, drifted = set(), [], []
    for r in reversed(records):
        if not r.get("quote_lines") or not r.get("total"):
            continue
        key = json.dumps(r["quote_lines"])
        if key in seen:
            continue
        seen.add(key)
        now = reprice(r["quote_lines"])
        logged = r["total"].replace(",", "")
        row = {"request_id": r["request_id"], "lines": r["quote_lines"], "logged": logged, "now": now,
               "snapshot": r.get("snapshot")}
        checked.append(row)
        if now != logged:
            drifted.append(row)
        if len(checked) >= sample:
            break
    return {"checked": checked, "drifted": drifted, "price_drift": len(drifted) if checked else None}


def independent_repricer(site_dir: Path):
    """Uses eval/independent_quote.py (shares no code with pl/) against the given site files."""
    def reprice(lines):
        args = [f"{sku}:{qty}" for sku, qty in lines]
        out = subprocess.run([sys.executable, "-I", str(ROOT / "eval/independent_quote.py"), str(site_dir), *args],
                             capture_output=True, text=True)
        try:
            return json.loads(out.stdout.strip().splitlines()[-1])["total"]
        except (IndexError, ValueError, KeyError):
            return "error"
    return reprice


def eval_metrics(records: list[dict], results: dict | None) -> dict | None:
    """Latest tagged eval run: what the log says vs what eval/results.json says."""
    if not results or not results.get("eval_run"):
        return None
    run = results["eval_run"]
    recs = [r for r in records if r.get("traffic") == "eval" and r.get("eval_run") == run]
    rs = [x for xs in results["results"].values() for x in xs]
    model_rs = [x for x in rs if "reply_check" in x["checks"]]
    convs = {r["session_id"] for r in recs}
    conv_ok = {s: all(r["reply_check_passed"] for r in recs if r["session_id"] == s) for s in convs}
    return {"eval_run": run, "log_conversations": len(convs), "results_conversations": len(model_rs),
            "results_total": len(rs), "pass": sum(1 for x in rs if x["pass"]),
            "log_check_rate": round(100 * sum(conv_ok.values()) / len(convs), 1) if convs else None,
            "results_check_rate": round(100 * sum(1 for x in model_rs if x["checks"]["reply_check"]) / len(model_rs), 1)
            if model_rs else None,
            "log_cost_usd": round(sum(r["est_cost_usd"] for r in recs), 4),
            "results_spend_usd": results.get("spend_usd")}


def export_case(records: list[dict], request_id: str, expect: str | None = None) -> str:
    """The conversation up to this request as an eval case in requests.yaml format (messages already masked)."""
    r = next(x for x in records if x["request_id"] == request_id)
    turns = [x for x in records if x["session_id"] == r["session_id"] and x["ts"] <= r["ts"]]
    turns = turns[:turns.index(r) + 1] if r in turns else [r]
    case = {"id": f"X-{request_id}", "turns": [x["message"] for x in turns], "decision": expect or r["decision"],
            "notes": f"Exported from {request_id} ({r['traffic']}, snapshot {r.get('snapshot')}); observed decision "
                     f"{r['decision']}, items {r.get('skus')}, total {r.get('total')}."
                     + ("" if expect else " Set decision (and top1/total) to the EXPECTED behaviour before adding.")}
    return yaml.safe_dump([case], allow_unicode=True, sort_keys=False, width=110)


# ---------------------------------------------------------------- page

def gather(log_path: Path, con, results_path: Path, traffic: str = "live", site_dir: Path | None = None,
           now: datetime | None = None) -> dict:
    records = load_records(log_path)
    now = now or datetime.now(timezone.utc)
    runs = [dict(r) for r in con.execute("SELECT * FROM runs")]
    cat = catalog_metrics(runs, now)
    view = [r for r in records if traffic == "all" or r.get("traffic", "live") == traffic]
    results = json.loads(results_path.read_text()) if results_path.exists() else None
    site_dir = site_dir or (Path("data/raw") / cat["live_run"] if cat.get("live_run") else None)
    drift = price_drift(view, independent_repricer(site_dir)) if site_dir and site_dir.exists() else \
        {"checked": [], "drifted": [], "price_drift": None}
    return {"traffic": traffic, "now": now.isoformat(timespec="seconds"), "m": traffic_metrics(view), "catalog": cat,
            "drift": drift, "eval": eval_metrics(records, results), "recent": view[-25:][::-1], "view": view}


_CSS = """
:root{--bg:#fafaf7;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e4e3dc;--ok:#1f7a4d;--alert:#b3261e;--na:#8a8a85}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--ink:#ecebe6;--mute:#a3a29c;--line:#34332f;
--ok:#4cc38a;--alert:#ff6b5f;--na:#77766f}}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0 2px}h2{font-size:15px;margin:22px 0 8px}.mute{color:var(--mute)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--na);border-radius:6px;padding:10px 12px}
.card.ok{border-left-color:var(--ok)}.card.alert{border-left-color:var(--alert)}
.v{font-size:24px;font-weight:600}.alert .v{color:var(--alert)}.th{font-size:12px;color:var(--mute)}
.act{font-size:12px;margin-top:6px}.ok .act{display:none}
table{border-collapse:collapse;width:100%;background:var(--card);font-size:13px}
td,th{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}
a{color:inherit}pre{white-space:pre-wrap;background:var(--card);border:1px solid var(--line);padding:10px;font-size:12px}
.wrap{overflow-x:auto}.bad{color:var(--alert);font-weight:600}
"""


def _fmt(key: str, v) -> str:
    if v is None:
        return "n/a"
    unit = THRESHOLDS[key][1]
    return f"${v:.4f}" if unit == "$" else f"{v:g}{'%' if unit == '%' else ' ' + unit}"


def _card(key: str, v, extra: str = "") -> str:
    label, unit, op, limit, action = THRESHOLDS[key]
    lim = f"${limit:.2f}" if unit == "$" else f"{limit:g}{'%' if unit == '%' else ' ' + unit}"
    st = status(key, v)
    return (f'<div class="card {st}" data-metric="{key}" data-status="{st}"><div class="th">{html.escape(label)}</div>'
            f'<div class="v">{_fmt(key, v)}</div><div class="th">alert when {op} {lim}</div>{extra}'
            f'<div class="act"><b>Do:</b> {html.escape(action)}</div></div>')


def _bars(mix: dict) -> str:
    total = sum(mix.values()) or 1
    rows, y = [], 0
    for k, v in mix.items():
        w = round(200 * v / total)
        rows.append(f'<text x="0" y="{y + 11}" font-size="11" fill="currentColor">{html.escape(k)}</text>'
                    f'<rect x="110" y="{y + 2}" width="{w}" height="10" fill="currentColor" opacity=".55"/>'
                    f'<text x="{115 + w}" y="{y + 11}" font-size="11" fill="currentColor">{v}</text>')
        y += 16
    return f'<svg viewBox="0 0 340 {y}" width="100%" role="img" aria-label="decision mix">{"".join(rows)}</svg>'


def _latency_svg(recs: list[dict]) -> str:
    lat = [r["latency_ms"] / 1000 for r in recs]
    if not lat:
        return ""
    bins = [0] * 8   # 0-2,2-4,...,14+ s
    for x in lat:
        bins[min(7, int(x // 2))] += 1
    m = max(bins)
    bars = "".join(f'<rect x="{i * 28}" y="{40 - round(36 * b / m)}" width="24" height="{round(36 * b / m)}" '
                   f'fill="currentColor" opacity=".55"/>' for i, b in enumerate(bins))
    return (f'<svg viewBox="0 0 224 52" width="100%" role="img" aria-label="latency histogram">{bars}'
            f'<text x="0" y="51" font-size="9" fill="currentColor">0s</text>'
            f'<text x="196" y="51" font-size="9" fill="currentColor">14s+</text></svg>')


def render(d: dict) -> str:
    m, cat, drift, ev = d["m"], d["catalog"], d["drift"], d["eval"]
    tabs = " · ".join(f'<b>{t}</b>' if t == d["traffic"] else f'<a href="/ops?traffic={t}">{t}</a>'
                      for t in ("live", "eval", "all"))
    warn = "".join(f"<li>{html.escape(w)}</li>" for w in cat.get("last_warnings", []))
    ingest_extra = (f'<div class="th">last run {html.escape(str(cat.get("last_run")))}: '
                    f'<b>{html.escape(str(cat.get("last_status")))}</b></div>' + (f"<ul class='th'>{warn}</ul>" if warn else ""))
    drift_rows = "".join(
        f'<li class="{"bad" if x in drift["drifted"] else ""}"><a href="/ops/trace/{x["request_id"]}">{x["request_id"]}</a>'
        f' {html.escape(str(x["lines"]))}: logged {x["logged"]}, now {x["now"]}</li>' for x in drift["checked"])
    cards = [
        _card("check_fail_rate", m.get("check_fail_rate")), _card("template_rate", m.get("template_rate")),
        _card("no_match_share", m.get("no_match_share"), _bars(m.get("decision_mix", {}))),
        _card("not_sold_share", m.get("not_sold_share")),
        _card("p50_latency_s", m.get("p50_latency_s")),
        _card("p95_latency_s", m.get("p95_latency_s")),
        _card("cost_per_conversation_usd", m.get("cost_per_conversation_usd"),
              f'<div class="th">total ${m.get("total_cost_usd", 0):.2f} over {m.get("conversations", 0)} conversations</div>'),
        _card("catalog_age_days", cat.get("catalog_age_days"),
              f'<div class="th">live snapshot {html.escape(str(cat.get("live_run")))}</div>'),
        _card("last_ingest_not_promoted", cat.get("last_ingest_not_promoted"), ingest_extra),
        _card("price_drift", drift.get("price_drift"), f"<ul class='th'>{drift_rows}</ul>" if drift_rows else ""),
    ]
    rows = "".join(
        f'<tr><td><a href="/ops/trace/{r["request_id"]}">{r["request_id"]}</a><br><span class="mute">{r["ts"][5:16]}</span></td>'
        f'<td>{html.escape(r.get("message", "")[:90])}</td><td>{r["decision"]}</td><td>{r.get("total") or ""}</td>'
        f'<td>{r["latency_ms"] / 1000:.1f}s</td><td>{"" if r["reply_check_passed"] and not r["regenerated"] else "<span class=bad>rewrite</span>"}'
        f'{" <span class=bad>template</span>" if r["template_used"] else ""}</td>'
        f'<td><a href="/ops/export/{r["request_id"]}">yaml</a></td></tr>'
        for r in d["recent"] if "request_id" in r)
    ev_html = "<p class='mute'>No tagged eval run in eval/results.json.</p>"
    if ev:
        same = lambda a, b, tol: "✓" if a is not None and b is not None and abs(a - b) <= tol else "✗"
        ev_html = (f"<table><tr><th>Eval run {html.escape(ev['eval_run'])}</th><th>From the request log</th>"
                   f"<th>From eval/results.json</th><th></th></tr>"
                   f"<tr><td>Model conversations</td><td>{ev['log_conversations']}</td><td>{ev['results_conversations']}</td>"
                   f"<td>{same(ev['log_conversations'], ev['results_conversations'], 0)}</td></tr>"
                   f"<tr><td>Pass</td><td></td><td>{ev['pass']}/{ev['results_total']}</td><td></td></tr>"
                   f"<tr><td>Reply-check pass rate (conversation)</td><td>{ev['log_check_rate']}%</td>"
                   f"<td>{ev['results_check_rate']}%</td><td>{same(ev['log_check_rate'], ev['results_check_rate'], 0)}</td></tr>"
                   f"<tr><td>Spend</td><td>${ev['log_cost_usd']:.4f}</td><td>${(ev['results_spend_usd'] or 0):.4f}</td>"
                   f"<td>{same(ev['log_cost_usd'], ev['results_spend_usd'], 0.01)}</td></tr></table>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PaperLane Ops</title><style>{_CSS}</style></head><body><main>
<h1>PaperLane assistant: operations</h1>
<div class="mute">{html.escape(d["now"])} · traffic: {tabs} · {m.get("requests", 0)} requests, {m.get("conversations", 0)} conversations.
Red = threshold crossed; the card says what to do.</div>
<h2>Health</h2><div class="grid">{"".join(cards)}</div>
<h2>Latency distribution</h2><div class="card" style="max-width:420px">{_latency_svg(d["view"])}</div>
<h2>Latest eval run</h2>{ev_html}
<h2>Recent requests</h2><div class="wrap"><table><tr><th>Request</th><th>Customer message (masked)</th><th>Decision</th>
<th>Total</th><th>Latency</th><th>Check</th><th>Eval case</th></tr>{rows}</table></div>
</main></body></html>"""


def render_trace(records: list[dict], request_id: str) -> str:
    r = next(x for x in records if x.get("request_id") == request_id)
    flags = []
    if r["template_used"]:
        flags.append("template reply sent")
    if r["regenerated"]:
        flags.append("rewrite after failed reply check")
    if r.get("error"):
        flags.append(f"error: {r['error']}")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trace {html.escape(request_id)}</title><style>{_CSS}</style></head><body><main>
<p><a href="/ops">← ops</a> · <a href="/ops/export/{request_id}">export as eval case</a></p>
<h1>{html.escape(request_id)}</h1>
<div class="mute">{html.escape(r["ts"])} · {r.get("traffic")} · conversation {html.escape(r["session_id"])} · snapshot {r.get("snapshot")}
· {r["latency_ms"]} ms · ${r["est_cost_usd"]:.4f}</div>
<p class="bad">{html.escape("; ".join(flags))}</p>
<h2>Customer message (masked)</h2><pre>{html.escape(r.get("message", ""))}</pre>
<h2>Decision: {html.escape(r["decision"])}</h2><pre>{html.escape(json.dumps(r.get("criteria"), indent=1, ensure_ascii=False))}</pre>
<h2>Reply-check problems per attempt</h2><pre>{html.escape(json.dumps(r.get("check_problems"), indent=1, ensure_ascii=False))}</pre>
<h2>Reply sent</h2><pre>{html.escape(r.get("reply", ""))}</pre>
<h2>Spans</h2><pre>{html.escape(json.dumps(r.get("spans"), indent=1, ensure_ascii=False))}</pre>
</main></body></html>"""
