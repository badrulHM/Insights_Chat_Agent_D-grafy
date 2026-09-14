"""User identity: validation and lookup against the customer table (spec 4.3).

Authentication is by `user_id` only - no passwords, per spec. This module owns
the BigQuery lookup; `auth.rbac` owns what a user is then allowed to do.

The customer table is queried here through the plain BigQuery client, NOT
through the LLM agent. The agent's SQLDatabase only ever exposes the master
view, so no prompt can reach user records.
"""

import re

from db.bigquery_client import run_query
from db.schema import CUSTOMERS_TABLE, DEFAULT_TIER, TIER_QUESTION_LIMITS

# Prototype IDs look like `user_001`. Validating the shape before touching
# BigQuery means junk input costs nothing instead of a query job.
USER_ID_PATTERN = re.compile(r"^[a-z0-9_-]{3,64}$")


class User:
    """A row from the customer table, normalised."""

    def __init__(self, user_id, email=None, tier=None, is_active=False):
        self.user_id = user_id
        self.email = email
        self.tier = (tier or DEFAULT_TIER).strip().lower()
        self.is_active = bool(is_active)

    @property
    def question_limit(self):
        """Questions allowed per session for this user's tier."""
        return TIER_QUESTION_LIMITS.get(self.tier, TIER_QUESTION_LIMITS[DEFAULT_TIER])

    def as_dict(self):
        return {
            "user_id": self.user_id,
            "email": self.email,
            "tier": self.tier,
            "is_active": self.is_active,
            "question_limit": self.question_limit,
        }

    def __repr__(self):
        return f"User(user_id={self.user_id!r}, tier={self.tier!r}, active={self.is_active})"


def normalise_user_id(raw):
    """Trim and lowercase a user-supplied ID. Returns '' for junk input."""
    if not raw or not isinstance(raw, str):
        return ""

    return raw.strip().lower()


def is_valid_user_id(user_id):
    """True if the ID is the right shape to bother looking up."""
    return bool(USER_ID_PATTERN.match(user_id or ""))


def lookup_user(user_id):
    """Fetch a user from the customer table, or None if there is no such row.

    Does not consider `is_active` - that is a policy decision and belongs to
    `auth.rbac.authenticate`. The ID is bound as a query parameter, so it can
    never be interpreted as SQL.
    """
    user_id = normalise_user_id(user_id)

    if not is_valid_user_id(user_id):
        return None

    rows = run_query(
        f"""
        SELECT user_id, email, tier, is_active
        FROM {CUSTOMERS_TABLE}
        WHERE LOWER(user_id) = @user_id
        LIMIT 1
        """,
        params={"user_id": user_id},
        max_rows=1,
    )

    if not rows:
        return None

    row = rows[0]

    return User(
        user_id=row.get("user_id"),
        email=row.get("email"),
        tier=row.get("tier"),
        is_active=row.get("is_active"),
    )
