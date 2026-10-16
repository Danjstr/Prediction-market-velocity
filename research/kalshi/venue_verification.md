# Kalshi venue verification: Phase 1 batch 2 summary

**Status:** research record for Phase 1 batch 2 (`phase1/kalshi-venue-verification`). Not a gate record, not an owner decision, and not an approved requirement.

**Sources:** official Kalshi documentation at `docs.kalshi.com`, retrieved 2026-10-15 (UTC) under AR-1. Every URL, retrieval time, and SHA-256 is in `research/sources.md`. Spec versions: `openapi.yaml` 3.34.0, `asyncapi.yaml` 2.0.0.

**Not retrieved:** `kalshi.com` (terms, Developer Agreement, fee-schedule PDF, contract pages). It answered HTTP 429 with a Vercel bot challenge, which was not circumvented. See AR-3 in `docs/phase1.md`.

**No real market observation was used.** No Kalshi API host was contacted. Example payloads in the documentation are illustrations only.

**Detailed records:**
- `research/kalshi/api_documentation_findings.md`: the API / Execution field-level note. Every fact is tagged VERIFIED, UNRESOLVED, INFERENCE, or CONFLICT, with URL and quote. It also lists unresolved items U1–U25.
- `research/kalshi/statistician_review.md`: the development Statistician's methodology review, covering settlement, labels, point-in-time metadata, leakage, and split, purge, and embargo. It is self-review, not independent audit.
- `research/kalshi/red_team_review.md`: the Reliability / Red-Team fail-closed review of this batch.

"Verified" here always means **stated in official documentation**. Nothing is verified by test, demo, or recorded data. Documentation can be stale, internally inconsistent (several conflicts are listed below), or wrong, and it is never a contract rule.

---

## 1. Verified facts (documentation level)

### 1.1 Environments, access, authentication

| Fact | Source |
|---|---|
| Production REST is `https://external-api.kalshi.com/trade-api/v2` (also `api.elections.kalshi.com`). Production WS is `wss://external-api-ws.kalshi.com/trade-api/ws/v2`. Demo uses `external-api.demo.kalshi.co` and `demo-api.kalshi.co`. | `getting_started/api_environments.md` |
| Demo uses mock funds, and demo and production credentials are separate. "The price and behavior of markets in the demo environment may not be reflective of those in real markets." | `getting_started/demo_env.md` |
| REST market-data reads need **no authentication**: markets, events, series, order book, trades, candlesticks, fee changes, exchange status and schedule, and the public historical endpoints. | `openapi.yaml` (no `security` on those operations); `getting_started/orderbook_responses.md`; `getting_started/quick_start_market_data.md` |
| The **WebSocket handshake always requires a signed API key**, even for public channels. `orderbook_delta` is classed as a "private" channel. The changelog (label date 2026-07-23) states that subaccount-restricted keys still receive the full book. Access with a read-only key is unverified (UR-9). Own-order annotation fields can appear on the stream. | `websockets/websocket-connection.md`; `getting_started/quick_start_websockets.md`; changelog 2026-07-23 |
| API key scopes include `read` and `write` and narrower children. **No market-data-only scope exists.** A `read` key can also read portfolio, orders, fills, and positions. | `openapi.yaml#/components/schemas/ApiKeyScope` |
| Key types are Ed25519 or RSA-2048 (RSA-PSS SHA-256). Requests are signed over timestamp, method, and path without the query string. | `getting_started/api_keys.md`; `getting_started/api_environments.md` |
| "By continuing to use or access Kalshi's API, you are agreeing to be bound to our Developer Agreement" (`https://kalshi.com/developer-agreement`). | `welcome/index.md` |
| CF Benchmarks REST passthrough: requires authentication and "the appropriate entitlement", and costs 50 read tokens. The `pyth_value` feed (which includes gold indices) costs "$1,000/month". | `cfbenchmarks/rest-passthrough.md`; `websockets/pyth-value.md` |

### 1.2 Market structure, lifecycle, settlement

| Fact | Source |
|---|---|
| Statuses: `initialized`, `active`, `inactive`, `closed`, `determined`, `disputed`, `amended`, `finalized`. | `getting_started/market_lifecycle.md`; `openapi.yaml` Market |
| `close_time` "May be moved earlier if `can_close_early` is true". A closed market can be **reopened** (`close_date_updated`, then `activated`). | `getting_started/market_lifecycle.md` |
| Opening at `open_time` and closing at `close_time` emit **no WebSocket event**. | same |
| `disputed` and `amended` have **no WebSocket event type**. Amendment restarts the settlement timer. REST status shows them. FIX was not reviewed for these states. | `asyncapi.yaml` lifecycle `event_type` enum; `getting_started/market_lifecycle.md` |
| `result` ∈ {`yes`, `no`, `scalar`, `""`}. There is **no `void` value**. | `openapi.yaml` Market |
| After determination, a settlement timer (`settlement_timer_seconds`) runs before `finalized`. "Timing can vary based on market type, data source availability, and manual review requirements." | `getting_started/market_lifecycle.md`; `getting_started/market_settlement.md` |
| `metadata_updated` can change `floor_strike`, `cap_strike`, `strike_type`, `custom_strike`, and `yes_sub_title` of a market under the same ticker. The docs do not restrict this to live markets. Its fields are optional, and whether an absent field means "unchanged" or "cleared" is not stated. Per the changelog, some strike changes were not emitted before 2026-06-18 (label date). | `asyncapi.yaml#/components/schemas/marketMetadataUpdatedPayload`; changelog 2026-06-18 |
| `is_provisional` markets "may be removed after determination if there is no activity on it". | `openapi.yaml` Market |
| Weekly maintenance: every **Thursday 03:00–05:00 ET**, with a trading pause. Clients "should be prepared for session disconnections": possible, not guaranteed. The window is in ET, so its UTC position moves with DST. Exchange pauses outside that window mean an outage. | `getting_started/maintenance_and_pauses.md` |
| New Crypto and Commodities events are on exchange shard 2. The top-level `GET /exchange/status` fields "reflect the default exchange index (0)". Per-shard status is in `exchange_index_statuses`. | `getting_started/exchange_sharding.md`; `openapi.yaml` ExchangeStatus |
| Series carry `settlement_sources`, `contract_url` (the original filing), and `contract_terms_url` (the **current** terms). "Methodology is defined in the rulebook." | `openapi.yaml` Series |

### 1.3 Fees

| Fact | Source |
|---|---|
| Series `fee_type` ∈ {`quadratic`, `quadratic_with_maker_fees`, `quadratic_with_combo_maker_fees`, `flat`}, plus `fee_multiplier`. The formulas live in `https://kalshi.com/docs/kalshi-fee-schedule.pdf`. | `openapi.yaml` Series, FeeType |
| Events may carry `fee_type_override` and `fee_multiplier_override`, which take precedence over the series fee. A null override clears it. | `openapi.yaml` EventData, EventFeeChange |
| Fee changes are published with `scheduled_ts` (effective time) through `GET /series/fee_changes` (with `show_historical`) and `GET /events/fee_changes`. The WS `event_fee_update` carries **no effective time**. No source carries an announcement time. | `openapi.yaml`; `asyncapi.yaml` eventFeeUpdatePayload |
| Fee rounding: the trade fee is rounded up to $0.000001. A rounding fee restores the member's balance precision ($0.0001 direct, $0.01 non-direct). A per-order accumulator rebates overpayment, and the net fee is ≥ 0. | `getting_started/fee_rounding.md` |
| Settlement fees are zero for simple yes/no determinations. | `getting_started/market_settlement.md` |

### 1.4 Market data: REST and WebSocket

| Fact | Source |
|---|---|
| Prices are dollar strings and counts are fixed-point strings (fractional contracts). The valid price grid comes from `price_ranges`, which can change during a market's life. | `getting_started/fixed_point_migration.md`; changelog 2026-07-23 |
| The REST order book returns **bids only** (YES bids and NO bids). A NO bid at Y is a YES ask at 1 − Y. **It has no timestamp and no sequence number.** | `getting_started/orderbook_responses.md`; `openapi.yaml` GetMarketOrderbookResponse |
| WS `orderbook_delta` first sends `orderbook_snapshot`, then `orderbook_delta` messages (`price_dollars`, `delta_fp`, `side`). Both carry `sid` and `seq`. `seq`: "Sequential number that should be checked if you want to guarantee you received all the messages. Used for snapshot/delta consistency". | `websockets/orderbook-updates.md`; `asyncapi.yaml` |
| The `ticker` channel has **no `seq`**, so gaps in it cannot be detected. | `asyncapi.yaml#/components/schemas/tickerPayload` |
| Channel errors 10 (channel error) and 25 (subscription buffer overflow) are **terminal**: the client must resubscribe. | `asyncapi.yaml` info "Terminal Errors"; `getting_started/quick_start_websockets.md` |
| Server Ping every 10 s with body `heartbeat`. | `websockets/connection-keep-alive.md` |
| `use_yes_price` (orderbook channel): defaults to `false` (no-leg pricing for no-side levels). The default "will be flipped to `true` in a future release", with no date announced. | `websockets/websocket-connection.md`; `getting_started/order_direction.md` |
| **API versioning was removed.** There is no runtime version signal, so schema changes are detectable only by strict validation. | changelog 2025-07-29 |

### 1.5 Timestamps

| Field | Meaning (as documented) |
|---|---|
| `sending_ts_ms` (WS messages) | ms; "when Kalshi queued this message at the network layer". **Optional in every schema**, while the changelog says messages "now include" it (a conflict). Absence is flagged, not fatal. Changelog label date 2026-10-01; effective date unverified. |
| `orderbook_delta.ts_ms` (optional) | ms; "when the orderbook change was recorded" |
| `ticker.ts_ms`, `trade.ts_ms` | ms. Changelog label date 2026-04-15 (effective date unverified). Earlier captures may have seconds or RFC3339 only. |
| Lifecycle `open_ts`, `close_ts`, `determination_ts`, `settled_ts` | **seconds** |
| `orderbook_snapshot` | **no event timestamp** |
| REST `date-time` fields | OpenAPI `date-time`. The timezone and precision are not stated. |
| `cfbenchmarks_value_5hz` / `pyth_value` | `source_ts_ms` (upstream) and `received_at` (Kalshi receipt) |
| Exchange schedule | "All times are expressed in ET." |

### 1.6 Rate limits and historical data

| Fact | Source |
|---|---|
| Separate Read and Write token buckets. The default cost is 10 tokens. Basic tier: Read 200/s, Write 100/s. Higher tiers are tabled. A 429 carries no `Retry-After`. | `getting_started/rate_limits.md` |
| "Every **authenticated** request costs tokens." Limits for unauthenticated reads are not documented. | same |
| Data is split into live and historical tiers. Cutoffs are per data type and "advancing forward over time". | `getting_started/historical_data.md` |
| Historical endpoints: markets, market candlesticks, and trades (public); fills, orders, and positions (authenticated). **No historical order-book endpoint exists.** | same; `openapi.yaml` paths |
| Candlestick periods are 1, 60, or 1440 minutes, so **1 minute is the finest**. The historical candle schema differs from the live one. | `openapi.yaml` candlestick paths and schemas |
| Retention depth (earliest available date) is **not stated**. | — |

### 1.7 BTC and gold: what the documentation does and does not show

- `KXBTC15M` appears only as an example ticker and in a changelog sentence (2026-07-30: event live data serves "crypto price charts (e.g. `KXBTC15M` events)"). Event `product_metadata.cadence` can be `fifteen_min`. **That the series currently lists markets, and its rules, are not verified.**
- The `cfbenchmarks_value` channel computes `last_60s_windowed_average_15min` over `(quarter_close_ts_ms − 60000, quarter_close_ts_ms]` in the final minute before each quarter-hour. **This is a feed-field definition, not a contract rule.** No document ties it to any contract's settlement.
- **The documentation does not document any gold event-contract series; existence is UNRESOLVED.** Gold appears as Pyth reference feeds (paid) and as Margin perpetual futures, which are a different instrument and outside the approved scope. The docs do reference Commodities events (shard 2) and "commodity price timeseries" live data (changelog label date 2026-07-30).

---

## 2. Unresolved facts

Detailed list: `research/kalshi/api_documentation_findings.md` §13 (U1–U25). The items that block real work:

| # | Unresolved | Blocks |
|---|---|---|
| UR-1 | **Terms, Developer Agreement, permitted automated use, and data storage or redistribution rights.** Not retrievable (AR-3). | F-16, any API use (the welcome page says use binds the user to the Developer Agreement) |
| UR-2 | **Account and jurisdiction eligibility** for the owner's intended use. Not documented on docs.kalshi.com. | F-16, Gate 1 |
| UR-3 | **Fee rates and formulas** for each `fee_type`, and their effective-date history. | Any economics, F-17 |
| UR-4 | **BTC contract rules**: series existence, reference instant or averaging window, settlement source (BRTI?), strike construction and timing, tie handling (`greater` vs `greater_or_equal`), void or cancel treatment, settlement timer. | Kalshi `ContractSpec` builder, labels |
| UR-5 | **Gold event-contract existence** at all, and at 15–60 minute cadence. | Approved scope (see §5, Escalation E-1) |
| UR-6 | **`seq` scope** (per subscription, per market, or per connection), start value, reset on resubscribe, whether control replies (`ok`, `error`, `get_snapshot`) consume sequence numbers, and the gap or resync procedure. | Book parser |
| UR-7 | **Whether `delta_fp` is a relative change or an absolute level.** Strong inference: relative (named "delta"; documented examples are negative). Never stated. Behavior at zero is undocumented. | Book parser |
| UR-8 | Cross-channel ordering, duplicate delivery, and conflation. | Book and trade alignment |
| UR-9 | Whether a `read`-only key can open the WS session and subscribe to `orderbook_delta` and the CF Benchmarks channels, and whether those need an entitlement. | Credential design (F-03) |
| UR-10 | Unauthenticated REST rate limits and actual market-data endpoint costs. | Collector design |
| UR-11 | Historical retention depth and cutoff lag. | Gate 1 sufficiency |
| UR-12 | Demo scope: which series and channels exist in demo. | Demo-based tests |
| UR-13 | Whether `result` changes on amendment, and whether a second `determined` event is emitted. | Labels |
| UR-14 | REST `date-time` timezone and precision. | Parser |

**Documentation conflicts found** (detail in the API note):
- REST order-book sort order;
- burst capacity (2 s vs 3 s);
- the `taker_side` removal date;
- the lifecycle event list (guide vs schema);
- the `window_end_ts_exclusive` naming vs "close tick is included";
- the error-code tables;
- the pagination end signal;
- `sending_ts_ms` optional in schema vs "now include";
- settlement floors "not live yet" vs fields added 2026-10-01;
- category-to-shard ambiguity for series with several categories;
- the AsyncAPI's own past inaccuracy (corrected 2026-09-10/17);
- changelog label dates vs effective dates (every changelog date here is a label date).

Each is treated as unresolved, and the parser must fail closed on them.

---

## 3. Project assumptions and recommendations (not approved)

Everything in this section is a recommendation from this batch. None of it is an adopted rule.

1. **Availability time is PMV receipt time only.** Venue timestamps (`ts_ms`, `sending_ts_ms`, `created_time`, `determination_ts`, and so on) are for latency measurement, diagnostics, and label-side window alignment, never for feature cutoffs. This is consistent with F-08 and `docs/market_data.md`.
2. **Book integrity is fail-closed** until UR-6 and UR-7 are settled by a recorded test:
   - one book per (connection, `sid`, market);
   - any `seq` discontinuity invalidates every book on that `sid`;
   - recovery is not a `get_snapshot` rebase. Unsubscribe and resubscribe counts as recovery only with a confirmed `unsubscribed`, a new `sid`, and a new snapshot for every market. Otherwise reconnect. Subscribe is idempotent (changelog 2025-09-25), so re-subscribing the same tickers may do nothing;
   - control messages (`unsubscribed`, optionally `ok`, subscription-scoped `error`) carry `seq` and must be included in gap accounting;
   - the existing book engine must not treat a `get_snapshot` reply as recovery (Red-Team RT-B2-03);
   - a negative size, a crossed book, or an off-grid price is an integrity fault;
   - `ticker` is never book truth.
3. **Relative deltas must not be fed to `BookDelta`.** `BookDelta.new_quantity` is an absolute replacement (`docs/market_data.md`). The Red-Team prefers a relative-delta variant inside `books`, under the same fault model, over a stateful conversion in the normalizer (RT-B2-04). The parser batch decides after UR-7 is tested. The test must be a differential two-connection comparison plus invariants, not a comparison against `get_snapshot`. Demo results cannot close UR-6 or UR-7 for production.
4. **Set `use_yes_price` explicitly** and record it in raw capture metadata for each subscription.
5. **Strict schema validation replaces version checks.** Pin the schemas to the hashes recorded in `research/sources.md`. Unknown message types, enum values, or missing required fields fail closed. Unknown optional fields are kept in raw form and flagged.
6. **Lifecycle:** derive open and close from `open_time`/`close_time` on a synchronized clock. Poll REST until `finalized` to catch `disputed` and `amended`. Gate trading status on the `exchange_index_statuses` entry matching each market's own `exchange_index`. An absent breakdown or unknown index is UNKNOWN (fail closed). Never use the top-level fields, which reflect shard 0, and never hard-code shard 2. A lifecycle-stream gap must make `status_as_of` UNKNOWN until REST reconciliation (RT-B2-06).
7. **Historical archive data is a pilot or discovery source at most.** It has no book, no metadata history, no receipt times, and an activity-selected universe. After-cost EV evidence must come from live capture (Statistician §5). This strengthens the case for F-06.
8. **Reading archived rows needs an owner-approved availability rule.** Either forbid them, or define a flagged synthetic availability `venue_ts + L` with `L` fixed before outcome inspection. Either is a methodology change.
9. **Raw lifecycle frames are outcome-bearing.** `market_lifecycle_v2` cannot be filtered by market, and `determined` carries `result` for every Kalshi market. Under F-08, raw lifecycle captures should be classified as label-channel material and catalogued in the guard (RT-B2-10, owner decision).
10. **Equivalent observables.** CF Benchmarks BRTI history (passthrough), the `cfbenchmarks_value` channels, Pyth gold feeds, and event `live_data` are equivalent observables for protected BTC and gold windows. They must be catalogued in the data-access guard before a real protected scope exists.

---

## 4. Point-in-time contract metadata and versioning: options for the owner (blocking, not decided)

**Problem (batch 1, `docs/market_data.md` review m4 and Statistician M1, now confirmed by documentation).** These Kalshi fields change during a market's life:
- `close_time`: early close, extension, and reopen;
- strikes and `yes_sub_title` (`metadata_updated`);
- the tick grid (`price_level_structure_updated`);
- event and series fees, with effective times but no announcement times;
- trading status;
- the series' "current" terms.

`result`, `settlement_value`, `expiration_value`, the realized close, and the final volume are known only after the fact. A spec built from metadata fetched later would leak the outcome into `time_remaining`, moneyness, eligibility, and costs (Statistician §2.2, L1–L6).

**Options** (detail and collector requirements in `research/kalshi/statistician_review.md` §2.3):

| Option | Summary | Main strength | Main weakness |
|---|---|---|---|
| A | Stable semantic key plus **bitemporal** spec versions (`effective_from` from venue, `known_at` = PMV receipt) | Simple lookup; separates the economics time from the knowledge time | A derived table; every consumer carries a version ID; a strike change under the same key |
| B | **Append-only metadata log** in the existing `ObservationLog`, keyed by receipt time. The spec at *t* is a deterministic fold over the `AsOfView` | Reuses the tested point-in-time machinery; replay proves leakage safety | The fold is safety-critical; outcome fields in REST snapshots must be quarantined to the label channel |
| C | **Snapshot per REST poll**; the latest snapshot received by *t* | Simplest collector | Poll-interval resolution; misses changes near close, where it matters most |
| D | **Hybrid:** B as source of truth, A as a materialized view (with a parity test), C for reconciliation | Most auditable; catches missed WS events, including disputes | Most engineering |

**Separate identity question.** Should a strike change keep the same identity, with a new version and a regime flag, or create a new identity? The Statistician leans toward same identity plus a new version. Separately, should `verification` and fee data leave the `spec_key` hash (batch 1 recommendation m4)?

**Statistician's stated preference:** D, or B if engineering budget is tight. It is labeled a recommendation, not a decision. Development-Statistician self-review; an Independent Statistical Auditor must review whichever option is adopted before Gate 2.

**This batch does not choose or implement any option.** The Kalshi `ContractSpec` builder and the real-data label pipeline stay blocked until the owner decides **and** UR-4 (contract rules) is verified.

---

## 5. F-16 eligibility findings

**What the documentation establishes:**
- API use binds the user to the Kalshi Developer Agreement. Its content was not retrieved.
- Real-time order-book data needs a signed API key, so it needs an account. There is no market-data-only key scope.
- Unauthenticated REST market-data reads exist. Whether the Developer Agreement or terms permit automated collection, storage, and research use of those reads is **unknown**.
- An API key "location attestation" expiry limits trading in Sports, Elections, and Entertainment (changelog 2026-08-16). Its effect on Crypto and Commodities is not stated.
- The docs distinguish Direct members from FCM-cleared members, for example in balance precision and settlement-floor treatment. Which kind of account the owner would hold is an owner fact.
- Location attestation exists for API keys (`api_key_region_expiration_ts`). This implies location-dependent permissions. The rules behind it are not documented on docs.kalshi.com.

**What remains unresolved and requires owner judgment:**
1. **Jurisdiction and account eligibility** of the owner (residency, state restrictions, KYC) for Kalshi event contracts, and specifically for Crypto and Commodities series. Not documented on docs.kalshi.com. It needs kalshi.com terms or member agreement, help.kalshi.com, or the owner's own account status.
2. **Permitted use.** Is automated data collection, storage, and model research permitted under the Developer Agreement? Is automated trading permitted for the owner's account type?
3. **Credential.** WS book capture requires creating a Kalshi API key. That is a venue credential: F-03 (credential isolation), F-16, and an explicit owner decision are all required first. The narrowest documented option is a `read`-scope key, possibly subaccount-restricted. It still exposes portfolio reads (API / Execution recommendation 7).
4. **Scope (gold).** See Escalation E-1 below.

**F-16 status: OPEN.** This batch provides the documentation facts above. The legal and eligibility determination is the owner's, and needs AR-3 or owner-supplied documents.

---

## 6. Escalations to the owner

- **E-1. Gold scope conflict (blocking for the gold half of the approved scope).**
  - *Current requirement:* initial assets are Bitcoin and gold (CLAUDE.md, PROJECT_BRIEF.md); Polymarket is deferred (D2).
  - *Concern:* no Kalshi gold event-contract series is documented.
  - *Evidence:* §1.7.
  - *Options:*
    - verify gold-series existence through an approved path (AR-3, or a guarded metadata-only series listing once the guard and F-16 allow it);
    - if none exist, proceed BTC-only on Kalshi, with gold deferred to Polymarket or later;
    - or revise scope.
  - Every option other than verification is a **material scope change**. It needs owner approval and a PROJECT_BRIEF.md and CLAUDE.md change. The "gold via Polymarket" option cannot be assessed while D2 keeps Polymarket research outside the current charter.
  - Gold perps are a different instrument; substituting them would be a material change.
  - *Risk of BTC-only:* concentration in one underlying (Phase 4.5 caps bind).
- **E-2. Point-in-time versioning (blocking for the Kalshi spec builder and labels).** See §4.
- **E-3. Market-data credential (blocking for real-time book capture).** See §5 item 3.
- **E-4. Historical-row availability rule (blocking before any archive data trains a model).** See §3 item 8.
- **E-6. Demo environment classification (Red-Team RT-B2-09).** Any demo test needs a demo account and a demo key. AR-1 excludes accounts, D3 excludes credentials of any kind, and it is not recorded whether a demo key counts as "real". The owner should classify demo accounts and keys under F-03 and F-16. A demo test can falsify a semantic but cannot confirm production behavior.
- **E-7. Network egress scope (Red-Team RT-B2-17).** The docs link directly to live API hosts. The owner should confirm the allowlist is exact-host (`docs.kalshi.com`, `kalshi.com`), not `*.kalshi.com`, record AR-1's expiry and revocation, and implement the F-09 denies for the production and demo API hosts. In this batch, `www.kalshi.com` was refused, which is consistent with exact-host rules but does not prove them.
- **E-5. Label timing split (needed at the Phase 2 split freeze).** The Statistician recommends splitting R2's single "label end" into:
  - the rule-defined reference end (`ref_end`), for purge and embargo;
  - the finalization receipt, for walk-forward label availability.

  Scalar or other non-binary results on binary markets become exclusions, never coerced labels.
