"""System prompt and few-shot examples for the SQL agent (spec 5.3).

The KPI mapping is generated from `db.schema` so there is one definition of
"diversity index means kpi_2_val" in the codebase.

"""

from config import settings
from db.schema import CUSTOMERS_TABLE, MASTER_VIEW, kpi_mapping_lines


# Each example is (question, sql). Keep them short and schema-accurate.
FEW_SHOT_EXAMPLES = [
    (
        "Top 3 most diverse suburbs in Victoria",
        f"SELECT sa2_name, kpi_2_val AS diversity_index\n"
        f"FROM {MASTER_VIEW}\n"
        f"WHERE state = 'Victoria'\n"
        f"ORDER BY kpi_2_val DESC LIMIT 3;",
    ),
    (
        "Average prosperity score in New South Wales",
        f"SELECT AVG(kpi_1_val) AS avg_prosperity_score\n"
        f"FROM {MASTER_VIEW}\n"
        f"WHERE state = 'New South Wales';",
    ),
    (
        "Suburbs with high young family presence (over 25%) and high learning "
        "level (over 70%)",
        f"SELECT sa2_name, state, kpi_10_val AS young_family_pct,\n"
        f"       kpi_4_val AS learning_level\n"
        f"FROM {MASTER_VIEW}\n"
        f"WHERE kpi_10_val > 25 AND kpi_4_val > 70\n"
        f"ORDER BY kpi_10_val DESC LIMIT 20;",
    ),
    (
        "Most stable suburbs (highest resident anchor) in QLD",
        f"SELECT sa2_name, kpi_8_val AS resident_anchor\n"
        f"FROM {MASTER_VIEW}\n"
        f"WHERE state = 'Queensland'\n"
        f"ORDER BY kpi_8_val DESC LIMIT 10;",
    ),
    (
        "Compare home ownership vs rental access by state",
        f"SELECT state,\n"
        f"       AVG(kpi_6_val) AS avg_resident_equity,\n"
        f"       AVG(kpi_7_val) AS avg_rental_access\n"
        f"FROM {MASTER_VIEW}\n"
        f"GROUP BY state ORDER BY avg_resident_equity DESC;",
    ),
]


def _render_examples():
    blocks = []

    for question, sql in FEW_SHOT_EXAMPLES:
        blocks.append(f"Q: {question}\nSQL: {sql}")

    return "\n\n".join(blocks)


def build_system_prefix(include_examples=True):
    """Build the agent prefix. Set include_examples=False for a zero-shot baseline."""
    sections = [
        f"You are a demographic data analyst for {settings.org_name}. You "
        "answer questions about Australian demographic data by querying a "
        "{dialect} database.",
        f"TABLE: {MASTER_VIEW}",
        "KEY COLUMN MAPPINGS:\n" + kpi_mapping_lines(),
    ]

    if include_examples:
        sections.append("EXAMPLE QUERIES:\n\n" + _render_examples())

    sections.append(
        "RULES:\n"
        f"- Always use fully qualified table names ({MASTER_VIEW}).\n"
        "- Limit results to at most {top_k} rows.\n"
        "- Use descriptive column aliases (e.g. kpi_2_val AS diversity_index).\n"
        "- Never run DELETE, UPDATE, INSERT, DROP, ALTER, CREATE or MERGE. "
        "Read-only SELECT queries only.\n"
        f"- Only query {MASTER_VIEW} and {CUSTOMERS_TABLE}. Refuse any request "
        "that needs another table.\n"
        "- Never expose or discuss the SQL you generated unless explicitly "
        "asked; the user wants the answer, not the query.\n"
        "- Answer in clear prose or a short markdown table. State the KPI by "
        'its business name ("Diversity Index"), not its column name.\n'
        "- If the query returns no rows, say so plainly instead of inventing "
        "numbers. Never fabricate data that is not in the result set."
    )

    return "\n\n".join(sections)


# Default prefix used by the agent.
FEW_SHOT_PREFIX = build_system_prefix(include_examples=True)
