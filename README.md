# D'grafy Insight Agent

A natural-language interface to the client's BigQuery demographic data. Users
ask questions in plain English and get text-based insights, powered by Gemini,
LangChain and Streamlit.

```
Streamlit  ->  agent.service  ->  LangChain SQL agent (Gemini)  ->  BigQuery  ->  text answer
                    ^
                auth.rbac  ->  customer table (tier lookup, never via the LLM)
```

## Tech stack

| Layer | Tool |
| --- | --- |
| Data | Google BigQuery - one master view plus a customer table. Identifiers are configured in `.env`, never committed. |
| LLM | Gemini (model set by `GEMINI_MODEL`) |
| Framework | LangChain 1.x `create_agent` + `SQLDatabaseToolkit` |
| Frontend | Streamlit |
| Observability | LangSmith |

## Setup (under 5 minutes)

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env             # then fill in the values
```

For credentials, either point `GOOGLE_APPLICATION_CREDENTIALS` at a service
account JSON in the gitignored `secrets/`, or leave it blank and use your own
login:

```bash
gcloud auth application-default login
```

Verify everything before writing any code:

```bash
python -m scripts.check_connections
```

Then run the app:

```bash
streamlit run app.py
```

## Which tables do we use?

**Both datasets, but through completely separate paths.** This is a security
boundary, not an implementation detail.

| Table | Reached by | How |
| --- | --- | --- |
| `<project>.<prod_dataset>.<master_view>` | The **LLM agent** | LangChain generates SQL against it |
| `<project>.<ref_dataset>.<customers>` | The **auth layer only** | Hand-written parameterised query in `auth/users.py` |

The agent's `SQLDatabase` is built with `include_tables=[master_view]`, so
schema introspection cannot even *see* the customer table - no prompt can
coax it into reading user records. The system prompt forbids it explicitly as
a second layer, and `db/bigquery_client.py` rejects any query touching a table
outside the allowed pair as a third.

The customer table is queried directly through the BigQuery client with
`user_id` bound as a named parameter, so login input can never be parsed as
SQL.

## Project structure

```
Insights_Chat_Agent_D-grafy/
├── app.py                        # Streamlit entry point (thin; Frontend owns this)
├── config.py                     # Env-driven settings, single source for secrets
├── agent/
│   ├── service.py                # Application layer - the UI's only entry point
│   ├── sql_agent.py              # LangChain agent + Gemini wiring
│   ├── prompts.py                # System prompt + 10 few-shot examples
│   └── tools.py                  # Result formatting, SQL extraction
├── auth/
│   ├── users.py                  # User lookup + ID validation
│   └── rbac.py                   # Tier policy and question quotas
├── db/
│   ├── bigquery_client.py        # BigQuery wrapper + read-only guard
│   └── schema.py                 # Data dictionary: tables, KPIs, tiers
├── eval/                         # Golden dataset + LLM judge (Eval/QA teammate)
├── scripts/
│   ├── check_connections.py      # 8-step smoke test
│   └── explore_master_view.py    # Profiles the master view -> docs/data_profile.md
└── docs/data_profile.md          # Generated data profile (gitignored)
```

## Backend usage

The UI never imports LangChain directly. Two entry points:

**Asking a question**

```python
from agent.service import ask

result = ask("Top 3 most diverse suburbs in Victoria",
             user_id="user_001", tier="pro")

result.answer       # text response for the user
result.sql          # SQL the agent actually ran (for eval/debugging)
result.trace_url    # deep link to this question's LangSmith trace
result.ok           # never raises; failures come back as ok=False
```

**Login and quotas**

```python
from auth.rbac import authenticate, check_quota

auth = authenticate(user_id_from_login_box)
if not auth.ok:
    show_error(auth.error)          # auth.reason is a stable code to branch on
else:
    tier = auth.user.tier           # 'free' | 'basic' | 'pro'

quota = check_quota(tier, st.session_state.questions_used)
quota.allowed        # False once the tier limit is hit
quota.remaining      # for the sidebar counter
quota.should_warn    # True at 15 (basic) / 45 (pro)
quota.message        # ready-to-display warning or upgrade prompt
```

**Failure handling**

`ask()` never raises. On failure it returns `ok=False` plus a stable `reason`
code the UI can branch on, and a message that is honest about whose problem it
is - telling a user to "rephrase" when BigQuery is down blames them for our
outage and sends them into a pointless retry loop.

| `reason` | Cause | Suggested UI |
| --- | --- | --- |
| `rate_limited` | Gemini quota / 429 | Retry button |
| `model_unavailable` | Model 404 / misconfigured | Tell the team; retry won't help |
| `data_unavailable` | BigQuery unreachable or denied | Retry shortly |
| `too_complex` | Hit the recursion cap | Suggest splitting the question |
| `no_answer` | Agent ran but produced no text | Suggest a specific metric + area |
| `unknown` | Anything else | Generic apology |

The agent itself is instructed never to answer "please rephrase". It
translates abbreviations (`VIC`, `NSW`), informal metric names ("how wealthy" =
Prosperity Score), and misspellings; and where a name is genuinely ambiguous -
Brighton exists in Qld, SA and Vic - it returns every match labelled by state
rather than silently picking one.

`authenticate()` never raises - a BigQuery outage returns
`reason="lookup_failed"` so the login screen degrades instead of crashing.
RBAC holds **no session state**: the UI owns the counter and passes it in,
which keeps the rules testable without a Streamlit runtime.

| Tier | Questions / session | Warn at |
| --- | --- | --- |
| free | 5 | — |
| basic | 20 | 15 |
| pro | 50 | 45 |

## Data dictionary

The KPI mapping lives in `db/schema.py` and is the single source of truth.
`agent/prompts.py` generates the prompt's mapping block from it.

| Column | KPI | Range |
| --- | --- | --- |
| `kpi_1_val` | Prosperity Score | 0-100% (observed max 65) |
| `kpi_2_val` | Diversity Index | 0-1 |
| `kpi_3_val` | Migration Footprint | 0-100% |
| `kpi_4_val` | Learning Level | 0-100% |
| `kpi_5_val` | Social Housing | 0-100% |
| `kpi_6_val` | Resident Equity | 0-100% |
| `kpi_7_val` | Rental Access | 0-100% |
| `kpi_8_val` | Resident Anchor | 0-100% |
| `kpi_9_val` | Household Mobility Potential | 0-100 |
| `kpi_10_val` | Young Family Indicator | 0-100% |

"Suburb" means SA2 area - `sa2_name` is the primary geographic filter.

### Findings that contradict the spec

Profiling the live view (2,473 rows) turned up four things the spec's draft
dictionary gets wrong or omits. All four are now encoded in the prompt.
**Worth confirming with Demografy.**

1. **`population` exists but is undocumented.** An INTEGER column, 0-28,116.
   The spec's own example question filters on it, so it was always needed.
   143 SA2s have fewer than 1,000 residents.
2. **`kpi_9_val` is not 0-1.** Spec section 2.2 documents 0-1; the column
   actually holds 7.23-100. A prompt stating "0-1" produces thresholds that
   match nothing.
3. **KPIs 11-16 exist with real values but have no published definition.**
   The spec documents only 1-10, and `_ind` columns run to 16, not 8. The
   agent is instructed to say the definition is unavailable rather than guess.
4. **18 rows are ABS bookkeeping areas, not suburbs** - `Migratory - Offshore
   - Shipping (...)` and `No usual address (...)`. They carry extreme KPI
   values and topped every ranking before being excluded.

Also confirmed: `state` holds **full names** (`'Victoria'`, not `'VIC'`), and
`Other Territories` / `Outside Australia` are bookkeeping values rather than
real states. Every KPI column is 1.7%-4.9% NULL.

## Observability

Every question is traced to LangSmith with the asking user's ID and tier
attached as run metadata, so a trace can be tied back to who produced it.

```python
from agent.service import tracing_status
tracing_status()   # {'enabled': True, 'project': ..., 'dashboard_url': ...}
```

`ask()` returns `trace_url`, a deep link to that specific question's trace -
useful in a debug expander and for the eval report. Set
`LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` in `.env`;
`check_connections` verifies the key works rather than merely being present.

## Security

- **This repo is public.** No client identifier (GCP project, dataset, table
  or view name) appears in source, docs or committed config. They live in
  `.env` alone; `.env.example` is deliberately blank.
- `docs/data_profile.md` is gitignored - it holds real client data.
- Secrets live in `.env`, `secrets/` and `.secrets/`, all gitignored.
- The agent can only see the master view. The customer table is unreachable
  from any prompt.
- `db/bigquery_client.py` rejects anything that is not a single read-only
  `SELECT`/`WITH`, and any table outside the allowed pair.
- User input reaching SQL is always bound as a BigQuery named parameter.
- Every query runs under a `maximum_bytes_billed` ceiling.
- These are defence in depth. The primary control is a service account with
  only **BigQuery Data Viewer** + **Job User** on the two tables.

## Status

**Week 1 - foundation (done).** Config layer, BigQuery client with read-only
and allowed-table guards, data dictionary module, LangChain agent wired to
Gemini, application-layer seam, 8-step connection smoke test, master-view
profiling script.

**Week 2 - core backend features (done).**
- 10 few-shot examples tuned against the live view, encoding all four findings
  above. Verified: pseudo-suburbs excluded from rankings, `VIC` translated to
  `Victoria`, undocumented KPIs refused rather than hallucinated.
- RBAC: `user_id` login against the customer table, tier lookup, question
  quotas with per-tier warning thresholds. Inactive accounts denied.
- LangSmith tracing live, with per-question trace URLs and user/tier metadata.

**Week 3 - next.** Edge cases (malformed queries, empty results, timeouts),
then charts as a stretch goal once the text pipeline is solid.

### Known issues

- **We run `gemini-3.5-flash-lite`, not the `gemini-2.5-flash-lite` named in
  spec section 5.2.** Google has closed 2.5-flash-lite to new API keys and
  returns a 404 pointing at 3.5-flash-lite as its replacement, so the spec's
  model is simply not obtainable for keys issued now. This is a deliberate,
  approved deviation - flag it to the Lead Engineer. `GEMINI_MODEL` in `.env`
  switches models with no code change.
- LangChain **1.x is required**, not optional. The spec's 0.3-era
  `create_sql_agent` cannot be used with current Gemini models:
  langchain-google-genai 2.1.x drops Gemini's `thought_signature`, so
  replaying a tool call fails with `400 Function call is missing a
  thought_signature` - breaking every agent run, since each needs 2+ turns.
