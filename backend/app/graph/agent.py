"""LangGraph agent: a supervised tool-calling loop with a checkpointed thread."""
import sqlite3
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app.core.config import settings
from app.graph.tools import TOOLS

SYSTEM_PROMPT = """You are the analyst assistant embedded in a business dashboard.

Rules:
- Always ground numeric claims in a tool call. Never invent figures.
- Prefer get_metric / compare_segments; fall back to run_sql only when the
  question needs something those cannot express.
- Answer in two parts: a one-line headline, then the supporting detail.
- When a result is chartable, end with a line of the form
  CHART: {"type":"line|bar","title":"...","labels":[...],"values":[...]}
  so the dashboard can render it.
- If a question is outside the business data you can query, say so plainly."""


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _llm():
    s = settings()
    return ChatAnthropic(
        model=s.model,
        max_tokens=s.max_tokens,
        temperature=s.temperature,
        api_key=s.anthropic_api_key or None,
    ).bind_tools(TOOLS)


def _call_model(state: State) -> dict:
    messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    return {"messages": [_llm().invoke(messages)]}


def build_graph():
    s = settings()
    Path(s.checkpoint_db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(s.checkpoint_db, check_same_thread=False)

    builder = StateGraph(State)
    builder.add_node("agent", _call_model)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=SqliteSaver(conn))


GRAPH = None


def graph():
    global GRAPH
    if GRAPH is None:
        GRAPH = build_graph()
    return GRAPH
