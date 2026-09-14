"""Automated evaluation runner (spec 6.2 / 6.3).

    python -m eval.run_eval                 # full run, deterministic + judge
    python -m eval.run_eval --no-judge      # deterministic only (no LLM cost)
    python -m eval.run_eval --case 1 --case 7

Every case is checked twice:
  1. Deterministically, against ground truth computed from the database.
  2. By an LLM judge, scored 1-5 (spec 6.3).

The deterministic check is the one that decides pass/fail. The judge adds a
quality score and catches "technically right but useless" answers. Where they
disagree, the report flags it - that disagreement is usually the interesting
part of the run.

Writes docs/eval_report.md (gitignored: it contains real client data).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from agent.service import ask

DATASET_PATH = os.path.join(os.path.dirname(__file__), "golden_dataset.json")
REPORT_PATH = os.path.join("docs", "eval_report.md")


def load_cases(path=DATASET_PATH):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("cases", [])


def _numbers_in(text):
    """Every number in the answer, commas and % stripped."""
    import re

    found = []

    for raw in re.findall(r"-?\d[\d,]*\.?\d*", text or ""):
        try:
            found.append(float(raw.replace(",", "")))
        except ValueError:
            continue

    return found


def validate(case, answer, sql):
    """Deterministic check. Returns (passed, detail)."""
    kind = case.get("validation")
    expected = case.get("expected")
    text = (answer or "").lower()

    if kind == "contains_all":
        missing = [e for e in expected if e.lower() not in text]
        return (not missing), (
            "all expected values present" if not missing
            else f"missing: {', '.join(missing)}"
        )

    if kind == "first_of":
        # Ordering matters, but ties make the exact leader unstable; accept any
        # of the true top results appearing.
        hit = [e for e in expected if e.lower() in text]
        return bool(hit), (
            f"found {hit[0]}" if hit else f"none of {expected} present"
        )

    if kind == "numeric":
        tolerance = float(case.get("tolerance", 1.0))
        target = float(expected)
        close = [n for n in _numbers_in(text) if abs(n - target) <= tolerance]
        return bool(close), (
            f"found {close[0]} (expected {target} +/- {tolerance})" if close
            else f"expected {target} +/- {tolerance}, saw {_numbers_in(text)[:6]}"
        )

    if kind == "refusal":
        # Any phrasing that admits the definition is unavailable.
        hit = [e for e in expected if e.lower() in text]
        if hit:
            return True, f"correctly refused ('{hit[0]}')"
        return False, "did not refuse - possible hallucination"

    return False, f"unknown validation type: {kind}"


def check_sql(case, sql):
    """Soft check that the SQL looks right. Never fails a case on its own."""
    wanted = case.get("expected_sql_contains") or []

    if not wanted:
        return True, "n/a"

    if not sql:
        return False, "no SQL captured"

    lowered = sql.lower()
    missing = [w for w in wanted if w.lower() not in lowered]

    return (not missing), ("ok" if not missing else f"missing {missing}")


# Failure codes that mean "the case never really ran". Counting these as wrong
# answers produces a report that understates accuracy and sends people hunting
# for prompt bugs that do not exist.
INFRA_FAILURES = ("rate_limited", "model_unavailable", "data_unavailable")


def run_case(case, use_judge=True, judge_llm=None, retries=3, backoff=20):
    """Run one case, retrying through rate limits rather than scoring them."""
    started = time.perf_counter()
    result = None

    for attempt in range(retries + 1):
        result = ask(case["question"], user_id="eval_harness", tier="pro")

        if result.reason != "rate_limited" or attempt == retries:
            break

        wait = backoff * (attempt + 1)
        print(f"         rate limited, waiting {wait}s "
              f"(attempt {attempt + 1}/{retries})...")
        time.sleep(wait)

    elapsed = time.perf_counter() - started

    if result.reason in INFRA_FAILURES:
        return {
            "id": case["id"],
            "question": case["question"],
            "status": "error",
            "passed": False,
            "detail": f"infrastructure failure ({result.reason}) - case did not run",
            "sql_ok": False,
            "sql_detail": "n/a",
            "judge_score": None,
            "judge_reason": None,
            "answer": result.answer,
            "sql": result.sql,
            "error": result.error,
            "reason_code": result.reason,
            "trace_url": result.trace_url,
            "elapsed": elapsed,
        }

    passed, detail = validate(case, result.answer, result.sql)
    sql_ok, sql_detail = check_sql(case, result.sql)

    score, reason = None, None

    if use_judge:
        from eval.judge import score_answer

        score, reason = score_answer(
            case["question"], case.get("expected"), result.answer,
            result.sql, llm=judge_llm,
        )

    return {
        "id": case["id"],
        "question": case["question"],
        "status": "ok",
        "passed": passed,
        "detail": detail,
        "sql_ok": sql_ok,
        "sql_detail": sql_detail,
        "judge_score": score,
        "judge_reason": reason,
        "answer": result.answer,
        "sql": result.sql,
        "error": result.error,
        "reason_code": result.reason,
        "trace_url": result.trace_url,
        "elapsed": elapsed,
    }


def build_report(results, use_judge):
    errored = [r for r in results if r.get("status") == "error"]
    scored_cases = [r for r in results if r.get("status") != "error"]
    passed = [r for r in scored_cases if r["passed"]]
    accuracy = (len(passed) / len(scored_cases) * 100) if scored_cases else 0
    scored = [r["judge_score"] for r in results if r.get("judge_score")]
    avg_score = (sum(scored) / len(scored)) if scored else None

    lines = [
        "# Evaluation report",
        "",
        "> **CONFIDENTIAL - contains real client data. Gitignored.**",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
        f"- Cases: **{len(results)}**"
        + (f" ({len(errored)} could not run)" if errored else ""),
        f"- Passed (deterministic): **{len(passed)}/{len(scored_cases)} "
        f"= {accuracy:.0f}%**",
    ]

    if errored:
        lines.append(
            f"- **{len(errored)} case(s) failed on infrastructure** "
            f"({', '.join(sorted({r['reason_code'] for r in errored}))}) and are "
            "excluded from accuracy. Re-run them before quoting this report."
        )

    if avg_score is not None:
        lines.append(f"- Mean judge score: **{avg_score:.2f} / 5**")

    disagreements = [
        r for r in results
        if r.get("judge_score") and (r["judge_score"] >= 4) != r["passed"]
    ]

    if disagreements:
        lines.append(
            f"- **Judge disagrees with the deterministic check on "
            f"{len(disagreements)} case(s)** - review these first."
        )

    lines += [
        "",
        "## Results",
        "",
        "| # | Question | Pass | Judge | SQL | Time | Detail |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for r in results:
        mark = "ERROR" if r.get("status") == "error" else (
            "PASS" if r["passed"] else "FAIL")
        judge = f"{r['judge_score']}/5" if r.get("judge_score") else "-"
        sql_mark = "ok" if r["sql_ok"] else "?"
        lines.append(
            f"| {r['id']} | {r['question'][:48]} | {mark} | {judge} | "
            f"{sql_mark} | {r['elapsed']:.1f}s | {r['detail'][:60]} |"
        )

    lines += ["", "## Failures and disagreements", ""]
    notable = [r for r in results if not r["passed"] or r in disagreements]

    if not notable:
        lines.append("_None - every case passed and the judge agreed._")

    for r in notable:
        lines += [
            f"### Case {r['id']}: {r['question']}",
            "",
            f"- Deterministic: **{'PASS' if r['passed'] else 'FAIL'}** - {r['detail']}",
            f"- Judge: {r.get('judge_score') or '-'}/5 - {r.get('judge_reason') or ''}",
            f"- SQL check: {r['sql_detail']}",
        ]
        if r.get("trace_url"):
            lines.append(f"- [Trace]({r['trace_url']})")
        lines += ["", "```sql", (r["sql"] or "-- no SQL"), "```", "",
                  "Answer given:", "", "> " + (r["answer"] or "")[:500].replace("\n", "\n> "), ""]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run the golden-dataset eval.")
    parser.add_argument("--no-judge", action="store_true",
                        help="Skip LLM judging (deterministic checks only).")
    parser.add_argument("--case", type=int, action="append",
                        help="Run only these case ids (repeatable).")
    parser.add_argument("--delay", type=float, default=6.0,
                        help="Seconds to pause between cases (rate limits).")
    args = parser.parse_args()

    cases = load_cases()

    if args.case:
        cases = [c for c in cases if c["id"] in args.case]

    if not cases:
        print("No cases to run.")
        return 1

    use_judge = not args.no_judge
    judge_llm = None

    if use_judge:
        from eval.judge import build_judge_llm

        judge_llm = build_judge_llm()

    print(f"Running {len(cases)} case(s){' with judge' if use_judge else ''}...\n")
    results = []

    for case in cases:
        result = run_case(case, use_judge=use_judge, judge_llm=judge_llm)
        results.append(result)

        mark = "ERR " if result.get("status") == "error" else (
            "PASS" if result["passed"] else "FAIL")
        judge = f" judge={result['judge_score']}/5" if result.get("judge_score") else ""
        print(f"  [{mark}] {case['id']:>2}. {case['question'][:52]:<52}"
              f" {result['elapsed']:.1f}s{judge}")

        if not result["passed"]:
            print(f"         -> {result['detail'][:100]}")

        # Free-tier Gemini quotas are per-minute; pacing keeps a 10-case run
        # from failing halfway through for reasons unrelated to quality.
        if args.delay and case is not cases[-1]:
            time.sleep(args.delay)

    report = build_report(results, use_judge)
    os.makedirs("docs", exist_ok=True)

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write(report)

    failed = [r for r in results if not r["passed"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed. "
          f"Report written to {REPORT_PATH}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
