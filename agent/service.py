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

from agent.sql_agent import get_agent
from agent.tools import extract_sql
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
    elapsed_seconds: float = 0.0
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def as_dict(self):
        return {
            "question": self.question,
            "answer": self.answer,
            "sql": self.sql,
            "ok": self.ok,
            "error": self.error,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "run_id": self.run_id,
        }


# Shown to the user instead of a stack trace. The real error is logged and
# traced in LangSmith.
FRIENDLY_ERROR = (
    "Sorry - I couldn't answer that one. Try rephrasing it, or naming the "
    "state and the metric explicitly (for example: \"average prosperity score "
    "in New South Wales\")."
)


def ask(question, user_id=None, tier=None):
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
        "tags": [tag for tag in ["dgrafy-insight-agent", tier] if tag],
        "metadata": {"user_id": user_id or "anonymous", "tier": tier or "unknown"},
        "run_name": "insight-agent-question",
    }

    try:
        agent = get_agent()
        raw = agent.invoke({"input": question}, config=run_config)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        logger.exception("Agent failed for question: %s", question)

        return AgentAnswer(
            question=question,
            answer=FRIENDLY_ERROR,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            elapsed_seconds=elapsed,
        )

    elapsed = time.perf_counter() - started

    if isinstance(raw, dict):
        answer = raw.get("output") or ""
        sql = extract_sql(raw.get("intermediate_steps"))
    else:
        answer = str(raw)
        sql = None

    logger.info(
        "question=%r elapsed=%.2fs sql=%r", question, elapsed, (sql or "")[:200]
    )

    return AgentAnswer(
        question=question,
        answer=answer or FRIENDLY_ERROR,
        sql=sql,
        ok=bool(answer),
        elapsed_seconds=elapsed,
    )


def warm_up():
    """Build the agent ahead of the first question.

    Schema introspection and the BigQuery handshake take a few seconds; calling
    this once at app start keeps the first user question from paying for it.
    """
    try:
        get_agent()
        return True
    except Exception:
        logger.exception("Agent warm-up failed")
        return False


def tracing_enabled():
    """True if LangSmith tracing is configured (surface this in the UI/dev tools)."""
    return bool(settings.langchain_tracing and settings.langchain_api_key)
