"""Scoring engine: convert perk state -> recommendations -> top-3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from chase_agent.rules.clocks import period_for, urgency_from_period
from chase_agent.rules.perks import (
    ALL_PERKS,
    PERKS_BY_ID,
    SUB_REQUIRED_SPEND,
    SUB_REWARD_POINTS,
    SUB_WINDOW_DAYS,
    PerkKind,
)

if TYPE_CHECKING:
    from chase_agent.rules.perks import Perk


# Effort weights from SPEC.md scoring model
EFFORT_WEIGHTS: dict[str, int] = {"low": 1, "med": 2, "high": 4}

# Confidence reference values (SPEC.md scoring model)
CONFIDENCE_DEADLINE = 1.0
CONFIDENCE_ACTIVATION = 0.9
CONFIDENCE_BEHAVIOR = 0.7
CONFIDENCE_TRANSFER = 0.5


@dataclass(frozen=True)
class Recommendation:
    perk_id: str
    action: str
    estimated_value_usd: float
    deadline: date | None
    effort: str  # low|med|high
    confidence: float
    reason: str
    next_step: str
    score: float

    @classmethod
    def make(
        cls,
        *,
        perk_id: str,
        action: str,
        value: float,
        urgency: float,
        confidence: float,
        effort: str,
        deadline: date | None,
        reason: str,
        next_step: str,
    ) -> Recommendation:
        weight = EFFORT_WEIGHTS[effort]
        score = (value * urgency * confidence) / weight
        return cls(
            perk_id=perk_id,
            action=action,
            estimated_value_usd=value,
            deadline=deadline,
            effort=effort,
            confidence=confidence,
            reason=reason,
            next_step=next_step,
            score=score,
        )


def _credit_remaining(state: dict[str, float] | None, total: float) -> float:
    if state is None:
        return total
    return max(0.0, total - float(state.get("used_usd", 0.0)))


def _is_suppressed(perk_id: str, overrides: dict[str, dict[str, str]]) -> bool:
    return perk_id in overrides


def _is_active(perk_id: str, activations: dict[str, dict[str, int]]) -> bool:
    state = activations.get(perk_id)
    return bool(state and state.get("active"))


def build_credit_recommendations(
    perk: Perk,
    *,
    credit_states: dict[tuple[str, str], dict[str, float]],
    activations: dict[str, dict[str, int]],
    overrides: dict[str, dict[str, str]],
    card_open_date: date | None,
    today: date,
) -> Recommendation | None:
    """Generate a recommendation for a single credit perk if any value remains."""
    if perk.kind != PerkKind.CREDIT:
        return None
    if _is_suppressed(perk.id, overrides):
        return None
    if perk.activation_required and not _is_active(perk.id, activations):
        # Surfaced via activation rec instead
        return None

    period = period_for(perk, card_open_date=card_open_date, today=today)
    state = credit_states.get((perk.id, period.period_key))
    remaining = _credit_remaining(state, perk.total_usd or 0.0)
    if remaining <= 0:
        return None
    # Effective value override (eg DoorDash $25 headline -> ~$15 captureable)
    effective = _effective_value(perk, remaining)

    # Travel credit: silent unless deep into anniversary year with low usage.
    # SPEC: only flag if >=10 months in & <$200 used.
    if perk.id == "travel_credit":
        used = float(state.get("used_usd", 0.0)) if state else 0.0
        months_in = ((today - period.start).days) / 30.0
        if not (months_in >= 10 and used < 200):
            return None

    urgency = urgency_from_period(period)
    effort = _effort_for_credit(perk)
    deadline = period.end
    action, next_step = _credit_action_text(perk)

    return Recommendation.make(
        perk_id=perk.id,
        action=action,
        value=effective,
        urgency=urgency,
        confidence=CONFIDENCE_DEADLINE,
        effort=effort,
        deadline=deadline,
        reason=(
            f"${effective:.0f} effective of {perk.name} remaining, "
            f"{period.days_remaining}d left ({period.clock.value} clock)."
        ),
        next_step=next_step,
    )


def _effective_value(perk: Perk, remaining: float) -> float:
    """Apply real-world capture-rate haircuts (eg DoorDash post-April-2026 nerf)."""
    haircuts: dict[str, float] = {
        # Effective value of DoorDash credits is ~50-60% of headline
        # since $20 minimum on convenience pickups was added April 2026.
        "doordash_nonrestaurant": 0.55,
        "doordash_restaurant": 0.7,
    }
    factor = haircuts.get(perk.id, 1.0)
    return remaining * factor


def _effort_for_credit(perk: Perk) -> str:
    high_effort = {"edit_credit", "select_hotel_credit"}
    if perk.id in high_effort:
        return "high"
    medium = {"dining_h1", "dining_h2", "stubhub_h1", "stubhub_h2"}
    if perk.id in medium:
        return "med"
    return "low"


def _credit_action_text(perk: Perk) -> tuple[str, str]:
    by_id: dict[str, tuple[str, str]] = {
        "travel_credit": (
            "Use your travel credit on any eligible purchase",
            "Pay any travel category (airline, Uber, Amtrak, parking, OTA) with CSR.",
        ),
        "edit_credit": (
            "Book a 2+ night Edit hotel",
            "Open chase-agent trip helper or Chase Travel; filter The Edit; pay prepaid with CSR.",
        ),
        "select_hotel_credit": (
            "Book a 2+ night stay at IHG/Pendry/Omni/Virgin/Montage/Minor/Pan Pacific",
            "Search Chase Travel for the eligible brands; aim for properties also in The Edit "
            "(Pendry Park City / Manhattan West) to stack with Edit credit.",
        ),
        "dining_h1": (
            "Use your H1 dining credit at an Exclusive Tables restaurant",
            "Book on OpenTable Sapphire Reserve Exclusive Tables (eg Kabawa $145, Estela). "
            "Pay with CSR.",
        ),
        "dining_h2": (
            "Use your H2 dining credit at an Exclusive Tables restaurant",
            "Book on OpenTable Sapphire Reserve Exclusive Tables. Pay with CSR.",
        ),
        "stubhub_h1": (
            "Use your H1 StubHub credit",
            (
                "Buy event tickets on stubhub.com or viagogo.com (US); "
                "credit triggers on purchase post."
            ),
        ),
        "stubhub_h2": (
            "Use your H2 StubHub credit",
            "Buy event tickets on stubhub.com or viagogo.com (US).",
        ),
        "lyft_monthly": (
            "Use your $10 Lyft credit this month",
            "Open Lyft, ensure CSR is set as Personal default (NOT Apple Pay), take a ride.",
        ),
        "doordash_restaurant": (
            "Use your $5 DoorDash restaurant credit",
            "Place a restaurant order >$5 subtotal in DoorDash with CSR linked.",
        ),
        "doordash_nonrestaurant": (
            "Use your DoorDash non-restaurant credits",
            "Order grocery/household ≥$20 subtotal in DoorDash with CSR linked.",
        ),
        "peloton_monthly": (
            "Capture your Peloton credit",
            (
                "Subscribe to Peloton Strength+ (no bike needed) directly via peloton.com, "
                "pay with CSR."
            ),
        ),
        "instacart_monthly": (
            "Use your $15 Instacart credit (ends July 2026)",
            "Order groceries via Instacart, pay with CSR.",
        ),
    }
    return by_id.get(perk.id, (f"Use {perk.name}", "Pay an eligible purchase with CSR."))


def build_activation_recommendations(
    *,
    activations: dict[str, dict[str, int]],
    overrides: dict[str, dict[str, str]],
    today: date,
    user_phone_bill_on_csr: bool,
) -> list[Recommendation]:
    """Surface inactive activatable perks as recommendations."""
    out: list[Recommendation] = []
    for perk in ALL_PERKS:
        if not perk.activation_required:
            continue
        if _is_suppressed(perk.id, overrides):
            continue

        # Special: cell phone protection is gated by user_phone_bill_on_csr, not Chase activation
        if perk.id == "cell_phone_protection":
            if user_phone_bill_on_csr:
                continue
            value = 120.0  # imputed annual value of $1k/incident protection
            deadline = None
            urgency = 0.4
            action = "Switch phone bill autopay to CSR"
            next_step = (
                "Open your carrier app/site, change autopay payment method to CSR. "
                "Activates $1,000/incident phone protection."
            )
            reason = "Phone bill not on CSR. Cell phone protection is inactive."
        elif _is_active(perk.id, activations):
            continue
        else:
            value = _activation_value(perk)
            deadline = perk.hard_deadline
            urgency = _activation_urgency(perk, today)
            action = f"Activate {perk.name}"
            next_step = "Chase app -> Card Benefits -> Activate."
            reason = f"{perk.name} not activated."

        out.append(
            Recommendation.make(
                perk_id=perk.id,
                action=action,
                value=value,
                urgency=urgency,
                confidence=CONFIDENCE_ACTIVATION,
                effort="low",
                deadline=deadline,
                reason=reason,
                next_step=next_step,
            )
        )
    return out


def _activation_value(perk: Perk) -> float:
    """Imputed annual value for activations."""
    values: dict[str, float] = {
        "apple_tv": 96.0,
        "apple_music": 120.0,
        "ihg_platinum": 50.0,
        "dashpass": 120.0,
        "whoop_life": 359.0,
        "peloton_monthly": 120.0,
        "stubhub_h1": 150.0,
        "stubhub_h2": 150.0,
    }
    return values.get(perk.id, 0.0)


def _activation_urgency(perk: Perk, today: date) -> float:
    """Limited-time perks ramp urgency in last 30 days. Expired -> 0."""
    if perk.hard_deadline is None:
        return 0.4
    days_left = (perk.hard_deadline - today).days
    if days_left < 0:
        return 0.0  # expired
    if days_left <= 7:
        return 1.0
    if days_left <= 30:
        return 0.9
    if days_left <= 90:
        return 0.5
    return 0.3


@dataclass(frozen=True)
class SubStatus:
    spent: float
    required: float
    days_elapsed: int
    days_total: int
    expected_pace: float
    on_pace: bool
    cleared: bool

    @property
    def remaining_spend(self) -> float:
        return max(0.0, self.required - self.spent)

    @property
    def remaining_days(self) -> int:
        return max(0, self.days_total - self.days_elapsed)


def sub_status(
    *,
    sub_start: date | None,
    spent: float,
    today: date,
) -> SubStatus | None:
    """Compute SUB pacing status. None if no SUB tracked."""
    if sub_start is None:
        return None
    days_elapsed = (today - sub_start).days
    days_total = SUB_WINDOW_DAYS
    expected = (days_elapsed / days_total) * SUB_REQUIRED_SPEND if days_total else 0
    cleared = spent >= SUB_REQUIRED_SPEND
    on_pace = spent >= expected or cleared
    return SubStatus(
        spent=spent,
        required=SUB_REQUIRED_SPEND,
        days_elapsed=days_elapsed,
        days_total=days_total,
        expected_pace=expected,
        on_pace=on_pace,
        cleared=cleared,
    )


def sub_recommendation(
    status: SubStatus | None,
    *,
    points_value_cpp: float = 0.015,
) -> Recommendation | None:
    if status is None or status.cleared:
        return None
    if status.on_pace:
        return None
    behind = status.expected_pace - status.spent
    # Value at risk = full bonus (eg 125k pts * 1.5 cpp = $1,875), not the spend gap.
    bonus_value = SUB_REWARD_POINTS * points_value_cpp
    return Recommendation.make(
        perk_id="sub",
        action="Move safe everyday spend to CSR to catch up on sign-up bonus",
        value=bonus_value,
        urgency=1.0,
        confidence=CONFIDENCE_BEHAVIOR,
        effort="med",
        deadline=None,
        reason=(
            f"Behind SUB pace by ${behind:.0f}. ${status.remaining_spend:.0f} needed "
            f"in {status.remaining_days} days. Bonus at risk: ~${bonus_value:.0f} "
            f"({SUB_REWARD_POINTS:,} pts at {points_value_cpp:.2f}cpp)."
        ),
        next_step="Reallocate recurring bills (rent if eligible, taxes, insurance) to CSR.",
    )


def select_top_three(
    recs: list[Recommendation],
    *,
    today: date | None = None,
) -> tuple[list[Recommendation], list[Recommendation]]:
    """Returns (top_3, ignore_for_now) per SPEC.md scoring model.

    Tiebreaker: closer deadline > higher value > lower effort.
    Items below 30% of top-1 score go to ignore_for_now.
    `today` controls deadline tie-breaking; defaults to date.today().
    """
    if not recs:
        return [], []

    ref = today or date.today()

    def sort_key(r: Recommendation) -> tuple[float, float, float, int]:
        deadline_days = (r.deadline - ref).days if r.deadline else 10_000
        return (
            -r.score,
            deadline_days,
            -r.estimated_value_usd,
            EFFORT_WEIGHTS[r.effort],
        )

    sorted_recs = sorted(recs, key=sort_key)
    top_score = sorted_recs[0].score
    threshold = 0.3 * top_score

    top_3: list[Recommendation] = []
    ignored: list[Recommendation] = []
    for r in sorted_recs:
        if len(top_3) < 3 and r.score >= threshold:
            top_3.append(r)
        else:
            ignored.append(r)
    return top_3, ignored


def annual_fee_captured(
    *,
    credit_states: dict[tuple[str, str], dict[str, float]],
    activations: dict[str, dict[str, int]],
    user_phone_bill_on_csr: bool,
) -> float:
    """Imputed annual fee value captured to date.

    Sum: (credit $ used) + (activation imputed values for those active) + cell phone if on CSR.
    """
    total = 0.0
    for state in credit_states.values():
        total += float(state.get("used_usd", 0.0))
    for perk in ALL_PERKS:
        if not perk.activation_required:
            continue
        if perk.id == "cell_phone_protection":
            if user_phone_bill_on_csr:
                total += 120.0
            continue
        if _is_active(perk.id, activations):
            total += _activation_value(perk)
    return total


def all_recommendations(
    *,
    credit_states: dict[tuple[str, str], dict[str, float]],
    activations: dict[str, dict[str, int]],
    overrides: dict[str, dict[str, str]],
    sub_start: date | None,
    sub_spent: float,
    user_phone_bill_on_csr: bool,
    card_open_date: date | None,
    today: date,
) -> list[Recommendation]:
    out: list[Recommendation] = []
    for perk in ALL_PERKS:
        rec = build_credit_recommendations(
            perk,
            credit_states=credit_states,
            activations=activations,
            overrides=overrides,
            card_open_date=card_open_date,
            today=today,
        )
        if rec:
            out.append(rec)
    out.extend(
        build_activation_recommendations(
            activations=activations,
            overrides=overrides,
            today=today,
            user_phone_bill_on_csr=user_phone_bill_on_csr,
        )
    )
    sub = sub_recommendation(sub_status(sub_start=sub_start, spent=sub_spent, today=today))
    if sub:
        out.append(sub)
    return out


__all__ = [
    "Recommendation",
    "SubStatus",
    "all_recommendations",
    "annual_fee_captured",
    "build_activation_recommendations",
    "build_credit_recommendations",
    "select_top_three",
    "sub_recommendation",
    "sub_status",
]


_ = PERKS_BY_ID  # re-export marker for tests
