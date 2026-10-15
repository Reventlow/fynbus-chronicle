"""
Exports of the Statistik page: PDF, HTML, Markdown and JSON.

All four are built from the same two dicts the page uses
(``helpdesk_statistics`` and ``chronicle_statistics``), so an export always
shows the numbers the page showed at that moment.

* **PDF / HTML** share one template (``dashboard/exports/statistics_report.html``)
  and the week report's stylesheet (``static/css/pdf_styles.css``). The
  charts are drawn server-side with matplotlib and embedded as data URIs,
  so the files work offline.
* **Markdown** is plain tables, for pasting into documents and tickets.
* **JSON** is a self-describing document — every figure has a stable
  English key, an explicit unit, and the definitions behind it — meant to
  be handed to other tools (e.g. Claude Motion for animated summaries)
  without having to know Chronicle.
"""

import base64
import io
from datetime import date, datetime, timedelta

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from .statistics import (
    RESOLUTION_BUCKETS,
    WINDOW_DAYS,
    chronicle_statistics,
    helpdesk_statistics,
)

JSON_SCHEMA = "fynbus-chronicle/statistics"
JSON_SCHEMA_VERSION = 1

# Colours matching the week report's charts (apps/logbook/exports/chart.py).
_INK = "#4A4540"
_GRID = "#E5E0D8"
_BG = "#FFFFFF"
_INFO = "#286ED2"
_GOOD = "#468E66"
_ACCENT = "#B48438"
_BAD = "#A65D57"


def collect(now: datetime | None = None) -> dict:
    """Both statistics dicts plus the period, computed once for an export."""
    now = now or timezone.now()
    return {
        "now": now,
        "period_start": now - timedelta(days=WINDOW_DAYS),
        "helpdesk": helpdesk_statistics(now),
        "chronicle": chronicle_statistics(now),
    }


def filename(data: dict, extension: str) -> str:
    """``statistik_2026-10-15.<ext>``."""
    return f"statistik_{timezone.localtime(data['now']).date().isoformat()}.{extension}"


# --- JSON ---------------------------------------------------------------------


def _iso(value) -> str | None:
    if isinstance(value, datetime):
        return timezone.localtime(value).isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return None


def generate_json(data: dict) -> dict:
    """The statistics as a self-describing, tool-friendly document.

    Keys are English and stable (bump ``JSON_SCHEMA_VERSION`` on any
    breaking change); human-facing labels are Danish, as on the page.
    """
    h, c = data["helpdesk"], data["chronicle"]
    res = h["resolution"]
    pr, inc = c["priorities"], c["incidents"]

    return {
        "schema": JSON_SCHEMA,
        "schema_version": JSON_SCHEMA_VERSION,
        "generated_at": _iso(data["now"]),
        "language_of_labels": "da",
        "organisation": "FynBus IT",
        "period": {
            "start": _iso(data["period_start"]),
            "end": _iso(data["now"]),
            "days": WINDOW_DAYS,
            "description": "De seneste 12 måneder (rullende 365 dage).",
        },
        "sources": {
            "helpdesk": "ManageEngine ServiceDesk Plus (synkroniseret kopi i Chronicle)",
            "helpdesk_last_sync": _iso(h["last_sync"]),
            "chronicle": "FynBus Chronicle: prioriterede opgaver og hændelser",
        },
        "definitions": {
            "solved": "Lukket og ikke annulleret. Annullerede sager lukker en sag, men tæller ikke som løst.",
            "resolution_time": "Kalendertid fra oprettelse til lukning; nætter og weekender tæller med.",
            "median": "Den typiske sag: halvdelen er løst hurtigere, halvdelen langsommere.",
            "mean": "Summen af alle løsningstider delt med antallet; trækkes op af få meget lange sager.",
            "p90": "90 % af sagerne er løst inden for denne tid.",
            "weekday_average": "Nye sager på en gennemsnitlig dag af den ugedag i perioden.",
            "open_at_week_end": "Sager oprettet før ugens udgang og ikke lukket inden da (genberegnet).",
            "times": "Lokal tid, Europe/Copenhagen.",
        },
        "helpdesk": {
            "summary": {
                "tickets_created": h["total_created"],
                "tickets_solved": h["total_solved"],
                "tickets_cancelled": h["cancelled"],
                "distinct_requesters": h["requesters"],
                "avg_tickets_per_month": h["per_month"],
                "avg_tickets_per_requester": h["per_requester"],
                "open_now": h["open_now"],
            },
            "busiest": {"weekday": h["busiest_day"], "hour": h["busiest_hour"]},
            "weekday_average": [
                {"weekday": d["day"], "avg_new_tickets": d["avg"]} for d in h["weekday_avg"]
            ],
            "hourly_heatmap": {
                "description": "Nye sager pr. ugedag (rækker) og time (kolonner 0–23) i perioden.",
                "hours": list(range(24)),
                "rows": [
                    {
                        "weekday": row["day"],
                        "counts": [cell["count"] for cell in row["cells"]],
                        "avg_per_day": [cell["avg"] for cell in row["cells"]],
                    }
                    for row in h["heatmap"]
                ],
                "max_count": h["heat_max"],
            },
            "resolution_time": {
                "solved_tickets_measured": res["count"],
                "median_hours": res["median_hours"],
                "mean_hours": res["mean_hours"],
                "p90_hours": res["p90_hours"],
                "solved_within_24h_percent": res["within_day"],
                "display": {"median": res["median"], "mean": res["mean"], "p90": res["p90"]},
                "distribution": [
                    {
                        "bucket": b["label"],
                        "upper_bound_hours": upper,
                        "count": b["count"],
                        "percent": b["share"],
                    }
                    for b, (_label, upper) in zip(res["buckets"], RESOLUTION_BUCKETS)
                ],
            },
            "weekly": [
                {
                    "week": w["label"],
                    "week_start": _iso(w["week_start"]),
                    "created": w["created"],
                    "solved": w["solved"],
                    "open_at_week_end": w["open"],
                }
                for w in h["weekly"]
            ],
            "categories": {
                "uncategorised_count": h["uncategorised"],
                "uncategorised_percent": h["uncategorised_share"],
                "note": "Procenterne er af de kategoriserede sager.",
                "categorised": [
                    {"category": x["label"], "count": x["count"], "percent": x["share"]}
                    for x in h["categories"]
                ],
            },
            "solved_by_technician": [
                {"technician": x["label"], "count": x["count"], "percent": x["share"]}
                for x in h["technicians"]
            ],
            "open_by_age": [
                {"bucket": b["label"], "count": b["count"], "percent": b["share"], "color": b["color"]}
                for b in h["open_by_age"]
            ],
        },
        "chronicle": {
            "priority_tasks": {
                "created": pr["created"],
                "completed": pr["completed"],
                "auto_closed": pr["auto_closed"],
                "active_now": pr["active"],
                "median_lifetime_days": pr["median_days"],
                "active_by_status": [{"status": s["label"], "count": s["count"]} for s in pr["by_status"]],
                "created_by_priority": [
                    {"priority": s["label"], "count": s["count"], "percent": s["share"]}
                    for s in pr["by_priority"]
                ],
                "monthly": [
                    {"month": m, "created": cr, "completed": co}
                    for m, cr, co in zip(pr["months"], pr["created_by_month"], pr["completed_by_month"])
                ],
            },
            "incidents": {
                "total": inc["total"],
                "resolved": inc["resolved"],
                "unresolved": inc["unresolved"],
                "critical": inc["critical"],
                "avg_per_month": inc["per_month"],
                "by_severity": [{"severity": s["label"], "count": s["count"]} for s in inc["by_severity"]],
                "by_type": [
                    {"type": t["label"], "count": t["count"], "percent": t["share"]} for t in inc["by_type"]
                ],
                "monthly": [{"month": m, "count": n} for m, n in zip(inc["months"], inc["by_month"])],
            },
        },
    }


# --- Markdown -----------------------------------------------------------------


def _table(header: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return lines + [""]


def _pct(value) -> str:
    return f"{value:.0f} %"


def generate_markdown(data: dict) -> str:
    """The statistics as Markdown tables."""
    h, c = data["helpdesk"], data["chronicle"]
    res = h["resolution"]
    start = timezone.localtime(data["period_start"]).strftime("%d.%m.%Y")
    end = timezone.localtime(data["now"]).strftime("%d.%m.%Y")

    out = [
        "# FynBus IT — Statistik",
        "",
        f"Periode: {start} – {end} (seneste 12 måneder). "
        f"Genereret {timezone.localtime(data['now']).strftime('%d.%m.%Y %H:%M')}.",
        "",
        "## Helpdesk",
        "",
    ]
    out += _table(
        ["Nøgletal", "Værdi"],
        [
            ["Sager oprettet", f"{h['total_created']} (heraf {h['cancelled']} annulleret)"],
            ["Sager løst", h["total_solved"]],
            ["Kolleger der skrev", h["requesters"]],
            ["Gns. nye sager pr. måned", f"{h['per_month']:.0f}"],
            ["Åbne lige nu", h["open_now"]],
        ],
    )

    out += ["### Nye sager pr. ugedag (gennemsnit)", ""]
    out += _table(["Ugedag", "Sager i gns."], [[d["day"], f"{d['avg']:.1f}"] for d in h["weekday_avg"]])
    if h["busiest_day"]:
        out += [
            f"Travleste dag: {h['busiest_day'].lower()}. "
            f"Travleste time: kl. {h['busiest_hour']:02d}–{h['busiest_hour'] + 1:02d}.",
            "",
        ]

    out += ["### Hvornår skrives der (antal sager, kl. 06–18)", ""]
    hours = list(range(6, 19))
    out += _table(
        ["Dag"] + [f"{x:02d}" for x in hours],
        [[row["day"]] + [row["cells"][x]["count"] for x in hours] for row in h["heatmap"]],
    )

    out += ["### Løsningstid", "", "Kalendertid fra oprettelse til lukning; annullerede sager er ikke med.", ""]
    out += _table(
        ["Mål", "Værdi", "Betydning"],
        [
            ["Median", res["median"], "Halvdelen er løst hurtigere, halvdelen langsommere"],
            ["Gennemsnit", res["mean"], "Trækkes op af få meget lange sager"],
            ["9 ud af 10 løst inden", res["p90"], "De sidste 10 % tager længere"],
            ["Løst inden for et døgn", f"{res['within_day']} %", "Lukket under 24 timer efter oprettelse"],
        ],
    )
    out += _table(
        ["Løsningstid", "Sager", "Andel"],
        [[b["label"], b["count"], _pct(b["share"])] for b in res["buckets"]],
    )

    out += ["### Pr. uge", ""]
    out += _table(
        ["Uge", "Oprettet", "Løst", "Åbne ved ugens udgang"],
        [[w["label"], w["created"], w["solved"], w["open"]] for w in h["weekly"]],
    )

    out += ["### Kategorier", ""]
    if h["categories"]:
        out += _table(
            ["Kategori", "Sager", "Andel"],
            [[x["label"], x["count"], _pct(x["share"])] for x in h["categories"]],
        )
    out += [
        f"{h['uncategorised']} af {h['total_created']} sager ({h['uncategorised_share']} %) "
        "har ingen kategori; andelene ovenfor er af de kategoriserede.",
        "",
    ]

    out += ["### Løste sager pr. tekniker", ""]
    out += _table(
        ["Tekniker", "Sager", "Andel"],
        [[x["label"], x["count"], _pct(x["share"])] for x in h["technicians"]],
    )

    out += ["### Åbne sager efter alder", ""]
    out += _table(["Liggetid", "Sager"], [[b["label"], b["count"]] for b in h["open_by_age"]])

    pr, inc = c["priorities"], c["incidents"]
    out += ["## Chronicle", "", "### Prioriterede opgaver", ""]
    out += _table(
        ["Nøgletal", "Værdi"],
        [
            ["Oprettet", pr["created"]],
            ["Afsluttet", f"{pr['completed']} (heraf {pr['auto_closed']} auto-lukket)"],
            ["Aktive nu", pr["active"]],
            ["Median levetid", f"{pr['median_days']} dage" if pr["median_days"] is not None else "—"],
        ],
    )
    out += _table(
        ["Måned", "Oprettet", "Afsluttet"],
        [list(r) for r in zip(pr["months"], pr["created_by_month"], pr["completed_by_month"])],
    )

    out += ["### Nedbrud og hændelser", ""]
    out += _table(
        ["Nøgletal", "Værdi"],
        [
            ["Hændelser", inc["total"]],
            ["Pr. måned", f"{inc['per_month']:.1f}".replace(".", ",")],
            ["Kritiske", inc["critical"]],
            ["Ikke løst", inc["unresolved"]],
        ],
    )
    out += _table(["Alvorlighed", "Antal"], [[s["label"], s["count"]] for s in inc["by_severity"]])
    if inc["by_type"]:
        out += _table(
            ["Type", "Antal", "Andel"],
            [[t["label"], t["count"], _pct(t["share"])] for t in inc["by_type"]],
        )
    out += _table(["Måned", "Hændelser"], [list(r) for r in zip(inc["months"], inc["by_month"])])
    return "\n".join(out)


# --- Charts (PDF / HTML) ------------------------------------------------------


def _figure(width=7.0, height=2.6):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(width, height))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.tick_params(axis="both", colors=_INK, labelsize=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    # Counts: whole-number ticks only.
    from matplotlib.ticker import MaxNLocator

    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    return plt, fig, ax


def _encode(plt, fig) -> str:
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _bar(labels, values, color, *, percent=False, width=7.0, height=2.4) -> str:
    plt, fig, ax = _figure(width, height)
    ax.bar(labels, values, color=color, width=0.6)
    if percent:
        ax.yaxis.set_major_formatter(lambda v, _pos: f"{v:.0f} %")
    return _encode(plt, fig)


def _paired(labels, a, b, a_label, b_label, *, every=1) -> str:
    import numpy as np

    plt, fig, ax = _figure()
    x = np.arange(len(labels))
    ax.bar(x - 0.2, a, 0.4, color=_INFO, label=a_label)
    ax.bar(x + 0.2, b, 0.4, color=_GOOD, label=b_label)
    ax.set_xticks(x[::every], [labels[i] for i in range(0, len(labels), every)])
    ax.legend(frameon=False, fontsize=8, labelcolor=_INK)
    return _encode(plt, fig)


def _heatmap(heatmap: list[dict]) -> str:
    import numpy as np

    plt, fig, ax = _figure(7.0, 2.6)
    ax.grid(False)
    counts = np.array([[cell["count"] for cell in row["cells"]] for row in heatmap])
    ax.imshow(counts, cmap="Blues", aspect="auto", vmin=0)
    top = counts.max() or 1
    for (r, col), value in np.ndenumerate(counts):
        if value:
            ax.text(col, r, str(value), ha="center", va="center", fontsize=6,
                    color="white" if value / top > 0.55 else _INK)
    ax.set_xticks(range(24), [f"{h:02d}" for h in range(24)])
    ax.set_yticks(range(len(heatmap)), [row["day"] for row in heatmap])
    ax.tick_params(length=0)
    return _encode(plt, fig)


def _open_line(weekly: list[dict]) -> str:
    plt, fig, ax = _figure()
    labels = [w["label"] for w in weekly]
    values = [w["open"] for w in weekly]
    ax.plot(labels, values, color=_ACCENT, linewidth=2)
    ax.fill_between(labels, values, color=_ACCENT, alpha=0.12)
    ax.set_xticks(range(0, len(labels), 4), labels[::4])
    ax.set_ylim(bottom=0)
    return _encode(plt, fig)


def charts(data: dict) -> dict:
    """Every chart of the report as a PNG data URI."""
    h, c = data["helpdesk"], data["chronicle"]
    weekly = h["weekly"]
    pr, inc = c["priorities"], c["incidents"]
    return {
        "weekdays": _bar([d["short"] for d in h["weekday_avg"]], [d["avg"] for d in h["weekday_avg"]], _INFO),
        "heatmap": _heatmap(h["heatmap"]),
        "resolution": _bar(
            [b["label"] for b in h["resolution"]["buckets"]],
            [b["share"] for b in h["resolution"]["buckets"]],
            _GOOD,
            percent=True,
        ),
        "open": _open_line(weekly),
        "flow": _paired(
            [w["label"] for w in weekly],
            [w["created"] for w in weekly],
            [w["solved"] for w in weekly],
            "Oprettet",
            "Løst",
            every=4,
        ),
        "priorities": _paired(pr["months"], pr["created_by_month"], pr["completed_by_month"], "Oprettet", "Afsluttet"),
        "incidents": _bar(inc["months"], inc["by_month"], _BAD),
    }


# --- PDF / HTML ---------------------------------------------------------------


def _render(data: dict) -> str:
    return render_to_string(
        "dashboard/exports/statistics_report.html",
        {**data, "charts": charts(data)},
    )


def generate_pdf(data: dict) -> bytes:
    """The report as PDF (WeasyPrint, week-report stylesheet)."""
    from weasyprint import CSS, HTML

    css_path = settings.BASE_DIR / "static" / "css" / "pdf_styles.css"
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []
    # The shared stylesheet's running header says "Ugelog"; name this report.
    stylesheets.append(CSS(string='@page { @top-center { content: "FynBus IT Statistik"; } }'))
    return HTML(string=_render(data)).write_pdf(stylesheets=stylesheets)


def generate_html(data: dict) -> str:
    """The report as one standalone HTML file with the styles inlined."""
    from apps.logbook.exports.html import _BROWSER_CSS

    css_path = settings.BASE_DIR / "static" / "css" / "pdf_styles.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    return _render(data).replace(
        "</head>", f"<style>\n{css}\n{_BROWSER_CSS}\n</style>\n</head>", 1
    )
