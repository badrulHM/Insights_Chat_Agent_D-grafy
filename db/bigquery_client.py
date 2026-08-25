from google.cloud import bigquery

# connect to bigquery.
client = bigquery.Client()


# Run query and return the results.
def run_query(query):
    query_job = client.query(query)
    results = query_job.result()

    rows = []

    for row in results:
        rows.append(dict(row))

    return rows
