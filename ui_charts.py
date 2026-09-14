"""Render a ChartSpec with Plotly.

Lives on the UI side of the seam: `agent/charts.py` decides *whether* a visual
helps and *which* one; this module draws it.

Scope boundaries section 9 permits `st.bar_chart`, `st.pyplot` or
`st.plotly_chart` only, and simple bar charts, column charts or tables only -
no maps, heatmaps or custom JavaScript. Plotly is the permitted option that
also lets us pin the bar order.

Why not `st.bar_chart`: it hands the frame to Vega-Lite with a nominal axis,
which Vega sorts **alphabetically**. A "top 5 suburbs" chart therefore came out
in name order, silently contradicting the ranked list printed above it.

The TABLE type is not drawn here - the app renders it with `st.dataframe`,
which gives sorting and resizing for free.
"""

import plotly.graph_objects as go

from agent.charts import TABLE

# Demografy brand palette (brand guidelines section 3). Defined here because
# this is the only place colour is applied.
MEDIUM_SLATE_BLUE = "#9a66ee"
SERIES_COLOURS = [
    MEDIUM_SLATE_BLUE,  # Medium Slate Blue - main brand colour
    "#5e17eb",          # Ultrasonic Blue
    "#cb6ce6",          # Mauve Magic
    "#004aad",          # Cobalt Blue
    "#8df2ed",          # Soft Cyan
    "#818585",          # Grey Olive
]

BAR_THICKNESS = 26
COLUMN_HEIGHT = 300
MIN_HEIGHT = 160
MAX_HEIGHT = 380


def _pretty(name):
    """kpi_2_val -> Kpi 2 Val; avg_rental_access -> Avg Rental Access."""
    return name.replace("_", " ").strip().title()


def _value_format(values):
    """Value precision: 0-1 indices need decimals, counts do not."""
    numbers = [abs(v) for v in values if isinstance(v, (int, float))]
    peak = max(numbers) if numbers else 0

    if peak <= 1.5:
        return ".3f"
    if peak <= 100:
        return ".1f"

    return ",.0f"


def _height(spec, categories):
    """Deterministic sizing, so the page does not jump as the chat grows."""
    if spec.is_horizontal:
        series = 1 if spec.is_stacked else len(spec.value_columns)
        return min(
            max(BAR_THICKNESS * len(categories) * series + 70, MIN_HEIGHT),
            MAX_HEIGHT,
        )

    return COLUMN_HEIGHT


def build_chart(spec):
    """Return a Plotly figure for this ChartSpec.

    Raises ValueError for the TABLE type, which the app renders itself.

    Sets no font or background colours: `st.plotly_chart` applies Streamlit's
    own chart theme, which already tracks the active light/dark palette.
    Hardcoding them produced dark labels on a dark background.
    """
    if spec.chart_type == TABLE:
        raise ValueError("TABLE specs are rendered with st.dataframe, not Plotly")

    measures = list(spec.value_columns)
    categories = [str(row.get(spec.label_column)) for row in spec.rows]
    number_format = _value_format(
        [row.get(m) for row in spec.rows for m in measures]
    )

    figure = go.Figure()

    for index, measure in enumerate(measures):
        values = [row.get(measure) for row in spec.rows]
        colour = SERIES_COLOURS[index % len(SERIES_COLOURS)]

        if spec.is_horizontal:
            axes = {"y": categories, "x": values, "orientation": "h"}
            template = f"%{{y}}<br>{_pretty(measure)}: %{{x:{number_format}}}"
        else:
            axes = {"x": categories, "y": values}
            template = f"%{{x}}<br>{_pretty(measure)}: %{{y:{number_format}}}"

        figure.add_trace(
            go.Bar(
                name=_pretty(measure),
                marker_color=colour,
                hovertemplate=template + "<extra></extra>",
                **axes,
            )
        )

    figure.update_layout(
        barmode="stack" if spec.is_stacked else "group",
        height=_height(spec, categories),
        margin=dict(l=4, r=4, t=30 if len(measures) > 1 else 8, b=4),
        showlegend=len(measures) > 1,
        legend=dict(orientation="h", y=1.14, x=0, title_text=""),
        xaxis_title=None,
        yaxis_title=None,
        bargap=0.25,
    )

    # The order the query returned IS the ranking - pin it so Plotly cannot
    # re-sort. On a horizontal axis Plotly draws the first category at the
    # bottom, so reverse it to put the top-ranked bar on top.
    if spec.is_horizontal:
        figure.update_yaxes(
            categoryorder="array",
            categoryarray=list(reversed(categories)),
            automargin=True,
        )
    else:
        figure.update_xaxes(
            categoryorder="array", categoryarray=categories, automargin=True
        )

    return figure
