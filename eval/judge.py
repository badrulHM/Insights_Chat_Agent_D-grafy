"""LLM-as-a-judge support for the Demografy Golden Dataset.
The LLM judge is a secondary quality signal only.
Deterministic checks in eval/run_eval.py decide PASS or FAIL.
"""

import json
import re
from typing import Any, Dict, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from agent.tools import message_text
from config import settings


JUDGE_PROMPT = """You are grading an AI data analyst's answer.

QUESTION
{question}

EXPECTED ANSWER
{expected_answer}

EXPECTED FACTS
{expected_facts}

ACTUAL ANSWER
{actual_answer}

SQL USED BY THE AGENT
{actual_sql}

Score only the factual quality of the ACTUAL ANSWER.

5 = fully correct and complete
4 = correct data with only minor omissions or wording issues
3 = mostly correct but with a meaningful omission or small factual discrepancy
2 = partially correct with significant problems
1 = wrong, hallucinated, contradictory, or failed to answer

Rules:
- Focus on factual correctness, not writing style.
- Numeric rounding is acceptable when it preserves the expected value.
- Do not penalise harmless extra wording.
- If the expected behaviour is to refuse or explain that a definition is
  unavailable, a correct refusal/explanation should score highly.
- If the answer confidently invents information not supported by the expected
  facts, score 1.
- The SQL is context only. Do not reward correct-looking SQL if the user-facing
  answer is wrong.

Return ONLY valid JSON in this form:
{{"score": 5, "reason": "One short sentence."}}
"""


def build_judge_llm() -> ChatGoogleGenerativeAI:
    """Create a deterministic Gemini model for evaluation."""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
        max_retries=settings.gemini_max_retries,
    )


def _parse_judge_reply(raw: Any) -> Dict[str, Any]:
    """Parse the judge response into score, reason and error."""
    text = message_text(raw).strip()

    fenced = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if fenced:
        text = fenced.group(1)
    else:
        braces = re.search(
            r"\{.*\}",
            text,
            flags=re.DOTALL,
        )

        if braces:
            text = braces.group(0)

    try:
        payload = json.loads(text)

        score = int(
            payload.get("score", 0)
        )

        reason = str(
            payload.get("reason", "")
        ).strip()

        if 1 <= score <= 5:
            return {
                "score": score,
                "reason": reason[:500],
                "error": None,
            }

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        pass

    # Last-resort parser if Gemini returns prose.
    digit = re.search(
        r"\b([1-5])\b",
        text,
    )

    if digit:
        return {
            "score": int(
                digit.group(1)
            ),
            "reason": (
                "Score parsed from an "
                "unstructured judge response."
            ),
            "error": (
                "Judge did not return the "
                "requested JSON format."
            ),
        }

    return {
        "score": None,
        "reason": "",
        "error": (
            "Could not parse judge response: "
            f"{text[:200]}"
        ),
    }


def judge_answer(
    question: str,
    expected_answer: str,
    actual_answer: str,
    *,
    expected_facts: Optional[Any] = None,
    actual_sql: Optional[str] = None,
    llm: Optional[
        ChatGoogleGenerativeAI
    ] = None,
) -> Dict[str, Any]:
    """
    Return a 1-5 judge score plus reason.

    score=None means the judge itself failed.
    """

    judge_llm = (
        llm or build_judge_llm()
    )

    prompt = JUDGE_PROMPT.format(
        question=question,
        expected_answer=(
            expected_answer
            or "(not supplied)"
        ),
        expected_facts=json.dumps(
            expected_facts or {},
            ensure_ascii=False,
            indent=2,
        ),
        actual_answer=(
            actual_answer
            or "(no answer)"
        ),
        actual_sql=(
            actual_sql
            or "(no SQL executed)"
        ),
    )

    try:
        reply = judge_llm.invoke(
            prompt
        )

    except Exception as exc:
        return {
            "score": None,
            "reason": "",
            "error": (
                "Judge call failed: "
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }

    content = getattr(
        reply,
        "content",
        reply,
    )

    return _parse_judge_reply(
        content
    )


def score_answer(
    question: str,
    expected: Any,
    answer: str,
    sql: Optional[str] = None,
    llm: Optional[
        ChatGoogleGenerativeAI
    ] = None,
):
    """
    Backward-compatible wrapper.

    Returns:
        (score, reason)
    """

    result = judge_answer(
        question=question,
        expected_answer=(
            expected
            if isinstance(
                expected,
                str,
            )
            else json.dumps(
                expected,
                ensure_ascii=False,
            )
        ),
        actual_answer=answer,
        expected_facts=expected,
        actual_sql=sql,
        llm=llm,
    )

    return (
        result["score"],
        result["reason"]
        or result["error"]
        or "",
    )