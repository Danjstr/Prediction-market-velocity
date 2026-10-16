# Phase 2: Data Cleaning, Dataset Engineering, and Target Construction — Design

Working design for Phase 2. The authoritative requirements are START_HERE.md (Phase 2, Gate 2, Project-Wide Controls), CLAUDE.md, and PROJECT_BRIEF.md; where this file summarizes them, they win. This is not a gate record and not an owner-decision record. Items marked **(owner decision)** are proposals until the owner approves them in `docs/decisions/`.

**Status (2026-10-16).**
- Design only. Nothing here is implemented, beyond the Phase 1 foundation in `src/pmv/market_data/` (`docs/market_data.md`).
- No dataset or sample was downloaded, and no market-data API returned content. One request to an exchange API host was attempted and refused by the proxy. Agents were incidentally exposed to aggregate outcome statistics and to a page containing a live reference-index value (`research/historical_data/feasibility_summary.md` §7). Nothing was recorded or used.
- Written in Phase 1 batch 3 (`docs/decisions/2026-10-16_phase1_batch3_historical_data_strategy.md`).
- Reviews:
  - the development Statistician reviewed the identity, duplicate, dependence, and split design (`research/historical_data/statistician_review.md`);
  - Reliability / Red-Team reviewed provenance, licensing, revision, timestamp, and archive risks (`research/historical_data/red_team_review.md`);
  - both are development self-review, not Gate 2 independent audit.

## Why Phase 2 is broader than splitting

START_HERE.md Phase 2 names the observation unit, targets, settlement logic, eligibility, missing-data handling, timestamp alignment, and the split. P1 makes PMV depend on **acquired historical data** from several sources as well as on its own capture. Wrong, duplicated, revised, or mis-timed source data would therefore corrupt every later phase. Phase 2 owns turning raw data into **trustworthy, reproducible, point-in-time, dependence-aware datasets**. The split is one product of that work.

## Layers and their invariants

Every dataset is built through these layers. They stay separable (CLAUDE.md "Data"). Each derived artifact names its inputs by hash.

| Layer | Holds | Invariant |
|---|---|---|
| Raw | Byte-exact source payloads: PMV captures (`docs/raw_data.md`) and acquired historical files | Immutable, append-only, content-addressed. Never parsed, repaired, or deduplicated in place |
| Acquisition manifest | One record per acquisition: source, request, licence, fetch time, file hashes | Written by deterministic tooling, never by hand |
| Normalized | Typed observations (`pmv.market_data`), each with lineage to one raw record | Versioned by parser identity. A parser fix is a new version |
| Quality | Anomaly and exclusion ledgers, keyed to normalized records | Only records and classifies. Never deletes |
| Canonical dataset | Selected, deduplicated, reconciled observations, with every exclusion reason-coded | Deterministic function of (normalized versions, policy IDs), with a content-addressed manifest |
| Features and labels | `FeatureRow` (from an `AsOfView`) and `Label` (official resolution), in separate channels | Labels never enter feature inputs |
| Split | `research/splits/<split_id>.yaml`, assigned by contract information interval (Policy 2) | Frozen once. Never recomputed over a growing dataset |

## 1. Raw preservation, provenance, and lineage

- **Immutable raw.** Raw bytes are preserved exactly, for PMV captures and for acquired files alike (zip, CSV, Parquet, DBN, JSON pages). A re-download is a **new acquisition**, never an overwrite, even if the bytes are identical. Its identity is linked to the earlier one by hash.
- **Location.** Real raw data, including acquired historical files, lives under the protected raw store (`~/pmv-protected/raw`, Step 11 F-01). It is never in Git. Agents reach it only through the release path (H-2).
- **Acquisition manifest** (proposed closed schema, `acquisition_manifest_v1`):
  - `acquisition_id`;
  - `source_id`, from the source catalog below;
  - the request: endpoint or file identity, parameters, and time range requested;
  - `fetch_started_at` and `fetch_finished_at` on PMV's clock;
  - the tool's identity: code commit and version;
  - for each file: name, size, SHA-256, provider-published checksum where offered, and whether it matched;
  - provider-side version markers: a dataset version, schema version, ETag, Last-Modified, archive cutoff (for example Kalshi `GET /historical/cutoff`, batch 2 §4.4), or a vendor revision ID;
  - `licence_id` and the terms snapshot hash in force at fetch;
  - `post_fetch_scope_check`: the result of checking that nothing outside the requested time range was returned (Red-Team S-2).
- **Source catalog** (proposed `research/historical_data/source_catalog`, a closed schema, owner-reviewed). Each `source_id` records:
  - the provider and product;
  - the venue or asset;
  - the semantics class (trades, quotes, book, candles, index, settlement, metadata);
  - the timestamp fields and what each one means;
  - the timezone and precision;
  - the revision policy;
  - the licence;
  - its `quality_tier` (§14);
  - the equivalent-observable family, for the guard.

  A source without a catalog entry fails closed.
- **Lineage.** Every normalized record carries `raw_observation_id` (§ Identity). Every derived dataset manifest lists its input manifests by hash, its parser and policy IDs, and the code commit. A derived value can be traced back to the exact raw bytes, and every raw byte to its acquisition.

## 2. Schema and type validation

- **Strict schemas, pinned per source and version.** Unknown required-field changes, unknown enum values, and type changes fail closed. Unknown optional fields are preserved in raw and flagged.
- **Typing at the venue and accounting boundary.** Prices and quantities are integers in minimum units, or `Decimal` (`docs/conventions.md` "Numbers"). A float that arrives in a CSV is parsed by exact decimal-string parsing, never through binary float.
- **Version detection.** A source with no version signal (Kalshi removed API versioning, batch 2 §1.4) is pinned by schema hash. A change produces a new parser version, never silent acceptance.

## 3. Units, currency, and price-scale normalization

- Every numeric field has an explicit unit in the source catalog:
  - the currency and quote asset (USD vs USDT vs USDC is **not** interchangeable; a stablecoin basis is a real, time-varying spread);
  - the price scale (cents, dollars, fixed-point, tick multipliers, CME display factors);
  - the contract multiplier (GC 100 oz, MGC 10 oz, 1OZ 1 oz);
  - the quantity unit (contracts, fractional contracts, base-asset units, notional).
- Prediction-market prices are probabilities in payout units. YES and NO representations, and Kalshi's NO-bid-as-YES-ask complement, are mapped explicitly from verified semantics, never assumed.
- Tick-grid changes (Kalshi `price_level_structure_updated`, CME tick changes) are versioned contract metadata (§11), not constants.
- Gold prices from different instruments are **different quantities**: futures (by expiry, with carry and basis), spot XAU (OTC, indicative), the LBMA auction price, ETF shares (NAV, fees, market hours). They are never merged into one series. Each is a separate `source_id`, and any relationship between them is a modeled feature, not normalization.

## 4. Timestamp normalization

- **UTC everywhere** (`docs/conventions.md` "Time"). Source-local times are converted with the IANA zone stated in the source catalog. That zone is the source's documented zone, never guessed. Each conversion records the original field and zone in lineage.
- **DST.** Sources quoted in local time need care:
  - CME (Central Time sessions);
  - LBMA (London auctions);
  - Kalshi schedules and maintenance (ET).

  Ambiguous local times in the fall-back hour, and non-existent ones in spring-forward, are flagged anomalies. They are never resolved by default. Session calendars are versioned data, not code constants.
- **Precision.** The source's native precision is recorded: seconds, milliseconds, microseconds, or nanoseconds. Coarse timestamps are never padded into false precision. Ordering ties at coarse precision are kept in source order, and flagged as ties.
- **The timestamp kinds are never substituted for one another** (`docs/market_data.md` "Timestamp semantics"):

  | Kind | Example | Use |
  |---|---|---|
  | `event_time` | exchange match time (CME `ts_event`, Kalshi `created_time`, block time) | label-side alignment, ordering diagnostics |
  | `source_send_time` | Kalshi `sending_ts_ms`, a gateway send time | latency diagnostics |
  | `vendor_capture_time` | a vendor's own receive time (for example Databento `ts_recv`, Tardis `local_timestamp`) | latency diagnostics, and a **lower** bound for synthetic availability: `available_at ≥ vendor_capture_time + L_vendor→PMV`, with `L_vendor→PMV ≥ 0` preregistered |
  | `received_at` | PMV collector receipt time | **availability**, for PMV captures only |
  | `acquired_at` | PMV fetch time of a historical file | provenance only. Never availability: it is after the fact |

- **Availability.** `available_at = received_at` for PMV captures, always. Archive rows have no PMV receipt time. Their availability follows owner decision H-5 (explicit, fixed before the experiment, conservative against the hypothesis in each role, per S-8: later for predictor inputs, earlier for the prediction-market baseline; and evaluated over a preregistered latency ladder whose conservative primary rung is the headline result): a flagged synthetic `available_at = event_time + L` with `L` fixed before outcome inspection, or they are excluded. The `availability_class` (`RECEIPT` or `SYNTHETIC_ARCHIVE`) is carried on every row and every result.
- **Synthetic latency is conservative against the hypothesis (S-8).** The core hypothesis is a lead-lag claim: prediction-market prices under-react to underlying velocity. Its measured strength depends on the *difference* in effective latency between sources, so:
  - underlying sources get a high latency quantile, and prediction-market price staleness a low one;
  - the asymmetry is stated explicitly;
  - latency spikes cluster in fast markets, so a high quantile is used, never a median;
  - every archive-based result reports a preregistered ladder over the **relative** latency: each rung lengthens predictor-input delays and shortens prediction-market staleness (including taking the early end of any PM information interval) by preregistered factors. The **primary rung** is preregistered at the conservative end of plausible latency (high quantile for predictor inputs, low for PM staleness). It is the headline result (owner decision H-5) and the only rung that counts toward conclusions. Rungs more favorable to the hypothesis than the primary are diagnostics, never cited as evidence. Rungs less favorable are stress tests. An effect is "surviving" only if a preregistered criterion holds at the stated stress rung (for example, the block-bootstrap lower bound of the primary estimand stays above zero at the ×2 stress rung). Otherwise it is treated as a timing artifact. The ladder is logged as research degrees of freedom.
- **Coarse timestamps and block time.** A timestamp of precision `p` denotes `[t, t + p)`, so availability uses `t + p + L`. On-chain fills use the information interval `[block_time − D_max, block_time + 1 s)`, and archive lead-lag results are reported at both ends. The headline uses the end that is least favorable to the hypothesis in each role (the early end for the PM baseline or response), and an effect present only at the favorable end is a timing artifact (Red-Team RT-B3-07).
- **Archive rows support predictive-information claims only, never executable-EV claims.** Archive prints are prices at which someone else traded, and there are no books. Any fill simulation on archive rows is labeled "indicative, not executable".

## 5. Clock-offset problems and impossible timestamps

- **Clock offsets.**
  - PMV's clock against venue clocks: measured from `received_at − source_send_time` distributions, and needed for `LabelPolicy.max_clock_error` (F-12).
  - Vendor clocks against the exchange.
  - Exchange clocks against reference-index clocks.

  Offsets are measured and recorded per capture or acquisition. They are never assumed zero. A negative latency beyond a tolerance flags `source_time_after_receipt` (existing validation).
- **Impossible timestamps:** before the source's documented start, before the contract's listing, after the acquisition's fetch time, outside the requested window, of a non-existent local time, or a sentinel value (0, the epoch, 9999). Each is flagged and reason-coded, never clamped.
- **Ordering errors:**
  - regressions of `event_time` within a sequenced stream;
  - regressions of `received_at` within a capture (blocking, existing);
  - trades out of order relative to their sequence.

  Recorded order is never rewritten. The canonical dataset may sort by a declared key, but only by a documented, deterministic rule, with the original position kept in lineage.

## 6. Duplicates

Exact duplicates are removed only through a documented canonicalization that keeps lineage. Near-duplicates are **never** blindly removed. See also "Identity, duplicates, and statistical dependence" below.

- **Exact duplicate, same source.** The same `source_record_key` (§ Identity) with byte-identical normalized content, from overlapping acquisitions, a re-download, or overlapping pagination. The canonical dataset keeps one record, and lineage lists every copy.
- **Conflicting duplicate.** The same `source_record_key` with **different** content, for example a vendor revision or a corrected print. It is never silently resolved. It is flagged `duplicate_conflict`, and the source's documented revision policy (§12) decides which copy is canonical for which `as_of` time. If the policy is undocumented, the record is excluded with a reason.
- **Near-duplicate, same source.** Different keys and the same economic content within a tolerance, such as a trade re-reported with a new ID, or a candle and the trades it summarizes. Flagged by a rule-based detector with a recorded tolerance, kept, and resolved only by a reason-coded rule.
- **Same economic event, different sources.** For example the same CME trade from two vendors, or the same Polymarket fill from the API and from on-chain logs. These are **reconciliation** pairs (§7), not duplicates for deletion. One source is designated canonical by `quality_tier`, and the other is used for verification.
- **Different observations of correlated prices.** For example Coinbase and Kraken BTC trades, or a Kalshi and a Polymarket contract on the same window. These are **not duplicates**. They are distinct observations with statistical dependence, handled under "Identity, duplicates, and statistical dependence".

## 7. Cross-source reconciliation

- Every source that can be checked against another is checked, and the reconciliation reports carry no values in logs. Pairs:
  - vendor against vendor;
  - vendor against exchange-published statistics: CME settlement prices and volume;
  - API trades against on-chain fills, for Polymarket;
  - candles against the trades they summarize;
  - an index (BRTI or another reference) against its constituent exchanges.
- Output: match rates, offset distributions, missing-in-A and missing-in-B counts, and price-difference distributions, per day and per regime. A source whose reconciliation degrades in a period is flagged for that period only. It is not dropped globally.
- **No reconciliation result may be used to fill a gap silently.** Filling from a second source is an imputation (§8), and it needs an explicit, recorded policy.

## 8. Missing data and outages

- **Missing-data classification.** Every gap is one of:

  | Class | Example | Treatment |
  |---|---|---|
  | `feed_outage` | PMV collector down, a vendor gap, a stream reset, a sequence gap | Not inactivity. Decisions whose lookback or decision instant falls in the gap are excluded or flagged under policy. Books are invalid |
  | `venue_halt` | trading paused, maintenance, exchange outage | A distinct regime, recorded from status data, never inferred from silence alone |
  | `genuine_inactivity` | no trades in a quiet market, while heartbeats or book updates show the feed alive | A valid observation of zero activity |
  | `out_of_session` | CME daily break, weekends, LBMA non-auction days | Calendar-defined from versioned session calendars |
  | `undeterminable` | silence with no liveness evidence | Treated as `feed_outage` (fail closed) |

- **Feed outage against genuine inactivity.** This needs liveness evidence: heartbeats, book updates, or sequence continuity. Archive data with trades only (no heartbeats) usually **cannot** distinguish the two. Long trade-free gaps in archives are therefore `undeterminable` unless another source proves liveness.
- **Staleness.** "Usable is not fresh" (`docs/market_data.md`). Every feature records the age of its newest input. `max_silence` and `max_age` are explicit policy values, with no defaults. A value carried forward past its maximum age is stale and excluded under policy, never silently used.
- **Imputation policy (owner-approved per experiment, recorded with its `policy_id`).**
  - The default is **no imputation**: missing stays missing and is represented explicitly, as an indicator or as an exclusion.
  - Allowed imputations are enumerated: last observation carried forward within `max_age`, explicit zero-activity for proven `genuine_inactivity`, and a cross-source fill only under a recorded reconciliation tolerance.
  - A cross-source fill uses only second-source observations whose own availability satisfies `available_at + min_latency ≤ decision_time`.
  - Each is a feature-construction step fitted on the training fold only (§16), and each is flagged on the row.
  - Imputed values never enter labels.

## 9. Outliers, bad ticks, impossible values, and malformed books

- **Impossible values** (blocking): non-positive prices, prediction-market prices outside `(0, payout)`, negative or zero quantities, off-grid prices, a crossed book, a NaN or infinity in a source field. Existing validation kinds cover most of these (`docs/market_data.md` "Validation").
- **Bad ticks and outliers** (warning, reason-coded):
  - a jump beyond `k` robust standard deviations of a rolling, past-only window;
  - a print far outside the contemporaneous book;
  - a cross-exchange deviation beyond tolerance;
  - the reversion pattern of a fat-finger print. This flag is **future-confirmed**. It carries `flag_known_at` = the availability of the confirming observation. It may be used for underlying-series audit and label-side reference checks. It never feeds features or decision eligibility before `flag_known_at`.

  Detectors use **past-only** windows, so a flag is reproducible at decision time. Thresholds are recorded policy. Flagged ticks are kept and excluded or down-weighted only by policy.
- **Eligibility uses only flags known at decision.** A decision row may be excluded or down-weighted only by flags whose `flag_known_at + min_latency ≤ decision_time`. Rows whose inputs were later found bad stay in evaluation, counted as `input_later_flagged`, because a live system would have been misled by them too.
- **Real extreme moves are not outliers.** A velocity edge lives in fast markets, so clipping real moves would erase the signal. Any exclusion is reported by regime (M4 exclusion ledger), and results are shown with and without flagged rows.
- **Malformed, crossed, and locked books.** Existing book faults (`docs/market_data.md` "Order-book reconstruction"). A locked book (bid = ask) is distinguished from a crossed one (review n2). YES/NO cross-book consistency waits for verified venue semantics.

## 10. Snapshot and delta continuity, sequences, and reconnects

- These are already implemented for PMV captures: book faults, sequence gaps, regressions, duplicates, stream resets, and unsequenced books (`docs/market_data.md`). Phase 2 adds:
  - carrying frame dispositions into the book engine, so a rejected frame breaks continuity directly;
  - per-source sequence semantics from the source catalog: the scope, the start value, and reset behavior;
  - for vendor book data (MBO, MBP, L2 snapshots plus deltas), the vendor's own gap and recovery flags, mapped to the same fault model and never ignored.
- **Reconnect and reset.** Every reset invalidates book state until a fresh snapshot arrives. A decision row whose lookback spans a reset is flagged, and its feature values must be computable without the missing interval, or the row is excluded.

## 11. Contract metadata versioning and point-in-time correctness

- Contract metadata is **mutable** (batch 2: close time, strikes, tick grid, fees, status, current terms). Point-in-time contract metadata is required before any real label (Statistician M1).
- Architecture: Option D in `research/historical_data/point_in_time_metadata_architecture.md`, **adopted by owner decision H-3** (`docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`). In short:
  - an append-only metadata observation log keyed by PMV receipt time is the source of truth;
  - a bitemporal `ContractVersion` view is derived from it (`effective_from` from the venue, `known_at` from PMV), with a parity test;
  - periodic snapshots are used for reconciliation.
- **Feature-time rule.** A decision at `t` uses the latest version with `known_at + min_latency <= t`. **Economics rule.** Realized costs use the version effective at fill time. Where the two differ, the difference is a measured execution risk.
- **Archive metadata is post-hoc.** A historical market object is its end-of-life state. Rows built from it carry `metadata_pit_class = POST_HOC` and follow the admission policy **(owner decision H-4, adopted)**: admissible for discovery, data cleaning, pilot modeling, and historical predictive research, but not by itself proof of executable historical EV unless decision-time availability of each field used can be justified.
- **Universe selection.** The contract universe is enumerated from listings as received (lifecycle `created`), never from post-hoc listings. Archives that drop inactive or provisional markets bias the universe toward active markets. That bias is reported, never ignored.

## 12. Settlement and result revisions, and label cleaning

- **Labels come only from official resolution status** (START_HERE.md). Disputes and amendments (Kalshi `disputed` and `amended`, Polymarket UMA disputes) are tracked as versions of the resolution, each with its `known_at`.
- **Walk-forward label availability.** A training cutoff `T` may include an event only if its **finalization receipt** is no later than `T` (R2 and E-5). The frozen split uses the rule-defined reference end (`ref_end`) for purge.
- **Label cleaning is reason-coded exclusion, never relabeling:**
  - a void or cancellation, never coerced to NO;
  - a scalar or other non-binary result on a binary market;
  - an unresolved or unfinalized result;
  - a resolution received before the reference time;
  - a spec version that changed between decision and `ref_end` (the question changed). This exclusion applies to **training labels only**. In economic and strategy evaluation such decisions stay in, with P&L computed under the venue's actual handling of open positions through the change. If that handling is unverified, the decision is scored as a loss under a preregistered conservative rule. The rate is reported per series (S-7);
  - a disagreement between the venue result and the recomputed reference value. That last one is flagged for investigation. The official result stays the label: PMV models how the contract actually resolved, and the disagreement rate is itself a reported risk.
- **Reference recomputation.** Where the reference source's data is available, PMV recomputes the outcome from it as an **audit**, never as the label.
- **Underlying revisions.** Benchmark republication (LBMA, index restatements), CME settlement corrections, and busted trades. Each version is kept with its `known_at`. Features use the version known at decision. Labels are the venue's official resolution. Reference-recomputation audits use the reference version the contract rule names (for example, the first-published settlement), not a later correction unless the rule says so. Archive tapes may be bust-filtered survivors, which the source catalog records.

## 13. Reason-coded exclusions and the exclusion ledger

- **Nothing is dropped silently** (CLAUDE.md "Coding Rules"). Every excluded row, record, or contract gets an enumerated reason and the `policy_id` that excluded it. The existing label exclusions and book faults are extended with the Phase 2 reasons in this document.
- **The exclusion ledger** (Statistician M4) counts exclusions and faults by reason, source, venue, regime (volatility, time remaining, session), and period. Exclusions cluster in fast markets, so they are not missing at random. Every evaluation reports its exclusion profile, plus a sensitivity analysis with flagged rows included where that is possible.
- **Live reproducibility.** Every decision-row exclusion must be computable from information available at decision, so that the live system applies it identically. Exclusions that are not live-computable are label-side or audit-only.
- **Primary designation.** Which of "with" and "without flagged rows" is primary is preregistered. Only the primary analysis counts toward gate criteria.
- **Exclusion rules are frozen before outcome inspection** for the split and for each preregistered evaluation. A rule may not be changed after looking at the outcomes of the rows it affects.

## 14. Source-quality assessment

Each `source_id` gets a recorded `quality_tier`, reviewed by the owner and re-assessed when evidence changes:

| Tier | Meaning | Allowed use |
|---|---|---|
| `Q1_authoritative` | The settlement or reference source itself, or the exchange of record (official venue archive, the CME through a licensed vendor at exchange precision, the index administrator) | Labels (official resolution only), canonical observations, reconciliation anchor |
| `Q2_primary_vendor` | A licensed vendor redistributing exchange data with documented capture, timestamps, and gap flags | Canonical observations where no Q1 copy exists. Reconciled against Q1 where possible |
| `Q3_secondary` | A reputable aggregate or derived archive with documented methodology but coarse time or unverifiable gaps | Auxiliary features and research only. Never a label, never canonical book data |
| `Q4_unverified` | A third-party dump, Kaggle, Hugging Face, or scraped archive without traceable provenance or licence, including mirrors and repackagings until lineage to a primary source is proven | Not used for development evidence. At most a schema or coverage hint, and only if the licence permits. A quality or gap audit is not provenance |

Copies of one upstream are one source, not independent cross-checks. A packager of chain or venue data is admitted only by a deterministic reconciliation against the primary source, with a preregistered sample, threshold, and failure action. Claims resting only on a model-summarized web fetch are SECONDARY: VERIFIED-BY-DOC needs a verbatim quote plus a raw-byte hash.

The tier is a judgment about a source, never a property inferred from its results. It is assigned before any outcome-dependent result using that source is inspected. A re-tier is a dated record with its evidence, and every earlier result is re-reported under both tiers. A source may never be up-tiered because it produces better backtests.

## 15. Deterministic, reproducible derived datasets

- Every derived dataset is a **pure function** of its input manifests (by hash), the code commit, the parser versions, and the policy IDs: validation, exclusion, imputation, label, availability, and duplicate policies. A manifest records all of them, and rebuilding from the same inputs gives byte-identical output (checked by test).
- **No wall-clock reads and no network** in derivation (the existing `market_data` boundary tests). Randomness, if any, is seeded and recorded.
- **A moving source is pinned by acquisition.** A re-fetch is a new acquisition, so a dataset never refers to "the latest" vendor file. This matters for Kalshi's moving archive cutoff (batch 2 §4.4) and for vendors that revise history.
- Experiments name datasets by manifest hash (`docs/experiments.md`).

## 16. Split-safe fitted transformations and leakage prevention

- **Fitted transformations are fitted on training data only, inside each fold:** normalization statistics, imputation parameters, outlier thresholds tuned on data, feature binning, calibration maps, and any learned encoders. They are serialized with the model and applied unchanged to validation and test. Thresholds fixed a priori by policy, not fitted, are exempt and recorded.
- **Past-only windows.** Rolling statistics used in features or in cleaning flags use only data available at the decision time (an `AsOfView`, with `min_latency`).
- **Leakage checklist, enforced in code where possible:**
  - no feature input after `decision_time − min_latency`;
  - no post-hoc metadata in features (§11);
  - no label-channel field (`result`, settlement value, final volume, realized close) in an observation log;
  - no candle whose period ends after the decision, or that spans it;
  - no synthetic or projected candle treated as an observation;
  - no contract whose information interval crosses a fold or split boundary (Policy 2 and 3);
  - no transformation fitted on validation or protected data;
  - no exclusion rule chosen after outcome inspection;
  - no equivalent observable of the protected interval reaching development (the information embargo).

## Identity, duplicates, and statistical dependence

**This design was adopted by owner decision H-6** (`docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`). It refines R1, R2, and E-5 (`docs/phase1.md`), after Statistician review. Contracts on different venues whose `ref_end` falls in the same `outcome_cell_id`, including those on different reference sources, remain separate venue observations (separate `venue_contract_id`s; never dropped as duplicates). They are one dependence unit for split, purge and embargo, uncertainty, power, effective sample size, and correlated-exposure aggregation (Phase 4.5). This does not limit dependence to same-cell pairs: overlapping information intervals, serial dependence within and across `time_block_id`s, and cross-asset dependence are handled by Policies 2, 4, and 5. The Gate 2 independent audit of this design is still required.

### Canonical identities

| Identity | Definition | Example |
|---|---|---|
| `source_id` | A catalogued source and product | `kalshi.historical_trades`, `databento.glbx_mdp3.trades`, `polymarket.polygon.ctf_exchange_fills` |
| `acquisition_id` | One fetch or capture run (manifest above) | A PMV capture ID, or a historical download |
| `source_record_key` | The source's native identity for one record, stable across acquisitions | Kalshi `trade_id`; a Polymarket `(tx_hash, log_index)`; a Coinbase `(product, trade_id)`; a Databento `(publisher_id, instrument_id, ts_event, sequence)`. Where no native key exists, a documented content key |
| `raw_observation_id` | One raw record as preserved in one acquisition: `(acquisition_id, file or frame, item index)` plus content hash | Two downloads of one trade give two `raw_observation_id`s and one `source_record_key` |
| `economic_event_key` | Links records of one economic event seen through different sources, for reconciliation (§6, §7) | One CME trade from two vendors; one Polymarket fill from the API and from on-chain logs |
| `venue_contract_id` | Venue-namespaced, stable native contract identity, unchanged by metadata revisions | `kalshi:<market_ticker>` (with its event and series), `polymarket:<condition_id>` |
| `contract_version_id` | The hash of one point-in-time version of a contract's economic and rule terms, with `effective_from` and `known_at` (H-3). For `POST_HOC` rows: an explicit `POST_HOC:<end-of-life version hash>` marker that can never pass a `known_at` check | The original strike, then the revised strike |
| `outcome_reference_event_id` | The exact quantity that determines the outcome: underlying, reference source and methodology version, and the **fixing set** (one fixing for fixed-strike contracts; start and end fixings for up/down contracts) | "BTC, CF BRTI, 60 s average ending 14:15:00Z" (illustrative; actual rules unverified, UR-4) |
| `outcome_cell_id` | **The scoring and aggregation unit.** `(underlying, floor_G(ref_end))` on a declared, fixed UTC grid `G` per underlying. It is assigned from each contract's own `ref_end`, never by transitive overlap. Venues, strikes, and reference sources whose `ref_end` falls in one grid cell share it | A Kalshi BRTI contract and a Polymarket Chainlink contract both ending 14:15:00Z share the cell `(BTC, 14:00–14:15)`. A 1-hour contract ending 15:00:00Z shares the cell `(BTC, 14:45–15:00)` |
| `time_block_id` | **The resampling and HAC unit.** A contiguous calendar block of fixed, preregistered length `b` on one global UTC grid shared by all underlyings and venues, with `b ≥ max contract life + max feature lookback + label-availability lag`. Never delimited by realized market state. Regime labels are reporting strata computed from past-only information under fixed thresholds, and never define blocks | A UTC day for all underlyings. Gold session structure is a reporting stratum, not a block boundary |
| contract information interval `I(k)` | `[first_decision(k) − max_lookback, ref_end(k) + Δ_label]`, per contract. The unit for split and purge decisions | |
| `decision_time` | The PMV-clock instant at which a decision row's information cutoff is applied. It is generated by a preregistered clock rule (below) | |
| `decision_row_id` | `(venue_contract_id, contract_version_id known at t, decision_time, feature, label, and availability policy IDs)` | Many rows per contract |

Four points deserve emphasis:
- **No transitive clustering.** Serial and overlapping-window dependence is never handled by merging overlapping contracts into one cluster. That would chain back-to-back windows, start-anchored up/down contracts, and nested hourly contracts into one cluster per trading span (Statistician S-1). Instead, dependence is handled by contract-interval purge at boundaries (Policy 2) and by calendar-block resampling (Policy 4).
- **Different reference sources are different `outcome_reference_event_id`s.** A BRTI average and a Chainlink price at the same instant can resolve differently near the strike. That basis risk is real and measured (S-14). When their `ref_end` falls in one grid cell they share an `outcome_cell_id`, because their outcomes are nearly the same random variable.
- **Strikes inside one event share one fixing.** Their outcomes are monotone in the strike, so they are not independent samples.
- **Gold.** Gold contracts, if any are verified, settle on their stated reference: LBMA, a CME settlement, Pyth, or another. The COMEX and LBMA series used as explanatory data are **underlying sources**, not contract identities.

**Decision-time grid (S-12).**
- Decision times are generated by a preregistered clock rule, for example every `k` seconds from listing, or at fixed times remaining.
- An event-triggered decision rule may use only past-only triggers that the live system would compute identically.
- Archive trade or candle times are never decision times by default. Trade arrival is information arrival, so rows created at trade times select on activity.

### Policy (adopted, H-6)

1. **Do not drop cross-venue near-duplicates.** Kalshi and Polymarket contracts on the same reference interval are distinct venue observations, with different prices, costs, liquidity, and rules. Both are kept. That pairing is also what any line-shopping or near-arbitrage analysis needs.
2. **Split isolation, by contract information interval.**
   - For a frozen boundary pair (`B` = protected start, `E` = protected end) and protected-scope margin `m`, with `Δ_label` = averaging window + `max_clock_error`:
     - a contract is **development-eligible** iff `ref_end + Δ_label < B − m`;
     - a contract is **protected-eligible** iff `first_decision ≥ B` and `ref_end + Δ_label ≤ E`;
     - every other contract is **purged**, counted in the exclusion ledger with reason `split_boundary_purge`.
   - All contracts in one `outcome_cell_id` share `ref_end` up to the grid width. They therefore fall on the same side, or are purged together, without any transitive grouping. This requires `m + Δ_label ≥ G`, which is checked when the split is frozen.
3. **Walk-forward folds.**
   - A fold with training cutoff `T` and validation start `V` trains only on contracts whose label is **available** by `T`:
     - for `RECEIPT` rows, that is the finalization receipt;
     - for `POST_HOC` rows, it is a synthetic finalization time `ref_end + max(settlement timer) + dispute allowance + L_label`, fixed before inspection.
   - The fold requires `V ≥ T + max_lookback + max contract life`, and validates only contracts whose `first_decision ≥ V`.
   - The protected-scope margin `m` must be at least max(feature lookback, longest contract life, averaging window, settlement timer plus dispute delay).
4. **Cell scoring, calendar-block inference.**
   - For any per-row quantity `ℓ_r` (log loss, Brier, paired loss difference against the market, P&L per unit stake), compute a per-cell score `s_c = Σ_{r∈c} w_r ℓ_r`, with `Σ_{r∈c} w_r = 1`. By default, weights are equal across contracts in the cell, then equal across rows within a contract. The scheme is preregistered.
   - The point estimate is `θ̂ = (1/C) Σ_c s_c` over eligible cells.
   - Variance:
     - (a) Newey–West (Bartlett) on the time-ordered `s_c`, with a preregistered bandwidth of at least the cells spanned by max contract life + max lookback;
     - (b) a circular or stationary block bootstrap that resamples whole `time_block_id`s, recomputing `θ̂` as a ratio estimator.

     Both are reported, and the wider interval governs.
   - `ESS = C · var̂_iid(s) / σ̂²_HAC`.
   - Every result reports rows, contracts, cells, blocks, and ESS. Row counts are never called sample size.
5. **Joint resampling and path statistics.**
   - Multi-venue and multi-asset metrics resample the **same** calendar blocks for every asset and venue, which preserves cross-sectional correlation.
   - Daily P&L, drawdown, and losing streaks use a stationary bootstrap of daily P&L, with a preregistered mean block length.
   - Correlated-exposure caps (Phase 4.5) aggregate by `outcome_cell_id` and by overlapping information interval. An hourly contract and the 15-minute contract ending at the same instant are one exposure to the terminal fixing.
6. **Power (F-07).**
   - **Primary confirmatory estimand:** the paired per-cell loss difference against the executable-price-implied probability, on eligible `RECEIPT` cells. It tests information not already in the price, and its SD is set by forecast disagreement, not by outcome variance.
   - **Secondary estimand:** after-cost EV per traded cell.
   - For each estimand, the required effective N is `n = ((z_{1−α/2} + z_{1−β}) σ_s / Δ)²`. `σ_s` and the ESS ratio are estimated on development `RECEIPT` data available at cycle registration. Where none exist, as in the first cycle, the gate record states assumed values, their sources, and a sensitivity table, chosen conservatively (larger `σ_s`, smaller ESS ratio, smaller `Δ`). Historical-archive estimates may inform the assumption but are labeled as such.
   - The required protected span is `n / (cells per day × eligible fraction × traded fraction × ESS ratio)`. Rows, strikes, and venues add no independent samples.
   - An illustration with assumed values only (Statistician S-5): a 2-point net edge on 20% of cells traded, at ESS ratio 0.5, needs about 510 days of protected capture. If the secondary estimand cannot reach power within the planned span, that is recorded before `T0`. The holdout then tests incremental information and **bounds** EV rather than confirming it.
7. **Pooling across venues and strikes in training.** This is allowed, with venue and strike as explicit features or hierarchy. Each contract's rows sum to `1/n_contracts_in_cell`, so a cell with many strikes or two venues does not dominate. Evaluation reports per venue and pooled, both with cell-based, block-resampled intervals.
8. **Multiple decision rows per contract.**
   - For training, allowed, weighted as in item 7.
   - For strategy evaluation, there is one preregistered decision rule **per contract per venue**, with cell-level aggregation for inference.
   - Strike selection, for example "the strike with the largest model edge", is acceptable only if it is the preregistered strategy. Its upward selection bias is estimated by block-bootstrapping the **whole selection procedure**.
9. **Cross-asset.** BTC and gold use separate cell grids and a common calendar block grid. They are not pooled to inflate N without a hierarchical model that passes a leave-asset-out or asset-specific walk-forward test (batch 2 §6).

### Edge-falsifying controls (Statistician S-13 to S-16)

- **Structural breaks.** Preregistered heterogeneity tests across:
  - fee regimes (for example Kalshi maker and combo fee changes around 2026-08-20; applicability to BTC series unverified);
  - tick-size regimes;
  - settlement-methodology versions.

  Plus a preregistered trend test of the per-block paired loss difference against calendar time. A decaying edge is extrapolated to `T0`, not averaged.
- **Reference-source basis.** Features near the strike use the contract's settlement source, or a modeled basis to it, under its own availability. Cross-venue near-arbitrage P&L settles each leg on its **own** reference. Basis-disagreement rates are reported by distance to strike. A profit made mainly from reference disagreement is a basis bet, not an arbitrage.
- **Research degrees of freedom.** Cleaning, exclusion, imputation, availability, and duplicate policies are frozen per data pool before that pool's first outcome-dependent inspection. A later change is a new policy version, every earlier result is re-run under it, and the change is counted as a degree of freedom. An optional **historical lockbox**, the newest historical slice before `T0 − m`, may be reserved as an outer-development check. It is opened once, it is development data, and it is never holdout. Development performance on historical periods is treated as optimistic by construction, because agents may know historical regimes.
  - A revision of a synthetic availability policy (`L`, `D_max`, `L_vendor→PMV`, the ladder) may use only outcome-blind latency measurements (distributions of `received_at − event_time` or `received_at − source_send_time` from PMV capture, and overlap-window timing comparisons). It never uses an outcome-dependent result. Each revision is a new `policy_id`. Earlier results are re-run, and the revision is counted.
  - Periods and families listed in `docs/exposure_register.md` Part A count as already outcome-inspected. Policies for them are disclosed as fixed after exposure, and a historical lockbox must either exclude them or be disclosed as partially exposed.
  - Any regime-conditional design element (volatility, session, or liquidity filters or thresholds) is justified from development data alone. Its first version is dated in the experiment ledger, and one first proposed after `T0` is flagged for the auditor (S-10).
- **Universe survivorship.**
  - Enumerate universes from creation events (the lifecycle `created` stream, or on-chain condition preparation), never from post-hoc listings.
  - Compare archive universes against PMV's own enumeration on the overlap window.
  - Report a provably complete subset as a sensitivity analysis.
  - A source with no possible bound stays discovery-only.

## Strategy evaluation strata (owner direction, 2026-10-16)

The strategy objective is in PROJECT_BRIEF.md §3: late-window, high-confidence entries in the final few minutes of a contract. Everything below is a **development hypothesis**. Band edges and thresholds are tested only on development data, and are frozen in the audit-candidate manifest before protected evaluation.

**Strata.** Every strategy result is reported by both of these strata, separately and crossed:
- **Entry-price band**, on the executable price of the side bought (the ask actually payable, never the midpoint), initially about: 0.85–0.89, 0.90–0.92, 0.93–0.95, 0.96–0.97, >0.97.
- **Remaining-time band**, measured from the decision time to the contract's `ref_end` (identity table), initially about: ≤1 minute, 1–2 minutes, 2–3 minutes, 3–5 minutes. Decisions that fall inside a settlement averaging window are flagged and reported separately, because part of the settlement value is already observed at decision time.

**Rules:**
- **Bands are reporting strata, not entry rules.** No band admits or rejects a trade by itself. Entry requires calibrated probability materially above the executable, cost-adjusted break-even probability (payout structure, fees, spread, slippage, latency, execution uncertainty, and the preregistered safety and uncertainty margin).
- **Candidate-generation floor.** Decision rows are generated for executable prices at or above a preregistered floor, initially about $0.85. The floor bounds the search; it is not a signal. Rows below it are outside the intended strategy, and any analysis of them is labelled exploratory.
- **No imposed distribution.** The distribution of trades across bands must emerge from the decision rule on development data. Nothing forces it toward the expected $0.93–$0.97 concentration, a normal shape, or any other target.
- **Per-stratum reporting.** For each band and crossed cell: the eligible decision count; the trade count; the effective sample size by `outcome_cell_id` and `time_block_id` (Policies 4 and 5); predicted versus realized frequency with block-bootstrap intervals; after-cost EV per trade with an interval; and the fill and latency assumptions in force. Sparse cells are reported as sparse, never pooled after looking.
- **High-probability-tail calibration is a primary criterion.** Reliability is reported in fine bins over the candidate region (at least ≥0.85), with calibration error, interval estimates, and the Brier and log-loss decomposition restricted to that region. AUC or overall ranking metrics never substitute for it. The tail-calibration acceptance criterion is preregistered with the primary estimand.
- **Selection discipline.** Choosing bands, floors, margins, or time windows after seeing stratified results is a research degree of freedom. It is logged in the experiment ledger and covered by the Development-Validation Discipline (START_HERE.md). Selection comparisons use `RECEIPT` + `PIT_CAPTURED` folds (see "The split"). A band is never chosen because it looked best.
- **Freeze.** The final band edges, floor, remaining-time window, confidence and edge thresholds, and safety margin are frozen in the audit-candidate manifest before Gate 6. They are never tuned on the protected holdout.

## The split (unchanged requirements, applied to this design)

- The frozen split follows START_HERE.md Phase 2 exactly: an identified snapshot, explicit UTC boundaries, purge and embargo at both ends, a hashed definition in `research/splits/<split_id>.yaml`, and HOLDOUT_ACCESS_LOG.md.
- **Formation (H-1, adopted).** Under P1 and P2, historical data shown to development cannot be the holdout.
  - The formation is a **prospective protected period** from a declared `T0`: required for the first cycle, preferred thereafter. All admissible data before `T0 − m` is then development data, historical and captured alike, subject to Policy 2 eligibility. The protected set is PMV's own capture after `T0`, embargoed together with every equivalent observable.
  - Prospective formation is necessary but not sufficient against agent-model knowledge (S-10). See the conditions in the decision record, H-1 and H-8.
- **Sizing (S-11, adopted by owner decision H-1).**
  - Under prospective formation, the "~70/30" target applies to the **PMV-capture span** `[C0, T_end]`, where `C0` is the start of release-eligible PMV capture. It does not apply to historical development data.
  - The protected span must also meet the F-07 power requirement for the preregistered primary estimand. The power requirement is a floor. The protected span is at least the power-required span. It is lengthened (by a later `T_end` or a larger stopping count, never by an earlier `T0`) where the ~30% target falls short of power, and the deviation from 70/30 is recorded.
  - `T0`, the margin, `C0`, and either `T_end` or an outcome-blind stopping rule (an eligible-cell count from the trusted collector, with a calendar maximum) are fixed in the gate record at cycle registration, before any release. They are never extended or shortened on protected information, and after `T0 − m` only under a preregistered technical contingency (H-1).
  - **One preregistered re-sizing (owner ruling E-B4-8).** Before `T0 − m`, one preregistered re-estimate of the required sample size may use development receipt-time data only. It may only increase the required sample count or the calendar maximum. It never moves `T0` earlier or weakens the test, and it is logged in HOLDOUT_ACCESS_LOG.md.
- **A cycle's development data may mix historical archive rows and PMV-captured rows (S-9).** Mixing is governed by these rules:
  - Every result reports `RECEIPT` and `SYNTHETIC_ARCHIVE` rows, and `PIT_CAPTURED` and `POST_HOC` rows, separately.
  - Any validation result used for selection (features, model family, hyperparameters, calibration, thresholds, policy) is computed on `RECEIPT` + `PIT_CAPTURED` rows only. Archive-validated folds are discovery only.
  - Owner decision H-4 admits `POST_HOC` metadata for discovery, data cleaning, pilot modeling, and historical predictive research. Under this design:
    - `POST_HOC` and `SYNTHETIC_ARCHIVE` rows may be used in training, in pilot models, and in historical predictive-information studies, with results labelled by class;
    - such results may generate hypotheses (feature families, model families, regimes). Each hypothesis carried forward is logged in the experiment ledger as a research degree of freedom;
    - the comparison that selects among candidate features, model families, hyperparameters, calibration, thresholds, or policy for the audit candidate is computed on `RECEIPT` + `PIT_CAPTURED` folds;
    - field-level justification of decision-time availability (H-4) is necessary but not sufficient for an executable-EV claim, which also requires `RECEIPT` rows with live books (§4);
    - if `RECEIPT` + `PIT_CAPTURED` data at selection time are too few for a powered comparison, that is raised to the owner. It is never a reason to select on archive folds.
  - `availability_class` and `metadata_pit_class` are never model inputs.
  - Archive rows stay in the candidate's training set only if a preregistered ablation shows improvement on receipt-validated folds beyond the block-bootstrap interval.
  - Archive artifacts are quantified on an **overlap calibration window**, captured live and later acquired from the same archive, before `T0 − m`.
  - Covariate shift between the classes is tested on features alone.
  - After-cost EV claims rest on `RECEIPT` rows with live books.

## What Phase 2 must deliver (for Gate 2)

- The source catalog and quality tiers for every source used.
- The acquisition manifest and immutable raw storage for acquired data.
- Normalizers per source, with strict schemas and lineage.
- Duplicate, reconciliation, missing-data, outlier, and timestamp policies, each with a `policy_id`.
- Point-in-time contract metadata (H-3) and an admission policy for post-hoc metadata (H-4).
- Availability classes (H-5).
- Identity and dependence grouping (H-6).
- The exclusion ledger.
- Deterministic, rebuildable dataset manifests.
- The observation unit, targets, settlement logic, remaining-time representation, eligibility, and horizons (START_HERE.md Phase 2).
- The strategy evaluation strata (entry-price and remaining-time bands) and the high-probability-tail calibration reporting above.
- The frozen split manifest, purge and embargo.
- The Development-Validation Discipline design (START_HERE.md).
- Statistician review, and an Independent Statistical Auditor review where Gate 2 independence requires it. The Statistician co-authored the dependence design here, so the independent audit applies to it.
