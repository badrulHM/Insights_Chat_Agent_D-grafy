"""Application layer between the UI and the LangChain agent.

The Streamlit app should import *only* this module - never `sql_agent`
directly. That keeps the UI free of LangChain details and gives us one place
to add caching, logging and per-user metadata.

    from agent.service import ask
    result = ask("Top 3 most diverse suburbs in Victoria", user_id="user_001")
    st.markdown(result.answer)
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from langchain_core.tracers.context import collect_runs

from agent.charts import suggest_chart
from agent.safe_tools import AGENT_ALLOWED_TABLES, get_cached_rows
from agent.sql_agent import RECURSION_LIMIT, get_agent
from db.bigquery_client import run_query
from agent.tools import extract_sql, message_text
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class AgentAnswer:
    """Everything the UI (and the eval harness) needs from one question."""

    question: str
    answer: str
    sql: str = None
    ok: bool = True
    error: str = None
    # Stable failure code the UI can branch on; None when ok.
    reason: str = None
    # Result rows and a chart suggestion, populated when with_data=True.
    rows: list = None
    chart: object = None
    elapsed_seconds: float = 0.0
    # Local correlation id, always present - useful in app logs.
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # LangSmith identifiers, present only when tracing is enabled.
    trace_id: str = None
    trace_url: str = None

    def as_dict(self):
        return {
            "question": self.question,
            "answer": self.answer,
            "sql": self.sql,
            "ok": self.ok,
            "error": self.error,
            "reason": self.reason,
            "row_count": len(self.rows) if self.rows is not None else None,
            "chart": self.chart.as_dict() if self.chart else None,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "trace_url": self.trace_url,
        }


# Shown to the user instead of a stack trace. The real error is logged and
# traced in LangSmith.
# These messages must be honest about WHOSE problem it is. 
ERROR_MESSAGES = {
    "rate_limited": (
        "The service is handling too many requests right now. Wait a few "
        "seconds and ask again - your question was fine."
    ),
    "model_unavailable": (
        "The AI model is currently unavailable. This is a configuration "
        "problem on our side, not your question. Please tell the team."
    ),
    "data_unavailable": (
        "I couldn't reach the demographic database just now. Please try "
        "again shortly - your question was fine."
    ),
    "too_complex": (
        "That question needed more steps than I'm allowed to take. Try "
        "splitting it into two simpler questions."
    ),
    "no_answer": (
        "I ran the query but couldn't turn the result into an answer. Try "
        "asking for a specific metric and area, e.g. \"average prosperity "
        "score in New South Wales\"."
    ),
    "unknown": (
        "Something went wrong on our side and I couldn't answer that. "
        "Please try again - if it keeps happening, tell the team."
    ),
}


def classify_error(exc):
    """Map an exception to a (reason, user-facing message) pair.

    The reason is a stable code the UI can branch on (e.g. to show a retry
    button for `rate_limited` but not for `model_unavailable`).
    """
    text = f"{type(exc).__name__} {exc}".lower()

    if any(t in text for t in ("resource_exhausted", "429", "quota", "rate limit")):
        reason = "rate_limited"
    elif "recursion" in text or "iteration" in text:
        reason = "too_complex"
    elif "not_found" in text or "404" in text:
        reason = "model_unavailable"
    elif any(t in text for t in ("bigquery", "forbidden", "403", "denied",
                                 "notfound: 404 table", "google.api_core")):
        reason = "data_unavailable"
    else:
        reason = "unknown"

    return reason, ERROR_MESSAGES[reason]


def _trace_links(collected):
    """Return (run_id, run_url) for the root run LangSmith just recorded.

    Best effort: tracing is optional, and a LangSmith outage must never turn a
    good answer into an error. Any failure yields (None, None).
    """
    runs = getattr(collected, "traced_runs", None)

    if not runs:
        return None, None

    run = runs[0]
    run_id = str(getattr(run, "id", "") or "") or None
    run_url = None

    if run_id and tracing_enabled():
        try:
            from langsmith import Client

            run_url = Client().get_run_url(run=run)
        except Exception:
            logger.debug("Could not build LangSmith run URL", exc_info=True)

    return run_id, run_url


def fetch_result_data(sql, question=None):
    """Get the rows behind an answer, plus a chart suggestion.

    Normally free: the guarded query tool already cached the rows it fetched
    during the agent run, so there is no second BigQuery job. Reusing those
    exact rows also guarantees the chart agrees with the text - re-running
    could return different data than the answer describes.

    Falls back to re-executing only if the cache missed (evicted, or the agent
    answered from conversation rather than a fresh query).
    Returns (rows, chart_spec); never raises.
    """
    if not sql:
        return None, None

    rows = get_cached_rows(sql)

    if rows is None:
        logger.debug("Chart data cache miss; re-running SQL")

        try:
            rows = run_query(sql, allowed_tables=AGENT_ALLOWED_TABLES)
        except Exception:
            logger.debug("Could not re-run SQL for chart data", exc_info=True)
            return None, None

    return rows, suggest_chart(rows, question)


def ask(question, user_id=None, tier=None, with_data=False):
    """Run one question through the agent and return an AgentAnswer.

    Never raises: any failure comes back as `ok=False` with a friendly message,
    so a bad question cannot crash the Streamlit session.
    """
    question = (question or "").strip()

    if not question:
        return AgentAnswer(
            question=question,
            answer="Please enter a question.",
            ok=False,
            error="empty question",
        )

    started = time.perf_counter()

    # Tags and metadata show up in LangSmith, so a trace can be traced back to
    # the user and tier that produced it (spec 6.1).
    run_config = {
        "tags": [tag for tag in ["insight-agent", tier] if tag],
        "metadata": {"user_id": user_id or "anonymous", "tier": tier or "unknown"},
        "run_name": "insight-agent-question",
        # LangGraph's loop guard - stops a confused agent hammering BigQuery.
        "recursion_limit": RECURSION_LIMIT,
    }

    trace_id = None
    trace_url = None

    try:
        agent = get_agent()

        # collect_runs captures the root run so we can link straight to this
        # question's trace in LangSmith (spec 6.1). Cheap no-op when tracing
        # is off, so there is no need to branch on it here.
        with collect_runs() as collected:
            raw = agent.invoke(
                {"messages": [{"role": "user", "content": question}]},
                config=run_config,
            )

        trace_id, trace_url = _trace_links(collected)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        reason, message = classify_error(exc)
        logger.exception(
            "Agent failed (%s) for question: %s", reason, question
        )

        return AgentAnswer(
            question=question,
            answer=message,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            reason=reason,
            elapsed_seconds=elapsed,
        )

    elapsed = time.perf_counter() - started

    messages = raw.get("messages") if isinstance(raw, dict) else None

    if messages:
        answer = message_text(messages[-1].content).strip()
        sql = extract_sql(messages)
    else:
        answer = str(raw)
        sql = None

    rows = None
    chart = None

    if with_data and sql:
        rows, chart = fetch_result_data(sql, question)

    logger.info(
        "question=%r elapsed=%.2fs sql=%r", question, elapsed, (sql or "")[:200]
    )

    return AgentAnswer(
        question=question,
        answer=answer or ERROR_MESSAGES["no_answer"],
        sql=sql,
        ok=bool(answer),
        reason=None if answer else "no_answer",
        elapsed_seconds=elapsed,
        trace_id=trace_id,
        trace_url=trace_url,
        rows=rows,
        chart=chart,
    )


def tracing_enabled():
    """True if LangSmith tracing is configured (surface this in the UI/dev tools)."""
    return bool(settings.langchain_tracing and settings.langchain_api_key)


def tracing_status():
    """Everything the UI or a dev tool needs to show tracing state."""
    return {
        "enabled": tracing_enabled(),
        "project": settings.langchain_project,
        "dashboard_url": settings.langsmith_project_url,
    }
