"""Polite same-origin BFS crawler. Saves every raw response under data/raw/<run_id>/ for provenance."""
import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urlparse

import httpx

from .parse import links


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Fetched:
    url: str
    status: int
    text: str
    fetched_at: str


@dataclass
class Crawl:
    base_url: str
    pages: list[Fetched] = field(default_factory=list)
    requests: int = 0
    errors: list[str] = field(default_factory=list)


class Fetcher:
    """HTTP GET with a minimum gap between requests (robots.txt Crawl-delay, never below min_delay)."""

    def __init__(self, raw_dir: Path, base_url: str, min_delay: float = 1.0):
        self.client = httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "PaperLaneAssistantBot/0.1"})
        self.raw_dir, self.base_url, self.delay = raw_dir, base_url, min_delay
        self._last = 0.0
        self.count = 0

    def get(self, url: str) -> Fetched:
        wait = self._last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self.count += 1
        try:
            r = self.client.get(url)
            f = Fetched(url, r.status_code, r.text, now_iso())
        except httpx.HTTPError as e:
            f = Fetched(url, 0, "", now_iso())
            f.text = f"__error__ {e!r}"
        rel = url[len(self.base_url):] if url.startswith(self.base_url) else urlparse(url).path.lstrip("/")
        out = self.raw_dir / (rel or "index.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f.text if f.status == 200 else json.dumps({"status": f.status, "body": f.text[:500]}))
        return f


def crawl(base_url: str, raw_dir: Path, min_delay: float = 1.0, fetcher: Fetcher | None = None) -> tuple[Crawl, Fetcher]:
    if not base_url.endswith("/"):
        base_url += "/"
    fx = fetcher or Fetcher(raw_dir, base_url, min_delay)
    robots = fx.get(base_url + "robots.txt")
    m = re.search(r"crawl-delay:\s*([\d.]+)", robots.text, re.I) if robots.status == 200 else None
    if m:
        fx.delay = max(fx.delay, float(m.group(1)))
    out = Crawl(base_url)
    seen, queue = set(), deque([base_url + "index.html"])
    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        f = fx.get(url)
        if f.status != 200:
            out.errors.append(f"{url}: HTTP {f.status}")
            continue
        out.pages.append(f)
        for link in links(f.text, url):
            link = urldefrag(link)[0]
            if link.startswith(base_url) and link.endswith((".html", "/")) and link not in seen:
                queue.append(link)
    out.requests = fx.count
    return out, fx
