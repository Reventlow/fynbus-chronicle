"""
Server-side helpdesk trend chart generation using matplotlib.

Generates a line chart of open helpdesk tickets over time,
returned as a base64-encoded PNG data URI for embedding in exports.
"""

import base64
import io

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

matplotlib.use("Agg")


def generate_helpdesk_chart(weeklog) -> str | None:
    """
    Generate a helpdesk open-tickets trend chart.

    Queries up to 12 most recent WeekLogs (ending at the given weeklog)
    and renders a line chart showing open ticket counts over time.
    The current weeklog's data point is highlighted.

    Args:
        weeklog: The WeekLog instance being exported.

    Returns:
        Base64-encoded PNG data URI string, or None if insufficient data.
    """
    from django.db.models import Q

    from ..models import WeekLog

    # Get up to 12 weeks of data ending at this weeklog (inclusive)
    recent_logs = list(
        WeekLog.objects.filter(
            Q(year__lt=weeklog.year)
            | Q(year=weeklog.year, week_number__lte=weeklog.week_number)
        ).order_by("-year", "-week_number")[:12]
    )

    # Need at least 2 data points for a meaningful chart
    if len(recent_logs) < 2:
        return None

    # Reverse to chronological order
    recent_logs.reverse()

    # Build data series
    labels = [f"U{log.week_number}" for log in recent_logs]
    open_counts = [log.helpdesk_open for log in recent_logs]

    # Project colors
    color_sand = "#8B7355"
    color_gold = "#C4A35A"
    color_dark = "#4A4540"
    color_bg = "#FAF9F7"
    color_grid = "#E5E0D8"

    # Create figure
    fig, ax = plt.subplots(figsize=(7, 2.8))
    fig.patch.set_facecolor(color_bg)
    ax.set_facecolor(color_bg)

    # Plot line
    ax.plot(
        labels,
        open_counts,
        color=color_sand,
        linewidth=2,
        marker="o",
        markersize=5,
        markerfacecolor=color_sand,
        markeredgecolor=color_sand,
        zorder=2,
    )

    # Highlight current weeklog (last point)
    ax.plot(
        labels[-1],
        open_counts[-1],
        marker="o",
        markersize=9,
        markerfacecolor=color_gold,
        markeredgecolor=color_dark,
        markeredgewidth=2,
        zorder=3,
    )

    # Styling
    ax.set_title("Åbne sager over tid", fontsize=12, color=color_dark, pad=10)
    ax.set_ylabel("Åbne sager", fontsize=10, color=color_dark)
    ax.tick_params(axis="both", colors=color_dark, labelsize=9)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.grid(axis="y", color=color_grid, linewidth=0.8)
    ax.set_axisbelow(True)

    # Clean up spines
    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()

    # Render to base64 PNG
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    encoded = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
