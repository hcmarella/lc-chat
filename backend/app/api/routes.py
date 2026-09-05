import json
from typing import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.graph.agent import graph
from app.graph.tools import compare_segments, get_metric

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    thread_id: str = Field(default="default", max_length=128)


def _principal(request: Request) -> str:
    s = settings()
    if s.behind_api_gateway:
        pid = request.headers.get(s.principal_header)
        if not pid:
            raise HTTPException(401, "missing forwarded principal")
        return pid
    return "local-user"


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    """Non-streaming turn. Returns the final assistant message."""
    principal = _principal(request)
    cfg = {"configurable": {"thread_id": f"{principal}:{req.thread_id}"}}
    g = await graph()
    result = await g.ainvoke({"messages": [HumanMessage(req.message)]}, cfg)
    return {"reply": result["messages"][-1].content, "thread_id": req.thread_id}


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """Token stream plus tool-call events, as SSE."""
    principal = _principal(request)
    cfg = {"configurable": {"thread_id": f"{principal}:{req.thread_id}"}}

    async def events() -> AsyncIterator[dict]:
        try:
            g = await graph()
            async for kind, payload in g.astream(
                {"messages": [HumanMessage(req.message)]}, cfg, stream_mode=["messages", "updates"]
            ):
                if kind == "messages":
                    chunk, _meta = payload
                    if getattr(chunk, "content", None):
                        text = chunk.content
                        if isinstance(text, list):
                            text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
                        if text:
                            yield {"event": "token", "data": text}
                elif kind == "updates" and "tools" in payload:
                    yield {"event": "tool", "data": json.dumps({"status": "ran"})}
            yield {"event": "done", "data": "ok"}
        except Exception as exc:  # surfaced to the UI rather than a dead stream
            yield {"event": "error", "data": str(exc)}

    return EventSourceResponse(events())


@router.get("/dashboard/summary")
async def dashboard_summary():
    """KPI tiles + charts the dashboard renders without asking the agent."""
    tiles = []
    for metric in ("revenue", "active_users", "churn_rate", "gross_margin"):
        d = get_metric.invoke({"metric": metric, "months": 6})
        tiles.append({"metric": metric, "latest": d["latest"], "change_pct": d["change_pct"],
                      "periods": d["periods"], "values": d["values"]})
    return {
        "tiles": tiles,
        "segments": compare_segments.invoke({"metric": "revenue", "top_n": 5})["rows"],
    }


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    s = settings()
    return {"status": "ok" if s.anthropic_api_key else "degraded", "env": s.env}
