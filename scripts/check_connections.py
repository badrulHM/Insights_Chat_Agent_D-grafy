"""Week 1 smoke test: prove every external connection works.

    python -m scripts.check_connections

Checks, in order: environment variables -> BigQuery auth -> both tables ->
Gemini -> LangSmith -> the assembled LangChain agent. Exits non-zero if any
required check fails, so it can be wired into CI later.
"""

import sys

from config import settings

PASS = "[ OK ]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def _header(title):
    print(f"\n--- {title} ---")


def check_environment():
    _header("1. Environment")

    for key, value in settings.redacted().items():
        print(f"  {key}: {value}")

    missing = settings.missing_required()

    if missing:
        print(f"{FAIL} Missing/invalid: {', '.join(missing)}")
        return False

    print(f"{PASS} Required settings present.")
    return True


def check_bigquery():
    _header("2. BigQuery connection")

    try:
        from db.bigquery_client import get_client, run_query

        client = get_client()
        print(f"  Authenticated project: {client.project}")

        rows = run_query("SELECT 1 AS test_value")
        assert rows and rows[0]["test_value"] == 1

        print(f"{PASS} BigQuery reachable and running queries.")
        return True
    except Exception as exc:
        print(f"{FAIL} {type(exc).__name__}: {exc}")
        return False


def check_tables():
    _header("3. Table access")

    from db.bigquery_client import table_exists
    from db.schema import CUSTOMERS_TABLE, MASTER_VIEW

    all_ok = True

    for table in (MASTER_VIEW, CUSTOMERS_TABLE):
        if table_exists(table):
            print(f"{PASS} {table}")
        else:
            print(f"{FAIL} {table} - not found or not readable by this account.")
            all_ok = False

    return all_ok


def check_read_only_guard():
    _header("4. Read-only guard")

    from db.bigquery_client import UnsafeQueryError, assert_read_only

    try:
        assert_read_only("DROP TABLE some_project.some_dataset.some_table")
        print(f"{FAIL} Destructive SQL was NOT blocked.")
        return False
    except UnsafeQueryError:
        print(f"{PASS} Destructive SQL is blocked before it reaches BigQuery.")
        return True


def check_gemini():
    _header("5. Gemini")

    try:
        from agent.sql_agent import build_llm

        llm = build_llm()
        reply = llm.invoke("Reply with the single word: connected")

        # LangChain 1.x content may be typed blocks, not a bare string.
        from agent.tools import message_text

        print(f"  Model: {settings.gemini_model}")
        print(f"  Reply: {message_text(reply.content).strip()[:80]}")
        print(f"{PASS} Gemini responding.")
        return True
    except Exception as exc:
        print(f"{FAIL} {type(exc).__name__}: {exc}")
        return False


def check_langsmith():
    _header("6. LangSmith tracing")

    if not settings.langchain_tracing:
        print(f"{WARN} LANGCHAIN_TRACING_V2 is off - runs will not be traced.")
        return True

    if not settings.langchain_api_key:
        print(f"{WARN} Tracing is on but LANGCHAIN_API_KEY is empty.")
        return True

    settings.apply_langsmith_env()
    print(f"{PASS} Tracing on, project '{settings.langchain_project}'.")
    return True


def check_agent():
    _header("7. LangChain SQL agent")

    try:
        from agent.sql_agent import get_agent, get_db

        db = get_db()
        print(f"  Dialect: {db.dialect}")
        print(f"  Usable tables: {db.get_usable_table_names()}")

        get_agent()
        print(f"{PASS} Agent assembled (schema introspection succeeded).")
        return True
    except Exception as exc:
        print(f"{FAIL} {type(exc).__name__}: {exc}")
        return False


def main():
    print("D'grafy Insight Agent - connection check")

    checks = [
        ("environment", check_environment),
        ("bigquery", check_bigquery),
        ("tables", check_tables),
        ("read-only guard", check_read_only_guard),
        ("gemini", check_gemini),
        ("langsmith", check_langsmith),
        ("agent", check_agent),
    ]

    results = {}

    for name, check in checks:
        try:
            results[name] = check()
        except Exception as exc:
            print(f"{FAIL} {name} raised {type(exc).__name__}: {exc}")
            results[name] = False

    _header("Summary")
    failed = [name for name, ok in results.items() if not ok]

    for name, ok in results.items():
        print(f"  {PASS if ok else FAIL} {name}")

    if failed:
        print(f"\n{len(failed)} check(s) failed: {', '.join(failed)}")
        return 1

    print("\nAll checks passed - backend is wired up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
