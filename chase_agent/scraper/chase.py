"""End-to-end Chase Card Benefits scrape."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from chase_agent import config, db
from chase_agent.rules.clocks import period_for
from chase_agent.rules.perks import PERKS_BY_ID
from chase_agent.scraper import chrome, llm

CARD_BENEFITS_URL = "https://account.chase.com/sapphire/reserve/benefits"

# Cross-check tolerance: extracted "used" should be within this $ delta of
# what we observe in the local transaction ledger when transactions exist.
LEDGER_CROSS_CHECK_TOLERANCE_USD = 25.0


# ---- sanity bounds: defends against hallucinated values ----
SANITY_BOUNDS: dict[str, tuple[float, float]] = {
    "travel_credit": (0, 300),
    "edit_credit": (0, 500),
    "select_hotel_credit": (0, 250),
    "dining_h1": (0, 150),
    "dining_h2": (0, 150),
    "stubhub_h1": (0, 150),
    "stubhub_h2": (0, 150),
    "lyft_monthly": (0, 10),
    "doordash_restaurant": (0, 5),
    "doordash_nonrestaurant": (0, 20),
    "peloton_monthly": (0, 10),
    "instacart_monthly": (0, 15),
}


def _is_in_bounds(perk_id: str, used: float, total: float) -> bool:
    bounds = SANITY_BOUNDS.get(perk_id)
    if bounds is None:
        return True
    lo, hi = bounds
    return (lo <= used <= hi) and (lo <= total <= hi) and used <= total


def scrape_card_benefits(
    *,
    today: date | None = None,
    skip_verify: bool = False,
) -> dict[str, Any]:
    """Full scrape of the Chase Card Benefits page.

    Steps:
      1. Navigate via chrome-agent (using user's session)
      2. Capture text + screenshot
      3. LLM extraction with schema-locked tool use
      4. Optional dual-pass self-check
      5. Sanity bound check
      6. Persist to ledger

    Returns a dict with extracted credits, activations, anomalies.
    """
    today = today or date.today()
    run_id = db.start_scrape_run("card_benefits")
    anomalies: list[str] = []
    snapshot_path = config.SNAPSHOT_DIR / f"benefits-{run_id}.png"

    try:
        chrome.goto(CARD_BENEFITS_URL)
        chrome.screenshot(snapshot_path)
        page_text = chrome.text()

        if not chrome.is_logged_in(page_text):
            anomalies.append("login_required")
            db.finish_scrape_run(run_id, success=False, anomalies=anomalies)
            return {
                "success": False,
                "anomalies": anomalies,
                "snapshot_path": str(snapshot_path),
            }

        credits = llm.extract_credits(
            page_text=page_text,
            screenshot_path=snapshot_path,
        )
        activations = llm.extract_activations(
            page_text=page_text,
            screenshot_path=snapshot_path,
        )

        # Sanity bounds first
        valid_credits, rejected = _filter_credits(credits)
        if rejected:
            anomalies.extend([f"rejected: {r}" for r in rejected])

        # Self-check (gate)
        if not skip_verify:
            ok, verdict = llm.verify_credits_self_check(
                extracted=valid_credits,
                page_text=page_text,
            )
            if not ok:
                anomalies.append(f"self_check_disagree: {verdict[:160]}")
                db.finish_scrape_run(
                    run_id,
                    success=False,
                    anomalies=anomalies,
                    snapshot_path=snapshot_path,
                )
                return {
                    "success": False,
                    "credits": valid_credits,
                    "activations": activations,
                    "anomalies": anomalies,
                    "snapshot_path": str(snapshot_path),
                }

        # Ledger cross-check (gate when ledger has signal)
        ledger_anomalies = _ledger_cross_check(valid_credits, today=today)
        if ledger_anomalies:
            anomalies.extend(ledger_anomalies)
            db.finish_scrape_run(
                run_id,
                success=False,
                anomalies=anomalies,
                snapshot_path=snapshot_path,
            )
            return {
                "success": False,
                "credits": valid_credits,
                "activations": activations,
                "anomalies": anomalies,
                "snapshot_path": str(snapshot_path),
            }

        _persist_credits(valid_credits, today=today)
        _persist_activations(activations)

        db.finish_scrape_run(
            run_id,
            success=True,
            anomalies=anomalies or None,
            snapshot_path=snapshot_path,
        )
        return {
            "success": True,
            "credits": valid_credits,
            "activations": activations,
            "anomalies": anomalies,
            "snapshot_path": str(snapshot_path),
        }
    except Exception as e:
        anomalies.append(f"exception: {type(e).__name__}: {e}")
        db.finish_scrape_run(run_id, success=False, anomalies=anomalies)
        raise


def _filter_credits(
    credits: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    valid: list[dict[str, Any]] = []
    rejected: list[str] = []
    for c in credits:
        perk_id = c.get("perk_id")
        used = float(c.get("used_usd", 0))
        total = float(c.get("total_usd", 0))
        if not perk_id or perk_id not in PERKS_BY_ID:
            rejected.append(f"unknown_perk_id={perk_id}")
            continue
        if not _is_in_bounds(perk_id, used, total):
            rejected.append(f"bounds_violation:{perk_id} used={used} total={total}")
            continue
        valid.append(c)
    return valid, rejected


def _persist_credits(credits: list[dict[str, Any]], *, today: date) -> None:
    for c in credits:
        perk_id = c["perk_id"]
        perk = PERKS_BY_ID[perk_id]
        period = period_for(perk, today=today)
        db.upsert_credit_state(
            perk_id=perk_id,
            period_key=period.period_key,
            used_usd=float(c["used_usd"]),
            total_usd=float(c["total_usd"]),
            expires_iso=c.get("expires_iso") or period.end.isoformat(),
        )


def _ledger_cross_check(
    credits: list[dict[str, Any]],
    *,
    today: date,
) -> list[str]:
    """Cross-check extracted 'used' against transactions ledger when we have signal.

    Skipped silently when the ledger has no transactions for the relevant period
    (early days of usage). Once transactions exist, mismatches above tolerance
    return anomalies that block persistence.
    """
    anomalies: list[str] = []
    for c in credits:
        perk_id = c["perk_id"]
        used = float(c.get("used_usd", 0.0))
        perk = PERKS_BY_ID.get(perk_id)
        if perk is None:
            continue
        period = period_for(perk, today=today)
        # Sum transactions tagged with this perk in the period.
        tx_total = _sum_perk_transactions_in_period(perk_id, period.start, period.end)
        if tx_total is None:
            continue  # no signal — skip
        delta = abs(used - tx_total)
        if delta > LEDGER_CROSS_CHECK_TOLERANCE_USD:
            anomalies.append(
                f"ledger_mismatch:{perk_id} extracted={used:.2f} ledger={tx_total:.2f} "
                f"delta={delta:.2f}"
            )
    return anomalies


def _sum_perk_transactions_in_period(perk_id: str, start: date, end: date) -> float | None:
    """Sum transactions tagged with `triggered_perk_id`. None if no rows present."""
    txs = db.transactions_since(start - timedelta(days=1))
    relevant = [t for t in txs if t.get("triggered_perk_id") == perk_id]
    if not relevant:
        return None
    end_iso = end.isoformat()
    total = sum(float(t["amount_usd"]) for t in relevant if (t.get("posted_date") or "") <= end_iso)
    return total


def _persist_activations(activations: list[dict[str, Any]]) -> None:
    for a in activations:
        perk_id = a.get("perk_id")
        if not perk_id or perk_id not in PERKS_BY_ID:
            continue
        db.set_activation(
            perk_id,
            active=bool(a.get("active")),
            notes=a.get("raw_label"),
        )
