"""Seed realistic mock state for demo and dev (today: 2026-04-27)."""

from __future__ import annotations

from datetime import date

from chase_agent import config, db


def seed_demo() -> None:
    db.init_db()

    # User config tuned for the example user
    cfg = config.UserConfig(
        card_open_date=date(2025, 9, 15),
        sub_start_date=date(2026, 3, 1),
        sub_spend_to_date=3_200.0,
        sub_state="behind",
        cash_buffer_threshold=25_000.0,
        checking_balance_estimate=42_000.0,
        default_airports=["JFK", "LGA", "EWR"],
        home_city="NYC",
        phone_bill_on_csr=False,  # not yet — will surface as a top action
        cpc_active=True,
        family_sharing_setup=True,
        current_5_24_count=2,
        reactive_enabled=True,
    )
    db.save_user_config(cfg)

    today = date(2026, 4, 27)
    iso_today = today.isoformat()

    # Anniversary clock: travel credit partially burned (Uber/Amtrak/parking)
    db.upsert_credit_state(
        perk_id="travel_credit",
        period_key="anniv-2025-09-15",
        used_usd=180.0,
        total_usd=300.0,
        expires_iso="2026-09-14",
    )

    # Calendar 2026
    db.upsert_credit_state(
        perk_id="edit_credit",
        period_key="2026",
        used_usd=0.0,
        total_usd=500.0,
        expires_iso="2026-12-31",
    )
    db.upsert_credit_state(
        perk_id="dining_h1",
        period_key="2026-H1",
        used_usd=75.0,
        total_usd=150.0,
        expires_iso="2026-06-30",
    )
    db.upsert_credit_state(
        perk_id="dining_h2",
        period_key="2026-H2",
        used_usd=0.0,
        total_usd=150.0,
        expires_iso="2026-12-31",
    )
    db.upsert_credit_state(
        perk_id="stubhub_h1",
        period_key="2026-H1",
        used_usd=0.0,
        total_usd=150.0,
        expires_iso="2026-06-30",
    )
    db.upsert_credit_state(
        perk_id="stubhub_h2",
        period_key="2026-H2",
        used_usd=0.0,
        total_usd=150.0,
        expires_iso="2026-12-31",
    )

    # Limited-time
    db.upsert_credit_state(
        perk_id="select_hotel_credit",
        period_key="LT-select_hotel_credit-2026-12-31",
        used_usd=0.0,
        total_usd=250.0,
        expires_iso="2026-12-31",
    )

    # Monthly (April 2026)
    db.upsert_credit_state(
        perk_id="lyft_monthly",
        period_key="2026-04",
        used_usd=0.0,
        total_usd=10.0,
        expires_iso="2026-04-30",
    )
    db.upsert_credit_state(
        perk_id="doordash_restaurant",
        period_key="2026-04",
        used_usd=0.0,
        total_usd=5.0,
        expires_iso="2026-04-30",
    )
    db.upsert_credit_state(
        perk_id="doordash_nonrestaurant",
        period_key="2026-04",
        used_usd=0.0,
        total_usd=20.0,
        expires_iso="2026-04-30",
    )
    db.upsert_credit_state(
        perk_id="peloton_monthly",
        period_key="2026-04",
        used_usd=10.0,
        total_usd=10.0,
        expires_iso="2026-04-30",
    )
    db.upsert_credit_state(
        perk_id="instacart_monthly",
        period_key="2026-04",
        used_usd=0.0,
        total_usd=15.0,
        expires_iso="2026-04-30",
    )

    # Activations: Apple subs done, others pending
    db.set_activation("apple_tv", active=True, notes="activated 2026-03-12")
    db.set_activation("apple_music", active=True, notes="activated 2026-03-12")
    db.set_activation("peloton_monthly", active=True, notes="Strength+ subscription")
    db.set_activation("stubhub_h1", active=False, notes="not activated yet")
    db.set_activation("stubhub_h2", active=False, notes="not activated yet")
    db.set_activation("ihg_platinum", active=False, notes="free, not activated")
    db.set_activation("dashpass", active=False, notes="not linked")
    db.set_activation("whoop_life", active=False, notes="limited-time, expires 2026-05-12")

    # Mark a stale snapshot for "last scrape" indicator
    run_id = db.start_scrape_run("seed")
    db.finish_scrape_run(run_id, success=True)

    print(f"Seeded demo state. today={iso_today}, db={config.DB_PATH}")


if __name__ == "__main__":
    seed_demo()
