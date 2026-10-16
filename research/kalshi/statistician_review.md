# Statistician findings: Kalshi venue verification (Phase 1 batch 2)

Author: development Statistician (fresh session), 2026-10-16. Status: development self-review. This is **not** independent validation (START_HERE.md Gate 2 independence rule). If the owner adopts any option below, the development Statistician has co-authored it and an Independent Statistical Auditor must review it before Gate 2.

Sources: official Kalshi docs retrieved 2026-10-15 (UTC) from `https://docs.kalshi.com/`, with URLs and hashes recorded in `research/sources.md`. No network requests were made for this review. No real market observation was inspected. Example payload values in the docs (tickers, prices, timestamps) are illustrations, not data. `kalshi.com` (terms, fee-schedule PDF, contract rule pages) was **not** reachable, so the actual BTC and gold contract rules, settlement-source methodology, and fee formulas are **unverified** throughout.

> **Errata (Red-Team review, 2026-10-16; see `research/kalshi/red_team_review.md`).** Corrections C7 (delta relativity is INFERENCE), C8 (gold is undocumented, not established absent), and C16 (the m4 split is a separate open decision) are applied in place. Changelog dates are label dates; effective dates are unverified (C10).

Tags:
- **[VERIFIED-BY-DOC]**: stated in the cited official page. Docs can be stale or wrong, and a doc statement is not a contract rule.
- **[UNRESOLVED]**: docs are silent, ambiguous, or the source was unreachable.
- **[PROJECT-ASSUMPTION/RECOMMENDATION]**: my statistical reasoning or proposal. These are not decisions. Owner approval is required for any material change.

Repo context read: `docs/market_data.md` (review m4, M1), `docs/phase1.md` (R1, R2, F-08), `src/pmv/market_data/{contracts,labels,kalshi}.py`, START_HERE.md (Evaluation Cycles, Data and Contract Identity, Phases 1–2), `docs/protected_information.md`.

---

## 0. Headline findings (severity for the project)

| # | Finding | Class | Severity |
|---|---|---|---|
| H1 | The docs define **five distinct "end" times**: `close_time` (mutable), `expected_expiration_time`, `latest_expiration_time`, `determination_ts`, and `settled_ts`/`settlement_ts`. A result can be **disputed and amended** after determination. The label value must be the finalized result, and label availability must be finalization receipt time, not determination. | VERIFIED-BY-DOC + RECOMMENDATION | Blocking for the label parser |
| H2 | The lifecycle WebSocket emits **no `disputed` or `amended` event type**. Re-determination is visible only through REST status (or is undocumented). | VERIFIED-BY-DOC (absence) / UNRESOLVED (behaviour) | Major: the collector must poll REST |
| H3 | `metadata_updated` can change **`floor_strike`, `cap_strike`, `strike_type`, and `custom_strike`** of a live market. The contract question itself can change under the same ticker. | VERIFIED-BY-DOC | Blocking for the M1 spec design |
| H4 | `close_time` can move earlier **and** later. A closed market can **reopen**. Any `time_remaining` built from REST-fetched metadata is a lookahead leak unless the metadata is versioned by receipt time. | VERIFIED-BY-DOC | Blocking (M1, confirmed) |
| H5 | **No historical order book** exists. Historical market data is final-state REST objects, trades, and candles with a 1-minute minimum period. There is no historical lifecycle or metadata-change history, and no PMV receipt time. | VERIFIED-BY-DOC | Major: limits Gate 1 sufficiency |
| H6 | `is_provisional` markets "may be removed after determination if there is no activity on it". The historical universe is **selected on activity**. | VERIFIED-BY-DOC | Major: survivorship and selection bias |
| H7 | The docs do **not document any gold event-contract series**; existence is UNRESOLVED. Gold appears as Pyth reference feeds (paid) and Margin perps; the docs also reference Commodities events (shard 2) and "commodity price timeseries" live data (changelog 2026-07-30). | UNRESOLVED (not documented) | Escalate: scope |
| H8 | The CF Benchmarks quarter-hour final-minute average is a **feed field**. Whether any BTC contract settles on a 60 s average is unverified. If it does, `ContractSpec`'s single `outcome_reference_time` cannot represent the contract. | UNRESOLVED | Blocking for the BTC spec builder |
| H9 | The `seq` scope (per `sid`, per market, or per connection) is **not stated**. The `ticker` channel documents no `seq`. | UNRESOLVED | Major for book validity |

---

## 1. Settlement semantics and label timing

### 1.1 What the docs establish

- **[VERIFIED-BY-DOC] Status machine.** https://docs.kalshi.com/getting_started/market_lifecycle, Statuses table: `initialized`, `active`, `inactive` ("Temporarily deactivated by the exchange. Trading is paused but the market has not closed."), `closed` ("Past `close_time`. No new orders accepted. Awaiting determination."), `determined` ("Result is known. Settlement timer is running."), `disputed` ("Result has been challenged. May be re-determined."), `amended` ("Re-determined after a dispute. Settlement timer restarts."), `finalized` ("Settlement complete. Positions have been paid out. Terminal state.").
- **[VERIFIED-BY-DOC] Settlement timer.** Same page: "A settlement timer then runs for `settlement_timer_seconds` … During this window the market remains at `determined` and the result may be disputed." It continues: "In REST, settled markets end up at `finalized` … and `settlement_ts` is populated."
- **[VERIFIED-BY-DOC] Time fields.** Same page, Time fields table: `close_time` ("When trading stops. May be moved earlier if `can_close_early` is true."), `expected_expiration_time` ("When the outcome is expected to be known."), `latest_expiration_time` ("Latest possible expiration time."), and `expiration_time` ("Deprecated legacy field"). The FAQ adds: "`expected_expiration_time` can be earlier than `close_time`."
- **[VERIFIED-BY-DOC] WS lifecycle event set.** https://docs.kalshi.com/websockets/market-and-event-lifecycle and `asyncapi.yaml`: the event types are `created`, `activated`, `deactivated`, `close_date_updated`, `determined`, `settled`, `metadata_updated`, and `price_level_structure_updated`. There is **no** `disputed` or `amended` event. `determination_ts`, `result`, and `settlement_value` are present "ONLY … when the market is determined". `settled_ts` is present "ONLY … when the market is settled".
- **[VERIFIED-BY-DOC] Result values.** `openapi.yaml`, Market: `result` enum `['yes','no','scalar','']`. There is **no `void` value**. `settlement_value_dollars` is "Only filled after determination". `expiration_value` is "The value that was considered for the settlement".
- **[VERIFIED-BY-DOC] Timing varies.** https://docs.kalshi.com/getting_started/market_settlement: "Markets typically settle shortly after expiration, but timing can vary based on market type, data source availability, and manual review requirements."
- **[VERIFIED-BY-DOC] Settlement floors** are "not live yet" (https://docs.kalshi.com/getting_started/settlement_bounds). `settlement_floor_dollars` can be raised during a market's life, and "In rare cases, Kalshi may lower the settlement floor due to a settlement source correction." This is irrelevant to binary BTC contracts if their `settlement_bounds_type` is `default`, which is **[UNRESOLVED]** per series.

### 1.2 Which time is the label's outcome-reference time

- **[UNRESOLVED]** The instant (or window) at which the reference value is fixed is a contract-rule fact. The docs do not state it for any BTC or gold series, and `kalshi.com` rule pages were unreachable. None of the API time fields is the reference time by definition. `expected_expiration_time` is a forecast. `close_time` is a trading cutoff and is mutable. `occurrence_datetime` ("The recorded datetime when the underlying event occurred, if available") is post-hoc and optional.
- **[PROJECT-ASSUMPTION/RECOMMENDATION] Use four distinct label-side times.** `ContractSpec` currently holds one `outcome_reference_time`. The docs force the label layer to separate:
  1. **Outcome-information time (`ref_end`).** The end of the rule-defined reference instant or window. This is the **purge/leakage** end: after it, the underlying path determines the outcome. It is taken from the verified rule, never from an API field.
  2. **Determination receipt.** PMV receipt of `determined` (`determination_ts` is venue-reported). Provisional only.
  3. **Finalization receipt.** PMV receipt of `settled` (WS) or of REST `finalized` with `settlement_ts`. This is the **label-availability** time for walk-forward retraining and for any simulated "learn from resolved trades" step.
  4. **Amendment.** If a REST poll ever shows `disputed`/`amended`, the label value is the **finalized** result. The superseded determination must be retained as a provenance record, never overwritten.

  `ResolutionRecord` should record which lifecycle stage it came from. `label_for` should, by policy, refuse anything not `finalized`, or accept `determined` only with an explicit, recorded policy. R2's "later of outcome_reference_time and resolution receipt" should be split into these two roles:
  - (1) for the purge and embargo geometry;
  - (3) for label availability in walk-forward.

  Mixing them either over-purges (wastes data) or under-protects (lets a rolling retrain use labels it could not yet have had).
- **[PROJECT-ASSUMPTION/RECOMMENDATION] Scalar results.** `result = 'scalar'` and the absence of `void` mean the project's void handling is unverified. A binary BTC market that settles `scalar`, for example at 0.50, must become a `LabelExclusion` with its own reason, never be coerced to YES or NO. Whether voids or cancellations appear as `scalar` is **[UNRESOLVED]**.

### 1.3 Early close, close-date updates, reopen, pauses, maintenance

- **[VERIFIED-BY-DOC] Close can move either way, and markets can reopen.** Lifecycle page, Explicit transitions: "`closed` → reopened `active`: `close_time` is moved into the future. Events: `close_date_updated`, then `activated`." Also: "Close time updated … This can happen when a market is closed ahead of its scheduled close time, including before determination." Lifecycle WS `close_ts`: "Will be updated in case of early determination markets." `early_close_condition` (openapi Market) is "The condition under which the market can close early". `can_close_early` is included in the `created` event's `additional_metadata` (asyncapi `lifecycleAdditionalMetadata`).
- **[VERIFIED-BY-DOC] Pauses.** `inactive` comes with the `deactivated` and `activated` events. "All resting orders are cancelled on this reactivation." The `is_deactivated` flag "should only be interpreted for an open market".
- **[VERIFIED-BY-DOC] Weekly maintenance.** https://docs.kalshi.com/getting_started/maintenance_and_pauses: "Every **Thursday from 3:00 AM to 5:00 AM ET** … a **trading pause** is in effect." There are also rare exchange pauses, and "If an exchange pause occurs outside the scheduled Thursday window, it indicates a temporary Kalshi Exchange outage." Exchange-level state is in REST `GET /exchange/status` (`trading_active`, `exchange_active`, `exchange_estimated_resume_time`: "not guaranteed and can be extended") and `GET /exchange/schedule` (`maintenance_windows`). **[UNRESOLVED]** No exchange-status WebSocket channel was found in the captured pages.
- **[VERIFIED-BY-DOC] Order rejection after close.** "Once `close_time` passes, all order operations, including cancellations, are rejected with `MARKET_INACTIVE`."

**Implications [PROJECT-ASSUMPTION/RECOMMENDATION]:**

1. **`time_remaining` must be computed from the close time *known at decision*, as received.** Using the realized close (REST after the fact) feeds the outcome of an early-determination process into a first-class feature. For "early determination markets", an early close is itself outcome-informative: it happens *because* the outcome became known. This confirms M1.
2. **Eligibility must not use the realized close.** Excluding decisions in `[realized_close, scheduled_close)` is a future-informed eligibility filter. The honest treatment:
   - keep the decision row;
   - in execution simulation, treat the order as **rejected** (zero fill, zero P&L) when the venue had closed but PMV had not yet received the update;
   - exclude the row only when the `close_date_updated` or status was **received** before the decision (existing `not_open_at_decision` logic).

   This mirrors what live trading would experience.
3. **Reopen.** `status_as_of` must handle `closed → active` after `close_date_updated`. `time_remaining` then jumps upward, and the same market has two disjoint trading windows. Recommendation: version the spec per close-time change (§2), and tally reopened markets as a separate exclusion or regime class until they are understood.
4. **Pauses are not missing at random.** Deactivations probably cluster around volatile or anomalous periods, which is where a velocity edge would live (M4 exclusion ledger). Rows near pause boundaries should be kept in the ledger, and results reported with and without them. After `activated`, the book is reset ("All resting orders are cancelled"). Post-reactivation quotes are a distinct microstructure regime and need a regime flag.
5. **The exchange-wide pause is not a market lifecycle event.** The `not_open_at_decision` exclusion currently keys on per-market status. A Thursday trading pause or an exchange pause may leave market status `active` while trading is impossible (**[UNRESOLVED]** whether markets go `inactive`). The collector must poll `/exchange/status`, and the status-as-of logic must AND the market status with exchange status, both by receipt time. The maintenance window is in ET, so DST applies: compute it from the tz-aware schedule, never a fixed UTC offset.
6. **Maintenance is a deterministic weekly regime.** If 15-minute BTC markets are listed through 03:00–05:00 ET Thursdays (**[UNRESOLVED]**), roughly 8 windows per week are untradable. Exclude them by a pre-registered calendar rule, not ex post.

---

## 2. Point-in-time contract metadata

### 2.1 Fields that can change during a market's life [VERIFIED-BY-DOC unless marked]

| Field | Evidence |
|---|---|
| `close_time` | `close_date_updated` with `close_ts` (lifecycle WS); "May be moved earlier if `can_close_early` is true" (lifecycle page); moved into the future on reopen |
| `strike_type`, `floor_strike`, `cap_strike`, `custom_strike`, `yes_sub_title` | `metadata_updated` payload (asyncapi `marketMetadataUpdatedPayload`): "Updated strike information or yes subtitle" |
| `price_level_structure` (tick sizes) | `price_level_structure_updated` event |
| Status / trading permission | `deactivated`, `activated`; exchange status |
| Event fee override | `event_fee_update` (lifecycle page: "emits `event_fee_update` messages when an event-level fee override is set or cleared"); `GET /events/fee_changes` with `scheduled_ts`; "Event fees are an override layered on top of the parent series' fee structure" |
| Series fee type and multiplier | `GET /series/fee_changes`: `scheduled_ts` ("Timestamp when this fee change is scheduled to take effect"), `show_historical` parameter |
| Market fee waiver | Market `fee_waiver_expiration_time` |
| Series `settlement_sources`, `contract_terms_url`, `fee_type`, `fee_multiplier`, `last_updated_ts` | Series schema: `contract_terms_url` is "the URL to the **current** terms"; `last_updated_ts` is "when this series' metadata was last updated". Only the latest value is exposed. |
| `settlement_floor_dollars` | Can be raised, or lowered after a "settlement source correction" (settlement_bounds page). Not live yet. |
| Market `updated_time` | "Time of the last non-trading metadata update." This is the last one only, not a history. |
| `rules_primary`, `rules_secondary` | **[UNRESOLVED]** They are carried at creation (`created` `additional_metadata` requires them) and are not in the `metadata_updated` payload. Whether they can change, and how a change would be signalled, is undocumented. |

**[VERIFIED-BY-DOC] Learned only after the fact:** `result`, `settlement_value(_dollars)`, `expiration_value`, `determination_ts`, `settled_ts`/`settlement_ts`, `occurrence_datetime`, the realized `close_time`, final `volume_fp`, `open_interest_fp`, `last_price_dollars`, `previous_*` ("a day ago"), and final `status`.

**[VERIFIED-BY-DOC] Fee-change timing gap.** `EventFeeChange` and `SeriesFeeChange` carry `scheduled_ts` (effective time) but **no announcement time**. The `event_fee_update` WS payload carries `sending_ts_ms` but no `scheduled_ts`. **[UNRESOLVED]** It is unclear whether the WS message fires when the override is *set* or when it *takes effect*.

### 2.2 Leakage scenarios if a spec is built from post-hoc metadata [PROJECT-ASSUMPTION/RECOMMENDATION]

- **L1, realized close into `time_remaining`.** This is M1. In early-determination markets it leaks the outcome directly.
- **L2, strike revision.** A spec built from the final `floor_strike`/`cap_strike` makes earlier decision rows answer a question that was not the one trading at the time. Moneyness features (distance to threshold) would be computed against a strike the market did not yet price. If strike revisions correlate with the underlying path, which is plausible if strikes are re-centered, this leaks path information.
- **L3, eligibility on final status.** Filtering the universe by final status, volume, or `is_provisional` survival selects on post-hoc activity.
- **L4, fees.** Using the final fee schedule for decisions mis-states the decision rule. Using the fee *known* at decision for realized P&L mis-states economics. Recommendation: two lookups. The **decision rule** uses the schedule *known by receipt* at decision. **Realized P&L** uses the schedule *effective* at fill time (`scheduled_ts`). Where they differ, that difference is a real, measurable execution risk.
- **L5, terms.** `contract_terms_url` is "current". A rule-text SHA-256 captured today does not prove the rule in force for a historical market. `VERIFIED_OFFICIAL` for archived markets is therefore weaker than for markets whose rule text was captured live.
- **L6, final-state market objects as features.** `last_price_dollars`, `volume_24h_fp`, `previous_*`, and `open_interest_fp` in a REST snapshot are as of the fetch. In a historical object they are end-of-life values.

### 2.3 Options for point-in-time ContractSpec identity and versioning (owner decides)

The m4 split (verification status leaves the identity hash) is a **separate open owner decision**; the options below are described as if it were adopted. All of them require `build_feature_row`, `label_for`, and `TrainingExample` to select the version known at decision and refuse a later one, as stated in M1.

**Option A: semantic key plus bitemporal versions.** Key = `(venue, market_ticker, event_ticker, series_ticker)`, the stable venue identity. Each version records the economic and rule fields plus two times:
- `effective_from`: the venue's stated time, such as `scheduled_ts` or `close_ts`;
- `known_at`: PMV receipt time of the message or poll that revealed it.

Features use the latest version with `known_at + min_latency <= decision`. Economics uses `effective_from`.
- Pros: directly supports L1–L4. One stable key for R1 grouping and for observations, so there is no `unknown_contract` churn. The model is familiar (bitemporal tables).
- Cons: a strike change keeps the same key, so "same contract" no longer means "same question". Every consumer must carry a `version_id`. The version table is derived state, and its derivation must itself be reproducible.
- Risks: `known_at` for REST-polled changes is upper-bounded by the poll interval. A change missed during a WS gap is learned late. That is conservative, but it creates rows whose spec was stale.

**Option B: append-only metadata event log keyed by receipt time.** Every lifecycle message, `event_fee_update`, and REST metadata snapshot is stored as raw and as normalized "metadata observations" in the existing `ObservationLog`, with `available_at = received_at`. The spec at time *t* is a deterministic fold over the `AsOfView`.
- Pros: reuses the existing point-in-time machinery (capture-order prefix, `min_latency`, stream resets). No separate table is needed, and replay alone proves leakage-safety. A parser fix produces a new normalized version without mutation.
- Cons: the fold logic becomes safety-critical code. Every feature computation pays for the fold, unless the result is cached. It needs explicit "spec unknown / uncertain" states after a lifecycle-stream gap.
- Risks: if the fold consumes a REST snapshot containing `result` or a realized close, those fields must be quarantined into the label channel at normalization. Otherwise outcome data enters the observation log, violating "No observation carries a settlement result".

**Option C: snapshot-per-capture.** At each REST poll, store the full Market, Event, and Series objects. The spec at *t* is the latest snapshot received by *t*. WS lifecycle is used only to trigger re-polls.
- Pros: simplest collector. Each snapshot is self-contained and hashable.
- Cons: temporal resolution equals the poll interval. Snapshots bundle outcome-bearing fields (`result`, `last_price`, `volume`) with spec fields, so field-level quarantine is still needed. Rate-limit cost grows with the number of tracked markets.
- Risks: worst `known_at` latency. Intra-poll changes are invisible, and close-time changes near close are the ones that matter most.

**Option D: hybrid (B as source of truth, A as a materialized view, C as a reconciliation input).**
- Pros: B gives auditability and replay. A gives a cheap lookup and the `effective_from`/`known_at` distinction. C's periodic snapshots detect missed WS events, including `disputed`/`amended`, which have no WS event.
- Cons: the most engineering. It needs a parity test proving the A view equals the B fold.

**What each option requires from the collector [PROJECT-ASSUMPTION/RECOMMENDATION]:**
- Subscribe to `market_lifecycle_v2`. Per the lifecycle WS page, it receives "all market and event lifecycle notifications (`market_ticker` filters are not supported)", so filtering is client-side. Record raw bytes, PMV receipt time, `sid`, `seq`, and `sending_ts_ms`.
- On every lifecycle `seq` gap or reconnect, re-poll REST for all tracked markets and mark the gap interval "metadata uncertain".
- Poll REST `GET /markets` with `min_updated_ts` ("Return markets with metadata updated later than this Unix timestamp … Tracks non-trading changes only") at a fixed, recorded interval. The interval is an explicit assumption.
- Poll `GET /series/{ticker}`, `GET /series/fee_changes`, `GET /events/fee_changes`, `GET /exchange/status`, and `GET /exchange/schedule`.
- Poll market status after `determined` until `finalized`, to catch `disputed`/`amended`.
- Store the `created` event's `additional_metadata` (rules text, strikes, `can_close_early`, `expected_expiration_ts`). It is the best point-in-time record of the original terms. Hash `rules_primary` and `rules_secondary` at creation.
- Never take `known_at` from venue fields (`updated_time`, `last_updated_ts`, `sending_ts_ms`). Use them only as provenance and latency diagnostics.

**Statistically preferred: D, or B if engineering budget is tight [RECOMMENDATION, not a decision].** Reasoning:
- B makes leakage-safety a property of the same replay machinery already tested for observations. One point-in-time mechanism is easier to audit than two.
- The `effective_from` vs `known_at` split in A is required for L4 regardless.
- C alone cannot meet M1 near close, which is exactly where time remaining is shortest and the signal is most likely to be found.

On identity, I lean to a stable venue key with versioned terms. A strike change should be a **new version and a regime flag**, not a new identity. Training rows whose spec version changed between decision and `ref_end` should get their own exclusion reason, because the label answers a question that differs from the one priced at decision. This is the owner's decision.

---

## 3. Sequence and timestamp assumptions

- **[VERIFIED-BY-DOC] `seq` and `sid` text.** In every captured sequenced channel, `sid` is the "Server-generated subscription identifier (sid) used to identify the channel". `seq` is a "Sequential number that should be checked if you want to guarantee you received all the messages. Used for snapshot/delta consistency" (orderbook updates, lifecycle). Changelog, September 10, 2026: "`seq` is documented on the Predictions trade, market lifecycle, multivariate market lifecycle, event lifecycle, event fee update, and RFQ and quote messages … These channels have always been sequenced."
- **[UNRESOLVED] `seq` scope.** The docs do not say whether `seq` is per `sid`, per market within a `sid`, or per connection. They do not say whether it starts at 1 on subscribe, whether `update_subscription` (`add_markets`) or `get_snapshot` advances it, or what the documented recovery for a gap is (resubscribe vs `get_snapshot`). **Conservative project rule (current code):** treat the scope as `(connection, sid)`. A gap or regression invalidates every book on that `sid`. Keep it until empirically confirmed from collector metadata (F-08).
- **[VERIFIED-BY-DOC] `ticker` has no documented `seq`.** The captured `websockets_market-ticker` page shows `ts_ms` but no `seq`. Under current project rules, ticker-derived quotes cannot be continuity-checked. They may serve as features only with staleness and silence checks, never as a book.
- **Delta semantics (relevant to book validity).** [VERIFIED-BY-DOC] The `orderbook_delta` payload field is `delta_fp`: "Fixed-point contract delta (2 decimals)". [INFERENCE, not stated in the docs] This reads as **relative**, while `BookDelta.new_quantity` is an absolute replacement (`docs/market_data.md`). The adapter must not map relative deltas onto absolute ones. Flagged for API / Execution. It matters statistically because silently wrong books corrupt every depth and imbalance feature.
- **[VERIFIED-BY-DOC] Timestamp fields and meaning:**
  - `sending_ts_ms` (optional on all channels): "when Kalshi queued this message at the network layer";
  - `orderbook_delta.ts_ms` (optional): "when the orderbook change was recorded";
  - `ticker.ts_ms`: "when the update happened";
  - `trade.ts_ms`: "Unix timestamp in milliseconds";
  - REST trade `created_time`: "when this trade was executed";
  - CF Benchmarks tick `received_at`: "When Kalshi received the upstream frame (unix ms)", plus a source timestamp;
  - lifecycle `close_ts`, `determination_ts`, and `settled_ts` are in **seconds**;
  - `GET /exchange/user_data_timestamp`: "There is typically a short delay before exchange events are reflected in the API endpoints." REST state therefore lags exchange state.
- **Availability [PROJECT-ASSUMPTION/RECOMMENDATION], consistent with `docs/market_data.md` and F-08 release-by-receipt:**
  - **Valid for decision-time availability:** PMV's own receipt time (`received_at`), after F-12 monotonic hardening, plus the explicit `min_latency`. Nothing else.
  - **Not valid as availability:** `ts_ms`, `sending_ts_ms`, `created_time`, CF `received_at`, the source timestamp, `updated_time`, `last_updated_ts`, `scheduled_ts`, `determination_ts`, and `settlement_ts`. They are venue clocks that precede PMV receipt. The ordering is expected (not verified) to be source ≤ venue ≤ `sending_ts_ms` ≤ PMV receipt. Using any of them as a feature cutoff makes data appear usable before PMV had it.
  - **Valid uses of exchange timestamps:** latency measurement (receipt − `sending_ts_ms`), anomaly detection, ordering *within* a venue stream as a diagnostic, and **label-side alignment**. The rule-defined reference window is defined on the venue or source clock. Which ticks fall in a settlement window is a source-clock question, while feature availability is a receipt-clock question. The two clocks must never be swapped.
  - **Historical backfill has no receipt time.** Archived trades and candles carry only venue times, so `available_at = received_at` cannot be applied. The choices are:
    1. forbid historical-archive rows from training;
    2. define a separately flagged *synthetic availability* `venue_ts + L`, where `L` is a conservative upper quantile of measured (receipt − venue_ts) latency from live captures, fixed before outcome inspection.

    This is a **methodology change requiring owner approval**, because it departs from "`available_at = received_at`, always".

---

## 4. Leakage implications [mostly RECOMMENDATION, evidence VERIFIED-BY-DOC]

1. **REST Market objects mix spec, live state, and outcome.** The `openapi.yaml` Market schema includes `result`, `settlement_value_dollars`, `expiration_value`, `settlement_ts`, `last_price_dollars`, `volume_fp`, `volume_24h_fp`, `open_interest_fp`, `previous_*`, and `status`. The normalizer must split each response into (a) spec-version fields, (b) a quote observation with receipt time, and (c) a resolution record routed only to the label channel. `docs/market_data.md` already requires "Official resolutions … never enter an `ObservationLog`". This makes it concrete for Kalshi.
2. **Candlesticks.**
   - `end_period_ts` is the "inclusive end of the candlestick period". Periods are 1, 60, or 1440 minutes.
   - A candle is usable at decision *t* only if `end_period_ts + publication lag + min_latency <= t`. The publication lag is **[UNRESOLVED]**.
   - A 60- or 1440-minute candle spanning *t* contains post-decision highs and lows and must never be used.
   - `include_latest_before_start` prepends a **synthetic** candle "Projecting it forward to the first period boundary". It is not an observation and must be flagged or refused.
   - Whether candle `close` for `yes_bid`/`yes_ask` equals the quote at `end_period_ts` is **[UNRESOLVED]**.
3. **Historical endpoints return final state.** `GET /historical/markets` returns "Settled markets older than the cutoff" with the full Market schema. Every field is end-of-life (L1–L6). Old Events and Series "will always still be available through their original endpoints", but **current** Series terms and fees only.
4. **Moving archive cutoff makes snapshots non-reproducible.** https://docs.kalshi.com/getting_started/historical_data: "The cutoff timestamps will be regularly updated, advancing forward over time. Each data type has its own cutoff." A dataset assembled from live plus historical endpoints must record `GET /historical/cutoff` at fetch time and be content-addressed. Re-running the fetch later is not the same snapshot (START_HERE "Data and Contract Identity").
5. **CF Benchmarks averaging field.** `last_60s_windowed_average_15min` is "present only in the final minute before quarter-hour close". Its window is `(quarter_close_ts_ms - 60000, quarter_close_ts_ms]`, with "second-indexed counts". **[UNRESOLVED]** whether any Kalshi BTC contract settles on it. If one does:
   - a decision inside the final minute observes a **partially realized settlement value**. That is legitimate information, but it is a distinct regime with near-deterministic outcomes, where apparent edge is easy to overstate and fills are hardest;
   - `ref_end` = window end, and features must include time to window start;
   - `ContractSpec` currently refuses window-shaped references by design.

   Either way, the **presence** of the field marks the final minute and is itself a feature leak only if keyed by source time rather than receipt.
6. **`live_data` endpoint.** https://docs.kalshi.com/api-reference/live-data/get-event-live-data serves "crypto price charts (e.g. `KXBTC15M` events), commodity price timeseries". `is_historical` is "True when the event has matured and the payload is a frozen historical snapshot". Fetched after maturity, it returns the whole path including post-decision data. It is also an **equivalent observable** for protected windows under `docs/protected_information.md` and must go through the data-access guard.
7. **CF Benchmarks REST passthrough history.** https://docs.kalshi.com/cfbenchmarks/rest-passthrough: "Historical index values … `BRTI` … tick-level values". This is a direct equivalent observable of any protected BTC window and must be catalogued in the guard (protected_information prerequisite 3 already names BRTI). Pyth gold feeds (`Metal.XAU/USD`, `Metal.Index.GOLD/USD`) are equivalent observables for any gold contract.
8. **`previous_*` "a day ago" fields and `volume_24h_fp`** are trailing aggregates of unknown alignment. If used as features, the window boundaries are **[UNRESOLVED]**. Treat them as unverified until defined.

---

## 5. Split, purge, and embargo implications (building on R1 and R2)

- **[VERIFIED-BY-DOC] Inputs:** the existence of a `KXBTC15M` series is shown only as an example in the changelog (July 30, 2026, "crypto price charts (e.g. `KXBTC15M` events)"). Its rules, strike structure, and cadence are **[UNRESOLVED]**. Other docs examples (`KXBTCD-…-T114999.99`, `KXBTC-25APR30-T0915-B95000`) are illustrations only. They suggest, but do not establish, multi-strike events.
- **[RECOMMENDATION] R1 refinement: unit of independence.** Group by **outcome-reference event**, as R1 proposes: underlying × `ref_end`, merging all strikes and all decision rows of that event. For dependence-aware uncertainty, go one level higher: **block** by contiguous time (for example UTC day or a volatility-regime block). Back-to-back 15-minute windows share the underlying path, volatility regime, liquidity regime, and model error. Even if consecutive window *outcomes* are near-independent under a martingale, Brier, log-loss, and P&L residuals will be autocorrelated through regime. ESS should be estimated from the autocorrelation of per-event residual contributions (Newey-West / HAC, or a moving-block bootstrap with block length chosen on development data only), not from row or event counts.
- **[RECOMMENDATION] Illustrative power (assumption, not data).** Detecting a 2 percentage-point calibration or edge difference at 80% power and two-sided 5%, with outcome SD ≈ 0.5, needs ≈ (2.8 × 0.5 / 0.02)² ≈ 4,900 **independent** events. One 15-minute series yields at most 96 events per day nominal. A design effect of 3–10 from regime clustering, plus the strike multiplicity inside events, puts the needed calendar span at months, not weeks. A 30% protected slice must be sized by F-07 power analysis, not by convenience.
- **[RECOMMENDATION] Purge geometry at the frozen Phase 2 boundary B.** Assign whole events to a side by `ref_end`. Purge any development decision row whose event `ref_end + max_clock_error + averaging-window length` ≥ B − margin. This includes events that straddle B: opened before B, referenced after it. Back-to-back windows guarantee straddlers at every boundary.

  Feature lookbacks of protected rows reach back into development data. That is past information and not leakage for the model. Under the **information embargo**, however, the protected-scope margin `[start − margin, end + margin + lag)` in `docs/protected_information.md` already makes the guard refuse underlying data just before B. The development set therefore ends at B − margin, and the protected set's first usable decisions need lookback ≤ data that is released at evaluation. The margin must be ≥ max(feature lookback, label horizon, averaging window, settlement-timer plus dispute delay). The last term matters for label-availability purges in walk-forward, not for the frozen split.
- **[RECOMMENDATION] Walk-forward inside the 70%.**
  - Training cutoff T may include an event only if its **finalization receipt** ≤ T (§1.2 time 3).
  - The validation fold starts after an embargo ≥ max lookback.
  - Disputed or amended events use the finalized label only, and their count is reported.
  - `settlement_timer_seconds` is per market, so the label-availability delay must come from the version known at the time, not a constant.
- **[RECOMMENDATION] Calendar regimes.** Thursday 03:00–05:00 ET maintenance, exchange outages, and deactivations must be pre-registered exclusion rules recorded with the split, not fitted later. The split boundaries should avoid landing inside a known maintenance window, so purge accounting stays simple.
- **[VERIFIED-BY-DOC] Historical granularity:**
  - order book: REST `GET /markets/{ticker}/orderbook` is "the current order book". No historical order-book endpoint exists among the historical endpoints listed (`/historical/cutoff`, `markets`, `markets/{ticker}`, `candlesticks`, `trades`, `fills`, `orders`, `positions`);
  - candles: minimum period 1 minute;
  - trades: individual prints with `created_time`;
  - no lifecycle or metadata history;
  - `is_provisional`: "the market may be removed after determination if there is no activity on it".
- **[RECOMMENDATION] Gate 1 consequence.** Historical-archive data can at most support a **coarse discovery or pilot** study:
  - minute-resolution top-of-book OHLC and trade prints;
  - final-state specs (L1–L6 apply);
  - an activity-selected universe (H6);
  - no receipt times (§3).

  It **cannot** support the depth, slippage, imbalance, sub-minute velocity-vs-book, or point-in-time-spec evidence on which after-cost EV depends. Valid short-horizon training observations for the project's stated features must therefore come from **live capture**. This strengthens the case for the F-06 prospective-holdout default. It also means Gate 1 sufficiency should be stated as "N events of live capture with usable books", with N from F-07 power analysis. Any historical-archive study must be declared a development or discovery subset under a `cycle_id`, with its universe-selection bias reported. Using historical rows with synthetic availability (§3) needs owner approval.
- **[RECOMMENDATION] Universe definition.** Enumerate the market universe from the lifecycle `created` stream as received, not from post-hoc listings, so provisional or removed markets remain in the denominator. For historical studies, report the possible selection explicitly. It cannot be corrected from the API alone.

---

## 6. Gold

- **[VERIFIED-BY-DOC] Only these gold items appear:**
  - Pyth reference feeds `Metal.XAU/USD`, `Metal.Index.GOLD/USD` "(24/7)", and `Metal.Index.1OZGOLD/USD` on `pyth_value` (https://docs.kalshi.com/websockets/pyth-value), with "The Pyth data feed costs **$1,000/month**" and "spot metals and FX pairs follow their market sessions";
  - Margin **perps** "whose underlying index comes from Pyth, such as gold and silver" (changelog, October 1, 2026);
  - a `Commodities` category on shard 2 (exchange_sharding).

  **No gold event-contract series ticker, rule, or cadence is documented in the captured docs; existence is UNRESOLVED.** The docs do reference Commodities events and commodity price timeseries. CF Benchmarks indices listed are crypto only.
- **[UNRESOLVED]** Whether Kalshi lists short-horizon (15-minute to 1-hour) gold event contracts at all. This is an F-16 item. It needs `GET /series?category=Commodities`, which is a market-data API call and blocked, or the `kalshi.com` market pages, which were unreachable.
- **Consequences if none exist [RECOMMENDATION, escalate to owner]:**
  1. The approved scope (CLAUDE.md "Initial assets: Bitcoin and gold") cannot be met on Kalshi, and Polymarket is deferred. This is a **scope conflict to surface**, not to resolve silently.
  2. Gold perps are a different instrument (margin, funding, path-dependent P&L), not P(contract resolves in our favour). Substituting them would be a material change.
  3. If gold contracts exist only at daily or hourly cadence or session hours, gold sample sizes will be far smaller, with weekend and session gaps. Gold must not be pooled with BTC to inflate N without a hierarchical model and a cross-asset validation test. Gold-specific evidence would likely stay underpowered for a long time.
  4. Any gold contract settling on a Pyth or LBMA reference makes the $1,000/month feed (or an equivalent) a cost to include in the economics. The gold equivalent-observable list in `docs/protected_information.md` should add the Pyth gold indices.
  5. A BTC-only project concentrates all exposure in one underlying. Correlated-exposure caps then bind on everything, and regime risk is undiversified (Phase 4.5).

---

## 7. Items I could not verify (carry into AR-1 / AR-2)

These items need `kalshi.com` rule pages, the fee-schedule PDF, or CF Benchmarks methodology:
- BTC and gold contract rules: reference instant or window, settlement source and methodology, tie/rounding (`greater` vs `greater_or_equal` exists in the `strike_type` enum, but which applies is per market), void and cancel treatment, and whether a 15-minute BTC contract uses a 60 s average;
- the fee formula (`quadratic`, maker-fee multipliers: series schema says 0.25 standard, 0.5 combo) and the effective-date history. The changelog of August 20–22, 2026 records maker-fee and combo-fee changes. Any training span crossing them has a **structural break in costs**, and applicability to BTC series is **[UNRESOLVED]**;
- the `seq` scope and gap-recovery procedure;
- the candle publication lag and the bid/ask close definition;
- whether exchange-wide pauses change per-market status;
- `event_fee_update` timing (set vs effective);
- whether `rules_primary` can change.

## 8. Overall statistical position

Nothing here shows an edge or its absence. The docs show that the venue's metadata is **mutable, partly unversioned, and outcome-entangled**, and that historical data lacks books, metadata history, and receipt times. The main risks to the project are therefore:
- false edge from point-in-time leakage (L1–L6);
- inflated confidence from dependence (§5);
- an under-evidenced Gate 1 if historical data is mistaken for sufficient.

**Recommendation: proceed with conditions.**
- Block the Kalshi spec builder and label parser until the owner chooses a versioning option (§2.3) and the contract rules are verified (§7).
- Treat live capture as the primary evidence source.
- Escalate gold scope (§6).
