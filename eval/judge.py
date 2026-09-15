"""LLM-as-a-judge scoring (spec 6.3).

Scores an answer 1-5 against the expected result:

    5  perfect match with correct data
    4  correct data, minor formatting issues
    3  mostly correct, small discrepancies
    2  partially correct, significant errors
    1  wrong answer or failed to execute

The judge is deliberately a *second* signal. `run_eval.py` also checks the
answer deterministically (exact names, numeric tolerance), because an LLM
grading an LLM shares blind spots - both can agree on a plausible wrong number.
Where the two disagree, trust the deterministic check and read the trace.
"""

import json
import re

from langchain_google_genai import ChatGoogleGenerativeAI

from agent.tools import message_text
from config import settings

JUDGE_PROMPT = """You are grading a data analyst's answer against known-correct data.

QUESTION:
{question}

EXPECTED (ground truth computed directly from the database):
{expected}

ACTUAL ANSWER GIVEN:
{answer}

SQL THE ANALYST RAN:
{sql}

Score the ACTUAL ANSWER 1-5:
5 = perfect match with correct data
4 = correct data, minor formatting issues
3 = mostly correct, small discrepancies
2 = partially correct, significant errors
1 = wrong answer, hallucinated data, or failed to execute

Rules:
- Judge the DATA, not the writing style. Extra prose is fine.
- Numbers within 1% of expected are correct.
- If the expected behaviour is a refusal, a correct refusal scores 5 and a
  confident invented answer scores 1.
- Inventing data that is not in the expected result is always a 1.

Respond with ONLY a JSON object:
{{"score": <1-5>, "reason": "<one sentence>"}}"""


def build_judge_llm():
    """A separate, deterministic model instance for grading."""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
        max_retries=settings.gemini_max_retries,
    )


def _parse_score(raw):
    """Pull {"score": n, "reason": "..."} out of the model's reply."""
    text = message_text(raw).strip()

    # Models often wrap JSON in a markdown fence.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        braces = re.search(r"\{.*\}", text, re.DOTALL)
        if braces:
            text = braces.group(0)

    try:
        data = json.loads(text)
        score = int(data.get("score", 0))
        if 1 <= score <= 5:
            return score, str(data.get("reason", ""))[:300]
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Last resort: a bare digit somewhere in the reply.
    digit = re.search(r"\b([1-5])\b", text)
    if digit:
        return int(digit.group(1)), "parsed from unstructured reply"

    return 0, f"could not parse judge reply: {text[:120]}"


def score_answer(question, expected, answer, sql=None, llm=None):
    """Return (score, reason). Score 0 means the judge itself failed."""
    llm = llm or build_judge_llm()

    prompt = JUDGE_PROMPT.format(
        question=question,
        expected=json.dumps(expected, ensure_ascii=False),
        answer=answer or "(no answer)",
        sql=sql or "(no SQL executed)",
    )

    try:
        reply = llm.invoke(prompt)
    except Exception as exc:
        return 0, f"judge call failed: {type(exc).__name__}: {exc}"

    return _parse_score(reply.content)
