"""BigQuery connection wrapper.

Responsibilities:
  * build a single, lazily-created BigQuery client from the service account
  * enforce read-only SQL and a bytes-billed ceiling before anything executes
  * return plain Python rows the rest of the app can work with

The service account itself should be read-only on the two allowed tables
(spec section 10). The checks here are defence in depth, not the only control.
"""

import re

from google.cloud import bigquery

from config import settings
from db.schema import ALLOWED_TABLES

# Statements that must never reach BigQuery (spec 5.3 / 10).
FORBIDDEN_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "MERGE",
    "REPLACE",
    "GRANT",
    "REVOKE",
    "EXPORT",
)

_client = None


class UnsafeQueryError(ValueError):
    """Raised when a query fails the read-only / allowed-table checks."""


def get_client():
    """Return the shared BigQuery client, creating it on first use.

    Lazy so that importing this module never requires credentials - unit tests
    and the SQL guard can be exercised without a service account.
    """
    global _client

    if _client is None:
        _client = bigquery.Client(
            project=settings.bigquery_project or None,
            location=settings.bigquery_location or None,
        )

    return _client


def _strip_sql_noise(sql):
    """Remove comments and string literals so keyword checks can't be fooled."""
    without_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_line = re.sub(r"(--|#)[^\n]*", " ", without_block)
    without_strings = re.sub(r"'[^']*'|\"[^\"]*\"", " '' ", without_line)
    return without_strings


def assert_read_only(sql):
    """Raise UnsafeQueryError unless `sql` is a single read-only statement."""
    if not sql or not sql.strip():
        raise UnsafeQueryError("Empty query.")

    cleaned = _strip_sql_noise(sql).strip()

    # A trailing semicolon is fine; anything after it is a second statement.
    statements = [part for part in cleaned.split(";") if part.strip()]

    if len(statements) > 1:
        raise UnsafeQueryError(
            "Multiple SQL statements are not allowed - send one SELECT at a time."
        )

    first_word = statements[0].strip().split()[0].upper()

    if first_word not in ("SELECT", "WITH"):
        raise UnsafeQueryError(
            f"Only SELECT/WITH queries are allowed, got '{first_word}'."
        )

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", cleaned, flags=re.IGNORECASE):
            raise UnsafeQueryError(f"Destructive keyword '{keyword}' is not allowed.")

    return True


def referenced_tables(sql):
    """Best-effort list of table identifiers referenced after FROM/JOIN."""
    cleaned = _strip_sql_noise(sql)

    # CTE names are locally defined, not real tables.
    cte_names = {
        name.lower()
        for name in re.findall(r"\b(\w+)\s+AS\s*\(", cleaned, flags=re.IGNORECASE)
    }

    found = re.findall(
        r"\b(?:FROM|JOIN)\s+`?([A-Za-z_][\w\-.]*)`?", cleaned, flags=re.IGNORECASE
    )

    return [name for name in found if name.lower() not in cte_names]


def assert_allowed_tables(sql):
    """Raise UnsafeQueryError if the query reaches outside the allowed tables."""
    allowed_names = {table.split(".")[-1].lower() for table in ALLOWED_TABLES}

    for table in referenced_tables(sql):
        if table.split(".")[-1].lower() not in allowed_names:
            raise UnsafeQueryError(
                f"Table '{table}' is not in the allowed set: "
                f"{', '.join(ALLOWED_TABLES)}"
            )

    return True


def _job_config(dry_run=False):
    return bigquery.QueryJobConfig(
        dry_run=dry_run,
        use_query_cache=True,
        maximum_bytes_billed=settings.max_bytes_billed,
    )


def dry_run(query):
    """Validate a query and return the bytes it would process, without running it."""
    assert_read_only(query)
    assert_allowed_tables(query)

    job = get_client().query(query, job_config=_job_config(dry_run=True))
    return job.total_bytes_processed


def run_query(query, max_rows=None):
    """Execute a read-only query and return the rows as a list of dicts.

    `max_rows` defaults to MAX_RESULT_ROWS so a runaway query can never pull
    the whole view into memory.
    """
    assert_read_only(query)
    assert_allowed_tables(query)

    limit = max_rows or settings.max_result_rows

    query_job = get_client().query(query, job_config=_job_config())
    results = query_job.result(
        max_results=limit, timeout=settings.query_timeout_seconds
    )

    rows = []

    for row in results:
        rows.append(dict(row))

    return rows


def table_exists(table_ref):
    """Return True if the fully qualified table/view is readable."""
    try:
        get_client().get_table(table_ref)
        return True
    except Exception:
        return False
