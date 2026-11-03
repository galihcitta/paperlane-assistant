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
    warnings: list[str] = field(default_factory=list)
    quarantined: dict[str, str] = field(default_factory=dict)


def _tiers_for(fx: Fetcher, page_url: str, html: str, sku: str) -> tuple[list[Tier], str, list[str]]:
    """Tiers from the JSON endpoint tiers.js uses. Returns (tiers, url, per-SKU problems)."""
    root = (BeautifulSoup(html, "lxml").body or {}).get("data-root", "")
    url = urljoin(page_url, f"{root}api/pricing/{sku}.json")
    f = fx.get(url)
    if f.status == 404:
        return [], url, []
    if f.status != 200:
        return [], url, [f"pricing JSON HTTP {f.status} at {url}"]
    try:
        d = json.loads(f.text)
        tiers = [Tier(min_qty=int(t["min_qty"]), unit_price_satang=money_to_satang(t["unit_price"])) for t in d.get("tiers") or []]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return [], url, [f"pricing JSON not parseable at {url}"]
    probs = []
    if d.get("sku") != sku:
        probs.append(f"pricing JSON is for {d.get('sku')!r}")
    if d.get("vat_included", False):
        probs.append("pricing JSON says vat_included=true (site prices are ex-VAT)")
    if d.get("currency", "THB") != "THB" or d.get("unit", "pack") != "pack":
        probs.append(f"pricing JSON has unexpected terms {d.get('currency')}/{d.get('unit')}")
    return sorted(tiers, key=lambda t: t.min_qty), url, probs


def run_ingest(base_url: str, data_dir: Path = Path("data"), min_delay: float = 1.0,
               con=None, log=print, fetcher: Fetcher | None = None, accept: bool = False) -> IngestResult:
    """Promotion is per SKU: an item with a data problem is stored as not quotable (with the reason) and
    every other item goes live. Run-level oddities (dead links, SKU count swing) are warnings that hold the
    snapshot until accepted (--accept or `pl promote`). Rejected only when nothing usable was parsed."""
    con = con or db.connect()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    started = now_iso()
    raw_dir = data_dir / "raw" / run_id
    log(f"[ingest] run {run_id}: crawling {base_url} (>= {min_delay}s between requests)")
    c, fx = crawl(base_url, raw_dir, min_delay, fetcher)
    warnings = [f"dead link: {e}" for e in c.errors]
    failed_pages: list[str] = []
    items: dict[str, Item] = {}
    notes: list[tuple[str, str, str]] = []
    llm_pages, product_pages = [], 0
    prev_id = db.current_run_id(con)
    prev = db.load_items(con, prev_id) if prev_id else {}

    for page in c.pages:
        res = parse_page(page.text, page.url, page.fetched_at)
        if not res.is_product:
            continue
        product_pages += 1
        page_items, page_problem = res.items, None
        if res.errors:
            log(f"[ingest] {page.url}: deterministic parse failed ({'; '.join(res.errors[:3])}) -> LLM fallback")
            if not llm.available():
                page_problem = f"page failed to parse ({'; '.join(res.errors[:3])}) and no API key for the LLM fallback"
            else:
                try:
                    page_items = llm_extract.extract(res.main_text, page.url, page.fetched_at, res.category)
                    llm_pages.append(page.url)
                except Exception as e:
                    page_problem = f"page failed to parse and LLM fallback errored: {e!r}"
        if page_problem:
            failed_pages.append(f"{page.url}: {page_problem}")
        for it in page_items:
            if not it.sku:
                continue
            if it.sku in items:
                it.quarantine(f"duplicate SKU (also on {items[it.sku].source_url})")
                items[it.sku].quarantine(f"duplicate SKU (also on {page.url})")
                continue
            if it.sku in res.tier_skus or (res.errors and it.sale_price_satang is None):
                it.tiers, it.tiers_url, tprobs = _tiers_for(fx, page.url, page.text, it.sku)
                for p in tprobs:
                    it.quarantine(p)
            if it.sku in res.sale_skus and it.sale_price_satang is None:
                it.quarantine("marked on sale (data-sale='1') but no sale price found")
            if page_problem:
                it.quarantine(page_problem)
            for e in it.validation_errors():
                it.quarantine(e)
            items[it.sku] = it
        notes += [(sku, text, page.url) for sku, text in res.notes]

    # A page that failed outright keeps its SKUs visible (last known data) but not quotable.
    failed_urls = {f.split(": ", 1)[0] for f in failed_pages}
    for sku, old in prev.items():
        if sku not in items and old.source_url in failed_urls:
            keep = old.model_copy(deep=True)
            keep.quarantine(f"page failed to parse in this run; showing last known data from {prev_id}")
            items[sku] = keep

    # A moved or renamed tier endpoint shows up as volume pricing vanishing from many SKUs at once.
    prev_tiered = {s for s, it in prev.items() if it.tiers}
    now_tiered = {s for s, it in items.items() if it.tiers}
    if prev_tiered and len(now_tiered) < len(prev_tiered) / 2:
        for sku in prev_tiered - now_tiered:
            if sku in items and items[sku].sale_price_satang is None:
                items[sku].quarantine(f"volume pricing missing: SKUs with tiers fell from {len(prev_tiered)} to "
                                      f"{len(now_tiered)} (tier endpoint moved?)")

    usable = [it for it in items.values() if it.quotable]
    if prev and abs(len(items) - len(prev)) > MAX_COUNT_SWING * len(prev):
        warnings.append(f"SKU count {len(items)} differs from previous {len(prev)} by more than {MAX_COUNT_SWING:.0%}")
    if not usable:
        status = "rejected"
    elif warnings and not accept:
        status = "held"
    else:
        status = "promoted"

    changes = diff(prev, items) if prev else {}
    quarantined = {sku: it.quarantine_reason for sku, it in items.items() if not it.quotable}
    counts = {"pages": len(c.pages), "product_pages": product_pages, "skus": len(items), "quotable": len(usable),
              "not_quotable": len(quarantined), "with_tiers": sum(1 for i in items.values() if i.tiers),
              "on_sale": sum(1 for i in items.values() if i.sale_price_satang),
              "not_in_stock": sum(1 for i in items.values() if i.stock_status != "in_stock"),
              "llm_pages": len(llm_pages), "requests": fx.count, "warnings": len(warnings),
              "notes_quarantined": len(notes)}
    report = _report(run_id, base_url, status, counts, warnings, failed_pages, quarantined, llm_pages, prev_id, changes)
    report_path = data_dir / "reports" / f"{run_id}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    db.save_run(con, run_id, list(items.values()), notes)
    db.record_run(con, run_id, base_url, started, now_iso(), status, counts, report_path)
    log(report)
    problems = warnings + failed_pages + [f"{k}: {v}" for k, v in quarantined.items()]
    return IngestResult(run_id, status, items, report_path, report, problems, changes, warnings, quarantined)


def _report(run_id, base_url, status, counts, warnings, failed_pages, quarantined, llm_pages, prev_id, changes) -> str:
    note = {"promoted": "", "held": " (previous snapshot stays live; review the warnings, then `pl promote " + run_id
            + "` or re-run with --accept)", "rejected": " (nothing usable parsed; previous snapshot stays live)"}[status]
    lines = [f"# Ingest report {run_id}", "", f"- Source: {base_url}", f"- Status: **{status}**" + note,
             "- Counts: " + ", ".join(f"{k}={v}" for k, v in counts.items()), ""]
    if warnings:
        lines += ["## Warnings (hold promotion until accepted)", ""] + [f"- {w}" for w in warnings] + [""]
    if failed_pages:
        lines += ["## Pages that failed to parse", ""] + [f"- {p}" for p in failed_pages] + [""]
    if quarantined:
        lines += ["## SKUs stored as NOT quotable (data problem)", ""] + [f"- {k}: {v}" for k, v in quarantined.items()] + [""]
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
