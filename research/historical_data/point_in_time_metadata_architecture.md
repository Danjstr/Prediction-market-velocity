# Point-in-time contract metadata: proposed architecture (for owner decision H-3, H-4, H-5)

**Status:** research proposal from Phase 1 batch 3. Not an approved requirement, and nothing here is implemented. It turns batch 2's options A–D (`research/kalshi/venue_verification.md` §4, `research/kalshi/statistician_review.md` §2.3) into a concrete design, extended to acquired historical data. Reviews: `research/historical_data/statistician_review.md` and `research/historical_data/red_team_review.md`.

## Problem

Contract metadata changes during a contract's life:
- `close_time` (early close, extension, reopen);
- strikes and subtitles;
- the tick grid;
- fees (effective times, but no announcement times);
- trading status;
- "current" terms.

Batch 2 confirmed this from Kalshi documentation. Polymarket has analogous mutable fields; the inventory (`inventory_prediction_markets.md`) records what is known. A spec built from metadata learned later leaks the outcome into `time_remaining`, moneyness, eligibility, and costs (L1–L6). Historical archives make this worse: they return **end-of-life state only**.

## Proposed design (recommendation: batch 2 option D)

### 1. Identity is split from versioned terms (resolves review m4)

| Object | Key | Changes when |
|---|---|---|
| `ContractIdentity` | `venue_contract_id`: venue plus native identifiers, with explicit event and series relationships, never parsed from tickers | Never |
| `ContractVersion` | `contract_version_id` = SHA-256 of the canonical economic and rule terms | Any term changes: strike, region, times, tick grid, rules text hash, settlement source |
| `FeeVersion` | `fee_version_id`, keyed to the identity, or to the event or series it applies to | Any fee change (series, event override, waiver) |
| `VerificationRecord` | `(contract_version_id, rules_source_sha256, verification status, verified_at)` | Verification happens. **It is not part of any identity hash** |

- Observations are keyed to `venue_contract_id`, not to a version. A strike change therefore no longer orphans earlier observations as `unknown_contract` (the m4 defect).
- A strike change is a **new version and a regime flag**, not a new identity (the Statistician's lean). A decision row whose version changed between `decision_time` and `ref_end` gets the exclusion `contract_terms_changed_before_reference`: the label then answers a different question from the one priced. This exclusion uses post-decision information, so it applies to **training labels only**. In economic evaluation the decision stays in, with P&L under the venue's actual handling of open positions (Statistician S-7).

### 2. Source of truth: an append-only metadata observation log (option B)

- **What is logged.** Every metadata-bearing message and snapshot becomes a `MetadataObservation` in the existing `ObservationLog`, with `available_at = received_at`:
  - lifecycle events (`created`, `metadata_updated`, `close_date_updated`, `price_level_structure_updated`, `deactivated` and `activated`, and so on);
  - `event_fee_update`;
  - REST market, event, and series snapshots;
  - fee-change listings.
- **Quarantine at normalization.** Normalization splits every REST object into:
  1. spec fields, which become a `MetadataObservation`;
  2. live-state fields (`last_price`, volume, open interest, `previous_*`), which become a separate, flagged quote and state observation;
  3. outcome fields (`result`, settlement value, `expiration_value`, determination and settlement times, realized close), which become `ResolutionRecord` versions in the **label channel only**.

  An unknown field is preserved in raw and flagged, never routed to features.
- **The spec at `t`** is a deterministic fold over `AsOfView(t, min_latency)`. A lifecycle stream gap, reset, or sequence break makes the fold return `METADATA_UNCERTAIN` until REST reconciliation. Rows in that state are reason-coded exclusions.

### 3. A bitemporal materialized view (option A)

- `ContractVersion` rows carry two times:
  - `effective_from`: the venue-stated time (`scheduled_ts`, `close_ts`);
  - `known_at`: the `received_at` of the first metadata observation that revealed the version.

  The view is derived deterministically from the log.
- **Parity test.** For every `t` in replay, `view.version_known_at(t) == fold(AsOfView(t))`.
- **Two lookups:**
  - the **decision rule** uses the version with `known_at + min_latency <= decision_time`;
  - **realized economics** (fees, tick grid at fill) uses the version effective at the fill time.

  A disagreement is logged as an execution-risk observation, never reconciled silently.

### 4. Reconciliation snapshots (option C)

- **What is polled.** Fixed-interval REST polling of tracked markets, with `min_updated_ts` on Kalshi, plus:
  - series and fee-change endpoints;
  - the exchange status and schedule;
  - status after determination, until finalization (Kalshi has no WebSocket event for `disputed` or `amended`).

  The poll interval is an explicit, recorded assumption.
- **What a snapshot does.** It detects missed stream events and can only *add* versions, each with its own `known_at`, the poll's receipt time. A snapshot never backdates a version.

### 5. Collector obligations

These are batch 2 requirements, restated:
- subscribe to the lifecycle stream and filter client-side;
- record `sid`, `seq`, `sending_ts_ms`, and raw bytes;
- re-poll on every gap or reconnect;
- hash the `created` event's rule text;
- never take `known_at` from venue fields.

### 6. Code obligations

These are M1, unchanged:
- `build_feature_row`, `label_for`, and `TrainingExample` take a `contract_version_id`, and refuse one whose `known_at + min_latency > decision_time`;
- `FeatureRow` records the version ID and `min_latency`;
- `ContractSpec` keeps the scheduled close (as known) apart from the realized close, which is label-channel only.

## Historical archive data (new in batch 3)

Archive metadata has **no PMV `known_at`**. It reports the contract as it ended. Under the rule above, `known_at` would be the fetch time, after every decision, so a strict application excludes every archive row. Using archives at all (owner process change P1) therefore needs an explicit admission policy.

### H-4 proposal: admission of post-hoc metadata

Every archive-derived row carries `metadata_pit_class`:

| Class | Meaning |
|---|---|
| `PIT_CAPTURED` | The version came from PMV-received metadata observations |
| `POST_HOC` | Built from an end-of-life archive object |

Field-by-field rules for `POST_HOC`:

| Field class | Examples | Rule |
|---|---|---|
| Immutable by documented rule | venue identifiers; series; underlying; the reference source **as stated by the rule text in force for that market**; the cadence-defined scheduled close, where a verified series rule fixes it | Admissible. The rule text and its version must be verified **for the market's lifetime**. A current-terms URL fetched today is not evidence for an old market (L5) |
| Mutable, with a documented change history | fees (`fee_changes` with `scheduled_ts` and `show_historical`) | Admissible as `effective_from` for economics. For decision rules, no announcement time exists, so use the version effective at decision and flag `fee_known_at_unproven` |
| Mutable, without a change history | strikes, `close_time`, tick grid, subtitles | Admissible only where pre-decision evidence fixes the value. That evidence is restricted to (i) PMV's own earlier captures, (ii) a verified series rule fixing the field, or (iii) a Q1/Q2 source with a documented `known_at`, because third-party evidence is activity-selected. Alternatively, for a series, the field is admissible if PMV's own lifecycle capture bounds its per-series change rate below a preregistered threshold (upper 95% bound) and the rules version matches. Otherwise the row is excluded with `post_hoc_mutable_field_unverifiable`. **Do not exclude on the realized value alone.** For example, dropping early-closed markets selects on an outcome-correlated event; report it instead |
| Outcome and end-of-life state | `result`, settlement value, realized close, final volume and open interest, `last_price` | Label channel or excluded. Never a feature, never an eligibility filter |

**After the realized close.** A `POST_HOC` decision at or after the realized close gets zero fill in economics, consistent with live order rejection. In training it is excluded as `post_hoc_after_realized_close`. This uses future information only to *remove* rows a live system could not have traded, and the count is ledgered.

**Status of `POST_HOC` rows.** They are admissible for **discovery and pilot** work. They are admissible in training only when selection and evaluation are on `PIT_CAPTURED` + `RECEIPT` folds, and when the preregistered ablation (`docs/phase2.md` "The split") shows non-inferiority (Statistician H-4). Training contamination is then self-revealing: a leaky archive relationship performs worse on receipt folds. They are never by themselves evidence for a Gate 1 sufficiency claim, an after-cost EV claim, or a Phase 5 audit conclusion. Every result reports `POST_HOC` and `PIT_CAPTURED` rows separately.

**Polymarket on-chain metadata.** Market creation, condition preparation, and resolution are on-chain events with block times. A block time is an `event_time`, not a PMV `known_at`. Block finality makes the record more trustworthy than a REST archive, but it still needs the H-5 synthetic-availability rule.

### H-5 proposal: synthetic availability for archive observations

- Synthetic latencies are conservative in the direction that weakens the lead-lag hypothesis, with a preregistered `L` ladder; archive rows support predictive-information claims only, never executable EV (Statistician S-8, `docs/phase2.md` §4).
- Archive trades, candles, and quotes get `availability_class = SYNTHETIC_ARCHIVE` with `available_at = event_time + L_source`. `L_source` is fixed **before** any outcome inspection, per source, conservatively:
  - initially a documented upper bound, or a deliberately large default stated in the cycle's preregistration;
  - later re-estimated from PMV's own measured `received_at − event_time` distribution, as a pre-registered quantile, for the next cycle only.

  It is never tuned to results.
- **Candles.** A candle is available at `end_period + publication_lag + L`. A candle spanning a decision is never used, and a synthetic or projected candle is never an observation.
- **Reporting.** Results report `RECEIPT` and `SYNTHETIC_ARCHIVE` rows separately. Any edge that appears only under synthetic availability is presumed to be a timing artifact until reproduced on receipt-time data.

## Owner decisions needed

1. **H-3:** adopt option D as above (or B alone, if engineering budget is tight), with the identity split (m4) and "a strike change is a new version".
2. **H-4:** adopt the `POST_HOC` admission table, and the rule that `POST_HOC` rows are discovery and pilot evidence only.
3. **H-5:** adopt synthetic availability with a pre-fixed `L_source`, or forbid archive rows in training altogether.

Implementation is blocked until H-3 is decided. Real-data labels are additionally blocked by UR-4 (the contract rules, AR-3).

## Implementation sketch (after approval; synthetic-fixture first)

- Add `MetadataObservation`, `ContractIdentity`, `ContractVersion`, `FeeVersion`, and `VerificationRecord` to `pmv.market_data`. Re-key `spec_key` consumers to identity plus version.
- Add the deterministic fold, the materialized view, and the parity property test over synthetic event streams. The streams include gaps, reopen, extension, strike change, fee change, and dispute.
- Add the normalizer quarantine contract, tested so that no label-channel field can enter an `ObservationLog`.
- Add the new exclusion reasons and `metadata_pit_class` and `availability_class` on `FeatureRow` and `TrainingExample`.
- Add replay tests proving that a feature row built at `t` is byte-identical whether or not post-`t` metadata exists in the log.
