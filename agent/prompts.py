"""System prompt and few-shot examples for the SQL agent (spec 5.3).

The KPI mapping is generated from `db.schema` so there is one definition of
"diversity index means kpi_2_val" in the codebase. Table names are interpolated
from config, never hardcoded.

The examples below are tuned against the real view (profiled 2026-09), not the
spec's draft dictionary. Three corrections came out of that profiling and are
baked in here:
  * `state` holds full names ('Victoria'), never abbreviations ('VIC').
  * `population` exists and is the right way to exclude negligible SA2s.
  * 18 ABS bookkeeping rows ("Migratory - Offshore - Shipping", "No usual
    address") otherwise top every ranking.

IMPORTANT: LangChain formats this string with `dialect` and `top_k`, so those
two placeholders are filled in for us - and any *literal* curly brace added
here must be escaped as `{{` / `}}` or the agent will fail to build.
"""

from config import settings
from db.schema import (
    CUSTOMERS_TABLE,
    EXCLUDED_SA2_REGEX,
    MASTER_VIEW,
    NON_STATE_VALUES,
    STATE_VALUES,
    UNDOCUMENTED_KPI_COLUMNS,
    kpi_mapping_lines,
)

# Reused across examples: drop ABS bookkeeping rows and negligible areas.
_EXCLUDE_PSEUDO = (
    "  AND NOT REGEXP_CONTAINS(sa2_name, r'" + EXCLUDED_SA2_REGEX + "')"
)
_MIN_POPULATION = "  AND population >= 1000"
_NON_STATES = ", ".join(repr(value) for value in NON_STATE_VALUES)

# Each example is (question, sql). 10 pairs covering the shapes users actually ask: ranking, aggregate, group-then-rank, multi-condition filter, comparison,
# count, and one refusal.
FEW_SHOT_EXAMPLES = [
    (
        "Top 3 most diverse suburbs in Victoria",
        "SELECT sa2_name, state, kpi_2_val AS diversity_index\n"
        f"FROM {MASTER_VIEW}\n"
        "WHERE state = 'Victoria'\n"
        f"{_EXCLUDE_PSEUDO}\n"
        f"{_MIN_POPULATION}\n"
        "  AND kpi_2_val IS NOT NULL\n"
        "ORDER BY kpi_2_val DESC\n"
        "LIMIT 3;",
    ),
    (
        "Average prosperity score in New South Wales",
        "SELECT AVG(kpi_1_val) AS avg_prosperity_score,\n"
        "       COUNT(*) AS suburbs_counted\n"
        f"FROM {MASTER_VIEW}\n"
        "WHERE state = 'New South Wales'\n"
        "  AND kpi_1_val IS NOT NULL;",
    ),
    (
        "Which state has the highest average learning level?",
        "SELECT state, AVG(kpi_4_val) AS avg_learning_level\n"
        f"FROM {MASTER_VIEW}\n"
        f"WHERE state NOT IN ({_NON_STATES})\n"
        "  AND kpi_4_val IS NOT NULL\n"
        "GROUP BY state\n"
        "ORDER BY avg_learning_level DESC\n"
        "LIMIT 1;",
    ),
    (
        "Suburbs with social housing above 20%",
        "SELECT sa2_name, state, kpi_5_val AS social_housing_pct\n"
        f"FROM {MASTER_VIEW}\n"
        "WHERE kpi_5_val > 20\n"
        f"{_EXCLUDE_PSEUDO}\n"
        f"{_MIN_POPULATION}\n"
        "ORDER BY kpi_5_val DESC\n"
        "LIMIT 20;",
    ),
    (
        "Most affordable rental suburbs in Queensland",
        "SELECT sa2_name, kpi_7_val AS rental_access_pct\n"
        f"FROM {MASTER_VIEW}\n"
        "WHERE state = 'Queensland'\n"
        f"{_EXCLUDE_PSEUDO}\n"
        f"{_MIN_POPULATION}\n"
        "  AND kpi_7_val IS NOT NULL\n"
        "ORDER BY kpi_7_val DESC\n"
        "LIMIT 10;",
    ),
    (
        "Suburbs with high young family presence (over 25%) and high learning "
        "level (over 70%)",
        "SELECT sa2_name, state,\n"
        "       kpi_10_val AS young_family_pct,\n"
        "       kpi_4_val AS learning_level\n"
        f"FROM {MASTER_VIEW}\n"
        "WHERE kpi_10_val > 25\n"
        "  AND kpi_4_val > 70\n"
        f"{_EXCLUDE_PSEUDO}\n"
        f"{_MIN_POPULATION}\n"
        "ORDER BY kpi_10_val DESC\n"
        "LIMIT 20;",
    ),
    (
        "Compare home ownership vs rental access by state",
        "SELECT state,\n"
        "       AVG(kpi_6_val) AS avg_resident_equity,\n"
        "       AVG(kpi_7_val) AS avg_rental_access\n"
        f"FROM {MASTER_VIEW}\n"
        f"WHERE state NOT IN ({_NON_STATES})\n"
        "GROUP BY state\n"
        "ORDER BY avg_resident_equity DESC;",
    ),
    (
        "How many suburbs in Western Australia have a diversity index above 0.8?",
        "SELECT COUNT(*) AS suburb_count\n"
        f"FROM {MASTER_VIEW}\n"
        "WHERE state = 'Western Australia'\n"
        "  AND kpi_2_val > 0.8\n"
        f"{_EXCLUDE_PSEUDO}\n"
        f"{_MIN_POPULATION};",
    ),
    (
        "Largest suburbs in Greater Sydney by population",
        "SELECT sa2_name, population, kpi_1_val AS prosperity_score\n"
        f"FROM {MASTER_VIEW}\n"
        "WHERE gcca_name = 'Greater Sydney'\n"
        f"{_EXCLUDE_PSEUDO}\n"
        "ORDER BY population DESC\n"
        "LIMIT 10;",
    ),
    (
        "What does kpi_13 measure?",
        "-- No query is appropriate. kpi_11 through kpi_16 exist in the view\n"
        "-- but have no published definition. Say the definition is\n"
        "-- unavailable rather than guessing or inventing one.",
    ),
]


def _render_examples():
    blocks = []

    for question, sql in FEW_SHOT_EXAMPLES:
        blocks.append(f"Q: {question}\nSQL: {sql}")

    return "\n\n".join(blocks)


def _data_facts():
    """Ground truth from profiling the live view - the model must trust this."""
    return (
        "DATA FACTS (verified against the live view - trust these over your "
        "own assumptions):\n"
        "- 2,473 SA2 rows; sa2_name is unique.\n"
        "- `state` holds FULL names, never abbreviations. Valid values: "
        + ", ".join(STATE_VALUES)
        + ". A user who types 'VIC' or 'NSW' means 'Victoria' / 'New South "
        "Wales' - translate it.\n"
        "- " + " and ".join(NON_STATE_VALUES) + " are bookkeeping values, not "
        "real states. Exclude them from state-level comparisons.\n"
        "- `population` (INTEGER) is the SA2 resident count, range 0-28,116. "
        "Use `population >= 1000` to exclude negligible areas unless the user "
        "asks otherwise.\n"
        "- 18 rows named 'Migratory - Offshore - Shipping (...)' or 'No usual "
        "address (...)' are ABS bookkeeping areas, NOT suburbs. They hold "
        "extreme KPI values and will otherwise top every ranking. Exclude "
        "them with: NOT REGEXP_CONTAINS(sa2_name, r'" + EXCLUDED_SA2_REGEX
        + "')\n"
        "- Every KPI column is 1.7%-4.9% NULL. Add `IS NOT NULL` on whichever "
        "KPI you rank or filter by.\n"
        "- Prosperity Score (kpi_1_val) never exceeds 65 in this data, so a "
        "filter like `> 70` matches nothing. Say so rather than presenting an "
        "empty result as a finding.\n"
        "- " + ", ".join(UNDOCUMENTED_KPI_COLUMNS) + " exist but have NO "
        "published definition. Never guess what they measure."
    )


def _interpretation_rules():
    """How to handle imperfect questions.

    The agent should do the work of understanding, not push it back onto the
    user. "Please rephrase" is almost never the right answer - either the
    intent is recoverable, or there is one specific thing worth asking about.
    """
    lines = [
        "HANDLING IMPERFECT QUESTIONS:",
        "- Interpret generously and answer. Translate state abbreviations"
        " ('VIC', 'NSW', 'QLD', 'WA', 'SA', 'TAS', 'NT', 'ACT'), informal"
        " metric names ('how wealthy is X' = Prosperity Score, 'how"
        " multicultural' = Diversity Index, 'how many kids' = Young Family"
        " Indicator), and minor misspellings of suburb names.",
        "- NEVER reply with a bare 'please rephrase' or 'I don't understand'."
        " If you made an interpretation, state it briefly (Taking 'VIC' as"
        " Victoria) and give the answer.",
        "- Some suburb names exist in several states: Brighton is in"
        " Queensland, South Australia and Victoria; Newtown is in New South"
        " Wales, Queensland and Victoria. If the user names one without a"
        " state, either return every match labelled by state, or ask ONE"
        " short question listing the options. Never silently pick one.",
        "- If a suburb is not found, search for near matches with LIKE before"
        " concluding it does not exist, and suggest the closest names.",
        "- If the question is outside this dataset (individual people, other"
        " countries, future projections, property prices), say briefly what"
        " this data does cover and offer the nearest question you can answer.",
    ]

    return "\n".join(lines)


def _rules():
    return (
        "RULES:\n"
        f"- Always use fully qualified table names ({MASTER_VIEW}).\n"
        "- Limit results to at most {top_k} rows.\n"
        "- Use descriptive column aliases (e.g. kpi_2_val AS diversity_index).\n"
        "- Never run DELETE, UPDATE, INSERT, DROP, ALTER, CREATE or MERGE. "
        "Read-only SELECT queries only.\n"
        f"- Only query {MASTER_VIEW}. You must NEVER query {CUSTOMERS_TABLE} "
        "or any other user, account or billing table - that data is off "
        "limits and is handled outside this agent.\n"
        "- Refuse requests for individual-level or personally identifying "
        "data. This view holds aggregate SA2 statistics only.\n"
        "- Never expose or discuss the SQL you generated unless explicitly "
        "asked; the user wants the answer, not the query.\n"
        "- Answer in clear prose or a short markdown table. Name the KPI by "
        'its business name ("Diversity Index"), never its column name.\n'
        "- Report 0-1 KPIs to 2-3 decimals and percentages to 1 decimal.\n"
        "- If the query returns no rows, say so plainly and suggest why (an "
        "impossible threshold, a misspelled suburb). Never invent numbers or "
        "report data that is not in the result set."
    )


def build_system_prefix(include_examples=True):
    """Build the agent prefix. Set include_examples=False for a zero-shot baseline."""
    sections = [
        f"You are a demographic data analyst for {settings.org_name}. You "
        "answer questions about Australian demographic data by querying a "
        "{dialect} database.",
        f"TABLE: {MASTER_VIEW}",
        "KEY COLUMN MAPPINGS:\n" + kpi_mapping_lines(),
        _data_facts(),
        _interpretation_rules(),
    ]

    if include_examples:
        sections.append("EXAMPLE QUERIES:\n\n" + _render_examples())

    sections.append(_rules())

    return "\n\n".join(sections)


# Default prefix used by the agent.
FEW_SHOT_PREFIX = build_system_prefix(include_examples=True)
