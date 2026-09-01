"""Week 1 deliverable

    python -m scripts.explore_master_view

Answers the questions the spec asks us to settle in Week 1 (section 8):
row/SA2 counts, the *actual* state values ('Victoria' vs 'VIC'), KPI ranges,
and null patterns. The output file is what the few-shot prompt gets tuned
against in Week 2.
"""

import sys
from datetime import datetime, timezone

from db.bigquery_client import run_query
from db.schema import KPI_VALUE_COLUMNS, KPIS, MASTER_VIEW


def row_counts():
    sql = f"""
    SELECT
      COUNT(*) AS total_rows,
      COUNT(DISTINCT sa2_code) AS distinct_sa2_codes,
      COUNT(DISTINCT sa2_name) AS distinct_sa2_names,
      COUNT(DISTINCT state) AS distinct_states
    FROM {MASTER_VIEW}
    """
    return run_query(sql, max_rows=1)[0]


def state_values():
    """The important one - are states spelled out or abbreviated?"""
    sql = f"""
    SELECT state, COUNT(*) AS sa2_count
    FROM {MASTER_VIEW}
    GROUP BY state
    ORDER BY sa2_count DESC
    """
    return run_query(sql, max_rows=50)


def kpi_profile():
    """Min/max/avg plus null count for every kpi_N_val column."""
    parts = []

    for column in KPI_VALUE_COLUMNS:
        parts.append(
            f"MIN({column}) AS {column}_min, "
            f"MAX({column}) AS {column}_max, "
            f"AVG({column}) AS {column}_avg, "
            f"COUNTIF({column} IS NULL) AS {column}_nulls"
        )

    sql = f"SELECT {', '.join(parts)} FROM {MASTER_VIEW}"
    return run_query(sql, max_rows=1)[0]


def geo_nulls():
    sql = f"""
    SELECT
      COUNTIF(sa2_name IS NULL) AS sa2_name_nulls,
      COUNTIF(state IS NULL) AS state_nulls,
      COUNTIF(gcca_name IS NULL) AS gcca_name_nulls,
      COUNTIF(area IS NULL) AS area_nulls
    FROM {MASTER_VIEW}
    """
    return run_query(sql, max_rows=1)[0]


def sample_rows():
    sql = f"""
    SELECT sa2_name, state, kpi_1_val, kpi_2_val, kpi_10_val
    FROM {MASTER_VIEW}
    WHERE sa2_name IS NOT NULL
    LIMIT 5
    """
    return run_query(sql, max_rows=5)


def _fmt(value):
    if value is None:
        return "-"

    if isinstance(value, float):
        return f"{value:,.4f}"

    if isinstance(value, int):
        return f"{value:,}"

    return str(value)


def build_report():
    counts = row_counts()
    states = state_values()
    kpis = kpi_profile()
    nulls = geo_nulls()
    samples = sample_rows()

    total = counts["total_rows"] or 0
    lines = [
        "# Master view - data profile",
        "",
        "> **CONFIDENTIAL - client data. Gitignored; do not commit or publish.**",
        "> Share with the team through an approved private channel only.",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Source: `{MASTER_VIEW}`",
        "",
        "## Row counts",
        "",
        f"- Total rows: **{_fmt(counts['total_rows'])}**",
        f"- Distinct sa2_code: **{_fmt(counts['distinct_sa2_codes'])}**",
        f"- Distinct sa2_name: **{_fmt(counts['distinct_sa2_names'])}**",
        f"- Distinct state: **{_fmt(counts['distinct_states'])}**",
        "",
        "## State values",
        "",
        "These are the literals the few-shot prompt must use in WHERE clauses.",
        "",
        "| state | sa2 count |",
        "| --- | --- |",
    ]

    for row in states:
        lines.append(f"| {row['state']} | {_fmt(row['sa2_count'])} |")

    lines += [
        "",
        "## KPI ranges and nulls",
        "",
        "| Column | KPI | Documented range | Actual min | Actual max | Mean | Nulls | Null % |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for kpi in KPIS:
        column = kpi["column"]
        null_count = kpis.get(f"{column}_nulls") or 0
        null_pct = (null_count / total * 100) if total else 0

        lines.append(
            f"| `{column}` | {kpi['name']} | {kpi['range']} | "
            f"{_fmt(kpis.get(column + '_min'))} | {_fmt(kpis.get(column + '_max'))} | "
            f"{_fmt(kpis.get(column + '_avg'))} | {_fmt(null_count)} | {null_pct:.1f}% |"
        )

    lines += [
        "",
        "## Geographic nulls",
        "",
        "| Column | Nulls |",
        "| --- | --- |",
    ]

    for key, value in nulls.items():
        lines.append(f"| `{key.replace('_nulls', '')}` | {_fmt(value)} |")

    lines += ["", "## Sample rows", ""]

    if samples:
        columns = list(samples[0].keys())
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join("---" for _ in columns) + " |")

        for row in samples:
            lines.append("| " + " | ".join(_fmt(row[c]) for c in columns) + " |")

    lines += [
        "",
        "## Follow-ups for Week 2",
        "",
        "- Confirm the state literals above match `agent/prompts.py`; correct the",
        "  few-shot examples if the column holds abbreviations.",
        "- Flag any KPI whose actual range differs from the documented range -",
        "  e.g. a 0-100% KPI that actually stores 0-1.",
        "- Decide how to handle KPIs with a high null rate in generated SQL.",
        "",
    ]

    return "\n".join(lines)


def main():
    try:
        report = build_report()
    except Exception as exc:
        print(f"Exploration failed: {type(exc).__name__}: {exc}")
        print("Run `python -m scripts.check_connections` first.")
        return 1

    output_path = "docs/data_profile.md"

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(report)

    print(report)
    print(f"\nWritten to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
