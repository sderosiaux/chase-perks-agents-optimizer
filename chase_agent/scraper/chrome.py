"""Subprocess wrapper around the chrome-agent CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

CHASE_PROFILE = "chase"
CHASE_PAGE = "dashboard"


class ChromeAgentNotInstalledError(RuntimeError):
    pass


class ChromeAgentError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChromeAgentResult:
    stdout: str
    returncode: int
    parsed_json: dict | list | None  # type: ignore[type-arg]


def _binary() -> str:
    path = shutil.which("chrome-agent")
    if not path:
        raise ChromeAgentNotInstalledError(
            "chrome-agent CLI not found in PATH. Install it first.",
        )
    return path


def run(
    *args: str,
    json_output: bool = False,
    timeout: int = 60,
) -> ChromeAgentResult:
    """Run chrome-agent with given args. Returns parsed JSON if json_output=True."""
    cmd = [_binary(), *args]
    if json_output:
        cmd = [_binary(), "--json", *args]
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise ChromeAgentError(f"Timeout after {timeout}s: {' '.join(cmd)}") from e

    if result.returncode != 0:
        raise ChromeAgentError(
            f"chrome-agent exited {result.returncode}: {result.stderr.strip()[:300]}"
        )

    parsed: dict | list | None = None  # type: ignore[type-arg]
    if json_output and result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise ChromeAgentError(f"Invalid JSON from chrome-agent: {e}") from e

    return ChromeAgentResult(
        stdout=result.stdout,
        returncode=result.returncode,
        parsed_json=parsed,
    )


def goto(
    url: str,
    *,
    profile: str = CHASE_PROFILE,
    page: str = CHASE_PAGE,
    stealth: bool = True,
    copy_cookies: bool = True,
) -> ChromeAgentResult:
    """Navigate to a URL within the chase profile."""
    args = ["--browser", profile, "--page", page]
    if stealth:
        args.append("--stealth")
    if copy_cookies:
        args.append("--copy-cookies")
    args.extend(["goto", url])
    return run(*args, timeout=90)


def screenshot(
    output: Path,
    *,
    profile: str = CHASE_PROFILE,
    page: str = CHASE_PAGE,
) -> ChromeAgentResult:
    """Capture a screenshot to disk."""
    output.parent.mkdir(parents=True, exist_ok=True)
    return run(
        "--browser",
        profile,
        "--page",
        page,
        "screenshot",
        "--output",
        str(output),
        timeout=30,
    )


def text(
    *,
    profile: str = CHASE_PROFILE,
    page: str = CHASE_PAGE,
) -> str:
    """Extract visible text from current page."""
    result = run(
        "--browser",
        profile,
        "--page",
        page,
        "text",
        timeout=30,
    )
    return result.stdout


def inspect(
    *,
    profile: str = CHASE_PROFILE,
    page: str = CHASE_PAGE,
    max_depth: int = 5,
) -> ChromeAgentResult:
    """Get accessibility tree (structured)."""
    return run(
        "--browser",
        profile,
        "--page",
        page,
        "--max-depth",
        str(max_depth),
        "inspect",
        json_output=True,
        timeout=30,
    )


def is_logged_in(text_dump: str) -> bool:
    """Heuristic: page text suggests authenticated dashboard, not login wall.

    Requires both:
      - no negative login-wall signals
      - at least one positive authenticated marker (eg 'Card Benefits',
        'Available credit', 'Sign Out')
    """
    bad_signals = (
        "Sign in",
        "We need to verify",
        "session has expired",
        "Sign In to Your Account",
        "Verify it's you",
    )
    if any(s in text_dump for s in bad_signals):
        return False
    positive_signals = (
        "Sign Out",
        "Sign out",
        "Card Benefits",
        "Maximize your credit",
        "Available credit",
        "Sapphire Reserve",
    )
    return any(s in text_dump for s in positive_signals)
