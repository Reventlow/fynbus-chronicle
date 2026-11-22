"""Personal Kontrolpanel layout (1.21.0).

The Kontrolpanel is a fixed list of sections (``SECTIONS``); some hold more
than one card (``parts``). Each user may put the sections in their own order
and hide sections or single cards. Their choice is stored as two lists on
``DashboardLayout``:

* ``order``  — section keys, top to bottom;
* ``hidden`` — keys of hidden sections (``"trend"``) and cards
  (``"trend.flow"``).

Whatever is stored is read through ``build_layout``, which drops unknown
keys and appends sections that did not exist when the user saved. A section
added in a later release therefore shows up for everyone, in its default
place relative to the end of their list, without a migration of anyone's
layout. Hidden sections and cards are not rendered at all, so their
polling partials are never requested.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Part:
    key: str
    title: str


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    help: str
    template: str
    numbered: bool = True  # carries a "01", "02" … label on the page
    parts: tuple[Part, ...] = ()


SECTIONS: tuple[Section, ...] = (
    Section("kpi", "Nøgletal", "Nye, lukkede og åbne helpdesk-tickets",
            "dashboard/sections/kpi.html", numbered=False),
    Section("now", "Nu", "Sager og ugens log",
            "dashboard/sections/now.html",
            parts=(Part("cases", "Sårbarheder, hændelser og planlagt arbejde"),
                   Part("week", "Ugens log og rådighedsvagt"))),
    Section("open", "Åbne tickets", "Fordeling og lister over åbne tickets",
            "dashboard/sections/open.html",
            parts=(Part("breakdown", "Fordelt på tekniker, kategori og liggetid"),
                   Part("lists", "Nyeste og ældste åbne tickets"))),
    Section("trend", "Udvikling", "Helpdesk-flow over tid",
            "dashboard/sections/trend.html",
            parts=(Part("flow", "Flow pr. uge"),
                   Part("open_chart", "Åbne tickets pr. uge"))),
    Section("changelog", "Seneste ændring", "Den nyeste post fra ændringsloggen",
            "dashboard/sections/changelog.html", numbered=False),
)
BY_KEY = {s.key: s for s in SECTIONS}
DEFAULT_ORDER = [s.key for s in SECTIONS]
# Every key that may appear in ``hidden``.
HIDEABLE = {s.key for s in SECTIONS} | {f"{s.key}.{p.key}" for s in SECTIONS for p in s.parts}


def clean(order, hidden) -> tuple[list[str], list[str]]:
    """Known keys only, each once; every section present in ``order``."""
    seen: list[str] = []
    for key in order if isinstance(order, list) else []:
        if isinstance(key, str) and key in BY_KEY and key not in seen:
            seen.append(key)
    seen += [k for k in DEFAULT_ORDER if k not in seen]
    hidden_set = {k for k in (hidden if isinstance(hidden, list) else []) if isinstance(k, str) and k in HIDEABLE}
    return seen, sorted(hidden_set)


@dataclass
class ShownSection:
    """One section as the page renders it."""

    section: Section
    hidden: bool
    show: dict[str, bool] = field(default_factory=dict)  # part key -> shown
    n: str = ""  # "01", "02" … among the visible numbered sections

    @property
    def key(self) -> str:
        return self.section.key

    @property
    def template(self) -> str:
        return self.section.template

    key_hidden: bool = False  # the section itself is switched off (not just all its cards)

    @property
    def shown_parts(self) -> int:
        return sum(self.show.values())


def build_layout(order=None, hidden=None) -> list[ShownSection]:
    """The sections in the user's order, each with its hidden flag, the
    shown state of its cards and its running number. A section whose cards
    are all hidden counts as hidden."""
    order, hidden = clean(order or [], hidden or [])
    hidden_set = set(hidden)
    result, n = [], 0
    for key in order:
        section = BY_KEY[key]
        show = {p.key: f"{key}.{p.key}" not in hidden_set for p in section.parts}
        is_hidden = key in hidden_set or (bool(show) and not any(show.values()))
        item = ShownSection(section, is_hidden, show, key_hidden=key in hidden_set)
        if section.numbered and not is_hidden:
            n += 1
            item.n = f"{n:02d}"
        result.append(item)
    return result


# What each density mode hides on top of the user's own choice (the
# js-dashboard-* classes on the section templates, see input.css).
DENSITY_HIDES = {
    "compact": {"open", "trend", "changelog"},
    "dashboard": {"now", "changelog"},
}


def empty_in(layout: list[ShownSection]) -> list[str]:
    """Density modes in which nothing is left on the page: "all" when the
    user hid every section, else the modes that hide every visible one."""
    visible = {s.key for s in layout if not s.hidden}
    if not visible:
        return ["all"]
    return [mode for mode, hides in DENSITY_HIDES.items() if visible <= hides]


def layout_for(user) -> list[ShownSection]:
    from .models import DashboardLayout

    saved = DashboardLayout.objects.filter(user=user).first() if user.is_authenticated else None
    return build_layout(saved.order, saved.hidden) if saved else build_layout()
