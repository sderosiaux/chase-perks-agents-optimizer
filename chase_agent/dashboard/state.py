"""Build the dashboard view-model from DB state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from chase_agent import db
from chase_agent.rules.clocks import period_for, urgency_from_period
from chase_agent.rules.engine import (
    Recommendation,
    SubStatus,
    all_recommendations,
    annual_fee_captured,
    select_top_three,
    sub_status,
)
from chase_agent.rules.perks import ALL_PERKS, ClockType, Perk, PerkKind

CSR_ANNUAL_FEE = 795.0


@dataclass(frozen=True)
class ClockTile:
    name: str
    label: str
    perks: list[PerkRow]


@dataclass(frozen=True)
class PerkRow:
    perk_id: str
    name: str
    used_usd: float
    total_usd: float
    fraction_used: float
    days_remaining: int
    deadline_iso: str | None
    urgency: float  # 0..1
    status_color: str  # healthy | urgent | critical | inactive
    notes: str
    is_limited_time: bool


@dataclass(frozen=True)
class ActivationRow:
    perk_id: str
    name: str
    active: bool
    last_verified_at: str | None
    deadline_iso: str | None
    days_remaining: int | None
    notes: str


@dataclass(frozen=True)
class DashboardView:
    today: date
    captured_usd: float
    captured_pct: float
    annual_fee: float
    last_scrape_iso: str | None
    next_scrape_hint: str
    clocks: list[ClockTile]
    activations: list[ActivationRow]
    limited_time: list[PerkRow]
    top_actions: list[Recommendation]
    ignored: list[Recommendation]
    sub: SubStatus | None
    overrides: list[str] = field(default_factory=list)


def _color_for(urgency: float, fraction_used: float) -> str:
    if urgency >= 0.95:
        return "critical"
    if urgency >= 0.6:
        return "urgent"
    if fraction_used >= 0.99:
        return "inactive"
    return "healthy"


def _build_perk_row(
    perk: Perk,
    *,
    credit_states: dict[tuple[str, str], dict[str, float]],
    card_open_date: date | None,
    today: date,
) -> PerkRow | None:
    if perk.kind != PerkKind.CREDIT:
        return None
    period = period_for(perk, card_open_date=card_open_date, today=today)
    state = credit_states.get((perk.id, period.period_key))
    used = float(state.get("used_usd", 0.0)) if state else 0.0
    total = perk.total_usd or 0.0
    fraction_used = (used / total) if total else 0.0
    urgency = urgency_from_period(period)
    return PerkRow(
        perk_id=perk.id,
        name=perk.name,
        used_usd=used,
        total_usd=total,
        fraction_used=min(1.0, fraction_used),
        days_remaining=period.days_remaining,
        deadline_iso=period.end.isoformat(),
        urgency=urgency,
        status_color=_color_for(urgency, fraction_used),
        notes=perk.notes,
        is_limited_time=perk.clock == ClockType.LIMITED_TIME,
    )


def build_view(*, today: date | None = None) -> DashboardView:
    today = today or date.today()
    cfg = db.load_user_config()

    credit_state_rows = db.all_credit_states()
    credit_states: dict[tuple[str, str], dict[str, float]] = {
        (r["perk_id"], r["period_key"]): r for r in credit_state_rows
    }
    activations_raw = db.all_activations()
    activations: dict[str, dict[str, int]] = {
        k: {"active": int(v["active"]), **{kk: vv for kk, vv in v.items() if kk != "active"}}
        for k, v in activations_raw.items()
    }
    overrides = db.all_overrides()

    # Build perk rows grouped by clock
    anniversary_rows: list[PerkRow] = []
    calendar_rows: list[PerkRow] = []
    monthly_rows: list[PerkRow] = []
    limited_rows: list[PerkRow] = []
    for perk in ALL_PERKS:
        row = _build_perk_row(
            perk,
            credit_states=credit_states,
            card_open_date=cfg.card_open_date,
            today=today,
        )
        if row is None:
            continue
        if perk.clock == ClockType.ANNIVERSARY:
            anniversary_rows.append(row)
        elif perk.clock == ClockType.CALENDAR:
            calendar_rows.append(row)
        elif perk.clock == ClockType.MONTHLY:
            monthly_rows.append(row)
        else:  # LIMITED_TIME
            limited_rows.append(row)

    # Activations panel
    act_rows: list[ActivationRow] = []
    for perk in ALL_PERKS:
        if not perk.activation_required:
            continue
        state = activations_raw.get(perk.id)
        active = bool(state and state.get("active"))
        # Special: cell phone protection is gated on user config, not Chase activation
        if perk.id == "cell_phone_protection":
            active = cfg.phone_bill_on_csr
        days_left = (perk.hard_deadline - today).days if perk.hard_deadline else None
        act_rows.append(
            ActivationRow(
                perk_id=perk.id,
                name=perk.name,
                active=active,
                last_verified_at=str(state["last_verified_at"]) if state else None,
                deadline_iso=perk.hard_deadline.isoformat() if perk.hard_deadline else None,
                days_remaining=days_left,
                notes=perk.notes,
            )
        )

    recs = all_recommendations(
        credit_states=credit_states,
        activations=activations,
        overrides=overrides,
        sub_start=cfg.sub_start_date,
        sub_spent=cfg.sub_spend_to_date,
        user_phone_bill_on_csr=cfg.phone_bill_on_csr,
        card_open_date=cfg.card_open_date,
        today=today,
    )
    top, ignored = select_top_three(recs, today=today)

    captured = annual_fee_captured(
        credit_states=credit_states,
        activations=activations,
        user_phone_bill_on_csr=cfg.phone_bill_on_csr,
    )
    captured_pct = (captured / CSR_ANNUAL_FEE) * 100

    last_run = db.last_scrape_run()
    last_scrape_iso = last_run["finished_at"] if last_run and last_run.get("finished_at") else None

    return DashboardView(
        today=today,
        captured_usd=captured,
        captured_pct=captured_pct,
        annual_fee=CSR_ANNUAL_FEE,
        last_scrape_iso=last_scrape_iso,
        next_scrape_hint="next: 8h or 20h NYC",
        clocks=[
            ClockTile(name="Anniversary", label="Anniversary year", perks=anniversary_rows),
            ClockTile(name="Calendar", label="Calendar year", perks=calendar_rows),
            ClockTile(name="Monthly", label="This month", perks=monthly_rows),
        ],
        activations=act_rows,
        limited_time=limited_rows,
        top_actions=top,
        ignored=ignored,
        sub=sub_status(sub_start=cfg.sub_start_date, spent=cfg.sub_spend_to_date, today=today),
        overrides=list(overrides.keys()),
    )
