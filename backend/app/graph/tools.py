"""Business tools exposed to the agent.

Each tool is deliberately thin: it validates arguments, hits a data source and
returns JSON-serialisable rows. Replace the in-memory sample data with your
warehouse client (Snowflake / Redshift / BigQuery) without touching the graph.
"""
from datetime import date, timedelta
from typing import Literal

from langchain_core.tools import tool

_METRICS = {
    "revenue": [128_400, 141_900, 137_200, 155_800, 168_300, 172_100],
    "active_users": [12_040, 12_880, 13_110, 14_020, 15_330, 16_010],
    "churn_rate": [3.1, 2.9, 3.4, 2.7, 2.5, 2.3],
    "gross_margin": [61.2, 62.0, 60.4, 63.1, 64.0, 64.8],
}


def _months(n: int) -> list[str]:
    today = date.today().replace(day=1)
    out = []
    for i in range(n - 1, -1, -1):
        m = today - timedelta(days=31 * i)
        out.append(m.strftime("%Y-%m"))
    return out


@tool
def get_metric(
    metric: Literal["revenue", "active_users", "churn_rate", "gross_margin"],
    months: int = 6,
) -> dict:
    """Return a monthly time series for a core business metric.

    Use this before answering any question about trends, growth or totals.
    """
    months = max(1, min(months, 6))
    series = _METRICS[metric][-months:]
    return {
        "metric": metric,
        "periods": _months(months),
        "values": series,
        "latest": series[-1],
        "change_pct": round((series[-1] - series[0]) / series[0] * 100, 2) if series[0] else 0.0,
    }


@tool
def compare_segments(metric: Literal["revenue", "active_users"], top_n: int = 5) -> dict:
    """Break a metric down by business segment for the most recent period."""
    segments = {
        "revenue": {"Enterprise": 94_200, "Mid-Market": 41_600, "SMB": 22_800,
                    "Partner": 9_400, "Self-Serve": 4_100},
        "active_users": {"Enterprise": 3_120, "Mid-Market": 4_480, "SMB": 5_260,
                         "Partner": 1_940, "Self-Serve": 1_210},
    }[metric]
    rows = sorted(segments.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return {"metric": metric, "rows": [{"segment": s, "value": v} for s, v in rows]}


@tool
def run_sql(query: str) -> dict:
    """Run a read-only SQL query against the analytics warehouse.

    Only SELECT statements are permitted; anything else is rejected.
    """
    normalized = query.strip().lower()
    if not normalized.startswith("select"):
        return {"error": "only SELECT statements are allowed"}
    if any(kw in normalized for kw in (";", " insert ", " update ", " delete ", " drop ")):
        return {"error": "query rejected by the read-only guard"}
    # Wire your warehouse driver here.
    return {"query": query, "rows": [], "note": "connect BIZCHAT_WAREHOUSE_DSN to execute"}


TOOLS = [get_metric, compare_segments, run_sql]
