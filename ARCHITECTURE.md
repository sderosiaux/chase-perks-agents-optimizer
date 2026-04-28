# Architecture

Companion to `SPEC.md`. Captures the technical architecture and decisions for how the agent runs, ingests data, and reacts.

---

## Core stack

```
┌────────────────────────────────────────────────────────────────────┐
│  Mac (local, always-on)                                            │
│                                                                    │
│  ┌─ chrome-agent ─────┐    ┌─ daemon (Python) ────────────────────┐│
│  │  Chase scraping    │ ←→ │  ├─ scheduler (launchd cron)         ││
│  │  WhatsApp Web push │    │  ├─ rule engine                      ││
│  │  Lyft / DoorDash   │    │  ├─ ledger (SQLite)                  ││
│  │    web scraping    │    │  ├─ FastAPI server (dashboard)       ││
│  └────────────────────┘    │  └─ CLI (chase-agent binary)         ││
│                            └──────────┬───────────────────────────┘│
│                                       ▼                            │
│                        ┌─ SQLite (local)                           │
│                        ├─ Snapshots/ (HTML, screenshots)           │
│                        └─ reports/ (markdown archive)              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
        ▲                ▲                ▲                ▲
        │                │                │                │
        ▼                ▼                ▼                ▼
   Anthropic API    Dashboard         CLI            WhatsApp Web
   (Haiku +         localhost:7777    chase-agent    (optional,
    Sonnet)         (browser)         (terminal)      via chrome-agent)
```

### Surfaces (3, prioritized)

1. **Dashboard** (primary) — local web app at `http://localhost:7777`, always-on view of state
2. **CLI** (`chase-agent ...`) — power-user actions, config, suppression
3. **WhatsApp** (optional) — push notifications for weekly reports + reactive nudges, sent via WhatsApp Web automated through chrome-agent

---

## Data ingestion: chrome-agent + CDP

### Why this approach

- User already logged into Chase in their Chrome profile (cookies, MFA done)
- chrome-agent attaches to that session via Chrome DevTools Protocol — no fresh login, no MFA dance
- LLM reads pages semantically (accessibility tree + screenshots), not via DOM selectors
- Chase UI changes don't break the scraper — LLM still understands "Travel credit: $180 of $300"
- Zero third party (no Plaid, no SimpleFIN), max privacy
- Free (modulo LLM API cost)

### Setup

Uses `chrome-agent` CLI with a dedicated browser profile, isolated from the user's main Chrome.

1. User signs into Chase in their main Chrome (one time)
2. Daemon invokes chrome-agent with `--copy-cookies` to inherit the logged-in Chase session into a dedicated profile
3. The dedicated profile reuses cookies / session for all subsequent scrapes — no re-login needed unless Chase invalidates the session

```bash
chrome-agent --browser chase \
             --copy-cookies \
             --page dashboard \
             --stealth \
             goto https://secure.chase.com/web/auth/dashboard
```

- `--browser chase`: dedicated profile, won't disturb user's tabs
- `--copy-cookies`: inherits Chase login from real Chrome session (re-run if expired)
- `--page dashboard`: named tab persists across calls
- `--stealth`: 7 anti-detection patches (webdriver, UA, WebGL, etc.) to reduce bot flagging

The chrome-agent daemon mode (`chrome-agent pipe`) keeps the browser warm between scrapes for speed.

### Pages scraped

| Page | Purpose | Cadence |
|---|---|---|
| Dashboard summary | Account balances, alerts | 2x/day |
| Card Benefits / Maximize your credit | Live balance of every credit ($X / $300 travel, $X / $500 Edit, etc.) | 2x/day |
| Activity per card | New transactions | 2x/day |
| Statements | Verify posted credits | weekly |
| Rewards / UR portal | Points balance, Points Boost active offers | weekly |
| Chase Offers | Active merchant offers (often forgotten, can add $50-200/yr) | weekly |
| Activations status | Whether IHG Platinum, StubHub, Peloton, Apple subs are active | monthly |

### LLM extraction pattern

Each scrape task uses **tool use with strict schema** to force structured output:

```python
tool_schema = {
  "name": "extract_credits",
  "input_schema": {
    "type": "object",
    "properties": {
      "credits": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["name", "used_usd", "total_usd", "expires_iso", "clock_type"],
          "properties": {
            "name": {"type": "string"},
            "used_usd": {"type": "number"},
            "total_usd": {"type": "number"},
            "expires_iso": {"type": "string"},
            "clock_type": {"enum": ["anniversary", "calendar", "monthly", "limited_time"]}
          }
        }
      }
    }
  }
}
```

LLM is forced to fill the schema. No free-form. No hallucination drift.

### Hallucination mitigations

Numbers from a screenshot are the highest-risk extraction. Defenses:

1. **Schema-locked tool use** (above)
2. **Cross-check vs ledger**: if LLM reports `Edit: $250 used`, ledger must contain a corresponding Chase Travel transaction in the same period. Mismatch → flag, don't update.
3. **Dual-pass verification**: extraction call → second call asks LLM to verify its own extraction against the screenshot. Disagreement → flag.
4. **Screenshot archived** with timestamp for every scrape. Audit trail if a number ever looks suspicious.
5. **Sanity bounds**: any credit total outside known ranges (eg $300 travel can't suddenly become $3000) is rejected.
6. **Human spot-check on first 30 days**: report includes "raw extracted data" footer for user verification, until trust is established.

---

## Reactivity model

Three independent triggers:

### Scheduled (cron via launchd)

| Trigger | Cadence | Action |
|---|---|---|
| Daily scrape | 8h, 20h NYC | Pull dashboard + benefits + activity, update ledger |
| Weekly report | Mon 8h NYC | Run rule engine, generate report, push |
| Monthly sweep | Day 26 of month | Focus on monthly credits |
| Half-year sweep | Jun 15, Dec 15 | Focus on dining + StubHub |
| Quarterly activation re-verify | Every 90 days | Re-confirm activation states |
| Anniversary alert | 60d / 30d / 7d before reset | Travel credit reminder |
| Limited-time perk daily reminder | Last 7 days | Daily push for Whoop, etc. |

### Reactive (event-driven)

When the daily scrape detects a NEW transaction in the ledger:
1. Categorize the transaction
2. Run a micro-evaluation: did user pick the optimal card? Was a credit available?
3. Push **only if action is useful**:
   - "Just saw Uber $14, you had Lyft credit unused. Net miss ~$8."
   - "This $X hotel booking — was it eligible for Edit + select-hotel stack? Check."
   - "Phone bill paid on Amex — switch to CSR for $1k/incident protection."
4. Otherwise silent. No notification.

**Reactive mode is ON by default** with rate-limiting:
- Max 2 nudges/day
- No nudge if missed value < $5
- No nudge during quiet hours (22h–8h NYC)
- Disable via `chase-agent reactive off`

### On-demand (conversational)

User sends a question via the dashboard, CLI, or WhatsApp:
- "Carte pour billet d'avion United?"
- "J'ai 3 nuits Park City en juillet, optimise"
- "Mes activations en attente?"
- "Mes points UR pour Tokyo, portal vs transfer?"

Daemon receives, runs intent classification, routes to the appropriate interaction mode (purchase advisor / trip optimizer / status check / redemption advisor — see SPEC.md interaction modes). Returns a single-message answer.

---

## LLM allocation

| Task | Model | Why |
|---|---|---|
| Daily scrape extraction | Haiku 4.5 | Cheap, structured tool use, high volume |
| Weekly report phrasing | Haiku 4.5 | Templated, low ambiguity |
| Reactive transaction evaluation | Haiku 4.5 | Quick categorization, low context |
| Trip optimizer | Sonnet 4.6 | Multi-option reasoning, higher stakes |
| Redemption advisor | Sonnet 4.6 | Comparing portal vs partners with availability |
| Verification dual-pass | Haiku 4.5 | Self-check on extraction |

Prompt caching enabled on the system prompt + Chase page templates → ~50-70% token cost reduction on repeated scrapes.

**Estimated monthly cost:** $1–3 in API calls for typical usage.

---

## Storage

Local SQLite with these logical tables:

| Table | Purpose |
|---|---|
| `transactions` | All scraped transactions (immutable append) |
| `credits_state` | Current burn-down per credit, per clock |
| `activations` | State of every activatable perk + last_verified |
| `behavior_overrides` | User opt-outs, suppressed perks |
| `recommendations_history` | Every recommendation ever made + outcome (taken / ignored / declined) |
| `reports` | Archived weekly/monthly reports |
| `scrape_runs` | Metadata of each scrape (timestamp, success, anomalies, screenshot path) |
| `config` | Manual config fields (see SPEC.md) |

Backup: optional litestream replication to encrypted iCloud Drive folder.

---

## Surfaces

### 1. Dashboard (primary, always-on view)

Local web app served by the daemon at `http://localhost:7777`. Bound to 127.0.0.1 only, no auth needed.

**Stack:**
- FastAPI backend (already in daemon)
- HTMX + Tailwind v4 frontend (no build step, no SPA complexity)
- Server-Sent Events for real-time refresh from SQLite changes
- Inline SVG for progress bars (no chart libs)

**Sections (top-to-bottom):**

1. **Header** — annual fee captured progress bar (`$X / $795`), last scrape time, force re-scrape button
2. **Three-clock dashboard** — anniversary / calendar / monthly tiles, color-coded by urgency
3. **Activations panel** — toggle-style indicators per activatable perk, last verified, action buttons
4. **Limited-time perks** — countdown to deadlines (Whoop, select-hotel, Instacart, Hyatt chart change, 1.5 cpp transition)
5. **Top actions** — top 3 from rule engine
6. **Recent missed value** — last 7 days, sortable
7. **Upcoming travel** — detected trips + manual add
8. **Sign-up bonus** — progress bar (if active) or cleared badge

**Sidebar (collapsible, default closed):**
- Overview (default)
- History (every recommendation made + outcome)
- Reports (archived weekly reports)
- Activity (transactions feed)
- Activations (detailed status + audit log)
- Trips (trip optimizer + planning)
- Config (manual fields, behavior overrides, suppression list)
- Logs (scrape runs, errors, anomalies)

**Design:**
- Light theme only (per user preference)
- Color tokens: healthy (green), urgent (amber), critical (red), inactive (gray)
- Tablet/laptop-first layout
- Apple/Stripe/Linear visual style: minimalist, generous spacing, no chrome
- All colors via CSS variables / Tailwind tokens, no hardcoded values
- Hover transitions on progress bars → tooltip with breakdown
- Click on credit → modal with transaction history that consumed the credit

**Annual fee captured computation:**
```
captured = Σ (statement credits posted this card-year)
        + Σ (activation imputed values: Apple TV+ $96, Apple Music $120, Peloton $120, etc.)
        + (cell phone protection $120 imputed if phone bill on CSR)
        + (lounge visits × $35)
        + (DashPass $120 imputed if used ≥1×/month)
```

This is THE primary KPI of the dashboard.

### 2. CLI (`chase-agent`)

Power-user surface for actions, config, debugging. See "CLI commands" section below.

### 3. WhatsApp (optional)

Push notifications for weekly reports + reactive nudges + on-demand Q&A.

**Implementation:** chrome-agent automates WhatsApp Web (`web.whatsapp.com`).
- One-time QR code scan on first setup, session persists in dedicated chrome-agent profile
- Daemon → chrome-agent click into thread → type message → enter
- No third-party API, no Twilio cost, no business account needed
- Same auth pattern as Chase scraping (session in dedicated profile)

**Tradeoff:** WhatsApp Web is fragile (UI changes), unofficial. If it breaks, fall back to:
- Email (simple SMTP send)
- Dashboard-only mode

**Optional flag:** if `whatsapp.enabled = false` in config, all notifications stay in the dashboard. The agent works fully without push.

---

## Failure modes & graceful degradation

| Failure | Detection | Response |
|---|---|---|
| Chase requires re-MFA | Login page detected during scrape | Push "Re-auth needed in Chrome", pause scrapes until resolved |
| Chase UI radically changed | Schema extraction fails or values out of bounds | Push "Scrape anomaly, please verify in browser", attach screenshot, freeze ledger updates |
| Chrome not running | CDP connection refused | LaunchAgent auto-relaunch Chrome with debugging port |
| LLM API down | 5xx or timeout | Retry with backoff, fall back to last-known credit balances, flag staleness in next report |
| Hallucination on a number | Cross-check vs transactions fails | Reject extraction, retry, then flag for human review |
| Session expired | Login wall during navigation | Same as MFA: push, pause |
| Network down | Scrape fails entirely | Skip, retry next cycle, no panic |
| Account flagged by Chase (worst case) | Login blocked | Stop scraping, alert user immediately |

---

## Privacy stance

- All transaction data stays local (SQLite)
- Chrome profile stays local (cookies, session)
- LLM calls **anonymized**: amounts kept (necessary for reasoning), but no full account numbers, no personal identifiers in prompts
- Screenshots stored locally only, never sent except when needed for extraction
- LLM prompts cached with prompt caching → cached portions are content-only, no PII
- No telemetry outbound except Anthropic API
- API key stored in macOS Keychain
- User can wipe everything with one command: `agent wipe` clears SQLite + snapshots + reports

What Anthropic sees:
- Page screenshots and extracted text from Chase pages
- Transaction descriptions, amounts, dates
- Your scoring inputs and recommendation outputs

What Anthropic does NOT see:
- Account numbers
- Credentials
- Cookies / session tokens
- The user's identity (no name, no address, no SSN)

---

## Cost summary

| Component | Cost | Notes |
|---|---|---|
| chrome-agent | $0 | Open source, local |
| Chrome | $0 | Already running |
| Daemon | $0 | Local Go/Python |
| SQLite | $0 | Local |
| Anthropic API | $1–3/mo | Haiku-heavy with caching |
| WhatsApp Web (optional) | $0 | Via chrome-agent, no API |
| iCloud Drive backup | $0 | Existing user storage |
| **Total** | **~$2/month** | |

vs Plaid (~$5+/mo + B2B onboarding hassle), SimpleFIN ($15/yr), or Copilot Money ($156/yr).

---

## What this architecture unlocks (beyond ingestion)

Because the LLM can both **read and act** through chrome-agent, the agent can do things ingestion-only solutions cannot:

- "Activate IHG Platinum" → LLM navigates Card Benefits → clicks Activate
- "Check Chase Offers and tell me which to add" → reviews offers, recommends → with consent, adds them
- "Search The Edit for hotels in Park City for July 4-6" → live search, returns options with stack eligibility flagged
- "Check if any transfer bonus to Hyatt is active" → navigates UR portal
- "Verify the Whoop activation went through" → checks the page, confirms

This is a meaningful capability jump over "agent that just reads transactions". Surfaced in interaction modes (see SPEC.md), gated behind explicit user consent for any action.

---

## Resolved decisions

- **Daemon language**: Python
- **Chrome**: dedicated profile via `--browser chase --copy-cookies --stealth` (chrome-agent CLI). Isolated from user's main Chrome.
- **Surfaces**: Dashboard (primary, always-on) + CLI + optional WhatsApp Web push
- **Reactive mode**: ON by default, with rate-limit (max 2/day, $5 floor, quiet hours 22h–8h)
- **Multi-account**: out of scope for v1
- **Action capability rollout**: phased, read-only first month
- **Onboarding**: CLI prompts (single user, dev power-user)
- **Behavior overrides**: CLI commands (eg `chase-agent suppress doordash`)

## Remaining open questions

1. **Mac sleeping**: launchd `pmset` flags or Amphetamine to keep Mac awake at scrape times? Or accept missed runs and just retry on next wake.
2. **Failure escalation**: when scrape fails 3x in a row, what's the escalation? Dashboard banner? WhatsApp alert? Block all reports until resolved?
3. **User travels (IP/location changes)**: Chase may flag the dedicated profile. Mitigation: pause scraping during known travel windows? (calendar integration helps)

---

## CLI commands (planned)

Single binary `chase-agent` for all user interactions:

```bash
# Lifecycle
chase-agent init                       # First-run onboarding
chase-agent status                     # Show current state, last scrape, next run
chase-agent scrape now                 # Force a scrape immediately
chase-agent report now                 # Generate report immediately, push

# Suppression / overrides
chase-agent suppress <perk>            # Stop suggesting this perk
chase-agent suppress <perk> --reason "I never use it"
chase-agent unsuppress <perk>          # Resume suggestions
chase-agent overrides list             # Show active suppressions

# Reactive control
chase-agent reactive on
chase-agent reactive off
chase-agent reactive status

# Activations
chase-agent activations                # List status of all activatable perks
chase-agent activate <perk>            # Open Chase page for activation (or auto-click in action mode)

# Trip optimizer (one-shot)
chase-agent trip "3 nights Park City Jul 4-6, flying from JFK"

# Card advisor (one-shot)
chase-agent card-for "Hertz Madrid 5 days"

# Redemption advisor
chase-agent redeem "2 nights Park Hyatt Tokyo Sept"

# Config
chase-agent config show
chase-agent config set <key> <value>

# Maintenance
chase-agent reauth                     # Re-copy cookies from main Chrome
chase-agent wipe                       # Nuclear: clear all local state
```

Dashboard exposes the on-demand modes via UI forms. WhatsApp (if enabled) accepts the same commands as conversational messages.

---

## Phased rollout

### Phase 1: Read-only ingestion + dashboard
- chrome-agent setup with dedicated Chase profile
- Scrape dashboard + Card Benefits + activity (no actions)
- SQLite ledger
- Rule engine (the entire SPEC.md decision logic)
- Dashboard at localhost:7777 with three-clock view, activations, top actions
- Weekly report generated to markdown file (no push surface yet)

### Phase 2: Reactive transaction evaluation
- Real-time post-scrape evaluation
- Surface anomalies/missed value in dashboard live feed
- Rate-limited (max 2/day, $5 floor, quiet hours 22h–8h)

### Phase 3: On-demand modes via dashboard + CLI
- Trip optimizer / purchase advisor / redemption advisor via dashboard forms
- Same modes via CLI (`chase-agent trip ...`, `chase-agent card-for ...`)

### Phase 4: Action capability (gated)
- LLM can click Activate buttons, add Chase Offers, navigate The Edit search
- Always requires user confirmation before commit
- ~2 weeks additional

### Phase 5: WhatsApp push (optional)
- chrome-agent automates WhatsApp Web for push
- Weekly reports + reactive nudges + on-demand Q&A via WhatsApp
- One-time QR scan, session persists in dedicated chrome-agent profile
- Fallback to email if WhatsApp Web breaks

### Phase 6: Polish
- Visual diff alerts
- Backup/restore
- Action mode rollout (gated)
