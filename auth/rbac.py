"""Tier policy and per-session question quotas (spec 4.3).

Backend policy only. This module holds no session state - the UI owns the
counter (`st.session_state`) and asks these functions what to do with it, so
the rules stay testable without a Streamlit runtime.

    from auth.rbac import authenticate, check_quota

    auth = authenticate(user_id_from_login_box)
    if not auth.ok:
        show(auth.error)
    else:
        quota = check_quota(auth.user.tier, st.session_state.questions_used)
        if not quota.allowed:
            disable_input(quota.message)
"""

from auth.users import lookup_user, normalise_user_id
from db.schema import DEFAULT_TIER, TIER_QUESTION_LIMITS, TIER_WARN_AT

# Reasons a login can fail, so the UI can branch without matching on prose.
REASON_EMPTY = "empty"
REASON_UNKNOWN = "unknown_user"
REASON_INACTIVE = "inactive_account"
REASON_LOOKUP_FAILED = "lookup_failed"


class AuthResult:
    """Outcome of a login attempt."""

    def __init__(self, ok, user=None, reason=None, error=None):
        self.ok = ok
        self.user = user
        self.reason = reason
        self.error = error

    def as_dict(self):
        return {
            "ok": self.ok,
            "reason": self.reason,
            "error": self.error,
            "user": self.user.as_dict() if self.user else None,
        }


class QuotaStatus:
    """Whether this user may ask another question right now."""

    def __init__(self, allowed, used, limit, tier, should_warn=False, message=None):
        self.allowed = allowed
        self.used = used
        self.limit = limit
        self.tier = tier
        self.should_warn = should_warn
        self.message = message

    @property
    def remaining(self):
        return max(self.limit - self.used, 0)

    def as_dict(self):
        return {
            "allowed": self.allowed,
            "used": self.used,
            "limit": self.limit,
            "remaining": self.remaining,
            "tier": self.tier,
            "should_warn": self.should_warn,
            "message": self.message,
        }


def question_limit(tier):
    """Questions per session for a tier, falling back to the free limit."""
    tier = (tier or DEFAULT_TIER).strip().lower()
    return TIER_QUESTION_LIMITS.get(tier, TIER_QUESTION_LIMITS[DEFAULT_TIER])


def warn_threshold(tier):
    """Question count at which to warn the user, or None if the tier has none."""
    return TIER_WARN_AT.get((tier or DEFAULT_TIER).strip().lower())


def authenticate(user_id):
    """Look up a user and decide whether they may log in.

    Never raises: a BigQuery outage comes back as ok=False with
    REASON_LOOKUP_FAILED, so the login screen degrades instead of crashing.
    """
    user_id = normalise_user_id(user_id)

    if not user_id:
        return AuthResult(
            False, reason=REASON_EMPTY, error="Please enter your user ID."
        )

    try:
        user = lookup_user(user_id)
    except Exception as exc:
        return AuthResult(
            False,
            reason=REASON_LOOKUP_FAILED,
            error="Could not reach the account service. Please try again.",
        )

    if user is None:
        # Note: this distinguishes "no such user" from "deactivated", which
        # technically allows ID enumeration. Acceptable for a prototype with
        # dummy IDs; collapse both into one message if this ever goes public.
        return AuthResult(
            False,
            reason=REASON_UNKNOWN,
            error=f"No account found for '{user_id}'.",
        )

    if not user.is_active:
        return AuthResult(
            False,
            user=user,
            reason=REASON_INACTIVE,
            error="This account is deactivated. Contact your administrator.",
        )

    return AuthResult(True, user=user)


def check_quota(tier, questions_used):
    """Decide whether another question is allowed, and what to tell the user.

    `questions_used` is the count the UI has tracked for this session. Pass the
    count BEFORE the pending question.
    """
    tier = (tier or DEFAULT_TIER).strip().lower()
    used = max(int(questions_used or 0), 0)
    limit = question_limit(tier)

    if used >= limit:
        return QuotaStatus(
            allowed=False,
            used=used,
            limit=limit,
            tier=tier,
            message=_limit_reached_message(tier, limit),
        )

    warn_at = warn_threshold(tier)
    should_warn = warn_at is not None and used >= warn_at
    remaining = limit - used
    message = None

    if should_warn:
        message = (
            f"You have {remaining} of your {limit} questions left this session."
        )

    return QuotaStatus(
        allowed=True,
        used=used,
        limit=limit,
        tier=tier,
        should_warn=should_warn,
        message=message,
    )


def _limit_reached_message(tier, limit):
    if tier == "free":
        return (
            f"You have used all {limit} questions in your free session. "
            "Upgrade to Basic or Pro for more."
        )

    if tier == "basic":
        return (
            f"You have used all {limit} questions in this session. "
            "Upgrade to Pro for 50 questions per session."
        )

    return (
        f"You have used all {limit} questions in this session. "
        "Start a new session to continue."
    )
