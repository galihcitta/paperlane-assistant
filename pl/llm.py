"""Shared Anthropic client settings."""
import os
from pathlib import Path

import anthropic


def _load_dotenv(path: Path = Path(".env")):
    """Minimal .env support (KEY=VALUE lines); real environment variables win."""
    if path.is_file():
        for line in path.read_text().splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#"):
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

DEFAULT_MODEL = "claude-sonnet-5-5"


def model() -> str:
    return os.environ.get("PL_MODEL", DEFAULT_MODEL)


def effort() -> str:
    return os.environ.get("PL_EFFORT", "medium")


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


_client = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=3, timeout=120)
    return _client


# USD per 1M tokens (input, output), for the request log's cost estimate.
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50)}


def est_cost(model_id: str, usage: dict) -> float:
    """Cache reads bill at 0.1x input, 5-minute cache writes at 1.25x."""
    pin, pout = PRICES.get(model_id, (2.0, 10.0))
    inp = usage["input"] + 0.1 * usage["cache_read"] + 1.25 * usage["cache_write"]
    return round((inp * pin + usage["output"] * pout) / 1e6, 6)
