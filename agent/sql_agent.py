"""LangChain SQL agent wiring (spec 5.2).

Builds the three pieces the agent needs - a SQLDatabase pointed at the
configured master view, a Gemini chat model, and the agent that ties them
together - and caches them so Streamlit reruns don't rebuild on every keystroke.

"""

from langchain.agents import create_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.prompts import FEW_SHOT_PREFIX, build_system_prefix
from config import settings

# Stop a confused agent looping against BigQuery. LangGraph counts every node
# visit, and one agent step is roughly two of them, so leave headroom.
MAX_AGENT_STEPS = 8
RECURSION_LIMIT = 2 * MAX_AGENT_STEPS + 1

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
        max_retries=settings.gemini_max_retries,
    )


def build_system_prompt(prefix, dialect):
    """Resolve the {dialect}/{top_k} placeholders in the prompt prefix.

    `create_agent` takes the system prompt as a plain string and does no
    formatting of its own, so we do it here.
    """
    return prefix.format(dialect=dialect, top_k=settings.max_result_rows)


def create_insight_agent(include_examples=True):
    """Build a fresh SQL agent."""
    # LangSmith tracing is opt-in via .env; do it here so every agent run is
    # traced no matter which entry point built the agent (spec 6.1).
    settings.apply_langsmith_env()

    prefix = FEW_SHOT_PREFIX if include_examples else build_system_prefix(False)

    db = get_db()
    llm = build_llm()

    return create_agent(
        model=llm,
        # The standard SQL toolkit: list tables, get schema, check query, run
        # query. Scoped to the one view `build_db` exposes.
        tools=SQLDatabaseToolkit(db=db, llm=llm).get_tools(),
        system_prompt=build_system_prompt(prefix, db.dialect),
        name="insight-agent",
    )


def get_agent():
    """Return the shared agent, building it on first use."""
    global _agent

    if _agent is None:
        _agent = create_insight_agent()

    return _agent


def reset_agent():
    """Drop the cached agent and DB - useful after changing prompts in dev."""
    global _agent, _db
    _agent = None
    _db = None
