"""Perk catalog: every CSR perk modeled as data.

Source of truth for what exists, when it resets, deadlines, conditions.
The rule engine reads from here. The dashboard reads from here.
Numbers (used / total) come from scraped state, not from this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class ClockType(StrEnum):
    ANNIVERSARY = "anniversary"
    CALENDAR = "calendar"
    MONTHLY = "monthly"
    LIMITED_TIME = "limited_time"


class PerkKind(StrEnum):
    CREDIT = "credit"  # has $ used / total
    ACTIVATION = "activation"  # binary active/inactive
    PASSIVE = "passive"  # always-on (insurance, points multipliers)


@dataclass(frozen=True)
class Perk:
    id: str
    name: str
    kind: PerkKind
    clock: ClockType
    total_usd: float | None = None  # None for activations / passive
    period_label: str = ""  # eg "H1", "Apr", "anniversary"
    # for limited_time: hard end date; for calendar/anniversary, computed from clock
    hard_deadline: date | None = None
    description: str = ""
    activation_required: bool = False
    notes: str = ""


# ----- Anniversary year -----
TRAVEL_CREDIT = Perk(
    id="travel_credit",
    name="Annual travel credit",
    kind=PerkKind.CREDIT,
    clock=ClockType.ANNIVERSARY,
    total_usd=300.0,
    description=(
        "Broad eligibility: airlines, hotels, cars, taxis, "
        "Uber, Lyft, Amtrak, tolls, parking, OTAs."
    ),
)

# ----- Calendar 2026 -----
EDIT_CREDIT = Perk(
    id="edit_credit",
    name="The Edit credit",
    kind=PerkKind.CREDIT,
    clock=ClockType.CALENDAR,
    total_usd=500.0,
    notes="Max $250/transaction, 2-night minimum prepaid, 2 separate stays needed.",
    description="Prepaid Pay Now bookings on The Edit by Chase Travel.",
)

SELECT_HOTEL_CREDIT = Perk(
    id="select_hotel_credit",
    name="Select-hotel credit (2026 only)",
    kind=PerkKind.CREDIT,
    clock=ClockType.LIMITED_TIME,
    total_usd=250.0,
    hard_deadline=date(2026, 12, 31),
    notes="IHG / Montage / Pendry / Omni / Virgin / Minor / Pan Pacific only. 2+ nights prepaid.",
    description="One-time 2026 stack opportunity with Edit credit.",
)

DINING_H1 = Perk(
    id="dining_h1",
    name="Dining credit Jan-Jun",
    kind=PerkKind.CREDIT,
    clock=ClockType.CALENDAR,
    total_usd=150.0,
    period_label="H1",
    hard_deadline=date(2026, 6, 30),
    description="Sapphire Reserve Exclusive Tables on OpenTable.",
)

DINING_H2 = Perk(
    id="dining_h2",
    name="Dining credit Jul-Dec",
    kind=PerkKind.CREDIT,
    clock=ClockType.CALENDAR,
    total_usd=150.0,
    period_label="H2",
    hard_deadline=date(2026, 12, 31),
    description="Sapphire Reserve Exclusive Tables on OpenTable.",
)

STUBHUB_H1 = Perk(
    id="stubhub_h1",
    name="StubHub/viagogo credit Jan-Jun",
    kind=PerkKind.CREDIT,
    clock=ClockType.CALENDAR,
    total_usd=150.0,
    period_label="H1",
    hard_deadline=date(2026, 6, 30),
    activation_required=True,
    notes="Activation required. Trigger date = purchase posting, not event.",
)

STUBHUB_H2 = Perk(
    id="stubhub_h2",
    name="StubHub/viagogo credit Jul-Dec",
    kind=PerkKind.CREDIT,
    clock=ClockType.CALENDAR,
    total_usd=150.0,
    period_label="H2",
    hard_deadline=date(2026, 12, 31),
    activation_required=True,
)

# ----- Monthly -----
LYFT_MONTHLY = Perk(
    id="lyft_monthly",
    name="Lyft monthly credit",
    kind=PerkKind.CREDIT,
    clock=ClockType.MONTHLY,
    total_usd=10.0,
    notes="In-app credit, NOT statement. Set CSR direct, NOT Apple Pay.",
)

DOORDASH_RESTAURANT = Perk(
    id="doordash_restaurant",
    name="DoorDash $5 restaurant",
    kind=PerkKind.CREDIT,
    clock=ClockType.MONTHLY,
    total_usd=5.0,
)

DOORDASH_NONREST = Perk(
    id="doordash_nonrestaurant",
    name="DoorDash 2x $10 non-restaurant",
    kind=PerkKind.CREDIT,
    clock=ClockType.MONTHLY,
    total_usd=20.0,
    notes="$20 minimum on convenience pickups (April 2026 nerf).",
)

PELOTON_MONTHLY = Perk(
    id="peloton_monthly",
    name="Peloton monthly credit",
    kind=PerkKind.CREDIT,
    clock=ClockType.MONTHLY,
    total_usd=10.0,
    activation_required=True,
    notes="Strength+ standalone app at $9.99/mo fully covers it. No bike needed.",
)

INSTACART_MONTHLY = Perk(
    id="instacart_monthly",
    name="Instacart monthly credit",
    kind=PerkKind.CREDIT,
    clock=ClockType.MONTHLY,
    total_usd=15.0,
    hard_deadline=date(2026, 7, 31),
    notes="Ends July 2026.",
)

# ----- Activations / memberships -----
APPLE_TV = Perk(
    id="apple_tv",
    name="Apple TV+ membership",
    kind=PerkKind.ACTIVATION,
    clock=ClockType.LIMITED_TIME,
    hard_deadline=date(2027, 6, 22),
    activation_required=True,
    notes="Family Sharing works for Apple TV+.",
)

APPLE_MUSIC = Perk(
    id="apple_music",
    name="Apple Music membership",
    kind=PerkKind.ACTIVATION,
    clock=ClockType.LIMITED_TIME,
    hard_deadline=date(2027, 6, 22),
    activation_required=True,
    notes="Individual plan only. Family Sharing limited.",
)

IHG_PLATINUM = Perk(
    id="ihg_platinum",
    name="IHG One Rewards Platinum",
    kind=PerkKind.ACTIVATION,
    clock=ClockType.LIMITED_TIME,
    hard_deadline=date(2027, 12, 31),
    activation_required=True,
    notes="60% bonus pts, space-available upgrades.",
)

DASHPASS = Perk(
    id="dashpass",
    name="DashPass membership",
    kind=PerkKind.ACTIVATION,
    clock=ClockType.LIMITED_TIME,
    hard_deadline=date(2027, 12, 31),
    activation_required=True,
)

WHOOP_LIFE = Perk(
    id="whoop_life",
    name="Whoop Life membership",
    kind=PerkKind.ACTIVATION,
    clock=ClockType.LIMITED_TIME,
    hard_deadline=date(2026, 5, 12),
    activation_required=True,
    notes="Limited-time. Includes physical band, ~$359 value, resaleable.",
)

CELL_PHONE_PROTECTION = Perk(
    id="cell_phone_protection",
    name="Cell phone protection",
    kind=PerkKind.PASSIVE,
    clock=ClockType.LIMITED_TIME,
    activation_required=True,  # via switching phone bill autopay to CSR
    notes="$1,000/incident if phone bill paid on CSR.",
)

TRAVEL_INSURANCE = Perk(
    id="travel_insurance",
    name="Travel insurance + primary CDW",
    kind=PerkKind.PASSIVE,
    clock=ClockType.LIMITED_TIME,
    notes="Trip cancel/interrupt, primary CDW on car rentals, lost luggage.",
)


ALL_PERKS: list[Perk] = [
    TRAVEL_CREDIT,
    EDIT_CREDIT,
    SELECT_HOTEL_CREDIT,
    DINING_H1,
    DINING_H2,
    STUBHUB_H1,
    STUBHUB_H2,
    LYFT_MONTHLY,
    DOORDASH_RESTAURANT,
    DOORDASH_NONREST,
    PELOTON_MONTHLY,
    INSTACART_MONTHLY,
    APPLE_TV,
    APPLE_MUSIC,
    IHG_PLATINUM,
    DASHPASS,
    WHOOP_LIFE,
    CELL_PHONE_PROTECTION,
    TRAVEL_INSURANCE,
]


PERKS_BY_ID: dict[str, Perk] = {p.id: p for p in ALL_PERKS}


def perks_by_clock(clock: ClockType) -> list[Perk]:
    return [p for p in ALL_PERKS if p.clock == clock]


# ----- Sign-up bonus (modeled separately, not a perk) -----
SUB_REQUIRED_SPEND = 6_000.0
SUB_REWARD_POINTS = 125_000
SUB_WINDOW_DAYS = 90
SUB_MONTHLY_PACE = SUB_REQUIRED_SPEND / 3  # $2,000/month
