"""LangChain SQL agent wiring (spec 5.2).

Builds the three pieces the agent needs - a SQLDatabase pointed at the
configured master view, a Gemini chat model, and the agent executor that ties
them together - and caches them so Streamlit reruns don't rebuild on every keystroke.
"""

from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.prompts import FEW_SHOT_PREFIX
from config import settings

_agent = None
_db = None


def build_db():
    """Connect LangChain's SQLDatabase to the BigQuery production dataset.

    Only the master view is exposed, so schema introspection cannot leak other
    tables into the prompt (spec section 10).
    """
    uri = f"bigquery://{settings.bigquery_project}/{settings.bigquery_dataset}"

    return SQLDatabase.from_uri(
        uri,
        include_tables=[settings.bigquery_master_table],
        # A couple of sample rows help Gemini get literals right (e.g. whether
        # `state` holds 'Victoria' or 'VIC') without bloating the prompt.
        sample_rows_in_table_info=3,
    )


def get_db():
    """Return the shared SQLDatabase, building it on first use."""
    global _db

    if _db is None:
        _db = build_db()

    return _db


def build_llm():
    """Create the Gemini chat model used for SQL generation."""
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        # Deterministic output - we want the same question to produce the same
        # SQL, which also makes the golden-dataset eval meaningful.
        temperature=0,
    )


def create_insight_agent(verbose=True, include_examples=True):
    """Build a fresh SQL agent executor."""

    settings.apply_langsmith_env()

    from agent.prompts import build_system_prefix

    prefix = FEW_SHOT_PREFIX if include_examples else build_system_prefix(False)

    return create_sql_agent(
        llm=build_llm(),
        db=get_db(),
        # "tool-calling" is the provider-neutral equivalent and is the correct choice for a Gemini model.
        agent_type="tool-calling",
        prefix=prefix,
        # Fills the {top_k} placeholder in the prefix and caps the
        # toolkit's own row suggestions at the same number.
        top_k=settings.max_result_rows,
        verbose=verbose,
        # Stop a confused agent from looping against BigQuery indefinitely.
        max_iterations=8,
        max_execution_time=settings.query_timeout_seconds,
        # NOTE: create_sql_agent only forwards these two to the AgentExecutor
        # via agent_executor_kwargs - passed as top-level kwargs they are
        # silently swallowed and intermediate steps come back empty.
        agent_executor_kwargs={
            # Surfaces the generated SQL to the service layer for eval/logging.
            "return_intermediate_steps": True,
            "handle_parsing_errors": True,
        },
    )


def get_agent():
    """Return the shared agent executor, building it on first use."""
    global _agent

    if _agent is None:
        _agent = create_insight_agent()

    return _agent


def reset_agent():
    """Drop the cached agent and DB - useful after changing prompts in dev."""
    global _agent, _db
    _agent = None
    _db = None
