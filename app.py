"""Streamlit entry point.

BACKEND NOTE: this is a thin harness that proves the backend pipeline works
end to end (question -> Gemini -> SQL -> BigQuery -> text answer -> chart).
Branding, the login screen, tier counters and chat styling belong to the
Frontend role - this file is expected to be rebuilt on the Frontend branch.

The UI needs two things from the backend: `agent.service.ask` for the answer,
and `ui_charts.build_chart` to draw the chart it suggests. RBAC is wired and
tested in `auth/rbac.py` but is NOT surfaced here - see the README.
"""

import streamlit as st

from agent.service import ask, tracing_enabled
from config import settings
from db.bigquery_client import run_query
from ui_charts import build_chart

st.set_page_config(
    page_title="D'grafy Insight Agent",
    page_icon=":bar_chart:",
    layout="wide",
)

st.title("D'grafy Insight Agent")
st.caption("Ask questions about Australian demographic data.")

with st.sidebar:
    st.subheader("Backend status")
    st.write(f"Project: `{settings.bigquery_project}`")
    st.write(f"Model: `{settings.gemini_model}`")
    st.write(f"LangSmith tracing: {'on' if tracing_enabled() else 'off'}")

    if st.button("Test BigQuery"):
        try:
            st.success(run_query("SELECT 1 AS test_value"))
        except Exception as exc:
            st.error(f"{type(exc).__name__}: {exc}")

    show_sql = st.checkbox("Show generated SQL (dev)", value=False)

if "messages" not in st.session_state:
    st.session_state.messages = []

def render_chart(chart):
    """Draw whatever visual the backend chose, if it chose one.

    The backend picks the form (bar, column, grouped, stacked or table); this
    just dispatches. Text is always the primary answer, and a failure here
    must never take the answer down with it.
    """
    if chart is None:
        return

    try:
        if chart.is_table:
            # Tables are explicitly permitted by scope section 9, and
            # st.dataframe gives sorting and resizing for free.
            st.dataframe(
                chart.to_table_frame(), use_container_width=True, hide_index=True
            )
        else:
            st.plotly_chart(
                build_chart(chart),
                use_container_width=True,
                config={"displayModeBar": False},
            )
    except Exception:
        st.caption("(chart unavailable for this result)")


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        render_chart(message.get("chart"))

question = st.chat_input("e.g. Top 3 most diverse suburbs in Victoria")

if question:
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Querying BigQuery..."):
            # with_data=True returns the rows and a chart suggestion. It costs
            # no extra BigQuery job - the rows are reused from the agent run.
            result = ask(question, with_data=True)

        st.markdown(result.answer)
        render_chart(result.chart)

        if show_sql and result.sql:
            st.code(result.sql, language="sql")

        st.caption(f"Answered in {result.elapsed_seconds:.1f}s")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result.answer,
            "chart": result.chart,
        }
    )
