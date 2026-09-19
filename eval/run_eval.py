"""Run the Demografy 10-question Golden Dataset.

PASS/FAIL is decided by deterministic checks.
The Gemini LLM judge is a secondary quality signal only.

Examples:

    first run only deterministic evaluation
    python -m eval.run_eval --no-judge --delay 5

    test one case including the judge
    python -m eval.run_eval --case 1

    run all 10:
    python -m eval.run_eval

    
"""

import argparse
import json
import re
import time
import traceback
from pathlib import Path

from agent.service import ask
from eval.judge import judge_answer


# ---------------------------------------------------------
# PATHS / SETTINGS
# ---------------------------------------------------------

BASE_DIR = Path(
    __file__
).resolve().parent

PROJECT_ROOT = BASE_DIR.parent

DATASET_FILE = (
    BASE_DIR
    / "golden_dataset.json"
)

DEFAULT_REPORT_FILE = (
    PROJECT_ROOT
    / "docs"
    / "eval_report.md"
)

DEFAULT_DELAY_SECONDS = 20.0

MAX_AGENT_RETRIES = 3

INITIAL_RETRY_WAIT_SECONDS = 30.0


# ---------------------------------------------------------
# LOAD GOLDEN DATASET
# ---------------------------------------------------------

def load_golden_dataset(
    path=DATASET_FILE,
):
    """Load and validate the Golden Dataset."""

    if not path.exists():
        raise FileNotFoundError(
            f"Golden dataset not found: "
            f"{path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        dataset = json.load(
            handle
        )

    if (
        not isinstance(
            dataset,
            list,
        )
        or not dataset
    ):
        raise ValueError(
            "Golden dataset must be "
            "a non-empty JSON list."
        )

    seen_ids = set()

    for index, case in enumerate(
        dataset,
        start=1,
    ):

        if not isinstance(
            case,
            dict,
        ):
            raise ValueError(
                f"Case {index} must "
                "be a JSON object."
            )

        case_id = str(
            case.get(
                "id",
                "",
            )
        ).strip()

        question = str(
            case.get(
                "question",
                "",
            )
        ).strip()

        if not case_id:
            raise ValueError(
                f"Case {index} "
                "is missing id."
            )

        if case_id in seen_ids:
            raise ValueError(
                f"Duplicate case id: "
                f"{case_id}"
            )

        if not question:
            raise ValueError(
                f"{case_id} is "
                "missing question."
            )

        seen_ids.add(
            case_id
        )

    return dataset


# ---------------------------------------------------------
# SELECT INDIVIDUAL TEST CASES
# ---------------------------------------------------------

def select_cases(
    dataset,
    requested_cases,
):
    """
    Select cases by number or ID.

    Examples:
        --case 1
        --case GD01
    """

    if not requested_cases:
        return list(
            dataset
        )

    selected = []

    for requested in requested_cases:

        token = str(
            requested
        ).strip()

        if token.isdigit():

            position = int(
                token
            )

            if (
                position < 1
                or position > len(
                    dataset
                )
            ):
                raise ValueError(
                    f"Case number "
                    f"{position} is "
                    f"outside 1.."
                    f"{len(dataset)}."
                )

            case = dataset[
                position - 1
            ]

        else:

            case = next(
                (
                    item
                    for item
                    in dataset
                    if str(
                        item.get(
                            "id",
                            "",
                        )
                    ).lower()
                    == token.lower()
                ),
                None,
            )

            if case is None:
                raise ValueError(
                    f"Unknown case id: "
                    f"{token}"
                )

        if case not in selected:
            selected.append(
                case
            )

    return selected


# ---------------------------------------------------------
# RESPONSE HELPERS
# ---------------------------------------------------------

def get_value(
    response,
    name,
    default=None,
):
    """
    Read an attribute from AgentAnswer
    or a key from a dictionary.
    """

    if response is None:
        return default

    if hasattr(
        response,
        name,
    ):
        return getattr(
            response,
            name,
        )

    if isinstance(
        response,
        dict,
    ):
        return response.get(
            name,
            default,
        )

    return default


def get_answer_text(
    response,
):
    if response is None:
        return ""

    answer = get_value(
        response,
        "answer",
    )

    if answer is not None:
        return str(
            answer
        )

    if isinstance(
        response,
        str,
    ):
        return response

    return str(
        response
    )


def get_sql(
    response,
):
    return str(
        get_value(
            response,
            "sql",
            "",
        )
        or ""
    )


def get_trace_url(
    response,
):
    return str(
        get_value(
            response,
            "trace_url",
            "",
        )
        or ""
    )


def get_agent_error(
    response,
):
    return str(
        get_value(
            response,
            "error",
            "",
        )
        or ""
    )


def get_agent_reason(
    response,
):
    return str(
        get_value(
            response,
            "reason",
            "",
        )
        or ""
    )


def agent_completed_successfully(
    response,
):
    if response is None:
        return False

    ok = get_value(
        response,
        "ok",
        None,
    )

    if ok is None:
        return True

    return bool(
        ok
    )


# ---------------------------------------------------------
# ERROR / RETRY HANDLING
# ---------------------------------------------------------

def is_rate_limit_error(
    value,
):
    text = str(
        value or ""
    ).lower()

    markers = (
        "rate_limited",
        "resource_exhausted",
        "429",
        "quota exceeded",
        "rate limit",
    )

    return any(
        marker in text
        for marker
        in markers
    )


def classify_exception(
    error,
):
    text = (
        f"{type(error).__name__}: "
        f"{error}"
    ).lower()

    if is_rate_limit_error(
        text
    ):
        return "rate_limited"

    if (
        "timeout" in text
        or "deadline" in text
    ):
        return "timeout"

    if (
        "403" in text
        or "forbidden" in text
        or "permission" in text
    ):
        return "permission_error"

    if (
        "credential" in text
        or "authentication" in text
    ):
        return (
            "authentication_error"
        )

    if (
        "bigquery" in text
        or "google.api_core"
        in text
    ):
        return "data_unavailable"

    return "unknown"


def run_agent_with_retry(
    question,
):
    """
    Run the agent.

    Retry only rate-limit errors.
    """

    wait_seconds = (
        INITIAL_RETRY_WAIT_SECONDS
    )

    for attempt in range(
        1,
        MAX_AGENT_RETRIES + 1,
    ):

        try:

            response = ask(
                question,
                user_id=(
                    "eval_runner"
                ),
                tier="pro",
                with_data=False,
            )

            if (
                agent_completed_successfully(
                    response
                )
            ):

                return {
                    "success": True,
                    "answer":
                        get_answer_text(
                            response
                        ),
                    "sql":
                        get_sql(
                            response
                        ),
                    "trace_url":
                        get_trace_url(
                            response
                        ),
                    "error": "",
                    "error_type": "",
                }

            reason = (
                get_agent_reason(
                    response
                )
                or "unknown"
            )

            error = (
                get_agent_error(
                    response
                )
                or get_answer_text(
                    response
                )
            )

            rate_limited = (
                reason
                == "rate_limited"
                or is_rate_limit_error(
                    error
                )
            )

            if (
                rate_limited
                and attempt
                < MAX_AGENT_RETRIES
            ):

                print(
                    f"Rate limit on "
                    f"attempt {attempt}/"
                    f"{MAX_AGENT_RETRIES}. "
                    f"Retrying after "
                    f"{wait_seconds:.0f}s..."
                )

                time.sleep(
                    wait_seconds
                )

                wait_seconds *= 2

                continue

            return {
                "success": False,
                "answer":
                    get_answer_text(
                        response
                    ),
                "sql":
                    get_sql(
                        response
                    ),
                "trace_url":
                    get_trace_url(
                        response
                    ),
                "error": error,
                "error_type": reason,
            }

        except Exception as error:

            error_type = (
                classify_exception(
                    error
                )
            )

            if (
                error_type
                == "rate_limited"
                and attempt
                < MAX_AGENT_RETRIES
            ):

                print(
                    f"Rate limit on "
                    f"attempt {attempt}/"
                    f"{MAX_AGENT_RETRIES}. "
                    f"Retrying after "
                    f"{wait_seconds:.0f}s..."
                )

                time.sleep(
                    wait_seconds
                )

                wait_seconds *= 2

                continue

            traceback.print_exc()

            return {
                "success": False,
                "answer": "",
                "sql": "",
                "trace_url": "",
                "error": (
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
                "error_type":
                    error_type,
            }

    return {
        "success": False,
        "answer": "",
        "sql": "",
        "trace_url": "",
        "error": (
            "Maximum retry "
            "attempts exceeded."
        ),
        "error_type":
            "rate_limited",
    }


# ---------------------------------------------------------
# NUMBER EXTRACTION
# ---------------------------------------------------------

NUMBER_PATTERN = re.compile(
    r"(?<![\w.])"
    r"[-+]?"
    r"(?:"
    r"\d{1,3}(?:,\d{3})+"
    r"|\d+"
    r")"
    r"(?:\.\d+)?"
    r"(?![\w.])"
)


def extract_numbers(
    text,
):
    """
    Extract numbers such as:

    58.44
    0.807
    15,829
    """

    values = []

    matches = (
        NUMBER_PATTERN.findall(
            text or ""
        )
    )

    for match in matches:

        try:
            value = float(
                match.replace(
                    ",",
                    "",
                )
            )

            values.append(
                value
            )

        except ValueError:
            continue

    return values


# ---------------------------------------------------------
# DETERMINISTIC CHECK 1
# SQL / NO SQL
# ---------------------------------------------------------

def check_sql_behavior(
    actual_sql,
    expect_sql,
):

    has_sql = bool(
        (
            actual_sql
            or ""
        ).strip()
    )

    if (
        expect_sql
        and not has_sql
    ):
        return (
            False,
            "Expected SQL but "
            "none was captured.",
        )

    if (
        not expect_sql
        and has_sql
    ):
        return (
            False,
            "Expected no SQL, "
            "but SQL was executed.",
        )

    return (
        True,
        "SQL behaviour matched "
        "expectation.",
    )


# ---------------------------------------------------------
# DETERMINISTIC CHECK 2
# KPI COLUMN
# ---------------------------------------------------------

def check_expected_column(
    actual_sql,
    expected_column,
    expect_sql,
):

    if (
        not expect_sql
        or not expected_column
    ):
        return (
            True,
            "Column check "
            "not required.",
        )

    if (
        expected_column.lower()
        in (
            actual_sql
            or ""
        ).lower()
    ):
        return (
            True,
            f"SQL used "
            f"{expected_column}.",
        )

    return (
        False,
        f"SQL did not use "
        f"expected column "
        f"{expected_column}.",
    )


# ---------------------------------------------------------
# DETERMINISTIC CHECK 3
# GEOGRAPHY
# ---------------------------------------------------------

def check_expected_geographies(
    actual_sql,
    expected_geographies,
    expect_sql,
):

    geographies = [
        str(
            geography
        ).strip()

        for geography
        in (
            expected_geographies
            or []
        )

        if str(
            geography
        ).strip()
    ]

    if (
        not expect_sql
        or not geographies
    ):
        return (
            True,
            "Geography check "
            "not required.",
        )

    sql_lower = (
        actual_sql
        or ""
    ).lower()

    missing = [
        geography

        for geography
        in geographies

        if geography.lower()
        not in sql_lower
    ]

    if missing:
        return (
            False,
            "Missing geography "
            "in SQL: "
            + ", ".join(
                missing
            ),
        )

    return (
        True,
        "Expected geography "
        "present in SQL.",
    )


# ---------------------------------------------------------
# DETERMINISTIC CHECK 4
# EXPECTED NUMERIC VALUES
# ---------------------------------------------------------

def allowed_tolerance(
    specification,
):

    expected = float(
        specification[
            "value"
        ]
    )

    tolerance_pct = float(
        specification.get(
            "tolerance_pct",
            1.0,
        )
    )

    tolerance_abs = float(
        specification.get(
            "tolerance_abs",
            0.0,
        )
    )

    percentage_tolerance = (
        abs(expected)
        * tolerance_pct
        / 100
    )

    return max(
        percentage_tolerance,
        tolerance_abs,
    )


def check_expected_values(
    actual_answer,
    expected_values,
):
    """
    Check the final answer against
    known Golden Dataset values.
    """

    if not expected_values:
        return (
            True,
            "Numeric value check "
            "not required.",
        )

    actual_numbers = (
        extract_numbers(
            actual_answer
        )
    )

    if not actual_numbers:
        return (
            False,
            "No numeric values "
            "found in answer.",
        )

    unused_indexes = set(
        range(
            len(
                actual_numbers
            )
        )
    )

    missing = []

    for specification in (
        expected_values
    ):

        expected = float(
            specification[
                "value"
            ]
        )

        tolerance = (
            allowed_tolerance(
                specification
            )
        )

        candidates = []

        for index in (
            unused_indexes
        ):

            difference = abs(
                actual_numbers[
                    index
                ]
                - expected
            )

            if (
                difference
                <= tolerance
            ):
                candidates.append(
                    (
                        index,
                        difference,
                    )
                )

        if not candidates:

            label = (
                specification.get(
                    "label",
                    "value",
                )
            )

            missing.append(
                f"{label}="
                f"{expected}"
            )

            continue

        best_index, _ = min(
            candidates,
            key=lambda item:
                item[1],
        )

        unused_indexes.remove(
            best_index
        )

    if missing:

        return (
            False,
            "Expected numeric "
            "value(s) not found "
            "within tolerance: "
            + "; ".join(
                missing
            ),
        )

    return (
        True,
        "All expected numeric "
        "values present within "
        "tolerance.",
    )


# ---------------------------------------------------------
# DETERMINISTIC CHECK 5
# REQUIRED ANSWER TERMS
# ---------------------------------------------------------

def check_required_terms(
    actual_answer,
    required_terms,
    required_any_terms,
):

    text = (
        actual_answer
        or ""
    ).lower()

    missing_required = [
        term

        for term
        in (
            required_terms
            or []
        )

        if str(
            term
        ).lower()
        not in text
    ]

    if missing_required:

        return (
            False,
            "Missing required "
            "answer term(s): "
            + ", ".join(
                map(
                    str,
                    missing_required,
                )
            ),
        )

    missing_groups = []

    for group in (
        required_any_terms
        or []
    ):

        group = [
            str(
                term
            )

            for term
            in group

            if str(
                term
            ).strip()
        ]

        if (
            group
            and not any(
                term.lower()
                in text
                for term
                in group
            )
        ):
            missing_groups.append(
                group
            )

    if missing_groups:

        rendered = " | ".join(
            "("
            + " OR ".join(
                group
            )
            + ")"

            for group
            in missing_groups
        )

        return (
            False,
            "Missing required "
            "meaning group(s): "
            f"{rendered}",
        )

    return (
        True,
        "Required answer terms "
        "were present.",
    )


# ---------------------------------------------------------
# RUN ALL DETERMINISTIC CHECKS
# ---------------------------------------------------------

def run_deterministic_checks(
    test,
    actual_answer,
    actual_sql,
):

    expect_sql = bool(
        test.get(
            "expect_sql",
            True,
        )
    )

    sql_ok, sql_reason = (
        check_sql_behavior(
            actual_sql,
            expect_sql,
        )
    )

    column_ok, column_reason = (
        check_expected_column(
            actual_sql,
            test.get(
                "expected_column"
            ),
            expect_sql,
        )
    )

    geography_ok, geography_reason = (
        check_expected_geographies(
            actual_sql,
            test.get(
                "expected_geography",
                [],
            ),
            expect_sql,
        )
    )

    values_ok, values_reason = (
        check_expected_values(
            actual_answer,
            test.get(
                "expected_values",
                [],
            ),
        )
    )

    terms_ok, terms_reason = (
        check_required_terms(
            actual_answer,
            test.get(
                "required_answer_terms",
                [],
            ),
            test.get(
                "required_any_terms",
                [],
            ),
        )
    )

    checks = {
        "sql_behavior": {
            "passed": sql_ok,
            "reason":
                sql_reason,
        },
        "column": {
            "passed":
                column_ok,
            "reason":
                column_reason,
        },
        "geography": {
            "passed":
                geography_ok,
            "reason":
                geography_reason,
        },
        "values": {
            "passed":
                values_ok,
            "reason":
                values_reason,
        },
        "answer_terms": {
            "passed":
                terms_ok,
            "reason":
                terms_reason,
        },
    }

    passed = all(
        check["passed"]
        for check
        in checks.values()
    )

    return {
        "passed":
            passed,
        "checks":
            checks,
    }


# ---------------------------------------------------------
# EXPECTED FACTS FOR LLM JUDGE
# ---------------------------------------------------------

def build_expected_facts(
    test,
):

    return {
        "category":
            test.get(
                "category"
            ),

        "expected_kpi":
            test.get(
                "expected_kpi"
            ),

        "expected_column":
            test.get(
                "expected_column"
            ),

        "expected_geography":
            test.get(
                "expected_geography",
                [],
            ),

        "expected_values":
            test.get(
                "expected_values",
                [],
            ),

        "expect_sql":
            test.get(
                "expect_sql",
                True,
            ),

        "required_answer_terms":
            test.get(
                "required_answer_terms",
                [],
            ),

        "required_any_terms":
            test.get(
                "required_any_terms",
                [],
            ),
    }


# ---------------------------------------------------------
# RUN ONE TEST
# ---------------------------------------------------------

def run_test(
    test,
    use_judge=True,
):

    test_id = test[
        "id"
    ]

    question = test[
        "question"
    ]

    print()
    print(
        "=" * 78
    )

    print(
        f"{test_id}: "
        f"{question}"
    )

    started = (
        time.perf_counter()
    )

    agent_result = (
        run_agent_with_retry(
            question
        )
    )

    latency = round(
        time.perf_counter()
        - started,
        2,
    )

    # -----------------------------------------------------
    # Infrastructure error
    # -----------------------------------------------------

    if not agent_result[
        "success"
    ]:

        print(
            f"Result: ERROR "
            f"("
            f"{agent_result['error_type']}"
            f")"
        )

        print(
            f"Latency: "
            f"{latency}s"
        )

        if agent_result[
            "error"
        ]:
            print(
                "Error: "
                + agent_result[
                    "error"
                ]
            )

        if agent_result[
            "trace_url"
        ]:
            print(
                "LangSmith trace: "
                + agent_result[
                    "trace_url"
                ]
            )

        return {
            "test_id":
                test_id,

            "question":
                question,

            "status":
                "ERROR",

            "deterministic_pass":
                None,

            "checks":
                {},

            "judge_score":
                None,

            "judge_reason":
                "",

            "judge_error":
                "",

            "judge_disagreement":
                False,

            "expected_answer":
                test.get(
                    "expected_answer",
                    "",
                ),

            "actual_answer":
                agent_result[
                    "answer"
                ],

            "actual_sql":
                agent_result[
                    "sql"
                ],

            "error_type":
                agent_result[
                    "error_type"
                ],

            "error":
                agent_result[
                    "error"
                ],

            "latency_seconds":
                latency,

            "langsmith_trace":
                agent_result[
                    "trace_url"
                ],
        }

    # -----------------------------------------------------
    # Successful agent response
    # -----------------------------------------------------

    actual_answer = (
        agent_result[
            "answer"
        ]
    )

    actual_sql = (
        agent_result[
            "sql"
        ]
    )

    deterministic = (
        run_deterministic_checks(
            test,
            actual_answer,
            actual_sql,
        )
    )

    # IMPORTANT:
    # Deterministic checks decide PASS / FAIL.
    status = (
        "PASS"
        if deterministic[
            "passed"
        ]
        else "FAIL"
    )

    # -----------------------------------------------------
    # LLM judge
    # -----------------------------------------------------

    judge_score = None
    judge_reason = ""
    judge_error = ""

    if use_judge:

        judge_result = (
            judge_answer(
                question=question,
                expected_answer=(
                    test.get(
                        "expected_answer",
                        "",
                    )
                ),
                actual_answer=(
                    actual_answer
                ),
                expected_facts=(
                    build_expected_facts(
                        test
                    )
                ),
                actual_sql=(
                    actual_sql
                ),
            )
        )

        judge_score = (
            judge_result.get(
                "score"
            )
        )

        judge_reason = (
            judge_result.get(
                "reason",
                "",
            )
        )

        judge_error = (
            judge_result.get(
                "error",
                "",
            )
            or ""
        )

    # -----------------------------------------------------
    # Judge disagreement
    # -----------------------------------------------------

    judge_disagreement = (
        judge_score is not None
        and (
            (
                deterministic[
                    "passed"
                ]
                and judge_score <= 2
            )
            or (
                not deterministic[
                    "passed"
                ]
                and judge_score >= 4
            )
        )
    )

    # -----------------------------------------------------
    # Print checks
    # -----------------------------------------------------

    for (
        name,
        check,
    ) in deterministic[
        "checks"
    ].items():

        marker = (
            "PASS"
            if check[
                "passed"
            ]
            else "FAIL"
        )

        print(
            f"{name:14}: "
            f"{marker} - "
            f"{check['reason']}"
        )

    # -----------------------------------------------------
    # Judge output
    # -----------------------------------------------------

    if use_judge:

        if judge_score is None:

            print(
                "LLM judge      : "
                "NOT SCORED - "
                f"{judge_error}"
            )

        else:

            print(
                "LLM judge      : "
                f"{judge_score}/5 "
                f"- {judge_reason}"
            )

            if (
                judge_disagreement
            ):

                print(
                    "Judge flag     : "
                    "DISAGREES with "
                    "deterministic result"
                )

    else:

        print(
            "LLM judge      : "
            "SKIPPED"
        )

    print(
        f"Latency        : "
        f"{latency}s"
    )

    print(
        f"Result         : "
        f"{status}"
    )

    print()
    print(
        "Actual answer:"
    )
    print(
        actual_answer
    )

    if actual_sql:

        print()
        print(
            "Generated SQL:"
        )

        print(
            actual_sql
        )

    if agent_result[
        "trace_url"
    ]:

        print()

        print(
            "LangSmith trace: "
            + agent_result[
                "trace_url"
            ]
        )

    return {
        "test_id":
            test_id,

        "question":
            question,

        "status":
            status,

        "deterministic_pass":
            deterministic[
                "passed"
            ],

        "checks":
            deterministic[
                "checks"
            ],

        "judge_score":
            judge_score,

        "judge_reason":
            judge_reason,

        "judge_error":
            judge_error,

        "judge_disagreement":
            judge_disagreement,

        "expected_answer":
            test.get(
                "expected_answer",
                "",
            ),

        "actual_answer":
            actual_answer,

        "actual_sql":
            actual_sql,

        "error_type":
            "",

        "error":
            "",

        "latency_seconds":
            latency,

        "langsmith_trace":
            agent_result[
                "trace_url"
            ],
    }


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

def summarise_results(
    results,
):

    passed = sum(
        result[
            "status"
        ] == "PASS"

        for result
        in results
    )

    failed = sum(
        result[
            "status"
        ] == "FAIL"

        for result
        in results
    )

    errors = sum(
        result[
            "status"
        ] == "ERROR"

        for result
        in results
    )

    completed = (
        passed
        + failed
    )

    accuracy = (
        round(
            (
                passed
                / completed
            )
            * 100,
            2,
        )
        if completed
        else 0.0
    )

    judge_scores = [
        result[
            "judge_score"
        ]

        for result
        in results

        if result.get(
            "judge_score"
        )
        is not None
    ]

    if judge_scores:

        average_judge = round(
            sum(
                judge_scores
            )
            / len(
                judge_scores
            ),
            2,
        )

    else:

        average_judge = None

    latencies = [
        float(
            result.get(
                "latency_seconds",
                0.0,
            )
        )

        for result
        in results
    ]

    average_latency = (
        round(
            sum(
                latencies
            )
            / len(
                latencies
            ),
            2,
        )
        if latencies
        else 0.0
    )

    disagreements = sum(
        bool(
            result.get(
                "judge_disagreement"
            )
        )

        for result
        in results
    )

    return {
        "total":
            len(
                results
            ),

        "passed":
            passed,

        "failed":
            failed,

        "errors":
            errors,

        "completed":
            completed,

        "accuracy":
            accuracy,

        "average_judge":
            average_judge,

        "average_latency":
            average_latency,

        "judge_disagreements":
            disagreements,
    }


def print_summary(
    results,
):

    summary = (
        summarise_results(
            results
        )
    )

    print()
    print(
        "=" * 78
    )

    print(
        "DEMOGRAFY GOLDEN DATASET "
        "EVALUATION SUMMARY"
    )

    print(
        "=" * 78
    )

    print(
        f"Total test cases       : "
        f"{summary['total']}"
    )

    print(
        f"Passed                 : "
        f"{summary['passed']}"
    )

    print(
        f"Failed                 : "
        f"{summary['failed']}"
    )

    print(
        f"Infrastructure errors  : "
        f"{summary['errors']}"
    )

    print(
        f"Completed tests        : "
        f"{summary['completed']}"
    )

    print(
        f"Deterministic accuracy : "
        f"{summary['accuracy']}%"
    )

    if (
        summary[
            "average_judge"
        ]
        is None
    ):

        print(
            "Average LLM judge      : "
            "NOT SCORED"
        )

    else:

        print(
            f"Average LLM judge      : "
            f"{summary['average_judge']}/5"
        )

    print(
        f"Judge disagreements    : "
        f"{summary['judge_disagreements']}"
    )

    print(
        f"Average latency        : "
        f"{summary['average_latency']}s"
    )

    if summary[
        "failed"
    ]:

        print()
        print(
            "Failed tests:"
        )

        for result in results:

            if (
                result[
                    "status"
                ]
                == "FAIL"
            ):

                print(
                    f"  "
                    f"{result['test_id']}"
                )

    if summary[
        "errors"
    ]:

        print()
        print(
            "Infrastructure/API "
            "errors:"
        )

        for result in results:

            if (
                result[
                    "status"
                ]
                == "ERROR"
            ):

                print(
                    f"  "
                    f"{result['test_id']} "
                    f"- "
                    f"{result.get('error_type')}"
                )

    print(
        "=" * 78
    )

    return summary


# ---------------------------------------------------------
# MARKDOWN REPORT
# ---------------------------------------------------------

def escape_table_cell(
    value,
):

    return str(
        value or ""
    ).replace(
        "|",
        "\\|",
    ).replace(
        "\n",
        " ",
    )


def write_markdown_report(
    results,
    report_file,
):

    summary = (
        summarise_results(
            results
        )
    )

    report_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = [
        "# Demografy Golden Dataset Evaluation",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Total test cases | {summary['total']} |",
        f"| Passed | {summary['passed']} |",
        f"| Failed | {summary['failed']} |",
        f"| Infrastructure errors | {summary['errors']} |",
        f"| Deterministic accuracy | {summary['accuracy']}% |",
    ]

    if (
        summary[
            "average_judge"
        ]
        is not None
    ):

        lines.append(
            "| Average LLM judge | "
            f"{summary['average_judge']}/5 |"
        )

    else:

        lines.append(
            "| Average LLM judge | "
            "Not scored |"
        )

    lines.extend(
        [
            "| Judge disagreements | "
            f"{summary['judge_disagreements']} |",

            "| Average latency | "
            f"{summary['average_latency']}s |",

            "",
            "## Cases",
            "",
            "| Case | Status | Judge | Latency | Question |",
            "|---|---|---:|---:|---|",
        ]
    )

    for result in results:

        judge = (
            str(
                result[
                    "judge_score"
                ]
            )
            if result.get(
                "judge_score"
            )
            is not None
            else "-"
        )

        lines.append(
            "| "
            + escape_table_cell(
                result[
                    "test_id"
                ]
            )
            + " | "
            + escape_table_cell(
                result[
                    "status"
                ]
            )
            + " | "
            + judge
            + " | "
            + str(
                result.get(
                    "latency_seconds",
                    0,
                )
            )
            + "s | "
            + escape_table_cell(
                result[
                    "question"
                ]
            )
            + " |"
        )

    for result in results:

        lines.extend(
            [
                "",
                f"### "
                f"{result['test_id']} "
                f"- "
                f"{result['status']}",
                "",
                "**Question:** "
                + result[
                    "question"
                ],
                "",
                "**Expected answer:** "
                + result.get(
                    "expected_answer",
                    "",
                ),
                "",
                "**Actual answer:** "
                + result.get(
                    "actual_answer",
                    "",
                ),
                "",
            ]
        )

        if result.get(
            "checks"
        ):

            lines.append(
                "**Deterministic checks:**"
            )

            lines.append(
                ""
            )

            for (
                name,
                check,
            ) in result[
                "checks"
            ].items():

                marker = (
                    "PASS"
                    if check[
                        "passed"
                    ]
                    else "FAIL"
                )

                lines.append(
                    f"- {name}: "
                    f"{marker}. "
                    f"{check['reason']}"
                )

            lines.append(
                ""
            )

        if (
            result.get(
                "judge_score"
            )
            is not None
        ):

            lines.append(
                "**LLM judge:** "
                f"{result['judge_score']}/5. "
                f"{result.get('judge_reason', '')}"
            )

            lines.append(
                ""
            )

        elif result.get(
            "judge_error"
        ):

            lines.append(
                "**LLM judge:** "
                "Not scored. "
                + result[
                    "judge_error"
                ]
            )

            lines.append(
                ""
            )

        if result.get(
            "actual_sql"
        ):

            lines.extend(
                [
                    "**SQL:**",
                    "",
                    "```sql",
                    result[
                        "actual_sql"
                    ],
                    "```",
                    "",
                ]
            )

        if result.get(
            "error"
        ):

            lines.append(
                "**Error:** "
                + str(
                    result.get(
                        "error_type",
                        "",
                    )
                )
                + ": "
                + result[
                    "error"
                ]
            )

            lines.append(
                ""
            )

        if result.get(
            "langsmith_trace"
        ):

            lines.append(
                "**LangSmith trace:** "
                + result[
                    "langsmith_trace"
                ]
            )

            lines.append(
                ""
            )

    report_file.write_text(
        "\n".join(
            lines
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------
# COMMAND LINE OPTIONS
# ---------------------------------------------------------

def build_parser():

    parser = (
        argparse.ArgumentParser(
            description=(
                "Run the Demografy "
                "Golden Dataset evaluation."
            )
        )
    )

    parser.add_argument(
        "--no-judge",
        action="store_true",
        help=(
            "Skip Gemini LLM judge "
            "and run deterministic "
            "checks only."
        ),
    )

    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        help=(
            "Run a specific case by "
            "number or ID. "
            "Can be repeated."
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=(
            DEFAULT_DELAY_SECONDS
        ),
        help=(
            "Seconds to wait between "
            "cases. Default: "
            f"{DEFAULT_DELAY_SECONDS:g}."
        ),
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=(
            DEFAULT_REPORT_FILE
        ),
        help=(
            "Markdown report path."
        ),
    )

    parser.add_argument(
        "--no-report",
        action="store_true",
        help=(
            "Do not write the "
            "Markdown report."
        ),
    )

    return parser


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main(
    argv=None,
):

    parser = (
        build_parser()
    )

    args = (
        parser.parse_args(
            argv
        )
    )

    if args.delay < 0:

        parser.error(
            "--delay cannot "
            "be negative."
        )

    dataset = (
        load_golden_dataset()
    )

    selected = (
        select_cases(
            dataset,
            args.cases,
        )
    )

    results = []

    for (
        index,
        test,
    ) in enumerate(
        selected,
        start=1,
    ):

        result = run_test(
            test,
            use_judge=(
                not args.no_judge
            ),
        )

        results.append(
            result
        )

        if (
            index
            < len(
                selected
            )
            and args.delay > 0
        ):

            print()

            print(
                f"Waiting "
                f"{args.delay:g}s "
                f"before next test..."
            )

            time.sleep(
                args.delay
            )

    summary = (
        print_summary(
            results
        )
    )

    if not args.no_report:

        write_markdown_report(
            results,
            args.report,
        )

        print(
            f"Report written to: "
            f"{args.report}"
        )

    # Exit codes are useful later
    # for CI/CD regression testing.

    if (
        summary[
            "errors"
        ]
        > 0
    ):
        return 2

    if (
        summary[
            "failed"
        ]
        > 0
    ):
        return 1

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )