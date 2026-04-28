# CLAUDE.md

Working notes for Claude Code on this project. Read this before any work.

## What this is

Personal Chase Sapphire Reserve perks optimizer. Single-user, local-first.
Scrapes Chase via chrome-agent (LLM-driven, attached to user's Chrome session),
runs a deterministic rule engine over the state, exposes a local dashboard at
`http://localhost:7777` and a CLI (`chase-agent`).

## Read first

- `SPEC.md` — behavior, decision rules, scoring, UX (the WHAT)
- `ARCHITECTURE.md` — stack, surfaces, scraping, phased rollout (the HOW)
- `RESEARCH_FINDINGS.md` — domain knowledge: perks, hacks, edge cases
- `chase_agent/rules/perks.py` — perk catalog (data-only source of truth)
- `chase_agent/rules/engine.py` — scoring engine

## Tech stack (locked)

- Python 3.12+ via `uv` (NOT pip / poetry / venv directly)
- FastAPI + Jinja2 + HTMX + Tailwind v4 (no SPA build step)
- SQLite (raw `sqlite3`, no ORM)
- Pydantic v2 for config / schema
- Anthropic SDK (Haiku 4.5 for daily, Sonnet 4.6 for advisor modes)
- chrome-agent CLI (subprocess) for browser automation
- Typer for CLI

## Coding standards

- **Ruff** with strict ruleset (see `pyproject.toml`). Auto-fix on save.
- **Mypy strict** mode. No `Any` unless unavoidable. No untyped functions.
- **Pre-commit hooks** enforce both. Don't skip with `--no-verify`.
- Line length 100.
- Single-quoted strings handled by ruff-format.
- `from __future__ import annotations` everywhere except where pydantic needs runtime types.
- ASCII only in identifiers and code strings (no `×`, `→`, `–`, `≤` in code/docstrings — only in markdown).

## Architecture rules (non-negotiable)

1. **Rule engine is pure functions.** No I/O, no DB calls, no LLM. Easy to test.
2. **LLM is in the seams, not the core.** Used for: page extraction (with schema-locked tool use), report phrasing, advisor modes. Never for: scoring, state, deterministic logic.
3. **Schema-locked tool use everywhere** the LLM extracts numbers. No free-form. Cross-check against ledger to reject hallucinations.
4. **Three-clock model is canonical.** Anniversary / Calendar / Monthly / Limited-time. Never confuse them.
5. **Chase Card Benefits page is the source of truth** for credit balances. The agent reads, doesn't compute.
6. **Local-first.** All data in SQLite under user data dir. Anthropic sees only anonymized prompts.
7. **No backwards-compat shims.** Single user, no legacy. Change schema, write migration if needed, move on.

## Design rules (UI)

- **Light theme only.** Never dark. (User preference.)
- Tablet/laptop-first.
- Linear / Stripe / Apple aesthetic. Generous spacing, no chrome.
- Color tokens: healthy (green), urgent (amber), critical (red), inactive (gray).
- All colors via Tailwind tokens / CSS variables. **Never hardcode hex.**
- Empty states guide the user to the next action.
- Smooth hover transitions on interactive elements.
- Collapsible sidebar, default closed.

## Common commands

```bash
# Setup
uv sync                              # install runtime + dev deps
uv pip install -e .                  # editable install

# Lint + types
uv run ruff check chase_agent/       # lint
uv run ruff check chase_agent/ --fix # auto-fix
uv run ruff format chase_agent/      # format
uv run mypy chase_agent              # strict types

# Test
uv run pytest -q                     # tests

# Run
uv run chase-agent --help            # CLI
uv run uvicorn chase_agent.dashboard.app:app --port 7777  # dashboard

# Pre-commit
uv run pre-commit run --all-files
```

## Build phases (current state)

- [x] Phase 0: Project skeleton, perk catalog, DB, rule engine
- [ ] Phase 1: Dashboard + CLI + mock data (in progress)
- [ ] Phase 2: chrome-agent scraping + LLM extraction
- [ ] Phase 3: Reactive transaction evaluation
- [ ] Phase 4: On-demand modes (trip optimizer, redemption advisor)
- [ ] Phase 5: WhatsApp push (optional)
- [ ] Phase 6: Action capability (gated)

## Common pitfalls (learned this session)

- **Don't use `from __future__ import annotations` in pydantic models** with `date` fields — pydantic needs runtime types.
- **Pyright sometimes can't resolve `chase_agent.rules.X` imports** even after editable install. Mypy is the source of truth, not pyright.
- **Ruff TC003** wants stdlib type-only imports inside `TYPE_CHECKING`. Add `noqa` only when pydantic needs them at runtime.
- **DoorDash credit value is ~$10–15 effective**, not the $25 headline (April 2026 nerf).
- **Lyft credit only triggers if CSR is set as direct payment** (not Apple Pay). Same for Peloton.
- **Whoop Life expires 5/12/2026** — limited time, surface aggressively until then.
- **Hyatt award chart change is May 2026** — warn proactively for any planned Hyatt trip.

## What NOT to do

- **Don't add dependencies casually.** Justify each one.
- **Don't write a frontend SPA.** HTMX + server-rendered Jinja is the path.
- **Don't add logging frameworks.** `print` to stderr or rich console is enough until proven otherwise.
- **Don't write unnecessary abstractions.** Three similar lines is fine.
- **Don't add try/except defensively.** Let exceptions propagate at boundaries; fail loud.
- **Don't write docstrings explaining what code does** when names suffice. Only WHY when non-obvious.
- **Don't introduce 3rd-party data ingestion (Plaid, SimpleFIN).** chrome-agent is the answer.
- **Don't mock the database in tests.** Use the real SQLite (in tmpdir).

## Privacy stance

- User account numbers, credentials, cookies → never in prompts, never in logs
- Transaction descriptions and amounts → OK in prompts (necessary for reasoning)
- API key → macOS Keychain only, never `.env` checked in
- All data → `~/Library/Application Support/chase-agent/` (or `$CHASE_AGENT_DATA_DIR`)

## Today's date for testing

`2026-04-27`. The seed data and example outputs are calibrated to this date.
Whoop Life perk has 15 days left as of "today". This is intentional — exercises
the limited-time urgency curve.
