import streamlit as st

from db.bigquery_client import run_query

# Set up the Streamlit page.
st.set_page_config(
    page_title="D'grafy Insight Agent",
    page_icon="📊",
    layout="wide"
)

# Show the app title and caption.
st.title("D'grafy Insight Agent")
st.caption("Ask questions about your business data.")

# Test the BigQuery connection from Streamlit.
if st.button("Test BigQuery"):
    query = """
    SELECT 1 AS test_value
    """

    results = run_query(query)

    st.subheader("BigQuery Test Results")
    st.dataframe(results)