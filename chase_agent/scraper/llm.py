"""Anthropic LLM extraction with schema-locked tool use.

Pattern: feed page text + screenshot to Claude, force a structured response
via tool use. Cross-check happens in scraper/chase.py against the ledger.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from anthropic import Anthropic

from chase_agent.scraper.redact import redact_text

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
ADVISOR_MODEL = "claude-sonnet-4-6"


def _client() -> Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=key)


# ----- Tool schemas -----

EXTRACT_CREDITS_TOOL: dict[str, Any] = {
    "name": "report_credits",
    "description": (
        "Report the credits visible on the Chase Sapphire Reserve "
        "Card Benefits page. Numbers must come ONLY from the page; "
        "do NOT compute or estimate."
    ),
    "input_schema": {
        "type": "object",
        "required": ["credits"],
        "properties": {
            "credits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["perk_id", "used_usd", "total_usd"],
                    "properties": {
                        "perk_id": {
                            "type": "string",
                            "enum": [
                                "travel_credit",
                                "edit_credit",
                                "select_hotel_credit",
                                "dining_h1",
                                "dining_h2",
                                "stubhub_h1",
                                "stubhub_h2",
                                "lyft_monthly",
                                "doordash_restaurant",
                                "doordash_nonrestaurant",
                                "peloton_monthly",
                                "instacart_monthly",
                            ],
                        },
                        "used_usd": {"type": "number", "minimum": 0},
                        "total_usd": {"type": "number", "minimum": 0},
                        "expires_iso": {"type": "string", "description": "YYYY-MM-DD"},
                        "raw_label": {
                            "type": "string",
                            "description": "Verbatim label from page",
                        },
                    },
                },
            }
        },
    },
}

EXTRACT_ACTIVATIONS_TOOL: dict[str, Any] = {
    "name": "report_activations",
    "description": "Report which activatable perks are currently active.",
    "input_schema": {
        "type": "object",
        "required": ["activations"],
        "properties": {
            "activations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["perk_id", "active"],
                    "properties": {
                        "perk_id": {
                            "type": "string",
                            "enum": [
                                "apple_tv",
                                "apple_music",
                                "ihg_platinum",
                                "dashpass",
                                "stubhub_h1",
                                "stubhub_h2",
                                "peloton_monthly",
                                "whoop_life",
                            ],
                        },
                        "active": {"type": "boolean"},
                        "raw_label": {"type": "string"},
                    },
                },
            }
        },
    },
}


def extract_credits(
    *,
    page_text: str,
    screenshot_path: Path | None,  # noqa: ARG001  reserved for future cropped use
    model: str = DEFAULT_MODEL,
    user_name_parts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Force a tool call to extract credits. Returns list of credit dicts.

    NOTE on screenshots: we DO NOT send the screenshot here in v1. The full page may
    contain account numbers, names, addresses. Cropping the screenshot to the
    benefits panel is a Phase 2 task; until then we feed text-only with redaction.
    """
    redacted = redact_text(page_text, user_name_parts=user_name_parts)
    client = _client()
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "You are extracting credit balances from the Chase Sapphire Reserve "
                "Card Benefits page. Use the report_credits tool. "
                "Numbers must be exactly what is shown. Do not infer values not present. "
                "Map labels to perk_ids as follows:\n"
                "- 'Travel credit' or '$300 annual travel credit' -> travel_credit\n"
                "- 'The Edit credit' or '$500 The Edit' -> edit_credit\n"
                "- 'Select hotel credit' (2026 only) -> select_hotel_credit\n"
                "- 'Dining credit' Jan-Jun -> dining_h1\n"
                "- 'Dining credit' Jul-Dec -> dining_h2\n"
                "- 'StubHub' Jan-Jun -> stubhub_h1\n"
                "- 'StubHub' Jul-Dec -> stubhub_h2\n"
                "- 'Lyft' monthly -> lyft_monthly\n"
                "- 'DoorDash' $5 restaurant -> doordash_restaurant\n"
                "- 'DoorDash' $10 non-restaurant -> doordash_nonrestaurant\n"
                "- 'Peloton' -> peloton_monthly\n"
                "- 'Instacart' -> instacart_monthly\n"
                "\nPage text (sanitized):\n"
                f"{redacted[:50_000]}"
            ),
        }
    ]
    # Screenshot deliberately omitted in v1; the text + tool schema is enough.

    response = client.messages.create(  # type: ignore[call-overload]
        model=model,
        max_tokens=2048,
        tools=[EXTRACT_CREDITS_TOOL],
        tool_choice={"type": "tool", "name": "report_credits"},
        messages=[{"role": "user", "content": content}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "report_credits":
            payload: dict[str, Any] = dict(block.input)
            credits: list[dict[str, Any]] = payload.get("credits", [])
            return credits
    raise RuntimeError("LLM did not call report_credits")


def extract_activations(
    *,
    page_text: str,
    screenshot_path: Path | None,  # noqa: ARG001  reserved for future cropped use
    model: str = DEFAULT_MODEL,
    user_name_parts: list[str] | None = None,
) -> list[dict[str, Any]]:
    redacted = redact_text(page_text, user_name_parts=user_name_parts)
    client = _client()
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "Extract activation status of each activatable Sapphire Reserve perk "
                "shown on the Card Benefits page. Use the report_activations tool. "
                "An item is 'active' only if explicitly indicated as activated/enrolled "
                "on the page. Otherwise active=false.\n\n"
                f"Page text (sanitized):\n{redacted[:50_000]}"
            ),
        }
    ]
    # Screenshot deliberately omitted in v1.

    response = client.messages.create(  # type: ignore[call-overload]
        model=model,
        max_tokens=2048,
        tools=[EXTRACT_ACTIVATIONS_TOOL],
        tool_choice={"type": "tool", "name": "report_activations"},
        messages=[{"role": "user", "content": content}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "report_activations":
            payload: dict[str, Any] = dict(block.input)
            activations: list[dict[str, Any]] = payload.get("activations", [])
            return activations
    raise RuntimeError("LLM did not call report_activations")


def verify_credits_self_check(
    *,
    extracted: list[dict[str, Any]],
    page_text: str,
    model: str = DEFAULT_MODEL,
    user_name_parts: list[str] | None = None,
) -> tuple[bool, str]:
    """Dual-pass: ask LLM to verify its own extraction. Returns (ok, comment)."""
    redacted = redact_text(page_text, user_name_parts=user_name_parts)
    client = _client()
    response = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": (
                    "You earlier extracted these credits from a Chase Card Benefits page. "
                    "Verify each row against the page text below. Return a one-line "
                    "verdict starting with OK: or DISAGREE: followed by reasons.\n\n"
                    f"Extracted:\n{json.dumps(extracted, indent=2)}\n\n"
                    f"Page text (sanitized):\n{redacted[:30_000]}"
                ),
            }
        ],
    )
    for block in response.content:
        if block.type == "text":
            verdict = block.text.strip()
            return (verdict.upper().startswith("OK"), verdict)
    return (False, "no text response")
