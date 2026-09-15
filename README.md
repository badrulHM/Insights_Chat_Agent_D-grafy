# Demografy Insight Agent

A natural-language interface to Demografy's BigQuery demographic data. Users
ask questions in plain English and get text-based insights, powered by Gemini,
LangChain and Streamlit.

```
Streamlit  ->  agent.service  ->  LangChain SQL agent (Gemini)  ->  BigQuery  ->  text answer + chart
                    ^
                auth.rbac  ->  customer table (tier lookup, never via the LLM)
```

## Tech stack

| Layer | Tool |
| --- | --- |
| Data | Google BigQuery - one master view plus a customer table. Identifiers configured in `.env`, never committed. |
| LLM | Gemini (model set by `GEMINI_MODEL`) |
| Framework | LangChain 1.x `create_agent` + `SQLDatabaseToolkit` |
| Frontend | Streamlit, charts via Plotly |
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
python -m scripts.check_connections      # env, BigQuery, Gemini, LangSmith, agent, RBAC
python -m scripts.check_scope --offline  # scope boundary guards (free, no LLM)
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
schema introspection cannot even *see* the customer table. The system prompt
forbids it as a second layer, and the query guard rejects it as a third - with
the agent's allow-list narrowed to the master view alone.

The customer table is queried through the BigQuery client with `user_id` bound
as a named parameter, so login input can never be parsed as SQL.

## Project structure

```
Insights_Chat_Agent_D-grafy/
├── app.py                        # Thin Streamlit harness (sign-in, chat, chart)
├── ui_charts.py                  # Plotly rendering of a ChartSpec
├── config.py                     # Env-driven settings, single source for secrets
├── agent/
│   ├── service.py                # Application layer - the UI's only entry point
│   ├── sql_agent.py              # LangChain agent + Gemini wiring
│   ├── prompts.py                # System prompt, scope rules, 14 few-shot examples
│   ├── safe_tools.py             # Guarded replacement for the SQL query tool
│   ├── charts.py                 # Picks the visual form (renders nothing)
│   └── tools.py                  # Message flattening, SQL extraction
├── auth/
│   ├── users.py                  # User lookup + ID validation
│   └── rbac.py                   # Tier policy, quotas, live session counter
├── db/
│   ├── bigquery_client.py        # BigQuery wrapper + read-only guard
│   └── schema.py                 # Data dictionary: tables, KPIs, tiers
├── eval/
│   ├── golden_dataset.json       # 10 cases, expected values from live data
│   ├── judge.py                  # LLM-as-a-judge, 1-5 scoring
│   └── run_eval.py               # Automated runner -> docs/eval_report.md
├── scripts/
│   ├── check_connections.py      # 9-step smoke test
│   ├── check_scope.py            # Scope Boundaries compliance
│   ├── check_rbac.py             # Tier/quota walkthrough, no LLM calls
│   └── explore_master_view.py    # Profiles the master view -> docs/data_profile.md
└── docs/                         # Client documents + generated reports (gitignored)
```

## Backend usage

The UI never imports LangChain directly.

**Asking a question**

```python
from agent.service import ask

result = ask("Top 3 most diverse suburbs in Victoria",
             user_id="user_001", tier="pro", with_data=True)

result.answer       # text response for the user
result.chart        # ChartSpec, or None if a chart would not help
result.rows         # typed result rows
result.sql          # SQL the agent actually ran (eval/debugging)
result.trace_url    # deep link to this question's LangSmith trace
result.ok           # never raises; failures come back as ok=False
result.reason       # stable failure code, None when ok
```

**Login and quotas**

```python
from auth.rbac import authenticate, check_quota, SessionQuota

auth = authenticate(user_id)
if not auth.ok:
    show_error(auth.error)      # auth.reason is a stable code to branch on

quota = SessionQuota(auth.user.tier)   # store in st.session_state
quota.status().allowed                 # False once the tier limit is hit
quota.remaining, quota.fraction_used, quota.label
quota.consume()                        # call AFTER a successful answer
```

`authenticate()` never raises - a BigQuery outage returns
`reason="lookup_failed"` so login degrades instead of crashing. `check_quota`
is a pure function, so every threshold is testable without a Streamlit
runtime; `SessionQuota` is the stateful counter the UI binds to.

| Tier | Questions / session | Warn at |
| --- | --- | --- |
| free | 5 | — |
| basic | 20 | 15 |
| pro | 50 | 45 |

**Failure handling**

`ask()` never raises. On failure it returns `ok=False` plus a stable `reason`
and a message that is honest about whose problem it is - telling a user to
"rephrase" when BigQuery is down blames them for our outage.

| `reason` | Cause | Suggested UI |
| --- | --- | --- |
| `rate_limited` | Gemini quota / 429 | Retry button |
| `model_unavailable` | Model 404 / misconfigured | Tell the team; retry won't help |
| `data_unavailable` | BigQuery unreachable or denied | Retry shortly |
| `too_complex` | Hit the recursion cap | Suggest splitting the question |
| `no_answer` | Agent ran but produced no text | Suggest a specific metric + area |
| `unknown` | Anything else | Generic apology |

## Scope boundaries

The Scope Boundaries Document is authoritative. Compliance is enforced in two
layers and verified by a script:

```bash
python -m scripts.check_scope --offline   # guards only, free
python -m scripts.check_scope             # + live agent behaviour
```

| Scope section | How it is enforced |
| --- | --- |
| 2. Permitted tables | Guard allow-list; the agent's is the master view alone |
| 3. Permitted query types | One few-shot example per category |
| 4.1 Destructive SQL | Prompt **and** `assert_read_only` (9 statement types) |
| 4.2 Other tables | Prompt **and** `assert_allowed_tables` |
| 4.3 Individual-level data | Prompt, approved refusal wording |
| 4.4 Non-demographic questions | Prompt, approved refusal wording |
| 4.5 Predictive / causal claims | Prompt, approved refusal wording |
| 4.6 Value judgements | Prompt; KPI descriptions in `db/schema.py` also stripped of "advantage/disadvantage" language so our own dictionary does not invite it |
| 5. Row cap 50 | `MAX_RESULT_ROWS`, enforced on every fetch |
| 5. Fully qualified names | `require_qualified=True` on the agent path - a bare `a_master_view` is rejected |
| 5. Column aliases | Prompt rule |
| 6. Auth and session | `auth/rbac.py`: tier read once at sign-in and never re-read, per-session quotas, inactive accounts denied. Surfaced in the harness |
| 7. Error handling | Stable `reason` codes; unrecognised KPI triggers a clarification listing the available KPIs |
| 8. Security | Guards, named parameters, no schema exposure, no credentials in traces |
| 9. Charts | Bar, column and table only, via `st.plotly_chart` / `st.dataframe`. No maps, heatmaps or dashboards. Text always primary |
| 10. Refusal wording | `REFUSALS` in `agent/prompts.py`, verbatim from the document |

Last run: **offline 6/6, live 7/7**, with the approved refusal wording on
sections 4.2, 4.3, 4.4 and 4.5.

**Prompt rules are not controls.** Sections 4.1, 4.2 and 5 are enforced in code
as well, and the offline checks are what prove it - a model can be talked out
of a prompt rule, but not out of the query guard.

## Data dictionary

The KPI mapping lives in `db/schema.py` and is the single source of truth;
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
| `kpi_9_val` | Household Mobility Potential | **0-100** (spec says 0-1) |
| `kpi_10_val` | Young Family Indicator | 0-100% |

"Suburb" means SA2 area - `sa2_name` is the primary geographic filter.
Descriptions are deliberately factual: scope 4.6 forbids the bot from
characterising areas as advantaged or disadvantaged, so our own dictionary
does not use that language either.

### Findings that contradict the spec

Profiling the live view (2,473 rows) turned up four things the spec's draft
dictionary gets wrong or omits. All four are encoded in the prompt.
**Worth confirming with Demografy.**

1. **`population` exists but is undocumented.** INTEGER, 0-28,116. The spec's
   own example question filters on it. 143 SA2s have fewer than 1,000
   residents.
2. **`kpi_9_val` is not 0-1.** The column holds 7.23-100. A prompt stating
   "0-1" produces thresholds that match nothing.
3. **KPIs 11-16 exist with real values but have no published definition.**
   `_ind` columns run to 16, not 8. The agent says the definition is
   unavailable rather than guessing.
4. **18 rows are ABS bookkeeping areas, not suburbs** - `Migratory - Offshore
   - Shipping (...)` and `No usual address (...)`. They carry extreme KPI
   values and topped every ranking before being excluded.

Also confirmed: `state` holds **full names** (`'Victoria'`, not `'VIC'`), and
`Other Territories` / `Outside Australia` are bookkeeping values rather than
real states. Every KPI column is 1.7%-4.9% NULL.

## Observability

Every question is traced to LangSmith with the asking user's ID and tier as run
metadata, so a trace ties back to who produced it. `ask()` returns `trace_url`,
a deep link to that question's trace.

```python
from agent.service import tracing_status
tracing_status()   # {'enabled': True, 'project': ..., 'dashboard_url': ...}
```

Set `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` in `.env`;
`check_connections` verifies the key works rather than merely being present.

## Evaluation

```bash
python -m eval.run_eval                 # deterministic + LLM judge
python -m eval.run_eval --no-judge      # deterministic only, no LLM cost
python -m eval.run_eval --case 1 --case 7
```

Every case is checked twice: deterministically against ground truth computed
from the database, and by an LLM judge scored 1-5. The deterministic check
decides pass/fail; the judge adds a quality score, and disagreements are
flagged - that is usually the interesting part.

**Infrastructure failures are not wrong answers.** A rate-limited case is
recorded as `ERROR` and excluded from accuracy, because a report claiming
"3/10" when seven cases never executed sends people hunting for prompt bugs
that do not exist. The runner retries through rate limits and paces itself with
`--delay`.

Current status: **10/10 passing**, written to `docs/eval_report.md`
(gitignored - real client data). Treat it as a regression guard, not proof of
general accuracy: we chose both the questions and the expected answers.

## Frontend

`app.py` is a **thin harness**, not the product UI. It proves the pipeline
end to end - question in, text answer and chart out - and is expected to be
rebuilt by whoever owns the frontend.

It needs exactly two things from this codebase:

```python
from agent.service import ask          # answer, chart, sql, trace
from ui_charts import build_chart      # ChartSpec -> Plotly figure
```

**RBAC is wired in**, with deliberately plain widgets - a sidebar text input
to sign in, a progress bar for the question counter, and a disabled chat input
at the limit. No CSS, no custom HTML.

Sign in with a `user_id` from the customer table (`user_001` free, `user_006`
basic, `user_003` pro; `user_004` is inactive and is denied). The tier is read
once at sign-in and never re-read, so it cannot change mid-session (scope
boundaries 6). A question is only counted after it produced an answer.

`scripts/check_rbac.py` exercises the same policy without a browser or any LLM
calls.

### Charts

The backend picks the visual form from the question's intent and the shape of
the result; `ui_charts.build_chart` draws it.

| Form | Chosen when |
| --- | --- |
| Horizontal **bar** | One measure, long labels (suburb rankings) |
| Vertical **column** | One measure, up to 8 short labels (state comparisons) |
| **Grouped** bar / column | 2-3 measures on a comparable scale |
| **Stacked** bar | Measures that genuinely sum to 100% or 1 - a composition |
| **Table** | 13-50 rows, more than 3 measures, a one-row profile, duplicate labels, or scales that cannot share an axis |
| *(nothing)* | A single number - that is a sentence, not a visual - or more than 50 rows |

Stacking is only used when each row's measures actually sum to a whole.
Stacking independent percentages would invent a total that does not exist.

**Why not "every chart type":** two hard constraints, not preferences.

1. Scope section 9 permits "simple bar charts, column charts, or tables only.
   No maps, heatmaps, or complex interactive dashboards."
2. The master view has **no date, year or timestamp column** - it is a single
   snapshot. Line and area charts need a time axis and cannot be drawn from
   this data at all; section 4.5 also forbids trend claims.

Pie and donut charts are excluded for a third reason: nearly every KPI is a
percentage *within* a suburb (Social Housing is 20% of that suburb's
dwellings), so slices across suburbs would not sum to anything meaningful.

If Demografy relaxes section 9, scatter (KPI against KPI) and histogram (the
distribution of one KPI) are the two additions that would genuinely suit this
data. Both are a small change to `agent/charts.py` and `ui_charts.py`.

Rendered with **Plotly** via `st.plotly_chart`; tables use `st.dataframe`,
which gives sorting and resizing for free. `st.bar_chart` would have been
simplest but hands Vega a nominal axis which it sorts **alphabetically** - a
"top 5 suburbs" chart came out in name order, silently contradicting the
ranked list above it. Plotly lets us pin the bar order to the order the SQL
returned.

Chart colours come from the brand palette (defined in `ui_charts.py`); axis and
label colours are left to Streamlit's chart theme so they track light/dark.

**Charts cost no extra query.** The guarded query tool caches the rows it
fetched during the agent run, so `with_data=True` reuses them - one BigQuery
job per question, not two.

### Custom HTML and CSS

Any raw HTML goes through `st.html`, never
`st.markdown(unsafe_allow_html=True)`. `st.markdown` runs the string through
Markdown first, and Markdown treats any line indented 4+ spaces as a code
block - so a stylesheet written inside a function body gets *printed on the
page* as literal text instead of applied.

## Security

- **This repo is public.** No client identifier (GCP project, dataset, table or
  view name) appears in source, docs or committed config. They live in `.env`
  alone; `.env.example` is deliberately blank.
- `docs/` is gitignored - it holds client documents and generated reports
  containing real client data. So are all PDFs.
- Secrets live in `.env`, `secrets/` and `.secrets/`, all gitignored.
- **The stock SQL toolkit bypasses every guard.** `SQLDatabaseToolkit`'s
  `sql_db_query` calls `SQLDatabase.run()`, which executes SQLAlchemy directly
  and never touches `db/bigquery_client.py`; `include_tables` only limits what
  schema *introspection* reveals, not what SQL can execute. Verified: the stock
  tool happily read customer emails. `agent/safe_tools.py` replaces it with a
  guarded tool whose allow-list is the master view alone.
- The guard rejects anything that is not a single read-only `SELECT`/`WITH`,
  any table outside the allowed pair, and any unqualified table name.
- User input reaching SQL is always bound as a BigQuery named parameter.
- Every query runs under a `maximum_bytes_billed` ceiling.
- Defence in depth. The primary control is a service account with only
  **BigQuery Data Viewer** + **Job User** on the two tables.

## Status

**Week 1 - foundation (done).** Config layer, BigQuery client with read-only
and allowed-table guards, data dictionary module, LangChain agent wired to
Gemini, application-layer seam, connection smoke test, profiling script.

**Week 2 - core features (done).** Few-shot examples tuned against the live
view; RBAC with tier lookup and question quotas; LangSmith tracing with
per-question trace URLs and user/tier metadata.

**Week 3 - polish and evaluate (done).** Closed the SQL-toolkit security hole;
golden dataset + automated runner + LLM judge (10/10); honest error
classification; chart suggestion; live question counter; RBAC walkthrough tool.

**Scope compliance (done).** Every section of the Scope Boundaries Document is
covered, with `scripts/check_scope.py` proving it.

**Frontend.** `app.py` is a thin harness: sign-in, chat, text answer, chart or
table, question counter, and a dev toggle for the generated SQL. Plain widgets
only - styling and branding are for whoever rebuilds the UI.

### Known issues

- **We run `gemini-3.5-flash-lite`, not the `gemini-2.5-flash-lite` named in
  the spec.** Google has closed 2.5-flash-lite to new API keys and returns a
  404 pointing at 3.5-flash-lite as its replacement. Deliberate, approved
  deviation - flag it to the Lead Engineer. `GEMINI_MODEL` in `.env` switches
  models with no code change.
- LangChain **1.x is required**, not optional. The spec's 0.3-era
  `create_sql_agent` cannot be used with current Gemini models:
  langchain-google-genai 2.1.x drops Gemini's `thought_signature`, so replaying
  a tool call fails with `400 Function call is missing a thought_signature` -
  breaking every agent run, since each needs 2+ turns.
- Four data-dictionary discrepancies remain open with Demografy, notably what
  KPIs 11-16 measure.
- Scope section 7 says "do not retry automatically in a loop". The Gemini
  client retries at most `GEMINI_MAX_RETRIES` (default 2) on transient errors
  and then surfaces `reason="rate_limited"` for the UI to offer a retry,
  rather than retrying itself. Bounded, not a loop - but worth confirming that
  reading. `GEMINI_MAX_RETRIES=0` makes it strictly literal.
