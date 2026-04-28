"""Rule engine: scoring, recommendations, top-3 selection, captured."""

from __future__ import annotations

from datetime import date

from chase_agent.rules.engine import (
    Recommendation,
    all_recommendations,
    annual_fee_captured,
    select_top_three,
    sub_status,
)


def test_recommendation_score_formula() -> None:
    r = Recommendation.make(
        perk_id="x",
        action="do thing",
        value=100.0,
        urgency=0.5,
        confidence=1.0,
        effort="med",  # weight 2
        deadline=None,
        reason="r",
        next_step="n",
    )
    # priority = (100 * 0.5 * 1.0) / 2 = 25
    assert r.score == 25.0


def test_top_three_threshold_at_30_pct() -> None:
    big = Recommendation.make(
        perk_id="big",
        action="big",
        value=500,
        urgency=1.0,
        confidence=1.0,
        effort="low",
        deadline=None,
        reason="",
        next_step="",
    )
    medium = Recommendation.make(
        perk_id="med",
        action="med",
        value=300,
        urgency=1.0,
        confidence=1.0,
        effort="low",
        deadline=None,
        reason="",
        next_step="",
    )
    tiny = Recommendation.make(
        perk_id="tiny",
        action="tiny",
        value=10,
        urgency=0.1,
        confidence=0.5,
        effort="high",
        deadline=None,
        reason="",
        next_step="",
    )
    top, ignored = select_top_three([big, medium, tiny])
    assert [r.perk_id for r in top] == ["big", "med"]
    assert [r.perk_id for r in ignored] == ["tiny"]


def test_whoop_surfaces_with_high_urgency_fifteen_days_left() -> None:
    today = date(2026, 4, 27)  # whoop expires 2026-05-12 -> 15 days left
    recs = all_recommendations(
        credit_states={},
        activations={},  # no activations
        overrides={},
        sub_start=None,
        sub_spent=0.0,
        user_phone_bill_on_csr=True,  # silence cell phone
        card_open_date=date(2025, 9, 15),
        today=today,
    )
    whoop = next((r for r in recs if r.perk_id == "whoop_life"), None)
    assert whoop is not None
    assert whoop.estimated_value_usd == 359.0
    # 15 days -> urgency 0.9 -> score = 359 * 0.9 * 0.9 / 1 ~= 290
    assert whoop.score > 250


def test_suppressed_perk_does_not_appear() -> None:
    today = date(2026, 4, 27)
    recs = all_recommendations(
        credit_states={},
        activations={},
        overrides={"whoop_life": {"reason": "no", "suppress_until": "2099-01-01"}},
        sub_start=None,
        sub_spent=0.0,
        user_phone_bill_on_csr=True,
        card_open_date=date(2025, 9, 15),
        today=today,
    )
    assert all(r.perk_id != "whoop_life" for r in recs)


def test_sub_status_on_pace() -> None:
    s = sub_status(sub_start=date(2026, 3, 1), spent=4_000.0, today=date(2026, 4, 27))
    assert s is not None
    assert s.cleared is False
    assert s.on_pace is True


def test_sub_status_behind() -> None:
    s = sub_status(sub_start=date(2026, 3, 1), spent=1_000.0, today=date(2026, 4, 27))
    assert s is not None
    assert s.on_pace is False


def test_sub_status_cleared() -> None:
    s = sub_status(sub_start=date(2026, 1, 1), spent=6_500.0, today=date(2026, 3, 1))
    assert s is not None
    assert s.cleared is True


def test_annual_fee_captured_sums_credits_and_activations() -> None:
    captured = annual_fee_captured(
        credit_states={
            ("travel_credit", "x"): {"used_usd": 180.0},
            ("dining_h1", "x"): {"used_usd": 75.0},
        },
        activations={
            "apple_tv": {"active": 1},  # imputed 96
            "apple_music": {"active": 1},  # imputed 120
        },
        user_phone_bill_on_csr=True,  # imputed 120
    )
    assert captured == 180 + 75 + 96 + 120 + 120
