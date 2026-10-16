# Normalized Market Data (Phase 1)

Venue-neutral data contracts between raw captures and research. Implementation: `src/pmv/market_data/`. Governing text: START_HERE.md ("Data and Contract Identity", Phase 1), CLAUDE.md ("Data", "Prediction Objective", "Holdout Protection").

**Status.** Synthetic data only. No module performs network access, reads real market data, or is wired to a loader of real observations. Real observations reach development only under `docs/protected_information.md`, and only through the H-2 per-row release tool, which is not yet built. F-06 and F-08 were decided in batch 4 as H-1 and H-2 (`docs/phase1.md`; `docs/release_tool_design.md`). The Kalshi adapter fails closed until its wire format is verified from current official sources.

## Layers

| Layer | Module | Holds |
|---|---|---|
| Raw | `pmv.raw_format`, `pmv.raw_storage` | Byte-exact payloads, receipt and source timestamps, operational events (`docs/raw_data.md`) |
| Normalization boundary | `market_data.replay` | Venue `Normalizer` protocol; one recorded disposition per raw frame |
| Observations | `market_data.events` | Book snapshots and deltas, trades, trading status, reference ticks, stream events |
| Contract identity | `market_data.contracts` | `ContractSpec` and its `spec_key` |
| Decision-time views and features | `market_data.point_in_time` | `ObservationLog`, `AsOfView`, `FeatureRow` |
| Order books | `market_data.books` | Books reconstructed from snapshots and deltas, with enumerated faults |
| Outcomes and labels | `market_data.labels` | `ResolutionRecord`, `Label`, `TrainingExample` |
| Data quality | `market_data.validation` | Deterministic anomaly report |
| Adapters | `market_data.synthetic`, `market_data.kalshi` | PMV synthetic fixture format; Kalshi boundary (fail-closed) |

## Timestamp semantics

Each observation carries two clocks, never substituted for each other:

- **`source_time`**: what the source says. It is untrusted, may be missing, and may be ahead of receipt. It is used only for latency and anomaly analysis.
- **`received_at`**: PMV's collector clock at delivery. It is the raw frame's `received_at`.

**`available_at = received_at`**, always. An observation can be used for a decision at time `t` only if `available_at + min_latency <= t`. `min_latency` is a required, explicit assumption, with no default. Using `source_time` for availability would let data appear usable before PMV received it.

Stream events (reconnect, gap, rate limit, clock regression, disk pressure) are PMV-originated. They are available at the raw event frame's `written_at`.

**Raw sequence governs order within a capture** (`docs/raw_data.md`). A log uses each observation's *effective availability*: the running maximum of `available_at` over its capture's order `(frame_sequence, item_index)`.

- Every view is therefore a capture-order prefix of every capture. An item never appears before an earlier-recorded item of its capture, such as a stream gap event or the snapshot a delta depends on, even across a local clock regression.
- Raising availability this way only ever delays use.
- The order of a log is `(effective availability, capture_id, frame_sequence, item_index)`. The cross-capture tie-break is deterministic, but it is not evidence of which simultaneous receipt came first.

**Known limit.** `received_at` is a wall clock. Raw v1 records clock regressions as events but has no monotonic receive time. Frame v2 timing and direction are tracked as Step 11 F-12 and must be done before real collection. Validation flags receive-time regressions; it never reorders.

## Contract identity

`ContractSpec` records the following:

- venue and market, event, and series identifiers. Kalshi tickers use the guard's normalization, and relationships are explicit, never parsed from a ticker;
- underlying;
- resolution-source and resolution-rule identifiers;
- the YES region, with explicit bound inclusion, which is the tie semantics;
- `open_time`, `close_time`, and `outcome_reference_time`, in UTC;
- the timezone of the rule text;
- rounding and void rule identifiers;
- the date-effective fee schedule identifier;
- price and quantity units;
- a verification status.

`spec_key` is the SHA-256 of the canonical encoding of every field. A changed rule, threshold, time, or fee schedule is a new identity.

- **Verification.** `UNVERIFIED` specs exist for plumbing. `labels.label_for` refuses them. `VERIFIED_OFFICIAL` requires the SHA-256 of the official rule source, recorded in `research/sources.md`. `SYNTHETIC` is for the `pmv_synthetic` venue only.
- **Venues.** Kalshi and synthetic only. Polymarket is deferred by owner direction and refused.
- **Refused shape.** An `outcome_reference_time` before `close_time` is refused. It would describe trading after the outcome is already determined, which is out of scope. A single reference instant cannot represent a settlement averaged over a window. Whether Kalshi's BTC and gold rules use one is an AR-1 verification item (`settlement_reference_window_or_averaging`).
- **Time remaining.** `time_remaining(t)` (to close) and `time_to_reference(t)` are defined only inside `[open_time, close_time)`, and every `FeatureRow` carries both.

## Observations

- Contract prices and quantities are integers in the contract's units. Reference prices are `Decimal`.
- Book levels are for one `Outcome` of a binary contract. A venue with separate YES and NO books must be mapped explicitly by its adapter, from verified semantics.
- `BookDelta.new_quantity` is an absolute level replacement; 0 removes the level.
- `venue_sequence` is scoped by `sequence_scope` within one capture. The adapter sets the scope from verified venue semantics.
- Construction checks types and structure only. Economic anomalies are kept as observed and flagged by validation.
- No observation carries a settlement result. Trading status is `open`, `paused`, `closed`, or `unknown`.

## Normalization boundary

`replay.normalize_frames(capture_id, frames, normalizer)` gives every raw frame exactly one disposition:

| Disposition | When |
|---|---|
| `parsed` | Zero or more items |
| `skipped` | Deliberately not normalized, for example a heartbeat. Carries an identifier reason |
| `rejected` | The parser raised `PayloadRejectedError(reason)`, or the collector flagged the frame malformed (`raw_flagged_malformed`) |
| `stream_event` | A raw event frame |

Raw bytes are always preserved in the raw store. The driver owns time and provenance: an item whose receipt time, capture, frame, item index, or parser identity differs from the driver's fails the whole replay (`NormalizationContractError`). A parser may not emit stream events. Any parser exception other than `PayloadRejectedError` propagates and fails the replay.

Official resolutions (`labels.ResolutionRecord`) leave the boundary in a separate channel and never enter an `ObservationLog`.

A normalized capture records its parser identity and version. A parser fix is a new version and a new result. It never mutates an earlier one.

## Features and labels

- **Feature inputs.** Feature code receives an `AsOfView`, never the log. The log admits only canonical observation types, so outcomes and labels are refused.
- **`FeatureRow`.** Records the view's `information_cutoff` and refuses a cutoff after `decision_time`. Values must be finite floats with identifier names. Missing-data handling is a Phase 2 decision, never a silent NaN.
- **Labels.** Labels come only from official resolution status.
  - `label_for(spec, resolution, decision_time, *, status, policy)` returns a `Label` or an explicit `LabelExclusion`.
  - A void is never coerced to NO.
  - A missing resolution (`None`) is the exclusion `resolution_missing`, never a silently dropped row. Every candidate decision is therefore accounted for, and exclusions can be tallied as a selection mechanism.
- **Exclusions**, in evaluation order:

  | Exclusion | Rule |
  |---|---|
  | `decision_outside_trading_window` | Decision not in `[open_time, close_time)` |
  | `within_clock_error_of_close` | `decision + max_clock_error >= close_time`. Decision times are on PMV's wall clock, contract times on the venue's, and no offset is measured yet (F-12) |
  | `not_open_at_decision` | The last trading status received by the decision time (`point_in_time.status_as_of`) is not `open`, or none was received. Halted or closed markets are not tradable decisions, and their prices may sit near the outcome |
  | `resolution_missing` | No official resolution supplied |
  | `resolution_available_at_decision` | The resolution was received at or before the decision |
  | `resolution_before_reference_time` | The resolution was received before `outcome_reference_time`, a provenance anomaly |
  | `void` | The official result is void |

- **`LabelPolicy`.** `LabelPolicy(policy_id, max_clock_error)` is explicit and has no defaults. Its `policy_id` is recorded with every experiment, as is `ValidationPolicy.policy_id`. `min_latency` and `max_silence` are call parameters and must be recorded with the experiment as well.
- **`TrainingExample`.** Build one with `training_example(spec, view, features, resolution, policy)`.
  - The feature row must come from that `AsOfView`: same decision time and information cutoff.
  - The trading status is derived from the view, never supplied.
  - The example holds the spec, policy, feature row, status, resolution, and label. It re-derives the label with `label_for` and the row's time fields from the spec, so a hand-built `Label` or `FeatureRow` cannot bypass the verification, window, clock-margin, status, void, or availability rules.
  - A feature cutoff after the decision, or a resolution received by the decision time, is refused.
- **Status limits.** `status_as_of` returns the last status in log order. A later stream reset does not invalidate it.
- **Dependency direction.** Feature-side modules (`timing`, `contracts`, `events`, `point_in_time`, `validation`, `books`) never import `labels`, `replay`, or adapters (`tests/unit/test_market_data_boundaries.py`).
- **Phase 2.** Purge and embargo across split boundaries, observation units, and target definitions belong to Phase 2 and are not implemented here.

## Order-book reconstruction

`books.reconstruct(source, specs)` replays snapshots and deltas into one `OrderBook` per `(capture_id, spec_key, outcome)`. `source` must be an `ObservationLog` or an `AsOfView`, never a list: a filtered list, such as `AsOfView.for_contract`, would silently drop the stream events and other scopes' sequence breaks that invalidate a book. `books.reconstruct_as_of(view, specs)` accepts a view only. A book then reflects exactly what PMV could hold at the view's decision time, given its `min_latency`.

Books never carry over between captures. Each capture is applied in its own capture order, and books are stamped with effective availability:
- `established_at`: the last snapshot;
- `updated_at`: the last change to the levels;
- `faulted_at`: the last change to the continuity faults.

A book is **usable** when its `faults` set is empty. Faults are enumerated (`BookFault`):

| Fault | Kind | Cleared by |
|---|---|---|
| `stream_reset` | Continuity: a reconnect, gap, rate limit, or hard stop (`events.RESETS_BOOK_STATE`) in the capture | The book's own next snapshot |
| `sequence_gap`, `sequence_regression`, `duplicate_sequence` | Continuity: a break in any sequence scope of the capture invalidates every book in it, as in validation | The book's own next snapshot |
| `unsequenced` | Continuity: a snapshot or delta for the book has no venue sequence, so a lost or rejected message could not be detected | A sequenced snapshot |
| `malformed_snapshot` | Continuity: unsorted or repeated snapshot prices | The next well-formed snapshot |
| `delta_price_out_of_range` | Continuity: a delta, including a removal, at a price outside `(0, price_units_per_payout)` | The next snapshot |
| `absent_level_removed` | Continuity: a delta removes a level the book does not hold, a sign the book is out of step with the source | The next snapshot |
| `unknown_contract` | Continuity: `spec_key` not in the supplied specs | A snapshot reconstructed with the spec supplied |
| `price_out_of_range`, `invalid_quantity`, `crossed_or_locked` | Consistency of the current levels | Any update that makes the levels consistent |

- A delta is not applied while a book has a continuity fault. Its last good levels stay visible for diagnosis, but the book is not usable.
- A delta before any snapshot in its capture creates no book. Validation flags it as `delta_without_snapshot`.
- Some rules are stricter than validation:
  - a duplicate venue sequence breaks the book, although validation only warns: two messages claiming one sequence number cannot both be applied with confidence;
  - unsequenced streams are never usable;
  - removing an absent level is a fault.
- An empty or one-sided book can be usable. `OrderBook.two_sided` reports it, and downstream code must handle the missing side explicitly.
- **Usable is not fresh.**
  - `OrderBook.age(t)` is the time since the levels last changed. A quiet market and a dead feed both age.
  - `BookSet.last_seen(capture_id)` is the latest availability of any observation in the capture.
  - `BookSet.latest(spec_key, outcome, decision_time=..., max_silence=...)` returns the most recently updated usable book among captures heard from within `max_silence`. `max_silence` is an explicit assumption with no default. Ties are broken by capture ID, deterministically but without any claim about which capture saw the market first.
- Trades and status updates do not change books.
- No YES/NO complement mapping is assumed, so crossing is checked within one outcome's book only.
- `BookDelta` is an absolute level replacement. Whether Kalshi deltas are absolute or relative is an AR-1 verification item (`kalshi.REQUIRED_VERIFICATIONS`). A relative feed must not be mapped onto `BookDelta` by an adapter that keeps its own book outside these continuity checks.

**Known limit.** Frames the normalizer rejects or skips produce no observation. With sequenced streams, a lost update shows up as a sequence gap. Detecting rejected frames directly needs frame dispositions to reach the book engine, which is not implemented yet.

These are conservative project rules, not venue facts. They are revisited once Kalshi semantics are verified (AR-1). A fresh-context Reliability / Red-Team review of this module (2026-10-15) found no blocking issue. Its major findings were fixed in this batch: filtered inputs, unsequenced books, liveness, the delta-semantics verification item, fault-time separation, and desync faults.

## Validation

`validation.validate(observations, specs, policy)` takes observations in strict capture order and returns a `ValidationReport`. It never removes, reorders, or repairs. Each anomaly has a kind, a severity (`blocking`, `warning`, or `info`), an index, and a provenance position. It never carries values or identifiers.

The policy fields `max_source_lead`, `max_receipt_delay`, and `max_feed_silence` are explicit and have no defaults. They must be recorded with any experiment that relies on them.

| Kind | Severity | Rule |
|---|---|---|
| `unknown_contract` | blocking | `spec_key` not in the supplied specs |
| `duplicate_venue_sequence` | warning | Same sequence again in a scope |
| `venue_sequence_gap` | blocking | Sequence skips, on a snapshot or a delta. Every book in the capture is invalid until its own new snapshot, because which books share a scope is unverified venue semantics |
| `venue_sequence_regression` | blocking | Sequence goes backwards. Invalidates every book in the capture, as for a gap |
| `delta_without_snapshot` | blocking | Delta before a snapshot, or after a reconnect, stream gap, rate limit, disk hard stop, or sequence break |
| `duplicate_trade_id` | warning | Same `(spec_key, venue_trade_id)` again, in any capture |
| `receive_time_regression` | blocking | `received_at` goes backwards within a capture |
| `source_time_regression` | warning | `source_time` goes backwards within a capture's stream |
| `source_time_after_receipt` | warning | Source more than `max_source_lead` ahead of receipt |
| `stale_on_receipt` | warning | Receipt more than `max_receipt_delay` after source |
| `feed_silence` | warning | More than `max_feed_silence` between consecutive receipts of one stream (a contract, or a reference provider and family) in a capture. Stream events are not feed activity. Silence after a stream's last receipt is not detected |
| `crossed_book` | blocking | Best bid ≥ best ask |
| `malformed_book` | blocking | Levels unsorted or with repeated prices |
| `price_out_of_range` | blocking | Not strictly between 0 and `price_units_per_payout` |
| `invalid_quantity` | blocking | Non-positive level or trade quantity, or negative delta quantity |
| `trade_outside_trading_window` | warning | Trade time (source time if present, else receipt) outside `[open, close)` |
| `non_positive_reference_price` | blocking | Reference price ≤ 0 |
| `stream_*` | per kind | Raw operational events: reconnect (info), gap (blocking), hard stop (blocking), rate limit, clock regression, storage pressure (warning). Reconnect, gap, rate limit, and hard stop reset sequence expectations and invalidate every book in the capture |

Severities and the open-interval price rule are conservative project defaults. They are not venue facts. If verified venue semantics differ (for example, quoting at the payout bound), changing them is a reviewed change.

## Review record and known limits

A fresh-context Reliability / Red-Team review of this batch (2026-10-15) found no blocking issue.

**Fixed in this batch:**
- M1: capture-order prefix views;
- M2: gaps on snapshots and cross-book invalidation;
- M3: hard stop and rate limit reset book state;
- M4: per-stream silence;
- M5: `TrainingExample` re-derives its label;
- m1: direct views validate latency, and the cutoff is the true maximum;
- m2: validation checks spec keys;
- m4 (part): canonical Decimal thresholds;
- m5: a resolution received before its reference time is excluded.

**Open, recorded here:**
- **Identity design (review m4, needs an owner decision).**
  - `verification`, `rules_source_sha256`, and the fee schedule are hashed into `spec_key`. Verifying a spec after capture, or a fee change during a market's life, therefore gives a new identity, and earlier observations keyed to the old one fail validation as `unknown_contract`.
  - Recommendation: split a semantic contract key (venue, identifiers, rules, region, times) from date-effective economic and verification metadata keyed to it.
  - Timezone aliases (`UTC` and `Etc/UTC`) are not canonicalized.
- **Not flagged yet (review m3):** activity after a `closed` status; snapshots or deltas outside the trading window; unsequenced deltas inside a sequenced scope.
- **Unverified design choices (review m6):** the refusal of contracts whose reference is fixed before close, and the one-book-per-outcome representation, must be checked against verified Kalshi rules.
- **Missing tail frames (review n1):** `normalize_frames` cannot detect them. It relies on the raw manifest's record count and hash.
- **Crossed and locked books (review n2):** a locked book (bid = ask) shares the `crossed_book` kind. YES/NO cross-book consistency waits for verified venue semantics.
- **Anomalies and views:** validation anomalies are not attached to views. A consumer must consult the validation report for the captures it uses.

## Statistical-methodology review (2026-10-15)

A fresh-context Statistician review of this batch found no blocking defect for synthetic data.

**Fixed in this batch:**
- M2: status-aware exclusion (`not_open_at_decision`);
- M3: clock-error margin before close (`within_clock_error_of_close`, `LabelPolicy.max_clock_error`);
- M4 (part): the `resolution_missing` exclusion, and `policy_id` on `LabelPolicy` and `ValidationPolicy`;
- R6 (part): a training example is bound to the `AsOfView` its features came from.

**Open. Blocking before the Kalshi spec builder or any real-data label (M1).** `ContractSpec` does not record when PMV learned it.
- Scenario: a spec built from metadata fetched after the market ends, for example with a realized early close or an extension, would feed the outcome into `time_remaining` and `time_to_reference`.
- Required: point-in-time spec versions (a `known_at` per version, the latest version known at decision time selected, scheduled close kept apart from realized close), with `build_feature_row`, `label_for`, and `TrainingExample` refusing a spec learned after the decision.
- This depends on the open identity-design decision (review m4 above), so it is left for an owner-approved design, not decided here. *Status (batch 4): the owner chose Option D (H-3, append-only point-in-time metadata), which settles E-2's versioning question. The implementation and the m4 identity design remain open, so the Kalshi spec builder stays blocked.*
- Batch 2 (venue verification) confirmed from Kalshi documentation that these fields change during a market's life: `close_time` (early close, extension, reopen), strikes (`metadata_updated`), the price grid, fees (effective time only), and trading status. Options A–D for the owner are in `research/kalshi/venue_verification.md` §4. None is chosen.
- Batch 2 also found that Kalshi's WebSocket `orderbook_delta` field is `delta_fp`, documented as a "contract delta". It is very likely a relative change, but this is not stated. `BookDelta.new_quantity` is absolute, so a Kalshi normalizer must not map one onto the other without an explicit, tested conversion (`research/kalshi/venue_verification.md` §3).

**Open, before real data:**
- M4: an exclusion ledger, with counts by reason, regime (volatility, time remaining), and period, covering label exclusions, book faults, and validation anomalies. Faults cluster in fast markets, where a velocity edge would live, so they are not missing at random.
- R5: live runtime and training must apply identical book-fault, staleness, status, and clock-margin rules, with a parity test by Phase 3.
- R6: feature values are not yet provably computed from the view. A future feature builder should call `feature_fn(view)`, and `FeatureRow` should record `min_latency`.
- Duplicate venue sequences are a validation warning but a book fault. Analyses must not mix the two classifications.
- `trade_outside_trading_window` uses the untrusted `source_time` when present.

**Owner decisions (methodology, Phase 2), recorded in `docs/phase1.md`:**
- R1: the unit of independence and split grouping;
- R2: label-end purge and embargo.

## Historical archive data (design, batch 3)

The owner's process change P1 (`docs/decisions/2026-10-16_phase1_batch3_historical_data_strategy.md`) makes acquired historical data a development source. Archive rows differ from PMV captures in ways this layer must represent explicitly. The design is in `docs/phase2.md` and `research/historical_data/point_in_time_metadata_architecture.md`, and nothing below is implemented yet.

- **Availability.** Archive rows have no PMV `received_at`, so `available_at = received_at` cannot apply. They either are excluded or get a flagged synthetic availability `event_time + L_source`, with `L_source` fixed before outcome inspection (owner decision H-5). Every row carries `availability_class` (`RECEIPT` or `SYNTHETIC_ARCHIVE`), and results report the two separately.
- **Metadata.** Archive contract metadata is end-of-life state. Rows built from it carry `metadata_pit_class = POST_HOC` and follow the admission policy (H-4). Outcome and end-of-life fields go to the label channel or are excluded.
- **Identity.** The proposed identities (`raw_observation_id`, `source_record_key`, `venue_contract_id`, `contract_version_id`, `outcome_reference_event_id`, `outcome_cell_id`, `time_block_id`, `decision_row_id`) are defined in `docs/phase2.md` "Identity, duplicates, and statistical dependence" (H-6). They would replace `spec_key` as the de facto row key, and the identity and verification split resolves review m4 above (H-3).
- **Timestamps.** `event_time`, `source_send_time`, `vendor_capture_time`, `received_at`, and `acquired_at` are distinct kinds and are never substituted for one another. `acquired_at` is provenance only.

## Not yet done (see `docs/phase1.md`)

- The Kalshi parser, contract-spec builder, and resolution parser, pending official documentation (ACCESS REQUEST AR-1).
- Persistence of normalized captures as content-addressed artifacts.
- Wiring a real-data loader through the protected-information controls (F-08).
