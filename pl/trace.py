"""One structured trace per customer request, written as a line of data/logs/requests.jsonl.

Span attributes use the OpenTelemetry GenAI semantic-convention names (gen_ai.*), so the records can be shipped
to an OTLP backend later without renaming. Logging only observes: nothing here feeds back into the agent.
"""
import re
import time
import uuid

PROVIDER = "anthropic"
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w.,])(?:\+66[\s-]?|0)\d(?:[\s-]?\d){7,8}(?!\d)")


def mask(text: str) -> str:
    """Customer PII out of the log: emails and phone numbers (Thai 0x / +66 formats)."""
    return _PHONE.sub("[phone]", _EMAIL.sub("[email]", text))


def new_request_id() -> str:
    return "req_" + uuid.uuid4().hex[:12]


def chat_span(resp, request_model: str, started: float, purpose: str) -> dict:
    """Span for one Messages API call. gen_ai.usage.input_tokens includes cache reads and writes (semconv)."""
    u = resp.usage
    cr, cw = u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
    return {"name": f"chat {request_model}", "purpose": purpose, "duration_ms": int((time.monotonic() - started) * 1000),
            "attributes": {
                "gen_ai.operation.name": "chat", "gen_ai.provider.name": PROVIDER,
                "gen_ai.request.model": request_model, "gen_ai.response.model": resp.model, "gen_ai.response.id": getattr(resp, "id", None),
                "gen_ai.response.finish_reasons": [resp.stop_reason],
                "gen_ai.usage.input_tokens": u.input_tokens + cr + cw, "gen_ai.usage.output_tokens": u.output_tokens,
                "gen_ai.usage.cache_read.input_tokens": cr, "gen_ai.usage.cache_write.input_tokens": cw}}


def tool_span(block, out: dict, is_err: bool, started: float) -> dict:
    return {"name": f"execute_tool {block.name}", "duration_ms": int((time.monotonic() - started) * 1000),
            "status": "ERROR" if is_err else "OK",
            "attributes": {"gen_ai.operation.name": "execute_tool", "gen_ai.provider.name": PROVIDER,
                           "gen_ai.tool.name": block.name, "gen_ai.tool.call.id": block.id,
                           "gen_ai.tool.call.arguments": block.input, "gen_ai.tool.call.result": summarise(block.name, out)}}


def summarise(name: str, out: dict) -> dict:
    """The parts of a tool result someone debugging a request needs, not the whole JSON."""
    if out.get("error"):
        return {"error": out["error"]}
    if name == "search_products":
        s = {"decision": out.get("decision"), "match_count": out.get("match_count"),
             "skus": [m["sku"] for m in out.get("matches", out.get("alternatives", []))],
             "unavailable": [u["sku"] for u in out.get("unavailable", [])]}
        for k in ("missing_or_ambiguous", "reason", "narrowing_question"):
            if out.get(k):
                s[k] = out[k]
        if out.get("best_quote"):
            s["best_total_incl_vat"] = out["best_quote"]["total_incl_vat"]
        return s
    if name == "quote":
        return {"lines": [[l["sku"], l["qty_packs"], l["line_total"]] for l in out.get("lines", [])],
                "total_incl_vat": out.get("total_incl_vat"), "refused": out.get("refused", [])}
    if name == "get_product":
        return {"sku": out.get("sku"), "stock": out.get("stock_status") or out.get("stock")}
    return {}
