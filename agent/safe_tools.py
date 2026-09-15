"""A guarded replacement for the SQL toolkit's query tool.

WHY THIS EXISTS: `SQLDatabaseToolkit`'s `sql_db_query` tool calls
`SQLDatabase.run()`, which executes SQLAlchemy directly and never touches
`db.bigquery_client`. `include_tables=[...]` only limits which tables schema
*introspection* reveals - it does not restrict what SQL can execute. So the
model (or a prompt injection) could read any table the service account can
see, including customer records.

This tool routes every agent-generated query through the same read-only and
allowed-table guards the rest of the app uses, with the allow-list narrowed to
the master view alone. Rejections are returned as text rather than raised, so
the agent reads the reason and corrects itself instead of the run dying.
"""

import logging
import threading
from collections import OrderedDict

from langchain_core.tools import tool

from db.bigquery_client import UnsafeQueryError, run_query
from db.schema import MASTER_VIEW

logger = logging.getLogger(__name__)

# The agent may only ever read the master view - never the customer table,
# even though the application as a whole is allowed to.
AGENT_ALLOWED_TABLES = (MASTER_VIEW,)

QUERY_TOOL_NAME = "sql_db_query"

# Rows the agent actually saw, keyed by the SQL that produced them.
#
# The tool already pays for these rows; without this they were formatted into a
# string for the model and discarded, forcing a second BigQuery job whenever
# the UI wanted to chart the result. Reusing them is not only cheaper - it is
# more correct: re-running the query could return different data than the
# answer describes, producing a chart that contradicts the text.
#
# Bounded and lock-guarded because LangGraph may execute tools on worker
# threads, and a Streamlit process serves several sessions at once.
_CACHE_MAX_ENTRIES = 64
_result_cache = OrderedDict()
_cache_lock = threading.Lock()


def _cache_key(sql):
    """Normalise whitespace and a trailing semicolon so near-identical SQL hits."""
    return " ".join((sql or "").split()).rstrip(";").lower()


def remember_rows(sql, rows):
    """Store the rows a query returned, evicting the oldest entry when full."""
    key = _cache_key(sql)

    if not key:
        return

    with _cache_lock:
        _result_cache[key] = rows
        _result_cache.move_to_end(key)

        while len(_result_cache) > _CACHE_MAX_ENTRIES:
            _result_cache.popitem(last=False)


def get_cached_rows(sql):
    """Return the rows this SQL produced during the agent run, or None."""
    key = _cache_key(sql)

    if not key:
        return None

    with _cache_lock:
        rows = _result_cache.get(key)

        if rows is not None:
            _result_cache.move_to_end(key)

        return rows


def clear_cache():
    """Drop every cached result (tests, and after a schema change)."""
    with _cache_lock:
        _result_cache.clear()


def _format_rows(rows):
    """Render rows the way the stock tool does, so prompt behaviour is unchanged."""
    if not rows:
        return "[]"

    return str([tuple(row.values()) for row in rows])


@tool(QUERY_TOOL_NAME)
def safe_sql_db_query(query: str) -> str:
    """Execute a SQL query against the demographic database and return results.

    Input must be a single, correct, read-only SELECT query. If the query is
    malformed or rejected, an error message is returned - rewrite the query and
    try again.
    """
    try:
        rows = run_query(
            query,
            allowed_tables=AGENT_ALLOWED_TABLES,
            # Scope 5: generated SQL must name the table in full.
            require_qualified=True,
        )
    except UnsafeQueryError as exc:
        logger.warning("Agent query rejected by guard: %s | %s", exc, query)
        return (
            f"Query rejected: {exc} "
            "Rewrite the query to read only the permitted demographic table."
        )
    except Exception as exc:
        # Malformed SQL, timeouts, bytes-billed ceiling. Hand the reason back
        # so the agent can fix its own query rather than failing the run.
        logger.info("Agent query failed: %s", exc)
        return f"Error: {type(exc).__name__}: {exc}"

    # Keep the rows so the UI can chart exactly what the agent saw.
    remember_rows(query, rows)

    if not rows:
        # Being explicit stops the model reporting an empty result as a finding.
        return (
            "[] (no rows matched - the filters may be too strict or a value "
            "may not exist; do not invent results)"
        )

    return _format_rows(rows)


def build_safe_tools(toolkit):
    """Return the toolkit's tools with the query tool swapped for the guarded one."""
    tools = [t for t in toolkit.get_tools() if t.name != QUERY_TOOL_NAME]
    tools.append(safe_sql_db_query)
    return tools
