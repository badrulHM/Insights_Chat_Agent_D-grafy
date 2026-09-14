"""Helpers for reading what the agent produced.

`message_text` flattens LangChain 1.x content blocks; `extract_sql` recovers
the query the agent actually executed, for charting and evaluation.
"""


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
