# eval/judge.py

import os
import time
from google import genai


# Judge model
JUDGE_MODEL = os.getenv(
    "EVAL_JUDGE_MODEL",
    "gemini-3.5-flash"
)

# Maximum retry attempts when Gemini returns a rate limit error
MAX_RETRIES = 3

# First wait period before retrying
INITIAL_RETRY_WAIT = 30


def is_rate_limit_error(error):
    """
    Check whether an exception is caused by Gemini API rate limiting.
    """

    error_text = str(error).lower()

    return (
        "429" in error_text
        or "resource_exhausted" in error_text
        or "rate limit" in error_text
        or "quota exceeded" in error_text
    )


def judge_answer(question, expected_answer, actual_answer):
    """
    Ask Gemini to judge whether the agent's answer is correct.

    Returns a dictionary.

    Example successful result:

    {
        "score": 1.0,
        "reason": "The answer matches the expected result.",
        "status": "SUCCESS"
    }

    If the judge cannot run:

    {
        "score": None,
        "reason": "...",
        "status": "ERROR"
    }
    """

    # Do not call the judge if there is no usable agent answer
    if actual_answer is None or str(actual_answer).strip() == "":
        return {
            "score": None,
            "reason": "No agent answer was available to judge.",
            "status": "NOT_SCORED",
        }

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        return {
            "score": None,
            "reason": "GOOGLE_API_KEY is not configured.",
            "status": "ERROR",
        }

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are evaluating an AI demographic insights agent.

QUESTION:
{question}

EXPECTED ANSWER:
{expected_answer}

ACTUAL AGENT ANSWER:
{actual_answer}

Judge whether the actual answer is correct based on the expected answer.

Return only one of these values:

1

if the answer is correct or meaningfully equivalent.

Return:

0

if the answer is incorrect.

Do not return any other text.
"""

    wait_seconds = INITIAL_RETRY_WAIT

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = client.models.generate_content(
                model=JUDGE_MODEL,
                contents=prompt,
            )

            response_text = (response.text or "").strip()

            if response_text.startswith("1"):
                return {
                    "score": 1.0,
                    "reason": "LLM judge marked the answer as correct.",
                    "status": "SUCCESS",
                }

            if response_text.startswith("0"):
                return {
                    "score": 0.0,
                    "reason": "LLM judge marked the answer as incorrect.",
                    "status": "SUCCESS",
                }

            return {
                "score": None,
                "reason": f"Unexpected judge response: {response_text}",
                "status": "ERROR",
            }

        except Exception as error:

            if is_rate_limit_error(error):

                print(
                    f"LLM Judge rate limited. "
                    f"Attempt {attempt}/{MAX_RETRIES}."
                )

                if attempt < MAX_RETRIES:
                    print(
                        f"Waiting {wait_seconds} seconds before retry..."
                    )

                    time.sleep(wait_seconds)

                    # Increase the delay for the next retry
                    wait_seconds = wait_seconds * 2

                    continue

                return {
                    "score": None,
                    "reason": f"LLM judge rate limited: {error}",
                    "status": "ERROR",
                }

            return {
                "score": None,
                "reason": f"LLM judge error: {error}",
                "status": "ERROR",
            }

    return {
        "score": None,
        "reason": "LLM judge could not complete.",
        "status": "ERROR",
    }