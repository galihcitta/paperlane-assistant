"""SQLite storage. Every ingest run writes its own rows (tagged run_id); 'current' is the latest promoted run."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Item, Tier

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, base_url TEXT, started_at TEXT, finished_at TEXT,
  status TEXT, counts TEXT, report_path TEXT, promoted_at TEXT
);
CREATE TABLE IF NOT EXISTS items (
  run_id TEXT, sku TEXT, product_url TEXT, product_name TEXT, category TEXT, product_type TEXT, brand TEXT,
  size_code TEXT, width_mm INTEGER, height_mm INTEGER, weight_gsm INTEGER, weight_lb_stated INTEGER,
  weight_source TEXT, colour TEXT, colour_raw TEXT, finish TEXT, finish_raw TEXT,
  sides INTEGER, colour_mode TEXT, pack_unit TEXT, sheets_per_pack INTEGER,
  list_price_satang INTEGER, sale_price_satang INTEGER, stock_status TEXT, stock_raw TEXT, back_in_stock TEXT,
  extraction TEXT, source_url TEXT, crawled_at TEXT, tiers_url TEXT, quotable INTEGER, quarantine_reason TEXT,
  PRIMARY KEY (run_id, sku)
);
CREATE TABLE IF NOT EXISTS tiers (
  run_id TEXT, sku TEXT, min_qty INTEGER, unit_price_satang INTEGER, source_url TEXT, crawled_at TEXT,
  PRIMARY KEY (run_id, sku, min_qty)
);
CREATE TABLE IF NOT EXISTS notes (run_id TEXT, sku TEXT, text TEXT, source_url TEXT);
"""

ITEM_COLS = [c for c in Item.model_fields if c != "tiers"]


def db_path() -> Path:
    return Path(os.environ.get("PL_DB", "data/paperlane.db"))


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)   # callers sharing one across threads must lock
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(items)")}
    for col, typ in [("quotable", "INTEGER DEFAULT 1"), ("quarantine_reason", "TEXT")]:
        if col not in cols:  # databases created before per-SKU quarantine
            con.execute(f"ALTER TABLE items ADD COLUMN {col} {typ}")
    if "promoted_at" not in {r["name"] for r in con.execute("PRAGMA table_info(runs)")}:
        con.execute("ALTER TABLE runs ADD COLUMN promoted_at TEXT")
        con.execute("UPDATE runs SET promoted_at=finished_at WHERE status='promoted'")
    return con


def save_run(con, run_id: str, items: list[Item], notes: list[tuple[str, str, str]]):
    for it in items:
        row = it.model_dump(exclude={"tiers"})
        row["back_in_stock"] = it.back_in_stock.isoformat() if it.back_in_stock else None
        con.execute(f"INSERT INTO items (run_id, {', '.join(ITEM_COLS)}) VALUES (?{', ?' * len(ITEM_COLS)})",
                    [run_id] + [row[c] for c in ITEM_COLS])
        for t in it.tiers:
            con.execute("INSERT INTO tiers VALUES (?,?,?,?,?,?)",
                        (run_id, it.sku, t.min_qty, t.unit_price_satang, it.tiers_url, it.crawled_at))
    con.executemany("INSERT INTO notes VALUES (?,?,?,?)", [(run_id, *n) for n in notes])
    con.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def record_run(con, run_id, base_url, started, finished, status, counts: dict, report_path):
    con.execute("INSERT OR REPLACE INTO runs (run_id, base_url, started_at, finished_at, status, counts, report_path, promoted_at)"
                " VALUES (?,?,?,?,?,?,?,?)", (run_id, base_url, started, finished, status, json.dumps(counts),
                                             str(report_path), _now() if status == "promoted" else None))
    con.commit()


def promote(con, run_id: str):
    con.execute("UPDATE runs SET status='promoted', promoted_at=? WHERE run_id=?", (_now(), run_id))
    con.commit()


def run_status(con, run_id: str) -> str | None:
    r = con.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()
    return r["status"] if r else None


def current_run_id(con) -> str | None:
    r = con.execute("SELECT run_id FROM runs WHERE status='promoted' ORDER BY promoted_at DESC, run_id DESC LIMIT 1").fetchone()
    return r["run_id"] if r else None


def load_items(con, run_id: str) -> dict[str, Item]:
    tiers: dict[str, list[Tier]] = {}
    for r in con.execute("SELECT sku, min_qty, unit_price_satang FROM tiers WHERE run_id=? ORDER BY min_qty", (run_id,)):
        tiers.setdefault(r["sku"], []).append(Tier(min_qty=r["min_qty"], unit_price_satang=r["unit_price_satang"]))
    out = {}
    for r in con.execute("SELECT * FROM items WHERE run_id=? ORDER BY sku", (run_id,)):
        d = {c: r[c] for c in ITEM_COLS}
        d["quotable"] = bool(d["quotable"]) if d["quotable"] is not None else True
        out[d["sku"]] = Item(**d, tiers=tiers.get(d["sku"], []))
    return out


def load_current(con=None) -> tuple[str, dict[str, Item]]:
    con = con or connect()
    run_id = current_run_id(con)
    if not run_id:
        raise RuntimeError("No promoted catalog snapshot. Run `pl ingest --base-url ...` first.")
    return run_id, load_items(con, run_id)
