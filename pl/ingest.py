"""Crawl -> parse -> (LLM fallback) -> tiers -> validate -> save snapshot -> diff -> promote or reject."""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from . import db, llm, llm_extract
from .crawl import Fetcher, crawl, now_iso
from .diff import diff
from .models import Item, Tier
from .normalise import money_to_satang
from .parse import parse_page

MAX_COUNT_SWING = 0.20


@dataclass
class IngestResult:
    run_id: str
    status: str
    items: dict[str, Item]
    report_path: Path
    report: str
    problems: list[str] = field(default_factory=list)
    changes: dict[str, list[str]] = field(default_factory=dict)


def _tiers_for(fx: Fetcher, page_url: str, html: str, sku: str, problems: list) -> tuple[list[Tier], str]:
    root = (BeautifulSoup(html, "lxml").body or {}).get("data-root", "")
    url = urljoin(page_url, f"{root}api/pricing/{sku}.json")
    f = fx.get(url)
    if f.status == 404:
        return [], url
    if f.status != 200:
        problems.append(f"{sku}: pricing JSON HTTP {f.status} at {url}")
        return [], url
    try:
        d = json.loads(f.text)
    except json.JSONDecodeError:
        problems.append(f"{sku}: pricing JSON not parseable at {url}")
        return [], url
    if d.get("sku") != sku:
        problems.append(f"{sku}: pricing JSON is for {d.get('sku')!r}")
    if d.get("currency", "THB") != "THB" or d.get("vat_included", False) or d.get("unit", "pack") != "pack":
        problems.append(f"{sku}: pricing JSON has unexpected terms {d.get('currency')}/{d.get('unit')}/vat={d.get('vat_included')}")
    tiers = [Tier(min_qty=int(t["min_qty"]), unit_price_satang=money_to_satang(t["unit_price"])) for t in d.get("tiers") or []]
    return sorted(tiers, key=lambda t: t.min_qty), url


def run_ingest(base_url: str, data_dir: Path = Path("data"), min_delay: float = 1.0,
               con=None, log=print, fetcher: Fetcher | None = None) -> IngestResult:
    con = con or db.connect()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    started = now_iso()
    raw_dir = data_dir / "raw" / run_id
    log(f"[ingest] run {run_id}: crawling {base_url} (>= {min_delay}s between requests)")
    c, fx = crawl(base_url, raw_dir, min_delay, fetcher)
    problems = list(c.errors)
    items: dict[str, Item] = {}
    notes: list[tuple[str, str, str]] = []
    llm_pages, product_pages = [], 0

    for page in c.pages:
        res = parse_page(page.text, page.url, page.fetched_at)
        if not res.is_product:
            continue
        product_pages += 1
        page_items = res.items
        if res.errors:
            log(f"[ingest] {page.url}: deterministic parse failed ({'; '.join(res.errors[:3])}) -> LLM fallback")
            if not llm.available():
                problems.append(f"{page.url}: parse failed and no ANTHROPIC_API_KEY for fallback: {res.errors}")
                continue
            try:
                cat = page_items[0].category if page_items else None
                page_items = llm_extract.extract(res.main_text, page.url, page.fetched_at, cat)
            except Exception as e:
                problems.append(f"{page.url}: LLM fallback error {e!r}")
                continue
            llm_pages.append(page.url)
        for it in page_items:
            if it.sku in items:
                problems.append(f"duplicate SKU {it.sku} on {page.url} and {items[it.sku].source_url}")
                continue
            if it.sku in res.tier_skus or (res.errors and it.sale_price_satang is None):
                it.tiers, it.tiers_url = _tiers_for(fx, page.url, page.text, it.sku, problems)
            errs = it.validation_errors()
            if errs:
                problems.append(f"{it.sku} ({page.url}): {'; '.join(errs)}")
            items[it.sku] = it
        notes += [(sku, text, page.url) for sku, text in res.notes]

    prev_id = db.current_run_id(con)
    prev = db.load_items(con, prev_id) if prev_id else {}
    missing = {sku: it.missing_required() for sku, it in items.items() if it.missing_required()}
    if prev and abs(len(items) - len(prev)) > MAX_COUNT_SWING * len(prev):
        problems.append(f"SKU count {len(items)} differs from previous {len(prev)} by more than {MAX_COUNT_SWING:.0%}")
    if not items:
        problems.append("no items parsed")
    status = "rejected" if problems else "promoted"

    changes = diff(prev, items) if prev else {}
    counts = {"pages": len(c.pages), "product_pages": product_pages, "skus": len(items),
              "with_tiers": sum(1 for i in items.values() if i.tiers), "on_sale": sum(1 for i in items.values() if i.sale_price_satang),
              "not_in_stock": sum(1 for i in items.values() if i.stock_status != "in_stock"),
              "llm_pages": len(llm_pages), "requests": fx.count, "missing_required": len(missing),
              "notes_quarantined": len(notes)}
    report = _report(run_id, base_url, status, counts, problems, llm_pages, prev_id, changes)
    report_path = data_dir / "reports" / f"{run_id}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    db.save_run(con, run_id, list(items.values()), notes)
    db.record_run(con, run_id, base_url, started, now_iso(), status, counts, report_path)
    log(report)
    return IngestResult(run_id, status, items, report_path, report, problems, changes)


def _report(run_id, base_url, status, counts, problems, llm_pages, prev_id, changes) -> str:
    lines = [f"# Ingest report {run_id}", "", f"- Source: {base_url}", f"- Status: **{status}**"
             + ("" if status == "promoted" else " (previous snapshot stays live)"),
             "- Counts: " + ", ".join(f"{k}={v}" for k, v in counts.items()), ""]
    if problems:
        lines += ["## Problems (block promotion)", ""] + [f"- {p}" for p in problems] + [""]
    if llm_pages:
        lines += ["## Pages extracted by LLM fallback (review these)", ""] + [f"- {u}" for u in llm_pages] + [""]
    if prev_id:
        lines += [f"## Changes vs {prev_id}", ""]
        total = 0
        for k, v in changes.items():
            if v:
                total += len(v)
                lines += [f"### {k} ({len(v)})"] + [f"- {x}" for x in v] + [""]
        if not total:
            lines += ["No changes.", ""]
    else:
        lines += ["First snapshot (nothing to diff against).", ""]
    return "\n".join(lines)
