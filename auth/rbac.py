# auth/rbac.py
from google.cloud import bigquery
import os

TIER_LIMITS = {
    "free": 5,
    "basic": 20,
    "pro": 50
}

def authenticate_user(user_id: str):
    """
    Validates user_id against dev_customers table in BigQuery.
    Returns (is_valid, user_data_dict)
    """
    client = bigquery.Client(project=os.getenv("BIGQUERY_PROJECT", "demografy"))
    
    query = """
        SELECT user_id, email, tier, is_active
        FROM `demografy.ref_tables.dev_customers`
        WHERE user_id = @user_id AND is_active = TRUE
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
        ]
    )
    
    query_job = client.query(query, job_config=job_config)
    results = list(query_job.result())
    
    if not results:
        return False, None
    
    row = results[0]
    tier = row["tier"].lower() if row["tier"] else "free"
    
    return True, {
        "user_id": row["user_id"],
        "email": row["email"],
        "tier": tier,
        "max_questions": TIER_LIMITS.get(tier, 5)
    }