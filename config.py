"""Central configuration for the D'grafy Insight Agent.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv(override=True)


def _env_str(name, default=""):
    value = os.getenv(name, default)
    return value.strip() if value else default


def _env_int(name, default):
    raw = os.getenv(name)

    if not raw:
        return default

    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name, default=False):
    raw = os.getenv(name)

    if raw is None:
        return default

    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    """Resolved application settings."""

    # BigQuery
    google_application_credentials: str = field(
        default_factory=lambda: _env_str("GOOGLE_APPLICATION_CREDENTIALS")
    )

    bigquery_project: str = field(
        default_factory=lambda: _env_str("BIGQUERY_PROJECT")
    )
    bigquery_dataset: str = field(
        default_factory=lambda: _env_str("BIGQUERY_DATASET")
    )
    bigquery_ref_dataset: str = field(
        default_factory=lambda: _env_str("BIGQUERY_REF_DATASET")
    )
    bigquery_master_table: str = field(
        default_factory=lambda: _env_str("BIGQUERY_MASTER_TABLE")
    )
    bigquery_customers_table: str = field(
        default_factory=lambda: _env_str("BIGQUERY_CUSTOMERS_TABLE")
    )
    # Used in the agent's system prompt so the client name is not baked in.
    org_name: str = field(default_factory=lambda: _env_str("ORG_NAME", "the client"))
    bigquery_location: str = field(
        default_factory=lambda: _env_str("BIGQUERY_LOCATION")
    )

    # Gemini
    gemini_api_key: str = field(default_factory=lambda: _env_str("GEMINI_API_KEY"))
    gemini_model: str = field(
        default_factory=lambda: _env_str("GEMINI_MODEL", "gemini-2.5-flash-lite")
    )

    # LangSmith
    langchain_tracing: bool = field(
        default_factory=lambda: _env_bool("LANGCHAIN_TRACING_V2", False)
    )
    langchain_api_key: str = field(
        default_factory=lambda: _env_str("LANGCHAIN_API_KEY")
    )
    langchain_project: str = field(
        default_factory=lambda: _env_str("LANGCHAIN_PROJECT", "dgrafy-insight-agent")
    )

    # Query guardrails (spec 5.3 / 10)
    max_result_rows: int = field(
        default_factory=lambda: _env_int("MAX_RESULT_ROWS", 50)
    )
    query_timeout_seconds: int = field(
        default_factory=lambda: _env_int("QUERY_TIMEOUT_SECONDS", 60)
    )
    max_bytes_billed: int = field(
        default_factory=lambda: _env_int("MAX_BYTES_BILLED", 2 * 1024**3)
    )

    def missing_required(self):
        """Return the names of required settings that are not configured."""
        missing = []

        for name, value in (
            ("BIGQUERY_PROJECT", self.bigquery_project),
            ("BIGQUERY_DATASET", self.bigquery_dataset),
            ("BIGQUERY_REF_DATASET", self.bigquery_ref_dataset),
            ("BIGQUERY_MASTER_TABLE", self.bigquery_master_table),
            ("BIGQUERY_CUSTOMERS_TABLE", self.bigquery_customers_table),
        ):
            if not value:
                missing.append(name)

        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")

        # Application Default Credentials may be in play instead of an explicit
        # key file, so only flag a path that was given but does not exist.
        if self.google_application_credentials and not os.path.exists(
            self.google_application_credentials
        ):
            missing.append(
                "GOOGLE_APPLICATION_CREDENTIALS (path set but file not found: "
                f"{self.google_application_credentials})"
            )

        return missing

    def apply_langsmith_env(self):
        """Export the LangSmith variables LangChain reads implicitly.

        LangChain picks tracing up from the process environment, so this makes
        the behaviour explicit and keeps `.env` as the single source of truth.
        """
        if not (self.langchain_tracing and self.langchain_api_key):
            return False

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = self.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = self.langchain_project
        return True

    def redacted(self):
        """Settings safe to print, screenshot or paste into a ticket.

        Secrets are masked, and so are the client's infrastructure identifiers
        (project/dataset/table names) - enough of each is shown to spot a typo,
        never enough to disclose the value.
        """

        def mask_secret(value):
            if not value:
                return "(not set)"
            return f"{value[:4]}...{value[-4:]} ({len(value)} chars)"

        def mask_id(value):
            if not value:
                return "(not set)"
            return f"{value[:2]}{'*' * (len(value) - 2)} ({len(value)} chars)"

        def mask_path(value):
            if not value:
                return "(using application default credentials)"
            # Show only the filename - the full path leaks the OS username.
            return f".../{os.path.basename(value)}"

        return {
            "BIGQUERY_PROJECT": mask_id(self.bigquery_project),
            "BIGQUERY_DATASET": mask_id(self.bigquery_dataset),
            "BIGQUERY_REF_DATASET": mask_id(self.bigquery_ref_dataset),
            "BIGQUERY_MASTER_TABLE": mask_id(self.bigquery_master_table),
            "BIGQUERY_CUSTOMERS_TABLE": mask_id(self.bigquery_customers_table),
            "BIGQUERY_LOCATION": self.bigquery_location or "(default)",
            "GOOGLE_APPLICATION_CREDENTIALS": mask_path(
                self.google_application_credentials
            ),
            "GEMINI_MODEL": self.gemini_model,
            "GEMINI_API_KEY": mask_secret(self.gemini_api_key),
            "LANGCHAIN_TRACING_V2": self.langchain_tracing,
            "LANGCHAIN_PROJECT": self.langchain_project,
            "LANGCHAIN_API_KEY": mask_secret(self.langchain_api_key),
            "MAX_RESULT_ROWS": self.max_result_rows,
            "QUERY_TIMEOUT_SECONDS": self.query_timeout_seconds,
            "MAX_BYTES_BILLED": self.max_bytes_billed,
        }


settings = Settings()
