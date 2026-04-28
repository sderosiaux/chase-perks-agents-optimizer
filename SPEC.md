Build a personal "Chase Sapphire Reserve Maximizer Agent".

Focus only on behavior, product logic, UX, recommendations, and decision-making.

Do NOT start with implementation details, frameworks, database schema, or code architecture.

---

## Goal

Create an AI agent that helps me maximize the value of:
- Chase Sapphire Reserve (CSR)
- Chase Private Client (CPC) relationship

The agent answers one question every week: **"What should I do this week to maximize my card value and avoid wasting benefits?"**

## User context

- NYC resident
- 5–6 plane trips per year
- Heavy Uber/Lyft usage
- Has CPC, CSR (annual fee $795 since 2026 update)
- Today's reference date: 2026-04-27 (used for time-bound perk computation)

## Core principle

The agent is a **personal CFO for card perks**. Not a dashboard. Not a passive tracker.

With $795 annual fee, the agent must surface ≥$795 of captured value/year as the minimum bar. Stretch goal: ≥$1,500/year.

---

## Behavior requirements

### 1. Action-first
Weekly output gives only the most useful actions. No long generic explanation. No exhaustive benefit list. No passive tracking.

### 2. Speak in money
Convert perks into estimated dollar value whenever possible.
- "You are leaving ~$86 on the table this week."
- "You missed ~$22 last week by using Uber instead of Lyft."
- "This credit expires in 11 days: potential loss $150."

### 3. Prioritize hard
Weekly report sections (defined later). Suppress low-value noise.

### 4. Be opinionated
Recommend a choice, not a comparison.
- Bad: "You may want to consider The Edit."
- Good: "Use The Edit for this stay. The $250 credit + breakfast beats direct booking points."

### 5. Learn behavior
After **min 4 data points** within 60 days, the agent may infer a preference and adjust output.
Patterns to watch:
- Uber > Lyft preference
- DoorDash credit ignored
- Hotels booked direct
- Lounges skipped
- Dining credits expired
- Idle cash in checking

### 6. Use urgency (formal definition)
Each credit has a deadline. Urgency `u ∈ [0, 1]` is a function of `days_remaining / total_window`:
- `u = 0.1` when >75% of window remains
- `u = 0.4` when 25–75% remains
- `u = 0.7` when 7–25% remains
- `u = 1.0` when ≤7 days remain
- Sign-up bonus: `u = 1.0` if behind linear pace, else `0.3`
- Limited-time perks (Whoop, Instacart): `u = 1.0` in last 30 days

### 7. Exact next-action template
Every recommendation includes:
```
- action (1 sentence)
- estimated_value ($ or pts)
- deadline (date)
- effort (low / med / high)
- confidence (0–1)
- reason (why this user, why now)
- next_step (concrete first move)
```

### 8. Track active state
Activatable perks (Apple TV+, Apple Music, Peloton, IHG Platinum, StubHub, DashPass↔Lyft link, cell phone protection trigger) require state tracking with `last_verified` date. Re-verify every 90 days.

---

## Three-clock model (CRITICAL)

The agent tracks THREE independent clocks. Confusing them is a common user mistake. Every weekly report must show all three.

### Anniversary-year clock (resets on card open-date anniversary)
- $300 annual travel credit

### Calendar-year clock (resets Jan 1)
- $500 The Edit credit (max $250 per transaction, 2 separate stays required)
- $250 select-hotel credit (**2026 ONLY** — disappears 12/31/2026)
- $300 dining credit (split $150 Jan-Jun / $150 Jul-Dec)
- $300 StubHub/viagogo credit (split $150 Jan-Jun / $150 Jul-Dec)

### Monthly clock (resets on the 1st)
- $10 Lyft credit
- $5 DoorDash restaurant + 2× $10 DoorDash non-restaurant
- $10 Peloton credit
- $15 Instacart credit (through July 2026)

---

## Credit absorption order

When a single transaction is eligible for multiple credits, they apply in this fixed order (per Chase posting behavior):

1. $300 annual travel credit (broadest eligibility, applies first if any anniversary-year balance remains)
2. $250 select-hotel credit (2026 only, prepaid 2+ night stays at eligible brands)
3. $250 The Edit credit (per-transaction cap)
4. Per-stay benefits ($100 property credit, breakfast, upgrade — these are NOT statement credits but on-property benefits)

The agent must compute hypothetical absorption when comparing booking options, not assume independence.

---

## Perks to model

### Chase Sapphire Reserve

**Earning categories (post-2026 update):**
- 8x — Chase Travel including The Edit
- 4x — flights and hotels booked DIRECT
- 3x — dining
- 5x — Lyft (through 9/30/27)
- 10x — Peloton equipment ≥$150
- 1x — everything else (incl. Uber, transit, OTAs — devalued from prior 3x)

**Sign-up bonus:**
- 125,000 pts after $6,000 spend in first 3 months
- Linear pace target: $2,000/month
- Authorized user spend counts
- State machine: `inactive → active → on_pace → behind → cleared → archived`
- After `cleared`, agent stops pacing alerts; archived after 30 days

**Hotel credits:**
| Credit | Amount | Period | Conditions |
|---|---|---|---|
| Annual travel credit | $300 | Anniversary year | Any travel purchase (broad eligibility) |
| The Edit | $500 (2× $250) | Calendar year | Prepaid Pay Now, 2+ nights, max $250/transaction, two separate stays |
| Select-hotel | $250 | Calendar 2026 ONLY | Prepaid 2+ nights at IHG / Montage / Pendry / Omni / Virgin / Minor / Pan Pacific |

The Edit per-stay benefits (in addition to statement credit):
- $100 property credit
- Daily breakfast for two
- Room upgrade subject to availability
- 8x UR points on the booking
- **Hotel loyalty points + elite night credits on the FULL stay** (not just paid portion) — important for status chasers
- Eligible for Points Boost (up to 2 cpp redemption)

**Dining:**
- $300 annual via Sapphire Reserve Exclusive Tables on OpenTable, $150 Jan-Jun / $150 Jul-Dec
- ~55 NYC restaurants (list curated by The Infatuation)
- No preregistration; pay with CSR at eligible venue

**Other credits:**
- $300 StubHub/viagogo — semi-annual split, **activation required**, through 12/31/27
- DashPass — complimentary
- DoorDash — $5/mo restaurant + 2× $10/mo non-restaurant, through 12/31/27 (post-April 2026 nerf)
- Lyft — $10/mo in-app credit, through 9/30/27
- Peloton — $10/mo statement credit, **activation required**, through 12/31/27
- Apple TV+ and Apple Music — full memberships, through 6/22/27
- Instacart — $15/mo, through July 2026

**Lounge access:**
- Priority Pass Select (incl. authorized users)
- Chase Sapphire Lounges (JFK T4, LGA T-B, Boston, others; DFW + LAX coming 2026)

**Underrated/passive perks (often missed):**
- Reserve Travel Designer — complimentary custom itinerary, ~$300/trip value
- IHG One Rewards Platinum status — free, **activation required**, 60% bonus pts + space-available upgrades
- Whoop Life membership — limited-time, expires **5/12/2026** (15 days from today), ~$359 value, includes physical band
- Cell phone protection — up to $1,000/incident if user pays phone bill with CSR (high-leverage one-time autopay switch)
- Travel insurance — trip cancellation/interruption, primary CDW on car rentals, lost luggage
- Authorized user spend counts toward SUB and travel credit

**Points redemption:**
- Baseline 1 cpp via Chase Travel portal
- **Existing CSR holders keep 1.5 cpp fixed redemption until 10/26/2027** (transition)
- Points Boost: 1.5–2 cpp on rotating offers (CSR gets 2 cpp on Edit hotels)
- 14 transfer partners at 1:1 (10 airlines, 4 hotels)

### Chase Private Client (CPC)

Treat as relationship leverage, not a points engine.

**Real ROI levers (where actual dollars live):**
1. Auto loan rate discount: 0.25–0.50% with auto-pay
2. Mortgage rate discount
3. Welcome bonus until 7/15/2026: $1k / $2k / $3k for $150k / $250k / $500k new-money deposits, hold 90 days
4. **Override 5/24** for some Chase card applications (biggest churning lever)
5. Wire / cashier check / foreign-ATM fees waived
6. Linked business account waives the $35/mo CPC fee even without $150k

**Fee waivers (low value unless usage exists):**
- No ATM fees worldwide
- No foreign transaction fees on debit
- No wire fees
- No overdraft / NSF fees
- 20% safe deposit box discount

**WARN:** J.P. Morgan Private Client (the upsell tier) charges fees if balance <$750k as of 2026.

If checking balance > configured cash buffer → suggest reviewing yield options with CPC banker. Do NOT give investment advice.

---

## Card-of-record advisor (per category)

| Category | Card | Why |
|---|---|---|
| Dining (US) | CSR | 3x + dining credit eligibility |
| Flights direct | CSR | 4x + travel insurance + lounge access proof |
| Hotels direct | CSR | 4x + travel protections + elite credits |
| Hotels via Chase Travel | CSR | 8x + Edit credits eligibility |
| Hotels — luxury 2+ nights | CSR via Edit | stack triple-credit (see rule 2) |
| Lyft | CSR (CSR set as default in app, NOT Apple Pay) | 5x + $10 credit |
| Uber | CSR during SUB / any 1x card after | only 1x post-2026 |
| Peloton equipment ≥$150 | CSR | 10x |
| Phone bill | CSR | unlocks $1k cell phone protection |
| Streaming (Apple TV+/Music) | n/a — comp via CSR | activate, don't pay |
| Other streaming (Netflix, Spotify) | 1x on CSR; better cards exist if user has them | |
| Gas | not CSR's strength | use a 3–5% gas card if user has one |
| US grocery | not CSR's strength | use a 4–6% grocery card if user has one |
| Online shopping (US, non-category) | 1x — meh after SUB | |
| Foreign spend (any currency) | CSR | $0 FX + 1x pts + travel protections |
| Non-category until SUB clears | CSR | drive sign-up bonus |
| Non-category after SUB | low priority | 1x is meh |

---

## Key decision rules

### 1. Sign-up bonus
- Track $6,000/3mo progress
- Linear pace: $2,000/month minimum
- If behind: recommend reallocating safe everyday spend to CSR
- Authorized user spend counts
- Never recommend manufactured spend
- 90-day countdown visible in EVERY weekly report until `cleared`
- On clear: one-time celebration message, then archive

### 2. Hotel triple-stack (highest-leverage rule)

If user has any planned 2+ night stay in 2026:
- Search Chase Travel for properties **at intersection of The Edit AND eligible brand list** (IHG, Montage, Pendry, Omni, Virgin, Minor, Pan Pacific)
- Canonical examples: Pendry Park City, Pendry Manhattan West
- A single 2-night Pay Now booking ≥$500 at such a property triggers BOTH $250 credits = $500 back
- Plus $300 travel credit auto-applies first if anniversary balance available
- Net stack potential: up to **$800 on one trip**

Booking constraints:
- Pay Now (prepaid) required
- 2+ consecutive nights
- Total cost ≥ $500 (to capture both stack credits)
- Cancellation reverses credits
- Edit credits cannot stack on same booking — do 2 separate stays for full $500
- Activate IHG Platinum BEFORE the stay if hitting an IHG property
- Verify Omni listings (had bugs in early 2026)

Decision tree per planned hotel:
```
2+ nights & in 2026?
├── No → use travel credit if available, otherwise direct (4x + elite)
└── Yes:
    ├── In Edit AND in eligible brand list?
    │   └── Yes → triple-stack (Edit + select-hotel + travel)
    ├── In Edit only?
    │   └── Yes → Edit credit + travel credit
    ├── In eligible brand only?
    │   └── Yes → select-hotel credit + travel credit + direct booking
    └── Neither → direct booking (4x + elite + protections)
```

### 3. Travel credit ($300, anniversary year)
Eligibility is **very broad**: airlines (incl. baggage/seat fees), hotels, car rentals, cruises, taxis, Uber, Lyft, Amtrak, buses, tolls, parking, OTAs (Expedia, Kayak), campgrounds.

In NYC, this credit auto-burns from Uber + occasional parking/Amtrak.

- Track silently
- Only flag if ≥10 months into anniversary year with <$200 used
- **Returns or cancellations reverse the credit at any time** (not just within 90 days)
- 90-day rule applies only to account closure
- Cross-anniversary edge: a purchase posting just after anniversary counts toward the NEW year

### 4. Dining credit
Track Jan-Jun and Jul-Dec separately.
- Normal months: silent
- May / November: light reminder
- June / December: aggressive — push specific NYC venue
- Target: a single ~$150 upscale meal per half (lower friction than 3× $50)
- Suggested NYC venues: Gramercy Tavern, Estela, Tolo, Kabawa ($145 prix fixe = clean burn), Le B, Una Pizza Napoletana, Bar Kabawa, Fairfax
- inKind hack: some venues (eg Gjelina) on inKind AND eligible — split bill across both

### 5. Lyft vs Uber (UPDATED for 2026)

The 2026 devaluation made Uber 1x points (was 3x). Lyft is 5x with CSR. Combined with $10 monthly credit, Lyft wins more often.

**Formula** (existing CSR holder, 1.5 cpp transition rate until 10/26/2027):
```
points_value_per_dollar = 0.015 × multiplier
Lyft_net  = Lyft_price  - min($10_credit_remaining, Lyft_price) - (Lyft_price × 0.075)   # 5x × 1.5cpp
Uber_net  = Uber_price  - (Uber_price × 0.015)                                            # 1x × 1.5cpp
Use Lyft if Lyft_net < Uber_net
```

After 10/26/2027 (baseline 1 cpp), recompute with 0.05 / 0.01 multipliers.

Rule of thumb (NYC, 2026): Lyft wins unless Uber is >$15 cheaper before tip.

**CRITICAL Lyft setup** (one-time, agent verifies on first run):
- In Lyft app → Payment → set CSR as default "Personal" payment method
- Do NOT pay via Apple Pay, Google Pay, Venmo (disqualifies $10 credit AND 5x points)
- Do NOT use Wait & Save (excluded)
- Bikes/scooters not eligible
- Credit applies to subtotal in-app (not statement credit); partial credit rolls to next ride within same month
- Stack: link DashPass to Lyft for additional discount

**Same direct-payment principle applies to Peloton:** must pay via Peloton site/app directly with CSR. Never App Store, never Apple Pay. Otherwise credit doesn't trigger.

### 6. DoorDash (UPDATED for April 2026 nerf)

DoorDash added $20 minimum on convenience pickups in April 2026. Free-pistachios trick is mostly dead.

- **Effective monthly captureable value: ~$10–15** (NOT the $25 headline) — agent uses lower figure for value computation
- Discount applies to subtotal only (not fees/taxes/tip)
- Stack store-specific offers ("Deals and gift cards" section) with the Chase promo
- Strategy: subtotal ~$20 on stuff already on shopping list (groceries, household)
- Alcohol workaround killed (state limits)
- Behavior cadence:
  - Days 1–23: silent
  - Days 24–29: remind once
  - Days 30–31: urgent
- If user ignored 3 consecutive months: suppress entirely until last 5 days

### 7. StubHub (semi-annual)

- **Trigger date is purchase posting date, not event date** → can buy December tickets for events 6 months out
- Activation required (Chase app → "$300 StubHub Credit" tile)
- Taxes & fees included in $150 calc
- Gift cards excluded as triggers, but: buy StubHub gift cards on sale → apply to large purchase → pay residual with CSR
- Viagogo (US site only — viagogo.com NOT stubhub.co.uk) works the same
- Behavior cadence:
  - Normal months: silent
  - May, November: light reminder
  - June, December: aggressive
- NYC event candidates: Knicks, Rangers, Yankees, Mets, MSG concerts, Beacon Theatre, Broadway, comedy clubs

### 8. The Edit decision

Recommend ONLY when:
- Hotel stay is 2+ nights
- Property is in Edit collection
- Pay Now (prepaid) rate available
- Total cost ≥ $500 (to capture both stack credits if eligible)

Compare:
- **Direct booking:** 4x pts + elite night credits + status benefits
- **Chase Travel portal:** 8x pts but loses elite credits (some loyalty programs don't credit OTA bookings)
- **The Edit:** $250 statement credit + $100 property credit + breakfast + upgrade + 8x pts + FULL elite night credits

Rule: if user is chasing hotel status, Edit is the only "best of both" option. Otherwise compare expected value per stay.

Include Points Boost angle (2 cpp on Edit) if user has UR balance to redeem.

### 9. Lounges (NYC focus)

**JFK Terminal 4 → Chase Sapphire Lounge:**
- Recommend BUT explicit "join digital waitlist immediately, then explore" — wait can be 1 hour+
- Arrive 2.5–3 hours before flight
- Backups: Primeclass, KAL (lower quality), Capital One Lounge (requires C1 card)

**LGA Terminal B → Chase Sapphire Lounge:**
- HIGH priority — widely rated best Priority Pass lounge in US
- 21,800 sqft, 2 floors, complimentary 20-min facials, full bar, showers
- 4:30am–9:30pm, 3-hour pre-flight window
- Departures-only
- Eligible airlines T-B: American, JetBlue, Air Canada, Southwest, United
- Suggest spa appointment on arrival

**Other airports:**
- Identify airport and terminal
- Surface ONE best lounge, not a list
- DFW + LAX Sapphire Lounges launching 2026

### 10. Activations

**Permanent activatable perks** (one-time, then track):
- Apple TV+ membership
- Apple Music membership
- IHG One Rewards Platinum status
- Peloton credit
- StubHub credit
- DashPass linkage to Lyft
- Cell phone protection (= phone bill autopay set to CSR)

Behavior:
- On first run: enumerate active vs inactive, push activation for everything inactive ONCE
- After activation: silent
- Re-verify every 90 days; if billing/usage signal broken, re-prompt
- If user explicitly declines an activation, suppress permanently (record in `behavior_overrides`)

**Apple Music caveat:** individual plan only. Family Sharing works for Apple TV+ but NOT Apple Music (cannot upgrade to Family without paying full).

**Peloton hack:** no bike/treadmill needed. Strength+ standalone app at $9.99/mo is fully covered by $10 credit. Net zero cost, useful free fitness app.

**Limited-time perks** (treated separately, urgency curve):
- Whoop Life — expires 5/12/2026. As of today (2026-04-27): 15 days left. Surface ONCE with effort estimate; if declined, suppress. If accepted, treat band as resaleable asset (~$80–120 secondary market) regardless of personal use.
- Instacart $15/mo — ends July 2026. After that, drop entirely.
- $250 select-hotel credit — ends 12/31/2026. Aggressive in Q4.

### 11. Cell phone protection (one-time switch)
If `phone_bill_on_csr = false`, push ONCE to switch phone bill autopay to CSR.
- Value: $1,000/incident protection (passive)
- Effort: low (one autopay change)
- Confidence: high
- After accepted/declined, never re-surface

### 12. Idle cash
If `checking_balance_estimate > cash_buffer_threshold`:
- Surface as a CPC banker question, not as advice
- "Ask CPC banker about better yield options for $X excess"
- Do NOT recommend specific investments

### 13. Points redemption (transfer partner advisor)

For any planned trip evaluate:
- Chase Travel portal (1 cpp baseline OR 1.5 cpp existing CSR transition rate, up to 2 cpp Points Boost on Edit)
- Best transfer partner

**Transfer sweet spots:**
| Partner | Best for | Value |
|---|---|---|
| World of Hyatt | Cat 1-4 hotels, Ziva/Zilara all-inclusive | 4.8–6.2 cpp / 3+ cpp |
| Air Canada Aeroplan | Star Alliance premium, EU stopovers | 5–6 cpp |
| Virgin Atlantic Flying Club | Delta One, ANA First | 5.5–6.5 cpp |
| United MileagePlus | Star Alliance, low fees, good search | 1.5–2 cpp |
| Iberia Avios | BOS/JFK → MAD off-peak | 4.7 cpp |

**Avoid transfers to:** Marriott Bonvoy, Wyndham (sub-1 cpp typical, only use during transfer bonuses)

**WARN — Hyatt May 2026 chart change:** peak pricing redemptions get more expensive. Today is 2026-04-27. **Less than 1 month**. If user has Hyatt trips planned, surface as TOP-3 action immediately.

**Transfer bonus monitoring:** Chase typically runs 20–30% airline / 50–80% hotel bonuses. Surface active ones that match user's known plans.

### 14. Trip detection

Trip data sources (in priority order):
1. Manual entry (user provides trip details)
2. Calendar integration (read-only, optional)
3. Transaction-based inference (airline ticket purchase → flag for confirmation)

Confidence handling:
- Manual: confidence 1.0
- Calendar event with travel keywords: 0.7
- Transaction inference: 0.5 — agent asks for confirmation before recommending lounges/Edit/etc.

---

## Computation rules

### "$X on the table" computation

The opening line `You are leaving approximately $X on the table` is computed as:

```
sum of:
  (remaining_unused_credits expiring within 30 days)
  + (estimated_missed_value_last_week)
  + (one-time activation values not yet captured)

where each item is weighted by:
  estimated_capture_probability (defaults: 1.0 for active credits, 0.5 for activations user hasn't actioned)
```

Excludes: limited-time perks user has explicitly declined; perks beyond 30-day horizon; SUB progress.

### Estimated missed value (lookback)

Lookback window: last 7 days from report date.

For each transaction in lookback:
- If a better card existed for that category → missed value = `(better_rate - actual_rate) × amount`
- If a credit could have absorbed it but wasn't applied → missed value = full credit value (capped at remaining balance)
- If lounge skipped (flight detected, no lounge entry recorded) → missed value = $35 default per lounge skip

### Suppression vs "Ignore for now"

| Mechanism | Behavior | Visible to user? |
|---|---|---|
| Suppression | Silent — not in output | No |
| "Ignore for now" section | Listed in report as transparency | Yes — user sees what was deprioritized |

A recommendation is suppressed (silent) when:
- User declined it ≥3 times → `behavior_overrides` entry
- Activation/perk user explicitly opted out of
- Confidence <0.3

A recommendation appears in "Ignore for now" when:
- Score below 30% of top-3 score
- Off-cycle for its urgency curve (eg DoorDash in early month)

---

## UX requirements

### Weekly report format

**Title:** "Weekly Card Maximizer"

**Opening line:** "You are leaving approximately $X on the table." (computed per rules above)

**Sections (fixed order):**
1. Three-clock dashboard (compact)
2. Top 3 actions this week
3. Sign-up bonus pace (only if SUB state ∈ {active, on_pace, behind})
4. Expiring or urgent credits
5. Missed value last week
6. Upcoming travel actions
7. Card choice recommendations (only categories relevant to upcoming spend)
8. Activation status (one-line check; show ONLY top inactive item with most leverage if multiple)
9. Low-value noise to ignore
10. Questions to ask CPC banker (rotating, 2–3 per report)

### Three-clock dashboard layout

```
ANNIVERSARY (resets MM/DD)
  Travel credit: $X / $300

CALENDAR 2026 (resets 1/1/27)
  Edit:         $X / $500
  Select-hotel: $X / $250  [2026 ONLY — expires 12/31]
  Dining H1:    $X / $150  [expires 6/30]
  StubHub H1:   $X / $150  [expires 6/30]

THIS MONTH (resets 1st)
  Lyft:      $X / $10
  DoorDash:  $X / $25  (effective ~$10–15)
  Peloton:   $X / $10
  Instacart: $X / $15  [ends July 2026]
```

### Example weekly output (today: 2026-04-27)

```
Weekly Card Maximizer

You are leaving approximately $186 on the table.

Clocks:
  ANNIVERSARY      Travel: $180 / $300
  CALENDAR 2026    Edit: $0 / $500 | Select-hotel: $0 / $250 [2026 ONLY]
                   Dining H1: $0 / $150 [64d] | StubHub H1: $0 / $150 [64d]
  THIS MONTH       Lyft: $0 / $10 [4d] | DoorDash: $0 / $25 [4d]
                   Peloton: $0 / $10 [4d] | Instacart: $0 / $15 [4d]

Top 3 actions this week:

1. Activate Whoop Life — 15 days left.
   Value: ~$359 (band + 1yr membership; resaleable if unused).
   Effort: low. Confidence: high.
   Next step: Chase app → Card Benefits → Whoop Life → Activate.

2. Use your H1 dining credit before June 30.
   Value: $150. Effort: medium. Confidence: high.
   Next step: book Kabawa or Estela on OpenTable; pay with CSR.

3. Switch phone bill autopay to CSR.
   Value: $1,000/incident protection (one-time, passive).
   Effort: low. Confidence: high.
   Next step: log into carrier, change autopay card.

Expiring soon (next 30d):
- Whoop Life perk: 15d (limited-time)
- Lyft / DoorDash / Peloton / Instacart monthly: 4d
- Hyatt May 2026 chart change in <30d → if any Hyatt trip planned, lock now

Missed last week:
- 3 Uber rides while $10 Lyft credit unused: ~$18 missed
- (no other detected misses)

Upcoming travel:
- None in calendar.

Card choice this week:
- Rideshare: Lyft (set CSR direct in app, NOT Apple Pay)
- Dining: CSR
- Non-category until SUB clears: CSR

Activation status:
- ✗ Whoop, Peloton, IHG Platinum, StubHub
- Top action: Whoop (deadline-driven). Then batch the others next week.

Ignore for now:
- DoorDash credits (early-cycle period, low urgency)
- The Edit / select-hotel push (no 2+ night stay planned)

Questions for CPC this month:
- Any current retention offer on my CSR?
- Best yield option for $X excess in checking?
- Am I eligible above 5/24 for any Chase business card?
```

### Tone
- Direct, simple, practical
- No fluff
- No "maybe you could"
- Give decisions

---

## Interaction modes

### 1. Weekly push
Format above. Default cadence: Monday 8am NYC.

### 2. Purchase advisor
"Which card should I use for this $X purchase at Y?"
→ One recommendation, 1–2 sentences, with reason.

### 3. Trip optimizer
User gives trip (dates, origin, destination, hotel preference).
Agent optimizes:
- Flight booking method (direct vs portal vs partner transfer)
- Hotel booking method (direct vs Chase Travel vs Edit; check stack eligibility — run decision tree from rule 2)
- Lounge plan per airport/terminal
- Rideshare plan
- Dining credit opportunities at destination
- Travel insurance reminder if booked on CSR

### 4. End-of-month sweep
Last 5 days of month. Focus only on monthly credits: Lyft, DoorDash, Peloton, Instacart.

### 5. Half-year sweep
June 15, December 15. Focus on dining + StubHub.

### 6. Redemption advisor
User has X UR points and wants Y trip. Compare:
- Chase Travel portal (with/without Points Boost)
- Best transfer partner (with current transfer bonuses if active)
- Recommend one path with cpp value and effort tradeoff

### 7. Status check / activation audit
On-demand: "what activations am I missing?"
Returns: list of inactive perks with one-click steps and current values.

---

## First-run / onboarding

When agent runs first time:
1. Collect manual config (see fields below)
2. Display three-clock dashboard with current zero state
3. Run activation audit — list every inactive perk with leverage estimate
4. Compute first weekly report
5. **Warm-up rule**: weeks 1–2 do NOT apply behavior pattern inference (insufficient data). Stick to baseline recommendations until ≥4 data points within 60-day window.

---

## Data needed (input sources)

### Manual config (one-time, then persist)

| Field | Type | Purpose |
|---|---|---|
| `card_open_date` | date | Anniversary clock |
| `sub_start_date` | date or null | SUB tracking |
| `sub_spend_to_date` | dollars | SUB tracking |
| `sub_state` | enum | inactive / active / on_pace / behind / cleared / archived |
| `cash_buffer_threshold` | dollars | CPC idle-cash trigger |
| `checking_balance_estimate` | dollars | CPC idle-cash trigger |
| `default_airports` | list | Lounge recommendations |
| `phone_bill_on_csr` | bool | Cell phone protection |
| `activations` | dict | per-perk {active: bool, last_verified: date} |
| `home_city` | string | Default "NYC" |
| `family_sharing_setup` | bool | Apple TV+ recommendation framing |
| `cpc_active` | bool | Card-of-record advisor |
| `current_5_24_count` | int | CPC card-add suggestions |
| `behavior_overrides` | list | `{perk: string, reason: string, suppress_until: date}` |
| `loyalty_ids` | dict | `{hyatt, ihg, united, aeroplan, ...}` optional |
| `pet_categories_blocked` | list | User-declared "I don't use this" perks |

### Recurring inputs

- Transactions (CSV import or manual entry; minimum: date, amount, merchant, category, card)
- Trip plans (manual / calendar / transaction-inferred)
- Anniversary or calendar reset confirmations

### Optional inputs

- Lyft / DoorDash / Peloton last-used timestamps
- StubHub gift card balance
- Active Chase transfer bonus list (manually entered or scraped)

---

## Notification rules

| Event | Cadence |
|---|---|
| Weekly report | Monday 8am NYC |
| Monthly sweep | 5 days before end of month |
| Half-year sweep | June 15, December 15 |
| Anniversary alert | 60 days before reset |
| SUB pacing alert | Weekly until cleared |
| Expiry alert | 7 days, 2 days before any credit deadline |
| Activation re-verify | Every 90 days for active subscriptions |
| Limited-time perk expiry | Daily reminder in last 7 days |
| Hyatt chart change | One-time alert in April 2026, with reminder 7 days out |

---

## Privacy constraints

- All transaction data stays local
- No transmission of full account numbers, balances, or PII outside the agent
- CPC banker conversations are user-driven; agent provides questions, not transcripts
- No investment advice
- No tax advice
- User-provided loyalty IDs stored locally only

---

## Edge cases

1. User cancels Edit booking → credit reverses → flag as "needs re-use"
2. Travel credit purchase returned (any time) → reverses, restore balance
3. Apple subscription auto-suspends on activation → don't double-charge
4. DashPass linkage breaks when Lyft default card changes → re-verify on next month
5. Sapphire Lounge waitlist text doesn't arrive → fallback plan ready (other PP lounges)
6. StubHub purchase posts in next year → counts against next year's credit
7. Chase Travel listing bugs (eg Omni in early 2026) → verify property availability before recommending
8. **Hyatt May 2026 award chart change** → today + 4 days; surface NOW
9. Transfer partners require 1,000-point increments → round expectations
10. 5/24 status changes silently as cards age out → user-confirmed only
11. Card cancellation within 90 days reverses received credits
12. Authorized user spend during SUB period — confirm it counted (Chase sometimes lags)
13. Cross-anniversary travel credit edge: purchase posting just after anniversary counts toward NEW year
14. **Whoop Life expires 5/12/2026 — drop reminders after that date**
15. **Instacart credit ends July 2026 — drop after that**
16. **Existing-CSR 1.5 cpp transition sunsets 10/26/2027** — surface as advance warning starting mid-2027
17. JPMPC upsell — flag the new <$750k fee if user gets pitched
18. Pop-up jail / 2/30 rule / 5/24 — for CPC card-add suggestions, factor in user's status
19. Family Sharing for Apple TV+ works; for Apple Music doesn't — clarify when surfacing
20. Tiebreaker: equal priority scores → closer deadline wins, then higher value, then lower effort
21. SUB cleared but transactions still posting — agent should keep counting until 95-day mark in case of reversal
22. User on a 5+ night stay where Edit credit + select-hotel both apply — agent recommends booking 2 separate 2-night reservations to capture full $500 Edit, NOT one 4-night
23. User books a stay then changes dates (modification) — credit may reverse and re-apply; flag for verification
24. Anniversary credit balance edge: travel transactions in same billing cycle as anniversary may straddle — check posting date carefully

---

## Scoring model for recommendations

Each recommendation scored on 4 axes:

- **Value ($)** — estimated dollar capture if user takes the action
- **Urgency (0–1)** — proximity to deadline, expiry, or pace miss (per behavior rule 6)
- **Effort weight** — low=1, med=2, high=4
- **Confidence (0–1)** — how certain the value materializes

**Composite priority:**
```
priority = (value × urgency × confidence) / effort_weight
```

**Confidence reference values:**
- 1.0: hard credit deadline (use it or lose it)
- 0.9: activation that unlocks tracked future value (IHG Platinum, cell phone protection)
- 0.7: behavior change recommendation (Lyft vs Uber)
- 0.5: partner transfer recommendation (depends on availability)
- 0.3: speculative suggestion (DoorDash credit user historically ignores)

**Tiebreaker order** (when scores equal):
1. Closer deadline wins
2. Higher absolute value wins
3. Lower effort wins

**Top-3 selection:**
- Sort by priority descending
- Take top 3
- If item below 30% of top-1 score, exclude (move to "Ignore for now")

**Suppression rules:**
- User ignored a recommendation 3 weeks in a row → drop urgency by 50% next week
- User explicitly declined a perk → suppress permanently (`behavior_overrides`)
- User activated an item → silent until next 90-day verify cycle
- Confidence <0.3 → suppress (do not even show in "Ignore for now")

---

## Success criteria

After 12 months, the agent succeeded if:
- User captured ≥$795 of perks (annual fee covered) — minimum bar
- Stretch: ≥$1,500 captured
- Zero credits expired unused that user could have used
- Zero "wait, I didn't know that perk existed" moments
- SUB cleared on time (if applicable)
- Hotel triple-stack triggered at least once if user traveled ≥1 night-stay-eligible trip in 2026

---

## Architecture summary

Detailed in `ARCHITECTURE.md`. Resolved decisions:

- **Ingestion**: chrome-agent + CDP attached to user's logged-in Chrome profile. LLM reads pages semantically, no DOM parser.
- **Storage**: local SQLite + snapshot folder + report archive
- **Surfaces**: Dashboard (primary, localhost:7777) + CLI (`chase-agent`) + optional WhatsApp Web push (via chrome-agent)
- **Trip detection**: calendar read-only OAuth + transaction inference, with confidence scoring
- **Update cadence**: 2x/day scrape (8h, 20h NYC) for dashboard + activity; weekly for rewards/offers
- **LLM**: Haiku 4.5 daily + Sonnet 4.6 for advisor modes; prompt caching enabled
- **Cost**: ~$2/month
- **Action capability**: phased — read-only first month, action mode (activations, bookings) gated behind explicit consent

## Resolved architecture decisions

All settled in `ARCHITECTURE.md`:
- Onboarding: CLI prompts
- Behavior overrides: CLI commands (`chase-agent suppress <perk>`)
- Daemon: Python
- Multi-account: out of scope v1
- Reactive mode: ON by default with rate-limits (max 2/day, $5 floor, quiet hours 22h–8h)
- Chrome: dedicated profile via `chrome-agent --browser chase --copy-cookies --stealth`

---

## Deliverables (next phase, before code)

- [ ] User stories
- [ ] Behavior rules (refined from this draft)
- [ ] Recommendation types catalog
- [ ] Weekly report UX (final mock with 5+ scenarios)
- [ ] Notification rules (final)
- [ ] Data model (schema-free, just fields)
- [ ] Privacy constraints (confirmed)
- [ ] Example outputs (5+ scenarios)
- [ ] Edge cases (refined)
- [ ] Manual config fields (final)
- [ ] Scoring model (validated against worked examples)

After confirmation: implementation plan, then code.
