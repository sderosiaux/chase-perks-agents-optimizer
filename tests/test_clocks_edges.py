"""Edge cases for the three-clock model: leap year, end-inclusive, expired."""

from __future__ import annotations

from datetime import date

import pytest

from chase_agent.rules.clocks import (
    Period,
    _anniversary_for_year,
    anniversary_period,
    monthly_period,
    urgency_from_period,
)
from chase_agent.rules.perks import ClockType


def test_leap_day_anniversary_normalizes_in_non_leap_year() -> None:
    """Card opened Feb 29, 2024. In 2025 (non-leap), anniversary is Feb 28."""
    assert _anniversary_for_year(date(2024, 2, 29), 2025) == date(2025, 2, 28)
    assert _anniversary_for_year(date(2024, 2, 29), 2028) == date(2028, 2, 29)


def test_anniversary_period_handles_leap_day_open_date() -> None:
    """Should not crash; should produce a valid period."""
    p = anniversary_period(date(2024, 2, 29), today=date(2025, 6, 1))
    assert p.start == date(2025, 2, 28)
    # End = anniversary 2026 (non-leap, so Feb 28) - 1 day = Feb 27
    assert p.end == date(2026, 2, 27)


def test_anniversary_open_date_feb29_in_leap_target_year() -> None:
    """Opened 2024-02-29, today 2024-03-15 -> first anniversary period 2024-02-29..2025-02-27."""
    p = anniversary_period(date(2024, 2, 29), today=date(2024, 3, 15))
    assert p.start == date(2024, 2, 29)
    # Anniversary 2025-02-28 (non-leap) - 1 day = 2025-02-27
    assert p.end == date(2025, 2, 27)


def test_period_end_is_inclusive_in_days_remaining() -> None:
    """If as_of == end, 1 day remains; if as_of < end by 3, 4 days remain."""
    p = Period(
        clock=ClockType.MONTHLY,
        period_key="x",
        start=date(2026, 4, 1),
        end=date(2026, 4, 30),
        as_of=date(2026, 4, 30),
    )
    assert p.days_remaining == 1
    p2 = Period(
        clock=ClockType.MONTHLY,
        period_key="x",
        start=date(2026, 4, 1),
        end=date(2026, 4, 30),
        as_of=date(2026, 4, 27),
    )
    assert p2.days_remaining == 4


def test_period_after_end_returns_zero_days_remaining() -> None:
    p = Period(
        clock=ClockType.MONTHLY,
        period_key="x",
        start=date(2026, 4, 1),
        end=date(2026, 4, 30),
        as_of=date(2026, 5, 1),
    )
    assert p.days_remaining == 0


@pytest.mark.parametrize(
    ("as_of", "expected_days"),
    [
        (date(2024, 2, 1), 29),  # leap year February
        (date(2025, 2, 1), 28),  # non-leap year February
    ],
)
def test_monthly_period_february_leap(as_of: date, expected_days: int) -> None:
    p = monthly_period(today=as_of)
    assert p.days_remaining == expected_days


def test_urgency_critical_at_seven_days() -> None:
    p = Period(
        clock=ClockType.CALENDAR,
        period_key="x",
        start=date(2026, 1, 1),
        end=date(2026, 12, 31),
        as_of=date(2026, 12, 25),
    )
    assert urgency_from_period(p) == 1.0
