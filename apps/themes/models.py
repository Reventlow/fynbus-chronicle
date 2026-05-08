"""Theme system — visual "events" like Star Wars Day, Christmas, etc.

A ``Theme`` is identified by a slug (used as ``data-event="<slug>"`` on
``<html>``). ``ThemeSchedule`` rows define date ranges where the theme
overrides whatever the user has picked in the tweaks panel. A user's
manual pick lives in ``localStorage`` and only applies on days where
nothing is scheduled.

Active-theme resolution per request:

  1. ``?force-theme=<slug>`` query param — preview hatch.
  2. ``ThemeSchedule.active_today()`` — admin-defined date overrides.
  3. None server-side. Client-side Alpine then applies the user's
     localStorage pick (if any), unless one of the above already
     populated ``data-event`` on ``<html>``.
"""

from django.db import models
from django.utils import timezone


class Theme(models.Model):
    """A visual theme that can be activated globally or by schedule."""

    slug = models.SlugField(
        verbose_name="Slug",
        unique=True,
        max_length=40,
        help_text="Bruges som data-event på <html>. Skal matche CSS-reglerne.",
    )
    name = models.CharField(
        verbose_name="Navn",
        max_length=80,
        help_text="Vises i tweaks-panelet og i admin.",
    )
    description = models.TextField(
        verbose_name="Beskrivelse",
        blank=True,
        help_text="Hvad gør temaet visuelt? Hvilken anledning?",
    )
    is_active = models.BooleanField(
        verbose_name="Aktiv",
        default=True,
        help_text="Inaktive temaer ignoreres af både skedule og bruger-pick.",
    )
    user_selectable = models.BooleanField(
        verbose_name="Kan vælges af brugere",
        default=True,
        help_text=(
            "Hvis sand: dukker op i tweaks-panelets Tema-dropdown. "
            "Sæt falsk for et tema der kun bør køre på specifikke datoer."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tema"
        verbose_name_plural = "Temaer"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def scheduled_for_today(cls) -> "Theme | None":
        """Return the active theme for today (Europe/Copenhagen), if any
        schedule covers it.

        One-shot schedules are filtered cheaply at the DB level; annual
        schedules are checked in Python via ``ThemeSchedule.covers()``
        because their (month, day) match doesn't translate cleanly to
        SQL across year boundaries. Earliest start_date wins on overlap.
        """
        today = timezone.localdate()
        # One-shot match — filter in SQL.
        one_shot = (
            ThemeSchedule.objects.filter(
                recurs_annually=False,
                start_date__lte=today,
                end_date__gte=today,
                theme__is_active=True,
            )
            .select_related("theme")
            .order_by("start_date")
            .first()
        )
        if one_shot:
            return one_shot.theme

        # Annual match — small set, evaluated in Python.
        annuals = (
            ThemeSchedule.objects.filter(
                recurs_annually=True,
                theme__is_active=True,
            )
            .select_related("theme")
            .order_by("start_date")
        )
        for sched in annuals:
            if sched.covers(today):
                return sched.theme
        return None


class ThemeSchedule(models.Model):
    """A date range where ``theme`` overrides user preferences globally.

    If ``recurs_annually`` is true the year of ``start_date``/``end_date``
    is ignored and the schedule fires every year on those month/day
    coordinates (Star Wars Day, Pirate Day etc.). Year-spanning ranges
    (e.g. 27 Dec → 3 Jan) are supported.
    """

    theme = models.ForeignKey(
        Theme,
        on_delete=models.CASCADE,
        related_name="schedules",
        verbose_name="Tema",
    )
    start_date = models.DateField(verbose_name="Start")
    end_date = models.DateField(verbose_name="Slut", help_text="Inklusiv.")
    recurs_annually = models.BooleanField(
        verbose_name="Gentages årligt",
        default=False,
        help_text=(
            "Hvis sand: kun måned + dag betyder noget — temaet "
            "aktiveres samme datoer hvert år. Året i felterne "
            "ovenfor bruges kun som anker."
        ),
    )
    label = models.CharField(
        verbose_name="Etiket",
        max_length=120,
        blank=True,
        help_text="Fri tekst — fx 'Star Wars Day' eller 'Julestemning uge 51-52'.",
    )

    class Meta:
        verbose_name = "Tema-skedule"
        verbose_name_plural = "Tema-skeduler"
        ordering = ["start_date"]
        indexes = [
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self) -> str:
        if self.recurs_annually:
            if self.start_date == self.end_date:
                return f"{self.theme.name}: {self.start_date.strftime('%d. %b')} (årligt)"
            return f"{self.theme.name}: {self.start_date.strftime('%d. %b')} – {self.end_date.strftime('%d. %b')} (årligt)"
        return f"{self.theme.name}: {self.start_date} – {self.end_date}"

    def covers(self, today) -> bool:
        """Return True if ``today`` falls within this schedule's range.

        For one-shot schedules this is a plain date comparison. For
        annual schedules it compares ``(month, day)`` and handles
        ranges that wrap across a year boundary (e.g. 27 Dec → 3 Jan).
        """
        if not self.recurs_annually:
            return self.start_date <= today <= self.end_date

        today_md = (today.month, today.day)
        start_md = (self.start_date.month, self.start_date.day)
        end_md = (self.end_date.month, self.end_date.day)

        if start_md <= end_md:
            return start_md <= today_md <= end_md
        # Year-spanning range — date is "in range" if it's >= start OR <= end.
        return today_md >= start_md or today_md <= end_md


class ThemeBannerMessage(models.Model):
    """One rotating message for a theme's sticky banner.

    Was previously a hardcoded Python list per theme (152 Star Wars +
    80 pirate). Lives in the DB now so editors can curate copy without
    a code change/redeploy and without needing a per-theme Python file.
    """

    theme = models.ForeignKey(
        Theme,
        on_delete=models.CASCADE,
        related_name="banner_messages",
        verbose_name="Tema",
    )
    text = models.TextField(
        verbose_name="Tekst",
        help_text="En enkelt linje der dukker op i banneret. Holdes kort — banneret afkorter med ellipsis.",
    )
    is_active = models.BooleanField(
        verbose_name="Aktiv",
        default=True,
        help_text="Inaktive beskeder ekskluderes fra rotationen uden at slette dem.",
    )
    order = models.PositiveIntegerField(
        verbose_name="Sortering",
        default=0,
        help_text="Rækkefølge i admin. Påvirker ikke rotationen (den er tilfældig).",
    )
    notes = models.CharField(
        verbose_name="Internt notat",
        max_length=200,
        blank=True,
        help_text="Editor-private kontekst (kilde, intern joke-forklaring osv.). Vises ikke i banneret.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Banner-besked"
        verbose_name_plural = "Banner-beskeder"
        ordering = ["theme", "order", "id"]
        indexes = [
            models.Index(fields=["theme", "is_active"]),
        ]

    def __str__(self) -> str:
        preview = self.text[:60] + ("…" if len(self.text) > 60 else "")
        return f"{self.theme.slug}: {preview}"
