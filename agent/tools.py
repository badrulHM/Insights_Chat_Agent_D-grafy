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


def extract_sql(intermediate_steps):
    """Pull the last SQL statement the agent actually executed.

    `intermediate_steps` is a list of (AgentAction, observation) pairs. The
    query-execution tool is the one whose input is the SQL string.
    """
    sql = None

    for step in intermediate_steps or []:
        action = step[0] if isinstance(step, (list, tuple)) else None

        if action is None:
            continue

        tool = getattr(action, "tool", "") or ""

        if "query" not in tool.lower() or "checker" in tool.lower():
            continue

        tool_input = getattr(action, "tool_input", None)

        if isinstance(tool_input, dict):
            tool_input = tool_input.get("query") or tool_input.get("__arg1")

        if isinstance(tool_input, str) and tool_input.strip():
            sql = tool_input.strip()

    return sql
