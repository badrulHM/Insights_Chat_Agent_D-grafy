"""Helpers for turning query results into readable text (spec 4.1).

Text is the primary output. Chart rendering is a stretch goal (spec 4.2) and
deliberately not started here.
"""


def format_rows_as_markdown(rows, max_rows=25):
    """Render a list of dict rows as a markdown table."""
    if not rows:
        return "_No matching rows._"

    columns = list(rows[0].keys())
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, divider]

    for row in rows[:max_rows]:
        cells = [_format_cell(row.get(column)) for column in columns]
        lines.append("| " + " | ".join(cells) + " |")

    if len(rows) > max_rows:
        lines.append(f"\n_Showing {max_rows} of {len(rows)} rows._")

    return "\n".join(lines)


def _format_cell(value):
    if value is None:
        return "-"

    if isinstance(value, float):
        # The 0-1 KPIs (Diversity Index, Household Mobility) need more decimals
        # than the 0-100% ones, or distinct suburbs render as the same number.
        return f"{value:,.4f}" if abs(value) < 10 else f"{value:,.2f}"

    if isinstance(value, int):
        return f"{value:,}"

    return str(value)


def message_text(content):
    """Flatten LangChain 1.x message content to plain text.

    Content may be a string or a list of typed blocks (text, reasoning, ...).
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []

        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))

        return "".join(parts)

    return str(content or "")


def extract_sql(messages):
    """Pull the last SQL statement the agent actually executed.

    Walks the LangGraph message list for tool calls to the query tool. The
    query *checker* is skipped - it only echoes a candidate back, so taking it
    would report SQL that may never have run.
    """
    sql = None

    for message in messages or []:
        for call in getattr(message, "tool_calls", None) or []:
            name = (call.get("name") or "").lower()

            if "query" not in name or "checker" in name:
                continue

            args = call.get("args") or {}
            candidate = args.get("query") or args.get("__arg1")

            if isinstance(candidate, str) and candidate.strip():
                sql = candidate.strip()

    return sql
