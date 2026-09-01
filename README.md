# D'grafy Insight Agent

A natural-language interface to the client's BigQuery demographic data. Users
ask questions in plain English and get text-based insights, powered by Gemini,
LangChain and Streamlit.

```
Streamlit  ->  agent.service  ->  LangChain SQL agent (Gemini)  ->  BigQuery  ->  text answer
```

## Tech stack

| Layer | Tool |
| --- | --- |
| Data | Google BigQuery - one master view plus a customer table. Identifiers are configured in `.env`, never committed. |
| LLM | Gemini 2.5 Flash-Lite |
| Framework | LangChain SQL agent |
| Frontend | Streamlit |
| Observability | LangSmith |

## Setup (under 5 minutes)

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env             # then fill in the values
```

Put the BigQuery service account JSON somewhere gitignored (`secrets/` is
already ignored) and point `GOOGLE_APPLICATION_CREDENTIALS` at it.

Verify every connection before writing any code:

```bash
python -m scripts.check_connections
```

Then run the app:

```bash
streamlit run app.py
```

## Project structure

```
Insights_Chat_Agent_D-grafy/
├── app.py                        # Streamlit entry point (thin; Frontend owns this)
├── config.py                     # Env-driven settings, single source for secrets
├── agent/
│   ├── service.py                # Application layer - the UI's only entry point
│   ├── sql_agent.py              # LangChain SQL agent + Gemini wiring
│   ├── prompts.py                # System prompt + few-shot examples
│   └── tools.py                  # Result formatting, SQL extraction
├── auth/                         # RBAC + tier lookup (Week 2)
├── db/
│   ├── bigquery_client.py        # BigQuery wrapper + read-only guard
│   └── schema.py                 # Data dictionary: tables, KPI mappings, tiers
├── eval/                         # Golden dataset + LLM judge (Week 3)
├── scripts/
│   ├── check_connections.py      # Smoke test: env, BigQuery, Gemini, LangSmith
│   └── explore_master_view.py    # Profiles the master view -> docs/data_profile.md
└── docs/data_profile.md          # Generated data profile
```

## Backend usage

The UI never imports LangChain directly - it calls the service layer:

```python
from agent.service import ask

result = ask("Top 3 most diverse suburbs in Victoria", user_id="user_001", tier="pro")
result.answer            # text response for the user
result.sql               # SQL the agent actually ran (for eval/debugging)
result.ok, result.error  # never raises; failures come back as ok=False
```

`ask()` never raises, so a malformed question cannot crash the Streamlit session.

## Data dictionary

The KPI name -> column mapping lives in `db/schema.py` and is the single
source of truth. `agent/prompts.py` generates the prompt's mapping block from
it, so adding a KPI alias means editing one file.

| Column | KPI | Range |
| --- | --- | --- |
| `kpi_1_val` | Prosperity Score | 0-100% |
| `kpi_2_val` | Diversity Index | 0-1 |
| `kpi_3_val` | Migration Footprint | 0-100% |
| `kpi_4_val` | Learning Level | 0-100% |
| `kpi_5_val` | Social Housing | 0-100% |
| `kpi_6_val` | Resident Equity | 0-100% |
| `kpi_7_val` | Rental Access | 0-100% |
| `kpi_8_val` | Resident Anchor | 0-100% |
| `kpi_9_val` | Household Mobility Potential | 0-1 |
| `kpi_10_val` | Young Family Indicator | 0-100% |

"Suburb" means SA2 area - `sa2_name` is the primary geographic filter.

## Security

- **This repo is public.** No client identifier (GCP project, dataset, table
  or view name) appears in source, docs or committed config. They live in
  `.env` alone. `.env.example` is deliberately blank.
- `docs/data_profile.md` is gitignored - it holds real client data.
- Secrets live in `.env` and `secrets/`, both gitignored. Never commit them.
- `db/bigquery_client.py` rejects anything that is not a single read-only
  `SELECT`/`WITH`, and rejects any table outside the two configured tables.
- The system prompt forbids destructive SQL.
- These are defence in depth. The primary control is a service account with
  only **BigQuery Data Viewer** + **Job User** on those two tables.
- Every query runs with a `maximum_bytes_billed` ceiling (`MAX_BYTES_BILLED`).

## Status - Week 1 (backend)

Built and verified:
- Project structure, `.gitignore` (`.env`, `.venv/`, `secrets/` all ignored)
- Dependencies pinned to the LangChain **0.3** line - 1.x reworked the agent
  APIs and breaks `create_sql_agent` as written in the spec
- Env-driven config layer with redacted diagnostics; a local `.env` overrides
  ambient shell variables so a stray `GOOGLE_APPLICATION_CREDENTIALS` from
  another project cannot hijack the connection
- BigQuery client with read-only + allowed-table guards and a bytes ceiling
  (verified against 10 pass/fail SQL cases, including `DROP`, stacked
  statements and off-limits tables)
- **No client identifiers in source.** GCP project, dataset and table names
  come from `.env` only - there are no defaults in code, and diagnostic output
  masks them
- Data dictionary module driving both the prompt and the eval harness
- LangChain SQL agent wired to Gemini - assembles cleanly, exposes the four
  SQL tools, and returns intermediate steps so the generated SQL is capturable
- Application layer `agent.service.ask()` - verified it never raises, and
  attaches user/tier metadata to every LangSmith trace
- Streamlit app boots headless and serves (HTTP 200)
- Connection smoke test and master-view exploration script

Blocked on credentials (spec 11A) - the code is written and import-clean, but
these checks cannot go green until the keys land:
- BigQuery service account JSON (Data Viewer + Job User on the two tables)
- Gemini 2.5 Flash-Lite API key
- LangSmith API key

Next (Week 2):
- Run `python -m scripts.explore_master_view` and correct the state literals in
  `agent/prompts.py` if the column holds abbreviations rather than full names
- Expand to 5-10 tuned few-shot examples
- Implement RBAC tier lookup in `auth/` (limits already in `db/schema.py`)
