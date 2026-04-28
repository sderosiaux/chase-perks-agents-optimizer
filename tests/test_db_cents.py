"""DB: INTEGER cents conversion + transaction upsert."""

from __future__ import annotations

from datetime import date

from chase_agent import db


def test_cents_round_trip() -> None:
    assert db.cents(123.45) == 12345
    assert db.usd(12345) == 123.45
    assert db.cents(0.0) == 0
    assert db.cents(99.999) == 10000  # banker's rounding


def test_upsert_credit_state_stores_cents() -> None:
    db.init_db()
    db.upsert_credit_state(
        perk_id="travel_credit",
        period_key="anniv-x",
        used_usd=180.0,
        total_usd=300.0,
        expires_iso="2026-09-14",
    )
    state = db.get_credit_state("travel_credit", "anniv-x")
    assert state is not None
    # API surface: USD floats.
    assert state["used_usd"] == 180.0
    assert state["total_usd"] == 300.0
    # Underlying storage: cents.
    assert state["used_cents"] == 18000
    assert state["total_cents"] == 30000


def test_transaction_upsert_overwrites_corrected_repost() -> None:
    """Chase reposts can correct merchant, amount; upsert must reflect latest."""
    db.init_db()
    db.insert_transaction(
        id="tx_1",
        posted_date=date(2026, 4, 27),
        amount_usd=14.20,
        merchant="Uber",
        raw_description="UBER TRIP",
        category="rideshare",
    )
    db.insert_transaction(
        id="tx_1",
        posted_date=date(2026, 4, 27),
        amount_usd=15.50,  # corrected up
        merchant="Uber Trip Adjustment",
        raw_description="UBER TRIP CORRECTED",
        category="rideshare",
    )
    txs = db.transactions_since(date(2026, 4, 1))
    matching = [t for t in txs if t["id"] == "tx_1"]
    assert len(matching) == 1
    assert matching[0]["amount_usd"] == 15.50
    assert "Adjustment" in matching[0]["merchant"]


def test_schema_version_recorded() -> None:
    db.init_db()
    with db.conn() as c:
        rows = c.execute("SELECT version FROM schema_version").fetchall()
    assert any(r["version"] == db.SCHEMA_VERSION for r in rows)
