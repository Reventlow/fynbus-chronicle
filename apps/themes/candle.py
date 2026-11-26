"""Kalenderlys — the Advent calendar candle of the Christmas theme.

A Danish kalenderlys is marked 1–24 from the top down and you burn one mark
a day, so on 24 December the last mark melts away. Chronicle's candle stands
on the Kontrolpanel right above the rådighedsvagt card and melts
continuously: the burned share is "whole days gone + share of today gone",
out of 24.

The rules, in one place (static/js/christmas-parade.js mirrors this function
as ``candleState`` and the tests check that both agree):

* 1–24 December: the real date, lit, burned down to the current time of day.
* 25 December onwards (2. juledag is still in the theme's schedule): burnt
  down and extinguished — a stub with a wisp of smoke and a "God jul".
* Any other date (a forced preview in November, or a user who picked the
  theme by hand in the summer): shown as 1 December at the current time of
  day, so the preview still shows the flame and the first mark melting.

Times are local wall-clock times: the server renders the candle from
Django's local time (Europe/Copenhagen), and the script then recomputes it
every few minutes from the browser's clock.
"""

from dataclasses import dataclass
from datetime import datetime

DAYS = 24
SECONDS_PER_DAY = 24 * 60 * 60


@dataclass(frozen=True)
class CandleState:
    """Where the kalenderlys stands at a given moment.

    ``day`` is the mark that is burning (1–24; 24 once burnt out),
    ``burned`` the share of the whole candle that is gone (0.0 = new,
    1.0 = burnt down) and ``lit`` whether the flame is on.
    """

    day: int
    burned: float
    lit: bool

    @property
    def remaining(self) -> float:
        """Share of the candle left (1.0 = a new candle)."""
        return 1.0 - self.burned

    @property
    def days_to_christmas_eve(self) -> int:
        """Whole days from the burning mark to 24 December (0 on the day)."""
        return DAYS - self.day


def candle_state(now: datetime) -> CandleState:
    """Return the candle's state at ``now`` (a local, wall-clock datetime).

    Pure: no clock, no timezone lookups — the caller passes local time.
    """
    if now.month == 12 and now.day > DAYS:
        return CandleState(day=DAYS, burned=1.0, lit=False)
    day = now.day if now.month == 12 else 1
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    burned = (day - 1 + seconds / SECONDS_PER_DAY) / DAYS
    return CandleState(day=day, burned=burned, lit=True)
