"""Exercise RBAC against the real customer table (spec 4.3).

    python -m scripts.check_rbac              # all tiers, sampled from the table
    python -m scripts.check_rbac user_003     # one specific user

Prints a per-tier walkthrough of the question counter so you can see exactly
where warnings and cut-offs fire, without clicking through the UI 50 times.
No LLM calls, so it is free and fast.
"""

import sys

from auth.rbac import (
    REASON_INACTIVE,
    REASON_UNKNOWN,
    SessionQuota,
    authenticate,
)
from db.bigquery_client import run_query
from db.schema import CUSTOMERS_TABLE, TIER_QUESTION_LIMITS


def sample_users():
    """One active and one inactive user per tier, straight from the table."""
    rows = run_query(
        f"""
        SELECT tier, is_active, ANY_VALUE(user_id) AS user_id, COUNT(*) AS n
        FROM {CUSTOMERS_TABLE}
        GROUP BY tier, is_active
        ORDER BY tier, is_active DESC
        """,
        max_rows=20,
    )
    return rows


def show_login_matrix():
    print("=== Login: real users from the customer table ===")
    print(f"  {'tier':8} {'active':7} {'user_id':12} {'result':10} reason")

    for row in sample_users():
        result = authenticate(row["user_id"])
        verdict = "ALLOW" if result.ok else "DENY"
        print(f"  {row['tier']:8} {str(row['is_active']):7} "
              f"{row['user_id']:12} {verdict:10} {result.reason or '-'}")

    print("\n=== Login: rejection cases ===")
    for label, uid in [
        ("unknown user", "user_999999"),
        ("empty", ""),
        ("sql injection", "x' OR '1'='1"),
        ("wrong shape", "!!!"),
    ]:
        result = authenticate(uid)
        expected_deny = not result.ok
        mark = "OK  " if expected_deny else "BUG!"
        print(f"  [{mark}] {label:16} -> {result.reason or 'ALLOWED'}")


def walk_tier(tier):
    """Step through a whole session for one tier, showing every transition."""
    quota = SessionQuota(tier)
    limit = quota.limit
    print(f"\n=== {tier.upper()} (limit {limit}) ===")

    # Only print the interesting rows: start, around the warning, and the edge.
    warn_at = limit - 5
    interesting = {0, 1, warn_at, warn_at + 1, limit - 1, limit, limit + 1}

    for step in range(limit + 2):
        status = quota.status()

        if step in interesting:
            state = "ALLOWED" if status.allowed else "BLOCKED"
            flag = " <-- WARNING" if status.should_warn else ""
            print(f"  used={quota.used:>3}/{limit}  {state:8} "
                  f"remaining={quota.remaining:<3} bar={quota.fraction_used:>4.0%}{flag}")
            if status.message:
                print(f"        message: {status.message}")

        if status.allowed:
            quota.consume()


def main():
    if len(sys.argv) > 1:
        result = authenticate(sys.argv[1])
        print(f"authenticate({sys.argv[1]!r}) -> ok={result.ok} "
              f"reason={result.reason} error={result.error}")
        if result.user:
            print(f"  {result.user.as_dict()}")
        return 0

    show_login_matrix()

    for tier in TIER_QUESTION_LIMITS:
        walk_tier(tier)

    print("\nDone. No LLM calls were made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
