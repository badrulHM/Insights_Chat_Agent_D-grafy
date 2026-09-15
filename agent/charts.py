"""Choose the right visual for a result set.

Decides *whether* a visual helps and *which* one; renders nothing, so the UI
stays free to draw it. `ui_charts.build_chart` does the drawing.

WHAT IS AVAILABLE, AND WHY IT IS NOT "every chart type":

  * Scope boundaries section 9 permits "simple bar charts, column charts, or
    tables only. No maps, heatmaps, or complex interactive dashboards."
  * The master view has NO date, year or timestamp column - it is a single
    snapshot. Line and area charts need a time axis, so they cannot be drawn
    from this data at all, and section 4.5 forbids trend claims anyway.
  * Pie charts need parts of a whole. Nearly every KPI here is a percentage
    *within* a suburb (Social Housing is 20% of that suburb's dwellings), so
    slices across suburbs would not sum to anything and would mislead.

So the permitted, meaningful set is: horizontal bar, vertical column, grouped
and stacked variants, and a table. Selection below picks between them using
the question's intent and the shape of the result.

Text is always the primary answer; the visual is supplementary.
"""

# Chart types this module can return.
BAR = "bar"                        # horizontal, one measure
COLUMN = "column"                  # vertical, one measure
GROUPED_BAR = "grouped_bar"        # horizontal, several measures side by side
GROUPED_COLUMN = "grouped_column"  # vertical, several measures side by side
STACKED_BAR = "stacked_bar"        # horizontal, measures that sum to a whole
TABLE = "table"                    # explicitly permitted by section 9

MIN_ROWS = 2
# Beyond this a bar chart in a panel is less readable than the text; a table
# still works, so fall back to one.
MAX_CHART_ROWS = 12
MAX_TABLE_ROWS = 50
# More than three series on one axis is unreadable whatever the orientation.
MAX_SERIES = 3
# Vertical columns only when the labels are short enough not to overlap.
SHORT_LABEL = 12
MAX_COLUMN_CATEGORIES = 8

# Columns that label a bar rather than measure one.
LABEL_COLUMNS = ("sa2_name", "state", "sa3_name", "sa4_name", "gcca_name")

# Question wording that signals measures should sit side by side ...
COMPARISON_WORDS = ("compare", "versus", " vs ", "against", "difference")
# ... or be broken into parts of a whole.
BREAKDOWN_WORDS = ("breakdown", "split", "composition", "make up", "made up")


class ChartSpec:
    """A description of the visual to draw. Rendering is the caller's job."""

    def __init__(self, chart_type, label_column, value_columns, rows, title=None):
        self.chart_type = chart_type
        self.label_column = label_column
        self.value_columns = value_columns
        self.rows = rows
        self.title = title

    @property
    def is_table(self):
        return self.chart_type == TABLE

    @property
    def is_horizontal(self):
        return self.chart_type in (BAR, GROUPED_BAR, STACKED_BAR)

    @property
    def is_stacked(self):
        return self.chart_type == STACKED_BAR

    def to_dataframe(self):
        """Rows as a DataFrame: label column plus the chosen measures."""
        import pandas as pd

        frame = pd.DataFrame(self.rows)
        columns = [self.label_column] + list(self.value_columns)

        return frame[[c for c in columns if c in frame.columns]]

    def to_table_frame(self):
        """Every column - nothing is hidden when the result is shown as a table."""
        import pandas as pd

        return pd.DataFrame(self.rows)

    def as_dict(self):
        return {
            "chart_type": self.chart_type,
            "label_column": self.label_column,
            "value_columns": list(self.value_columns),
            "title": self.title,
            "row_count": len(self.rows),
        }

    def __repr__(self):
        return (
            f"ChartSpec({self.chart_type}, x={self.label_column}, "
            f"y={self.value_columns}, rows={len(self.rows)})"
        )


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _classify_columns(rows):
    """Split columns into (label candidates, numeric columns)."""
    labels = []
    numerics = []

    for column in rows[0].keys():
        present = [r.get(column) for r in rows if r.get(column) is not None]

        if not present:
            continue

        if all(_is_number(v) for v in present):
            numerics.append(column)
        elif all(isinstance(v, str) for v in present):
            labels.append(column)

    return labels, numerics


def _pick_label_column(labels, rows):
    """Prefer a known geography column, else the first label that is unique."""
    for preferred in LABEL_COLUMNS:
        if preferred in labels:
            return preferred

    for column in labels:
        values = [row.get(column) for row in rows]
        if len(set(values)) == len(values):
            return column

    return labels[0] if labels else None


def _relevance(column, question):
    """How well a result column matches what the user asked about.

    "Top 5 suburbs by diversity index" over columns (population,
    diversity_index) must chart diversity, not population.
    """
    if not question:
        return 0

    asked = question.lower()
    words = [w for w in column.lower().replace("_", " ").split() if len(w) > 3]

    return sum(1 for word in words if word in asked)


def _magnitude(rows, column):
    """Rough scale bucket, so mismatched axes are never combined."""
    values = [abs(r.get(column)) for r in rows if _is_number(r.get(column))]
    peak = max(values) if values else 0

    if peak <= 1.5:
        return "index"
    if peak <= 100:
        return "percent"

    return "count"


def _comparable_values(rows, numerics, question):
    """Measures that can share one axis, anchored on what the question asked."""
    candidates = [c for c in numerics if not c.endswith("_code")]

    if not candidates:
        return []

    anchor = max(
        candidates,
        key=lambda c: (_relevance(c, question), -candidates.index(c)),
    )
    primary = _magnitude(rows, anchor)

    return [c for c in candidates if _magnitude(rows, c) == primary]


def _parts_of_a_whole(rows, measures):
    """True if each row's measures sum to ~100% or ~1 - i.e. a composition.

    Only then is stacking honest. Stacking independent percentages invents a
    total that does not exist.
    """
    if len(measures) < 2:
        return False

    for row in rows:
        values = [row.get(m) for m in measures]

        if not all(_is_number(v) for v in values):
            return False

        total = sum(values)

        if not (99.0 <= total <= 101.0 or 0.99 <= total <= 1.01):
            return False

    return True


def _wants_comparison(question):
    asked = (question or "").lower()
    return any(word in asked for word in COMPARISON_WORDS)


def _wants_breakdown(question):
    asked = (question or "").lower()
    return any(word in asked for word in BREAKDOWN_WORDS)


def _orientation(rows, label_column):
    """Vertical columns for few, short labels; horizontal bars otherwise.

    SA2 names run past 30 characters, so suburb rankings are always
    horizontal; state and region comparisons often fit vertically.
    """
    labels = [str(r.get(label_column) or "") for r in rows]

    if len(labels) <= MAX_COLUMN_CATEGORIES and all(
        len(v) <= SHORT_LABEL for v in labels
    ):
        return "column"

    return "bar"


def suggest_chart(rows, question=None):
    """Return a ChartSpec for these rows, or None if no visual helps.

    Falls back to a table rather than nothing whenever the data is worth
    showing but will not fit a bar chart - too many rows, too many measures,
    or scales that cannot share an axis.
    """
    if not rows or not isinstance(rows, list) or not isinstance(rows[0], dict):
        return None

    labels, numerics = _classify_columns(rows)

    if not numerics:
        return None

    def table():
        return ChartSpec(
            chart_type=TABLE,
            label_column=_pick_label_column(labels, rows) or list(rows[0])[0],
            value_columns=numerics,
            rows=rows,
            title=(question or "").strip() or None,
        )

    # A single number is a sentence, not a visual. A single row with several
    # measures is a profile, which reads best as a table.
    if len(rows) < MIN_ROWS:
        return table() if len(numerics) > 1 else None

    if len(rows) > MAX_CHART_ROWS:
        return table() if len(rows) <= MAX_TABLE_ROWS else None

    label_column = _pick_label_column(labels, rows)

    if label_column is None:
        return table()

    # Duplicate labels would silently merge into one bar.
    label_values = [row.get(label_column) for row in rows]

    if len(set(label_values)) < len(label_values):
        return table()

    measures = _comparable_values(rows, numerics, question)

    if not measures:
        return table()

    if len(measures) > MAX_SERIES:
        return table()

    orientation = _orientation(rows, label_column)

    if len(measures) == 1:
        chart_type = BAR if orientation == "bar" else COLUMN
    elif _parts_of_a_whole(rows, measures) and (
        _wants_breakdown(question) or not _wants_comparison(question)
    ):
        # Stacking is only honest for a composition.
        chart_type = STACKED_BAR
    else:
        chart_type = GROUPED_BAR if orientation == "bar" else GROUPED_COLUMN

    return ChartSpec(
        chart_type=chart_type,
        label_column=label_column,
        value_columns=measures,
        rows=rows,
        title=(question or "").strip() or None,
    )
