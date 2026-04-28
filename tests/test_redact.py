"""Redaction: PII stripped before LLM prompts."""

from __future__ import annotations

from chase_agent.scraper.redact import redact_text


def test_redacts_account_numbers() -> None:
    out = redact_text("Account 4147 1234 5678 9012 ending in 9012")
    assert "4147" not in out
    assert "[REDACTED" in out


def test_redacts_email_phone_zip_street() -> None:
    txt = "Stephane sderosiaux@conduktor.io (212) 555-0100, 350 5th Ave, NY 10118"
    out = redact_text(txt, user_name_parts=["Stephane"])
    assert "sderosiaux" not in out
    assert "212" not in out
    assert "10118" not in out
    assert "5th Ave" not in out
    assert "Stephane" not in out


def test_redacts_ssn() -> None:
    out = redact_text("SSN 123-45-6789")
    assert "123-45-6789" not in out


def test_keeps_perk_keywords() -> None:
    """Critical: don't redact merchant or perk vocab."""
    txt = "Travel credit: $180 of $300. Uber on April 12."
    out = redact_text(txt)
    assert "Travel credit" in out
    assert "Uber" in out
    assert "$180" in out


def test_redacts_last_four() -> None:
    out = redact_text("ending 1234 ··· 9012 xx 1111")
    assert "ending 1234" not in out
    assert "1111" not in out or "[REDACTED" in out
