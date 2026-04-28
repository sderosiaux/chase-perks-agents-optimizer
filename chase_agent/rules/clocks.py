"""Three-clock model: anniversary, calendar, monthly. Period keys + reset dates."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from chase_agent.rules.perks import ClockType

if TYPE_CHECKING:
    from chase_agent.rules.perks import Perk


@dataclass(frozen=True)
class Period:
    """A specific time window of a clock, anchored to `as_of`."""

    clock: ClockType
    period_key: str
    start: date
    end: date  # inclusive
    as_of: date

    @property
    def days_remaining(self) -> int:
        # `end` is inclusive: if as_of == end, 1 full day remains.
        if self.as_of > self.end:
            return 0
        return (self.end - self.as_of).days + 1

    @property
    def total_days(self) -> int:
        return max(1, (self.end - self.start).days + 1)

    @property
    def fraction_remaining(self) -> float:
        return min(1.0, max(0.0, self.days_remaining / self.total_days))


def _anniversary_for_year(open_date: date, year: int) -> date:
    """Return the anniversary date for a given year, normalizing Feb 29 -> Feb 28."""
    if open_date.month == 2 and open_date.day == 29:
        try:
            return date(year, 2, 29)
        except ValueError:
            return date(year, 2, 28)
    return date(year, open_date.month, open_date.day)


def anniversary_period(card_open_date: date, today: date | None = None) -> Period:
    """Anniversary year window containing `today`. Handles Feb 29 open dates."""
    today = today or date.today()
    candidate = _anniversary_for_year(card_open_date, today.year)
    if candidate > today:
        candidate = _anniversary_for_year(card_open_date, today.year - 1)
    next_anniv = _anniversary_for_year(card_open_date, candidate.year + 1) - timedelta(days=1)
    return Period(
        clock=ClockType.ANNIVERSARY,
        period_key=f"anniv-{candidate.isoformat()}",
        start=candidate,
        end=next_anniv,
        as_of=today,
    )


def calendar_period(today: date | None = None) -> Period:
    today = today or date.today()
    return Period(
        clock=ClockType.CALENDAR,
        period_key=str(today.year),
        start=date(today.year, 1, 1),
        end=date(today.year, 12, 31),
        as_of=today,
    )


def half_year_period(today: date | None = None) -> Period:
    """Jan-Jun (H1) or Jul-Dec (H2) of current year."""
    today = today or date.today()
    if today.month <= 6:
        return Period(
            clock=ClockType.CALENDAR,
            period_key=f"{today.year}-H1",
            start=date(today.year, 1, 1),
            end=date(today.year, 6, 30),
            as_of=today,
        )
    return Period(
        clock=ClockType.CALENDAR,
        period_key=f"{today.year}-H2",
        start=date(today.year, 7, 1),
        end=date(today.year, 12, 31),
        as_of=today,
    )


def monthly_period(today: date | None = None) -> Period:
    today = today or date.today()
    last = monthrange(today.year, today.month)[1]
    return Period(
        clock=ClockType.MONTHLY,
        period_key=f"{today.year}-{today.month:02d}",
        start=date(today.year, today.month, 1),
        end=date(today.year, today.month, last),
        as_of=today,
    )


def limited_time_period(perk: Perk, today: date | None = None) -> Period:
    today = today or date.today()
    end = perk.hard_deadline if perk.hard_deadline is not None else date(today.year + 1, 12, 31)
    return Period(
        clock=ClockType.LIMITED_TIME,
        period_key=f"LT-{perk.id}-{end.isoformat()}",
        start=today,
        end=end,
        as_of=today,
    )


def period_for(
    perk: Perk,
    *,
    card_open_date: date | None = None,
    today: date | None = None,
) -> Period:
    """Resolve the active period for a given perk."""
    today = today or date.today()
    if perk.clock == ClockType.ANNIVERSARY:
        if card_open_date is None:
            card_open_date = today.replace(year=today.year - 1)
        return anniversary_period(card_open_date, today)
    if perk.clock == ClockType.MONTHLY:
        return monthly_period(today)
    if perk.clock == ClockType.LIMITED_TIME:
        return limited_time_period(perk, today)
    if perk.period_label in ("H1", "H2"):
        return half_year_period(today)
    return calendar_period(today)


def urgency_from_period(period: Period) -> float:
    """0..1 urgency: 0 when plenty of time, 1 when <=7 days left.

    Buckets from SPEC.md behavior rule 6:
      - >75% remaining -> 0.1
      - 25-75%         -> 0.4
      - 7d to 25%      -> 0.7
      - <=7 days       -> 1.0
    """
    if period.days_remaining <= 7:
        return 1.0
    frac = period.fraction_remaining
    if frac >= 0.75:
        return 0.1
    if frac >= 0.25:
        return 0.4
    return 0.7
