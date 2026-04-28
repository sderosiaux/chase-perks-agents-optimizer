"""Three-clock model: anniversary / calendar / monthly / limited-time."""

from __future__ import annotations

from datetime import date

from chase_agent.rules.clocks import (
    anniversary_period,
    calendar_period,
    half_year_period,
    monthly_period,
    period_for,
    urgency_from_period,
)
from chase_agent.rules.perks import (
    DINING_H1,
    EDIT_CREDIT,
    LYFT_MONTHLY,
    SELECT_HOTEL_CREDIT,
    TRAVEL_CREDIT,
)


def test_anniversary_period_before_anniversary_in_year() -> None:
    """Card opened 2025-09-15, today 2026-04-27 -> anniversary period 2025-09-15..2026-09-14."""
    today = date(2026, 4, 27)
    p = anniversary_period(date(2025, 9, 15), today=today)
    assert p.start == date(2025, 9, 15)
    assert p.end == date(2026, 9, 14)
    # End is inclusive, so days_remaining = (end - as_of).days + 1
    assert p.days_remaining == (date(2026, 9, 14) - today).days + 1
    assert p.period_key.startswith("anniv-")


def test_anniversary_period_after_anniversary() -> None:
    """Today 2025-10-01, opened 2025-09-15 -> we're in the FIRST anniversary year."""
    p = anniversary_period(date(2025, 9, 15), today=date(2025, 10, 1))
    assert p.start == date(2025, 9, 15)
    assert p.end == date(2026, 9, 14)


def test_calendar_period() -> None:
    p = calendar_period(today=date(2026, 4, 27))
    assert p.start == date(2026, 1, 1)
    assert p.end == date(2026, 12, 31)


def test_half_year_h1() -> None:
    p = half_year_period(today=date(2026, 4, 27))
    assert p.period_key == "2026-H1"
    assert p.end == date(2026, 6, 30)


def test_half_year_h2() -> None:
    p = half_year_period(today=date(2026, 8, 1))
    assert p.period_key == "2026-H2"
    assert p.start == date(2026, 7, 1)
    assert p.end == date(2026, 12, 31)


def test_monthly_april() -> None:
    p = monthly_period(today=date(2026, 4, 27))
    assert p.start == date(2026, 4, 1)
    assert p.end == date(2026, 4, 30)
    assert p.period_key == "2026-04"


def test_monthly_february_non_leap() -> None:
    p = monthly_period(today=date(2027, 2, 15))
    assert p.end == date(2027, 2, 28)


def test_period_for_dispatch() -> None:
    today = date(2026, 4, 27)
    p_travel = period_for(TRAVEL_CREDIT, card_open_date=date(2025, 9, 15), today=today)
    assert p_travel.clock == TRAVEL_CREDIT.clock

    p_edit = period_for(EDIT_CREDIT, today=today)
    assert p_edit.start == date(2026, 1, 1)

    p_dining = period_for(DINING_H1, today=today)
    assert p_dining.end == date(2026, 6, 30)

    p_lyft = period_for(LYFT_MONTHLY, today=today)
    assert p_lyft.end == date(2026, 4, 30)

    p_select = period_for(SELECT_HOTEL_CREDIT, today=today)
    assert p_select.end == date(2026, 12, 31)


def test_urgency_critical_when_seven_days_or_less() -> None:
    p = monthly_period(today=date(2026, 4, 27))  # 4 days left -> critical
    assert urgency_from_period(p) == 1.0


def test_urgency_low_when_plenty_of_time() -> None:
    p = calendar_period(today=date(2026, 1, 5))  # almost a full year ahead
    assert urgency_from_period(p) == 0.1
