import shutil
from pathlib import Path

import pytest

from pl import db
from pl.crawl import Fetched, now_iso

SITE = Path(__file__).resolve().parents[2] / "paperlane"
BASE = "http://test.local/paperlane/"


class FileFetcher:
    """Serves the site from disk with the same interface as crawl.Fetcher (no network, no delay)."""

    def __init__(self, root: Path):
        self.root, self.delay, self.count = root, 0.0, 0

    def get(self, url: str) -> Fetched:
        self.count += 1
        p = self.root / url[len(BASE):]
        if p.is_file():
            return Fetched(url, 200, p.read_text(), now_iso())
        return Fetched(url, 404, "", now_iso())


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    # Tests never call the model (a key in .env must not turn the LLM fallback on).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)


@pytest.fixture
def site_copy(tmp_path):
    dst = tmp_path / "site"
    shutil.copytree(SITE, dst)
    return dst


@pytest.fixture
def con(tmp_path):
    return db.connect(tmp_path / "t.db")


@pytest.fixture(scope="session")
def v1_items(tmp_path_factory):
    from pl.ingest import run_ingest
    d = tmp_path_factory.mktemp("v1")
    c = db.connect(d / "t.db")
    res = run_ingest(BASE, data_dir=d, con=c, log=lambda *_: None, fetcher=FileFetcher(SITE))
    assert res.status == "promoted", res.problems
    return res.items
