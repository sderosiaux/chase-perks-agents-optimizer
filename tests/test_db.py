"""SQLite ledger: schema, upserts, idempotency."""

from __future__ import annotations

from datetime import date

from chase_agent import db


def test_init_db_creates_schema() -> None:
    db.init_db()
    cfg = db.load_user_config()
    assert cfg.home_city == "NYC"


def test_save_and_load_user_config_roundtrip() -> None:
    db.init_db()
    cfg = db.load_user_config()
    cfg.card_open_date = date(2025, 9, 15)
    cfg.phone_bill_on_csr = True
    db.save_user_config(cfg)

    loaded = db.load_user_config()
    assert loaded.card_open_date == date(2025, 9, 15)
    assert loaded.phone_bill_on_csr is True


def test_credit_state_upsert_overwrites_used() -> None:
    db.init_db()
    db.upsert_credit_state(
        perk_id="travel_credit",
        period_key="anniv-2025-09-15",
        used_usd=100.0,
        total_usd=300.0,
        expires_iso="2026-09-14",
    )
    db.upsert_credit_state(
        perk_id="travel_credit",
        period_key="anniv-2025-09-15",
        used_usd=180.0,
        total_usd=300.0,
        expires_iso="2026-09-14",
    )
    state = db.get_credit_state("travel_credit", "anniv-2025-09-15")
    assert state is not None
    assert state["used_usd"] == 180.0


def test_overrides_round_trip() -> None:
    db.init_db()
    db.add_override("doordash_restaurant", "I never use it")
    items = db.all_overrides()
    assert "doordash_restaurant" in items

    db.remove_override("doordash_restaurant")
    items = db.all_overrides()
    assert "doordash_restaurant" not in items
