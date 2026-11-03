from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import db
from .ingest import run_ingest
from .pricing import quote

app = FastAPI(title="PaperLane assistant")
_agent = None


def agent():
    global _agent
    if _agent is None:
        from .agent import Agent
        _agent = Agent()
    return _agent


class ChatIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)


class QuoteLine(BaseModel):
    sku: str
    qty_packs: int = Field(gt=0)


class QuoteIn(BaseModel):
    lines: list[QuoteLine] = Field(min_length=1)


class IngestIn(BaseModel):
    base_url: str
    accept: bool = False


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/chat")
def chat(body: ChatIn):
    return agent().chat(body.session_id, body.message)


@app.post("/quote")
def post_quote(body: QuoteIn):
    try:
        run_id, items = db.load_current()
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return quote([(l.sku, l.qty_packs) for l in body.lines], items).to_dict() | {"snapshot": run_id}


@app.post("/ingest")
def post_ingest(body: IngestIn):
    # Blocking on purpose: a crawl is ~2 minutes at 1 req/s and this is an operator action.
    res = run_ingest(body.base_url, accept=body.accept)
    return {"run_id": res.run_id, "status": res.status, "report": res.report, "warnings": res.warnings,
            "not_quotable": res.quarantined}


@app.get("/items")
def items():
    run_id, its = db.load_current()
    return {"snapshot": run_id, "count": len(its),
            "items": [it.model_dump(mode="json") for it in its.values()]}
