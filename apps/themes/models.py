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
        schedule covers it. Earliest start_date wins on overlap."""
        today = timezone.localdate()
        schedule = (
            ThemeSchedule.objects.filter(
                start_date__lte=today,
                end_date__gte=today,
                theme__is_active=True,
            )
            .select_related("theme")
            .order_by("start_date")
            .first()
        )
        return schedule.theme if schedule else None


class ThemeSchedule(models.Model):
    """A date range where ``theme`` overrides user preferences globally."""

    theme = models.ForeignKey(
        Theme,
        on_delete=models.CASCADE,
        related_name="schedules",
        verbose_name="Tema",
    )
    start_date = models.DateField(verbose_name="Start")
    end_date = models.DateField(verbose_name="Slut", help_text="Inklusiv.")
    label = models.CharField(
        verbose_name="Etiket",
        max_length=120,
        blank=True,
        help_text="Fri tekst — fx 'Star Wars Day 2026' eller 'Julestemning uge 51-52'.",
    )

    class Meta:
        verbose_name = "Tema-skedule"
        verbose_name_plural = "Tema-skeduler"
        ordering = ["start_date"]
        indexes = [
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.theme.name}: {self.start_date} – {self.end_date}"


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
