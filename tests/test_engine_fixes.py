"""Tests for engine fixes: expired guard, today injection, travel silent, SUB value, DoorDash."""

from __future__ import annotations

from datetime import date

from chase_agent.rules.engine import (
    Recommendation,
    _activation_urgency,
    all_recommendations,
    select_top_three,
    sub_recommendation,
    sub_status,
)
from chase_agent.rules.perks import (
    DOORDASH_NONREST,
    PERKS_BY_ID,
    SUB_REWARD_POINTS,
    WHOOP_LIFE,
)


def test_expired_limited_time_perk_has_zero_urgency() -> None:
    """Whoop expires 2026-05-12. After that, urgency must be 0, not 1."""
    after = date(2026, 6, 1)
    assert _activation_urgency(WHOOP_LIFE, after) == 0.0


def test_select_top_three_uses_injected_today() -> None:
    """Tiebreaker should use the supplied today, not date.today()."""
    today = date(2030, 1, 1)
    near = Recommendation.make(
        perk_id="a",
        action="A",
        value=100.0,
        urgency=1.0,
        confidence=1.0,
        effort="low",
        deadline=date(2030, 1, 10),
        reason="",
        next_step="",
    )
    far = Recommendation.make(
        perk_id="b",
        action="B",
        value=100.0,
        urgency=1.0,
        confidence=1.0,
        effort="low",
        deadline=date(2030, 12, 31),
        reason="",
        next_step="",
    )
    top, _ = select_top_three([far, near], today=today)
    # Same score; tiebreaker is closer deadline first.
    assert top[0].perk_id == "a"


def test_travel_credit_is_silent_when_user_is_using_it() -> None:
    """Anniversary opened 2025-09-15, today 2026-04-27 (~7 months in), $180 used.

    Travel credit should NOT be in recommendations: spec says only flag
    if >=10 months in AND <$200 used.
    """
    today = date(2026, 4, 27)
    recs = all_recommendations(
        credit_states={
            ("travel_credit", "anniv-2025-09-15"): {"used_usd": 180.0},
        },
        activations={},
        overrides={},
        sub_start=None,
        sub_spent=0.0,
        user_phone_bill_on_csr=True,
        card_open_date=date(2025, 9, 15),
        today=today,
    )
    assert all(r.perk_id != "travel_credit" for r in recs)


def test_travel_credit_surfaces_late_in_year_with_low_usage() -> None:
    """11 months in, only $50 used -> recommend."""
    today = date(2026, 8, 20)
    recs = all_recommendations(
        credit_states={
            ("travel_credit", "anniv-2025-09-15"): {"used_usd": 50.0},
        },
        activations={},
        overrides={},
        sub_start=None,
        sub_spent=0.0,
        user_phone_bill_on_csr=True,
        card_open_date=date(2025, 9, 15),
        today=today,
    )
    assert any(r.perk_id == "travel_credit" for r in recs)


def test_sub_recommendation_uses_bonus_value_not_spend_gap() -> None:
    """Behind by $1k spend; bonus value at risk = 125k pts * 1.5cpp = $1875."""
    status = sub_status(sub_start=date(2026, 3, 1), spent=1_000.0, today=date(2026, 4, 27))
    assert status is not None
    assert not status.on_pace
    rec = sub_recommendation(status)
    assert rec is not None
    assert rec.estimated_value_usd == SUB_REWARD_POINTS * 0.015


def test_doordash_nonrestaurant_uses_effective_value() -> None:
    """$20 headline -> ~$11 effective (55% haircut)."""
    today = date(2026, 4, 27)
    recs = all_recommendations(
        credit_states={
            ("doordash_nonrestaurant", "2026-04"): {"used_usd": 0.0},
        },
        activations={},
        overrides={},
        sub_start=None,
        sub_spent=0.0,
        user_phone_bill_on_csr=True,
        card_open_date=date(2025, 9, 15),
        today=today,
    )
    rec = next((r for r in recs if r.perk_id == "doordash_nonrestaurant"), None)
    assert rec is not None
    assert rec.estimated_value_usd < 15.0
    assert rec.estimated_value_usd > 5.0


def test_perks_by_id_has_all_referenced_ids() -> None:
    """Sanity: every perk shows up in the catalog."""
    assert "doordash_nonrestaurant" in PERKS_BY_ID
    assert "whoop_life" in PERKS_BY_ID
    assert PERKS_BY_ID["doordash_nonrestaurant"] is DOORDASH_NONREST
