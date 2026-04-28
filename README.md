# chase-agent

> A personal CFO for your Chase Sapphire Reserve perks. Scrapes your own Chase
> account through your already-logged-in Chrome session, runs a deterministic
> rule engine, and tells you the top 3 things to do this week to actually
> capture the $795 annual fee.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776ab.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![Mypy strict](https://img.shields.io/badge/types-mypy_strict-1f6feb.svg)](http://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](#license)

---

## Why this exists

The Chase Sapphire Reserve costs **$795/year**. It comes with ~15+ credits and
activatable perks, half of which:

- expire on different clocks (anniversary year, calendar year, semi-annual, monthly)
- require activation that breaks silently
- have hidden gotchas (Lyft credit dies if you pay via Apple Pay; DoorDash got
  nerfed in April 2026; Hyatt award chart changes in May 2026; Whoop perk
  expires 2026-05-12, etc.)

It is, in practice, an **operations problem**. Every cardholder I know either:

1. Lets a few hundred dollars/year evaporate, or
2. Babysits a personal spreadsheet that's always slightly out of date.

Existing tools don't help:

- **Plaid / SimpleFIN** see your transactions but can't see Chase's "Card Benefits"
  page — the canonical source of truth for credit balances. They miss 90% of
  what matters.
- **Mint / Copilot Money / Monarch** are general-purpose budgeting apps. Zero
  awareness of perks, activations, expiration clocks, or the points ecosystem.
- **Spreadsheets** rot.

So this is the agent I wanted: it reads Chase like I would, computes what's at
risk, and surfaces the 3 things I should actually do this week.

## What it does

- **Scrapes Chase Card Benefits** through your logged-in Chrome session via
  [`chrome-agent`](https://github.com/Conduktor/chrome-agent) — no third-party
  data aggregator, no credentials shared, all local.
- **Tracks four independent clocks** (anniversary / calendar / monthly /
  limited-time) so credits that reset on different schedules don't get confused.
- **Schema-locked LLM extraction** with hallucination defenses: bounds-checking,
  ledger cross-check, dual-pass verification, sanitized prompts (PII redacted
  before anything leaves the machine).
- **Deterministic rule engine** scores every recommendation by
  `value × urgency × confidence ÷ effort` and surfaces the top 3.
- **Local web dashboard** at `http://localhost:7777` showing burn-down per
  perk, clocks, activations, top actions, captured KPI.
- **CLI** for power-user actions: suppress, activate, scrape, report, init.
- **Light-theme UI** (because dark themes are not real engineering).

## What it explicitly is not

- Not a budgeting app
- Not a points / churning automation tool
- Not a generic "track your finances" dashboard
- Not multi-user, not multi-account, not cloud
- Not financial / tax / investment advice

## Outcome

**Phase 1 is shipped.** The project builds, scrapes (when wired to live Chase),
and runs end-to-end against seed data. Concretely:

```text
~3,000 lines of Python
46 unit tests, all passing
Strict ruff + mypy strict + pre-commit hooks green
Anthropic SDK call cost: ~$1–3/month for daily scrapes (Haiku 4.5 with prompt caching)
```

Sample output (seed data, today=2026-04-28):

```text
CSR captured: $601 / $795 (76%)

Top actions:
  1. Move safe everyday spend to CSR to catch up on sign-up bonus  $1,875
  2. Activate Whoop Life membership                                  $359
  3. Use your H1 dining credit at an Exclusive Tables restaurant     $150
```

The remaining phases (live scraping, reactive nudges, advisor modes, optional
WhatsApp push) are scoped in `ARCHITECTURE.md`.

## Architecture (one screen)

```text
┌─ chrome-agent (CDP attached to your real Chrome session)
│  └─ navigates Chase Card Benefits, extracts text
│
├─ daemon (Python)
│  ├─ scraper: chrome-agent + Anthropic LLM with schema-locked tool use
│  ├─ rule engine: pure functions (testable, no I/O)
│  ├─ ledger: SQLite, money stored as INTEGER cents
│  ├─ FastAPI dashboard (HTMX + Tailwind, light theme)
│  └─ CLI (Typer)
│
└─ outputs: dashboard at localhost:7777, CLI, optional WhatsApp push
```

Full details in [ARCHITECTURE.md](ARCHITECTURE.md).
Behavior, scoring, and decision rules in [SPEC.md](SPEC.md).
Domain knowledge (perks, hacks, edge cases) in [RESEARCH_FINDINGS.md](RESEARCH_FINDINGS.md).

## Getting started

```bash
git clone https://github.com/sderosiaux/chase-perks-agents-optimizer
cd chase-perks-agents-optimizer
uv sync
uv pip install -e .

# 1) See it work with seed data, no credentials needed
CHASE_AGENT_DATA_DIR=/tmp/chase-demo uv run python -m chase_agent.seed
CHASE_AGENT_DATA_DIR=/tmp/chase-demo DEMO_TODAY=2026-04-28 \
  uv run chase-agent dashboard --port 7777
# open http://localhost:7777

# 2) Real onboarding (requires chrome-agent CLI in PATH + ANTHROPIC_API_KEY)
cp .env.example .env  # then edit .env with your key
uv run chase-agent init
uv run chase-agent scrape benefits
uv run chase-agent dashboard
```

## CLI reference

```bash
chase-agent init                    # first-run config
chase-agent status                  # captured state + top actions
chase-agent dashboard               # local web UI
chase-agent scrape benefits         # scrape Chase Card Benefits page
chase-agent report weekly           # write markdown weekly report
chase-agent suppress doordash_restaurant --reason "never use it"
chase-agent activations             # list activation status
chase-agent activate ihg_platinum   # mark a perk as activated
chase-agent reactive on             # toggle real-time nudges
chase-agent recs                    # show every recommendation + score
chase-agent config                  # show current config
chase-agent config-set phone_bill_on_csr true
chase-agent wipe --yes              # nuclear: delete all local state
```

## Development

```bash
uv sync                       # install runtime + dev deps
uv pip install -e .           # editable install
uv run ruff check chase_agent/ tests/   # lint (strict)
uv run mypy chase_agent       # type-check (strict)
uv run pytest -q              # tests
uv run pre-commit install     # install git hooks
```

The pre-commit hooks enforce ruff + mypy + pytest. Don't `--no-verify`.

Read [`CLAUDE.md`](CLAUDE.md) for working notes, gotchas, and rules of the road
that AI assistants (and future-me) should know before touching this repo.

## Privacy stance

- **Account numbers, credentials, cookies** never leave your machine
- **Page text + screenshots** sent to Anthropic are sanitized: account numbers,
  emails, phone numbers, addresses, names, ZIP codes, and SSN-like patterns are
  stripped via [`chase_agent/scraper/redact.py`](chase_agent/scraper/redact.py)
- **Screenshots are not sent to the LLM in v1** (cropping to the benefits panel
  is a Phase 2 task); we feed text-only with redaction
- **All transaction and credit data** stored locally in SQLite under
  `~/Library/Application Support/chase-agent/` (or `$CHASE_AGENT_DATA_DIR`)
- **No telemetry** outbound except Anthropic API calls
- **No third-party data aggregator** (no Plaid, no SimpleFIN, no MX)

## Roadmap

- [x] **Phase 1** — Project skeleton, perk catalog, rule engine, dashboard, CLI, scraper scaffolding, tests
- [ ] **Phase 2** — Live scraping against real Chase
- [ ] **Phase 3** — Reactive transaction evaluation (rate-limited real-time nudges)
- [ ] **Phase 4** — On-demand advisor modes (trip optimizer, redemption advisor, purchase advisor)
- [ ] **Phase 5** — WhatsApp Web push (optional, via chrome-agent)
- [ ] **Phase 6** — Action capability (gated): activate IHG Platinum, scan Chase Offers, search The Edit

## Contributing

This is a personal project but the architecture is generic enough to fork for
other premium cards (Amex Platinum, Capital One Venture X, etc.) — the perk
catalog, rule engine, and dashboard are card-agnostic; only `perks.py` and the
scraper would need rewriting per card.

PRs welcome. Issues welcome. Stars welcome.

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by JPMorgan
Chase Bank, N.A., Anthropic, or any other entity mentioned. "Chase", "Sapphire
Reserve", "The Edit", and other product names are trademarks of their
respective owners.

The agent reads your own account data through your own browser session.
Automated access to chase.com may technically violate Chase's Terms of Service
even for personal use; use at your own risk and do not commercialize.

This project does not provide financial, tax, or investment advice. Numbers are
estimates. Verify in the Chase app before acting on any recommendation.
