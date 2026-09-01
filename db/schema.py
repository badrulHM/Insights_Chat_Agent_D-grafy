"""Single source of truth for the client's schema (spec section 2).

Prompts, the SQL safety guard and the exploration script all read from here so
the KPI mapping is defined exactly once.

No project, dataset or table name is hardcoded - they are assembled from
environment settings so this file is safe to publish.
"""

from config import settings

# --- Fully qualified table references -------------------------------------

MASTER_VIEW = ".".join(
    (
        settings.bigquery_project,
        settings.bigquery_dataset,
        settings.bigquery_master_table,
    )
)
CUSTOMERS_TABLE = ".".join(
    (
        settings.bigquery_project,
        settings.bigquery_ref_dataset,
        settings.bigquery_customers_table,
    )
)

# The agent must never touch anything else (spec section 10).
ALLOWED_TABLES = (MASTER_VIEW, CUSTOMERS_TABLE)

# --- Geographic columns (spec 2.1) ----------------------------------------

GEO_COLUMNS = {
    "sa2_code": "Statistical Area Level 2 code (finest geography)",
    "sa2_name": 'SA2 name - the "suburb" level users will query by',
    "sa3_code": "Statistical Area Level 3 code (group of suburbs)",
    "sa3_name": "Statistical Area Level 3 name",
    "sa4_code": "Statistical Area Level 4 code (broader region)",
    "sa4_name": "Statistical Area Level 4 name",
    "gcca_code": "Greater Capital City Area code",
    "gcca_name": "Greater Capital City Area name (e.g. Greater Sydney)",
    "state": "Australian state/territory",
    "area": "Geographic area (sq km)",
}

# --- KPI dictionary (spec 2.2) --------------------------------------------
# `aliases` are the natural-language phrases the few-shot prompt must map onto
# the column. Extend these as real user questions come in.

KPIS = [
    {
        "column": "kpi_1_val",
        "name": "Prosperity Score",
        "range": "0-100%",
        "aliases": ["prosperity score", "advantage", "socio-economic advantage"],
        "description": (
            "Relative advantage/disadvantage of households based on income, "
            "occupation, education and housing. Higher = greater advantage."
        ),
    },
    {
        "column": "kpi_2_val",
        "name": "Diversity Index",
        "range": "0-1",
        "aliases": ["diversity index", "cultural diversity", "diverse"],
        "description": (
            "Cultural diversity based on ancestry distribution. Close to 1 = "
            "very diverse; close to 0 = homogeneous."
        ),
    },
    {
        "column": "kpi_3_val",
        "name": "Migration Footprint",
        "range": "0-100%",
        "aliases": ["migration footprint", "migration", "overseas-born parents"],
        "description": (
            "% of residents with at least one parent born overseas. Proxy for "
            "migration-driven demand."
        ),
    },
    {
        "column": "kpi_4_val",
        "name": "Learning Level",
        "range": "0-100%",
        "aliases": ["learning level", "education", "year 12 completion"],
        "description": "% of residents who completed Year 12 (high school).",
    },
    {
        "column": "kpi_5_val",
        "name": "Social Housing",
        "range": "0-100%",
        "aliases": ["social housing", "public housing", "community housing"],
        "description": (
            "% of public or community housing. Very high values suggest "
            "socio-economic disadvantage."
        ),
    },
    {
        "column": "kpi_6_val",
        "name": "Resident Equity",
        "range": "0-100%",
        "aliases": ["resident equity", "home ownership", "owner occupied"],
        "description": (
            "% of dwellings owned outright or with a mortgage. Higher "
            "ownership = greater stability, lower transience."
        ),
    },
    {
        "column": "kpi_7_val",
        "name": "Rental Access",
        "range": "0-100%",
        "aliases": ["rental access", "affordability", "affordable rent"],
        "description": (
            "% of dwellings renting below $450/week. Indicates affordability "
            "for renters."
        ),
    },
    {
        "column": "kpi_8_val",
        "name": "Resident Anchor",
        "range": "0-100%",
        "aliases": ["resident anchor", "stability", "stayed 5+ years"],
        "description": (
            "% of residents who stayed in the same community for 5+ years. "
            "Higher = lower turnover."
        ),
    },
    {
        "column": "kpi_9_val",
        "name": "Household Mobility Potential",
        "range": "0-1",
        "aliases": ["household mobility", "mobility potential"],
        "description": (
            "Proportion of households in transitional socioeconomic positions "
            "(Q2+Q3). Indicates potential for socioeconomic change."
        ),
    },
    {
        "column": "kpi_10_val",
        "name": "Young Family Indicator",
        "range": "0-100%",
        "aliases": ["young family", "children", "families with kids"],
        "description": (
            "% of the population aged 0-14. 20%+ = strong young family "
            "presence; <10% = urban or aging."
        ),
    },
]

KPI_VALUE_COLUMNS = [kpi["column"] for kpi in KPIS]

# kpi_1_ind .. kpi_8_ind are indicator/index versions (spec 2.2). Queryable,
# but the _val columns are the primary metrics.
KPI_INDICATOR_COLUMNS = [f"kpi_{n}_ind" for n in range(1, 9)]

# --- Customer table (spec 2.3) --------------------------------------------

CUSTOMER_COLUMNS = {
    "user_id": "Primary key. Dummy IDs like user_001 for the prototype.",
    "email": "User email address.",
    "tier": "One of: free, basic, pro. Determines question limit.",
    "is_active": "Account enabled flag. Deny login if FALSE.",
    "created_at": "Account creation timestamp.",
    "updated_at": "Last modified timestamp.",
}

TIER_QUESTION_LIMITS = {"free": 5, "basic": 20, "pro": 50}


def kpi_mapping_lines():
    """Render the KPI mapping block used by the agent's system prompt."""
    lines = ['- "suburb" or "area" = sa2_name', '- "state" = state']

    for kpi in KPIS:
        aliases = " or ".join(f'"{alias}"' for alias in kpi["aliases"][:2])
        lines.append(f'{"- "}{aliases} = {kpi["column"]} ({kpi["range"]})')

    return "\n".join(lines)
