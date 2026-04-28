"""Redaction helpers: strip PII from page text before sending to Anthropic.

Defense-in-depth. We trust:
  - merchant names + amounts + dates (necessary for reasoning)
We strip:
  - account numbers (full or last-4)
  - SSN-like patterns
  - email addresses
  - street addresses
  - the user's name (if seen on the page)
  - phone numbers
  - long digit strings that look like card numbers
"""

from __future__ import annotations

import re

ACCOUNT_NUMBER_RE = re.compile(r"\b(?:\d[ -]*?){12,19}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
STREET_RE = re.compile(
    r"\b\d{1,5}\s+(?:\d+(?:st|nd|rd|th)|[A-Za-z][a-zA-Z'-]+)"
    r"(?:\s+(?:\d+(?:st|nd|rd|th)|[A-Za-z][a-zA-Z'-]+)){0,3}\s+"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Place|Pl)\b",
    re.IGNORECASE,
)
ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
LAST_FOUR_RE = re.compile(r"(?:ending|x{2,}|•{2,})\s*\d{4}\b", re.IGNORECASE)


def redact_text(text: str, *, user_name_parts: list[str] | None = None) -> str:
    """Apply all redaction passes. Returns sanitized text."""
    out = text
    out = ACCOUNT_NUMBER_RE.sub("[REDACTED_ACCOUNT]", out)
    out = SSN_RE.sub("[REDACTED_SSN]", out)
    out = EMAIL_RE.sub("[REDACTED_EMAIL]", out)
    out = PHONE_RE.sub("[REDACTED_PHONE]", out)
    out = STREET_RE.sub("[REDACTED_STREET]", out)
    out = ZIP_RE.sub("[REDACTED_ZIP]", out)
    out = LAST_FOUR_RE.sub("[REDACTED_LAST4]", out)
    if user_name_parts:
        for part in user_name_parts:
            if part and len(part) >= 3:
                out = re.sub(rf"\b{re.escape(part)}\b", "[REDACTED_NAME]", out, flags=re.IGNORECASE)
    return out
