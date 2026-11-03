"""Shared Anthropic client settings."""
import os

import anthropic

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


def est_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICES.get(model_id, (2.0, 10.0))
    return round((input_tokens * pin + output_tokens * pout) / 1e6, 6)
