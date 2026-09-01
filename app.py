"""Streamlit entry point.

BACKEND NOTE: this is a thin harness that proves the backend pipeline works
end to end (question -> Gemini -> SQL -> BigQuery -> text answer). Branding,
the login screen, tier counters and chat styling belong to the Frontend role -
this file is expected to be rebuilt on the Frontend branch.

The only import the UI needs from the backend is `agent.service.ask`.
"""

import streamlit as st

from agent.service import ask, tracing_enabled
from config import settings
from db.bigquery_client import run_query

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

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("e.g. Top 3 most diverse suburbs in Victoria")

if question:
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Querying BigQuery..."):
            result = ask(question)

        st.markdown(result.answer)

        if show_sql and result.sql:
            st.code(result.sql, language="sql")

        st.caption(f"Answered in {result.elapsed_seconds:.1f}s")

    st.session_state.messages.append(
        {"role": "assistant", "content": result.answer}
    )
