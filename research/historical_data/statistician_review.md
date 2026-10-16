# Statistician review: Phase 2 design, identity and dependence policy, PIT metadata, and holdout formation (Phase 1 batch 3)

**Status: development Statistician self-review. This is NOT an independent audit and does not satisfy Gate 2 independence.** Documentation and methodology only. No real market observation, dataset, or market-data endpoint was accessed or inspected for this review. No network requests were made.

**Authorship disclosure (START_HERE.md "Material Change and Material Authorship", Gate 2).** Earlier development Statistician sessions authored R1 (unit of independence), R2 (purge and embargo by label end), the E-5 label-time split, the batch 2 point-in-time options A–D, the synthetic-availability option (batch 2 §3), and the illustrative F-07 power figure. `docs/phase2.md` "Identity, duplicates, and statistical dependence" and `research/historical_data/point_in_time_metadata_architecture.md` refine those components. If the owner adopts this review's replacements, the development Statistician has co-authored the identity, dependence, split, purge/embargo, availability, and leakage-control design. An Independent Statistical Auditor must then review those components before Gate 2 passes.

**Documents reviewed:**
- `docs/decisions/2026-10-16_phase1_batch3_historical_data_strategy.md`
- `docs/phase2.md` (draft)
- `research/historical_data/point_in_time_metadata_architecture.md` (draft)
- `research/kalshi/statistician_review.md`
- `docs/phase1.md` (R1, R2, F-06/F-07/F-08)
- START_HERE.md, "Project-Wide Controls" and Phase 2
- `docs/market_data.md`, "Features and labels"
- `docs/protected_information.md`, margin semantics

`research/historical_data/feasibility_summary.md` is cited by the decision record but did not exist when this review was written. Nothing here depends on it.

Tags:
- **[RECOMMENDATION]**: my statistical judgment. It is not a decision, and owner approval is needed for any material change.
- **[UNVERIFIED]**: a factual premise I could not check from official sources in this session.

---

## 0. Headline findings

| # | Finding | Severity | Class |
|---|---|---|---|
| S-1 | `dependence_cluster_id` is defined by transitive overlap/adjacency. For 24/7 BTC with back-to-back 15-min windows, hourly contracts, and start-anchored up/down contracts, this **chains into one cluster per continuous trading span**, possibly one for the whole dataset. Split assignment "by the cluster's latest `ref_end`", cluster bootstrap, and cluster-based ESS all collapse. | **BLOCKING** | Replaceable |
| S-2 | `time_block_id` allows "a regime block". A regime block delimited by realized volatility or other ex-post state is outcome-informed. Blocks must come from a fixed calendar grid. Regimes are strata, built only from past-only information. | MAJOR | Repairable |
| S-3 | Purge, split, and walk-forward rules are stated in terms of the chaining cluster. They should be stated per contract, using each contract's information interval. Archive (`POST_HOC`) rows also have no finalization receipt, so walk-forward label availability is undefined for them. | MAJOR | Replaceable |
| S-4 | The ESS and uncertainty policy (items 4–5) has no estimator that could be preregistered. Cross-asset and cross-venue resampling is not required to be joint over calendar blocks. | MAJOR | Repairable |
| S-5 | Power (item 6): the 4,900 figure is for an unpaired outcome with σ = 0.5. The primary confirmatory estimand should be the **paired** loss difference against the market price. After-cost EV on the traded subset is probably underpowered over any feasible prospective span, and the owner should be told this now. The prospective holdout needs an outcome-blind stopping rule. | MAJOR | Repairable |
| S-6 | The outlier detector "reversion pattern of a fat-finger print" is **not past-only**. A flag confirmed in the future, used for decision-row eligibility, is a future-informed filter. | MAJOR | Repairable |
| S-7 | The exclusions `contract_terms_changed_before_reference` and §12 "spec version changed between decision and `ref_end`" use post-decision information. They are acceptable for **training labels**. In **economic evaluation** they are future-informed filters. | MAJOR | Repairable |
| S-8 | Synthetic availability (H-5) with one constant `L` per source can **manufacture a lead-lag edge**: a velocity signal from the underlying that "precedes" the prediction-market price. Latency is also clustered in fast markets. Archive prints overstate executable prices. | MAJOR (BLOCKING for any EV or lead-lag claim resting on archive rows) | Repairable |
| S-9 | In a mixed archive/receipt development pool, data domain and calendar time are **confounded**: archive rows are older, receipt rows newer. Reporting the two separately is necessary but cannot identify an archive artifact. That needs an overlap calibration window, covariate-shift diagnostics, and RECEIPT-only selection folds. | MAJOR | Repairable |
| S-10 | H-1: a prospective holdout is **not automatically clean of F-06**. Agent model upgrades whose training cutoff passes `T0`, and incidental real-time exposure to coarse BTC and gold prices during accumulation, both contaminate it. The model-cutoff governance and the granularity of the embargo need to be stated. | MAJOR | Repairable |
| S-11 | The "~70/30" target is ambiguous when development data is mostly historical. Proposed reading: 70/30 over the PMV-capture span, with a power floor and `T_end` (or the stopping rule) fixed at `T0`. | MAJOR | Owner interpretation |
| S-12 | Decision times in archive studies must sit on a **preregistered clock grid**, not at archive trade-event times. Otherwise rows are selected on activity, and the prints are treated as executable. | MAJOR | Missing control |
| S-13 | Structural breaks: fee regimes (Kalshi, August 2026, applicability unverified; Polymarket short-crypto fee changes, unverified), tick-size regimes, and product maturity, which drives edge decay. None of these is a required stratum or test. | MAJOR | Missing control |
| S-14 | Reference-source basis: feature underlying (for example Binance USDT) vs settlement index (BRTI, Chainlink) vs the other venue's settlement index. Apparent edge and cross-venue "arbitrage" can be basis exposure. | MAJOR | Missing control |
| S-15 | Using the historical pool aggressively multiplies research degrees of freedom. The design has no outer-development lockbox (START_HERE.md Development-Validation Discipline) and no per-pool policy freeze. Agents' knowledge of historical regimes also biases development, as distinct from the holdout. | MAJOR | Missing control |
| S-16 | Universe survivorship: provisional-market removal, hidden or delisted Polymarket markets, vendor coverage. It is reported, but not bounded. | MAJOR | Partly unresolved |
| S-17 | Minor identity and policy gaps: the fixing set in `outcome_reference_event_id`, the version marker for `POST_HOC` rows, a cross-source economic-event key, cross-source fill availability, primary-vs-sensitivity designation, and freezing quality tiers before inspection. | MINOR | Repairable |

Recommendation overall: **revise, then proceed with conditions.** S-1 must be replaced before any split or cycle is registered. The rest can be fixed by wording in `docs/phase2.md` and the PIT architecture before H-1, H-3 to H-6 are decided.

---

## 1. Canonical identities and the unit of independence

### S-1 (BLOCKING): `dependence_cluster_id` chains

**Current text** (`docs/phase2.md`, Canonical identities): "every `outcome_reference_event_id` on the same underlying whose reference windows overlap, or lie within a declared adjacency `δ`, across venues and reference sources."

**Why it fails.**
- "Overlap or within δ" is a pairwise relation. Turning it into a cluster ID requires the transitive closure, the connected components. Three common structures make every component span the whole trading period:
  1. **Back-to-back windows.** BTC trades 24/7. The 15-min windows `[14:00, 14:15]` and `[14:15, 14:30]` share an endpoint. Closed intervals overlap at that point, and any δ ≥ 0 merges them. Chaining then links every window of the day, and every day.
  2. **Start-anchored contracts.** For "up/down" contracts that resolve on `P(end) > P(start)`, the reference involves two fixings. Contract k's end fixing is contract k+1's start fixing. They share an observable, so the reference windows overlap by construction.
  3. **Nested horizons.** A 1-hour contract `[14:00, 15:00]` overlaps four 15-min windows. Hourly contracts listed every 15 minutes, or rolling, chain everything even if 15-min windows were disjoint.
- If the reference window is narrow (a 60 s average) and δ is small, 15-min fixed-strike contracts might not chain. But the definition does not say whether the "reference window" is the averaging window or the contract life, and the hourly and up/down cases chain anyway. The definition is unsafe under any plausible reading.
- Consequences:
  - "Assignment is by the cluster's latest `ref_end`" puts the whole dataset on one side.
  - "Clusters that straddle a boundary are purged" purges everything.
  - The cluster bootstrap has one cluster.
  - Cluster-based ESS is 1.

  Alternatively, implementers would silently pick an ad hoc δ to get a usable number of clusters. That is a research degree of freedom tuned on the data.

**Replacement [RECOMMENDATION].** Separate the three jobs the cluster tries to do. Each gets a partition that cannot chain.

1. **`outcome_cell_id`**: the unit for scoring and within-cell aggregation. It is a fixed grid on each underlying: `cell = (underlying, floor_G(ref_end))`, where `G` is a declared UTC grid (for BTC, the 15-min grid aligned to :00/:15/:30/:45). Every contract, venue, strike, and reference source whose `ref_end` falls in the same grid cell shares the cell.
   - It is a partition by construction. Assignment is a function of one contract's own `ref_end`, never of its neighbours, so nothing chains.
   - An hourly contract ending at 15:00 shares the 14:45–15:00 cell with the 15-min contracts ending at 15:00. Its terminal fixing is the same random variable.
   - Its dependence on the three earlier cells is serial dependence, handled by item 2, not by merging.
2. **`time_block_id`**: the unit for resampling and HAC. Contiguous **calendar** blocks of fixed length `b` on one global UTC grid, shared by all underlyings and venues. `b` must be at least the longest contract life plus the longest feature lookback plus the label-availability lag, rounded up to the grid. The default is one UTC day for BTC, and a declared session-day for gold. Blocks with no eligible rows are kept, so calendar structure is preserved.
3. **Contract information interval** (for purge and split, S-3): `I(k) = [first_decision(k) − max_lookback, ref_end(k) + Δ_label]` per contract `k`. Purge depends only on whether `I(k)` crosses a boundary, never on cluster membership.

**Proposed wording** (replaces the `dependence_cluster_id` row):

> | `outcome_cell_id` | The scoring and aggregation unit. `(underlying, floor_G(ref_end))` on a declared, fixed UTC grid `G` per underlying. It is assigned from each contract's own `ref_end`, never by transitive overlap. Venues, strikes, and reference sources whose `ref_end` falls in one grid cell share it. | A Kalshi BRTI contract and a Polymarket Chainlink contract both ending 14:15:00Z share the cell `(BTC, 14:00–14:15)`. A 1-hour contract ending 15:00:00Z shares the cell `(BTC, 14:45–15:00)` |
> | `time_block_id` | The resampling and HAC unit. A contiguous calendar block of fixed length `b` on one global UTC grid shared by all underlyings, with `b ≥ max contract life + max feature lookback + label-availability lag`, declared before outcome inspection. Never delimited by realized market state | A UTC day |

And add under "Three of these deserve emphasis":

> - **No transitive clustering.** Serial and overlapping-window dependence is never handled by merging overlapping contracts into one cluster. Merging chains across back-to-back windows into a single cluster. It is handled by contract-interval purge at boundaries (Policy 3) and by calendar-block resampling (Policy 5).

### S-2 (MAJOR): regime blocks

"(for example a UTC day, or a regime block)": a block whose edges are set by realized volatility or by a change-point fitted on the full series uses future information. It also lets a block's boundaries adapt to outcomes, so blocks become exchangeable in a way that understates variance. Regimes are legitimate **strata** for reporting. Their labels must be computable from past-only information at decision time (for example trailing realized volatility, with thresholds fixed before inspection). They are never resampling blocks.

**Proposed wording:** "`time_block_id`: a contiguous calendar block (for example a UTC day) of fixed, preregistered length. Regime labels are reporting strata computed from past-only information under fixed thresholds. They never define blocks."

### Other identity gaps (S-17, MINOR)

- `outcome_reference_event_id` should list the **fixing set**, not a single window: one fixing for fixed-strike contracts, start and end fixings for up/down contracts, plus the reference source and methodology version.
- `decision_row_id` uses "`contract_version_id` known at `t`". For `POST_HOC` rows no version is known at `t`. Use an explicit `POST_HOC:<end_of_life_version_hash>` marker, so the row can never pass a `known_at` check by accident.
- Add an `economic_event_key` for §6 "same economic event, different sources" (vendor A vs vendor B for one CME trade). Without it, reconciliation pairs cannot be distinguished mechanically from distinct observations.
- The layering is otherwise sound: `raw_observation_id` → `source_record_key` → normalized record; `venue_contract_id` → `contract_version_id`.

---

## 2. Duplicate and dependence policy (items 1–9)

### Agreed as written

- Item 1: keep cross-venue pairs. It is correct, and it is required for line-shopping analysis.
- Item 7: pooling with venue and strike as features or hierarchy.
- Item 9: no cross-asset pooling to inflate N.

### S-3 (MAJOR): split, purge, and embargo per contract, not per cluster

**Proposed wording** (replaces Policy items 2 and 3):

> 2. **Split isolation, by contract information interval.** For a frozen boundary pair (`B` = protected start, `E` = protected end) and protected-scope margin `m`, with `Δ_label` = averaging window + `max_clock_error`:
>    - a contract is **development-eligible** iff `ref_end + Δ_label < B − m`;
>    - a contract is **protected-eligible** iff `first_decision ≥ B` and `ref_end + Δ_label ≤ E`;
>    - every other contract is **purged**, counted in the exclusion ledger with reason `split_boundary_purge`.
>
>    All contracts in one `outcome_cell_id` share `ref_end` up to the grid width. They therefore fall on the same side, or are purged together, without any transitive grouping.
> 3. **Walk-forward folds.** A fold with training cutoff `T` and validation start `V`:
>    - trains on contracts whose label is **available** by `T`. That is finalization receipt for `RECEIPT` rows. For `POST_HOC` rows it is a synthetic finalization time: `ref_end + max(settlement_timer) + dispute allowance + L_label`, fixed before inspection;
>    - requires `V ≥ T + max_lookback + max contract life`;
>    - validates only contracts whose `first_decision ≥ V`.
>
>    The margin `m` must be at least max(feature lookback, longest contract life, averaging window, settlement timer plus dispute delay).

### S-4 (MAJOR): a preregistrable estimator for ESS and uncertainty

**Proposed wording** (replaces items 4 and 5):

> 4–5. **Cell scoring, calendar-block inference.**
>    - For any per-row quantity `ℓ_r` (log loss, Brier, paired loss difference against the market, P&L per unit stake), compute a per-cell score `s_c = Σ_{r∈c} w_r ℓ_r`, with `Σ_{r∈c} w_r = 1`.
>    - The default weights are equal across contracts in the cell, then equal across rows within a contract. The scheme is preregistered.
>    - The point estimate is `θ̂ = (1/C) Σ_c s_c` over eligible cells.
>    - **Variance**:
>      - (a) Newey–West (Bartlett) on the time-ordered `s_c`, with bandwidth `≥ cells spanned by max contract life + max lookback`, preregistered; and
>      - (b) a circular or stationary block bootstrap that resamples whole `time_block_id`s, recomputing `θ̂` as a ratio estimator (sum of scores / number of eligible cells), so blocks with few eligible cells are handled correctly.
>
>      Both are reported. The wider interval governs.
>    - **ESS** `= C · var̂_iid(s) / σ̂²_HAC`.
>    - **Every result reports:** rows, contracts, cells, blocks, and ESS. Row counts are never called sample size.
>    - **Joint resampling.** Multi-venue and multi-asset metrics (a pooled BTC + gold portfolio, or cross-venue line shopping) resample the **same** calendar blocks for every asset and venue, so cross-sectional correlation is preserved.
>    - **Daily P&L, drawdown, and losing streaks** use the stationary bootstrap of daily P&L, with the mean block length preregistered.

Why cells and not rows:
- Within a cell, rows from multiple strikes, venues, and decision times share one or two fixings. Their outcome correlation is close to 1, so they add almost no outcome information.
- Across cells, outcomes of non-overlapping increments are close to independent under a martingale. Losses are still autocorrelated, through volatility clustering, liquidity regimes, and nested hourly contracts. HAC or block resampling captures that.

### Item 8: multiple decision rows per contract

Agreed, with one clarification. "One preregistered decision rule per cluster" should read **per contract per venue** for strategy evaluation, with cell-level aggregation for inference. Otherwise a cross-venue pair is forced into one decision, which is a different strategy. Training weights: each contract's rows sum to `1/n_contracts_in_cell`, so a cell's total weight is fixed (Policy 7).

### Strikes within an event

- They share the fixing, and their outcomes are monotone in the strike.
- For evaluation, either:
  - score all strikes inside the cell score `s_c` (the probability-surface view); or
  - preregister a strike-selection rule computable at decision time.

  "The strike with the largest model edge" is acceptable only if that rule is the strategy itself and is fixed before inspection. Selecting the best-edge strike per cell is a maximum over correlated noisy estimates, so it is biased upward. Its bias must be estimated by the block bootstrap of the **whole selection procedure**, not of the selected trades.

### Overlapping windows (one hourly contract covering four 15-min windows)

- They are separate cells, and that dependence is serial.
- Required controls: walk-forward embargo ≥ max contract life (S-3), block length ≥ max contract life + lookback (S-4), and per-horizon reporting.
- A strategy holding both the hourly contract and the 15-min contract ending at the same instant has **one** exposure to the terminal fixing. Phase 4.5 correlated-exposure caps must aggregate by `outcome_cell_id` and by overlapping information interval.

### Cross-asset

- Keep separate cell grids. Use a common calendar block grid for joint inference (S-4).
- A pooled hierarchical model must pass a leave-asset-out or asset-specific walk-forward test before pooled N is cited.

### S-5 (MAJOR): power and the estimand

- The batch 2 figure, (2.8 × 0.5 / 0.02)² ≈ 4,900, is the sample size for detecting a 2-point shift in an unpaired binary mean.
- **The estimand that tests "information not already in the price" is the paired difference** `d_c = ℓ(model) − ℓ(market-implied)` per cell. Its SD is set by how far the two forecasts disagree, not by outcome variance. It is typically far below 0.5 in Brier units. This test is likely feasible over a realistic span.
- **After-cost EV on the traded subset is a different estimand.** Its N is the number of traded cells, discounted by ESS. Illustration only, with assumed values and no data:

  | Assumption | Value |
  |---|---|
  | Cells per day | 96 |
  | Fraction traded | 20% |
  | ESS ratio | 0.5 |

  Under these assumptions there are about 9.6 effective traded cells per day. With σ ≈ 0.5 per unit stake and a 2-point net edge, that is ≈ 4,900 / 9.6 ≈ 510 days of protected capture. A protected period of a few months may therefore only **bound** EV (an upper confidence limit), not confirm it.
- The owner should know this before choosing `T0` and the span. The Phase 5 and Phase 7 criteria should be written as preregistered lower confidence bounds with a stated α.

**Proposed wording** (replaces item 6):

> 6. **Power (F-07).**
>    - Preregister a primary confirmatory estimand: the paired per-cell loss difference against the executable-price-implied probability, on eligible `RECEIPT` cells.
>    - Preregister a secondary estimand: after-cost EV per traded cell.
>    - For each, the required effective N is `n = ((z_{1−α/2} + z_{1−β}) σ_s / Δ)²`. `σ_s` and the ESS ratio are estimated on development `RECEIPT` data only.
>    - The required protected span is `n / (cells per day × eligible fraction × traded fraction × ESS ratio)`.
>    - Rows, strikes, and venues add no independent samples.
>    - If the secondary estimand cannot reach power within the planned span, record that before `T0`. The holdout then tests incremental information and bounds EV.

---

## 3. Phase 2 statistical design generally

### S-6 (MAJOR): past-only outlier detection

- §9 lists "the reversion pattern of a fat-finger print". That pattern can only be recognized after the reversion, which is future data.
- More generally, a bad tick that was in the feature inputs at decision time would also have been in them live. Excluding the decision row later, because the tick was eventually identified as bad, removes exactly the rows on which a live system would have been misled. That inflates backtest quality.

**Proposed wording** (§9, replacing the fourth bullet and adding a rule):

> - the reversion pattern of a fat-finger print. This flag is **future-confirmed**. It carries `flag_known_at` = the receipt (or synthetic availability) of the confirming observation. It may be used for underlying-series audit and label-side reference checks. It never feeds features or decision eligibility at decision times before `flag_known_at`.
>
> **Eligibility uses only flags known at decision.** A decision row may be excluded or down-weighted only by flags whose `flag_known_at + min_latency ≤ decision_time`. Rows whose inputs were later found bad stay in evaluation. The exclusion ledger counts them as `input_later_flagged`, and results are reported with them.

### S-7 (MAJOR): post-decision changes of terms

- The text "a spec version that changed between decision and `ref_end` (the question changed)" (§12), and `contract_terms_changed_before_reference` in the PIT architecture, use information after the decision.
- **For training labels** this is acceptable and correct. The label answers a different question from the one priced.
- **For economic evaluation** it is a future-informed filter, of the same kind as the early-close warning. A live position would have been held through the change. If strike changes or early closes correlate with the path, excluding them inflates EV.

**Proposed wording** (§12, after the bullet):

> This exclusion applies to **training labels only**. In economic and strategy evaluation, such decisions stay in, with P&L computed under the venue's actual handling of open positions through the change. If that handling is unverified, the decision is a scored loss under a preregistered conservative rule. The rate is reported per series.

### Imputation (§8)

The approach is sound: no imputation by default, fitted inside the fold. One addition (MINOR): "a cross-source fill" must use only observations of the second source whose own availability (`RECEIPT` or `SYNTHETIC_ARCHIVE`) satisfies `available_at + min_latency ≤ decision_time`. A fill from a source with a different latency profile is a timing assumption, not a value assumption.

### Missing-not-at-random (§8, §13)

The ledger and with/without sensitivity analyses are right. Two additions:
- **Live-reproducibility rule.** Every decision-row exclusion must be applied identically by the live system: a rule computable from information available at decision. Otherwise the backtest evaluates a population that live trading never meets. Exclusions that are not live-computable are label-side or audit-only.
- **Primary designation (S-17).** "Results are shown with and without flagged rows" doubles the reported analyses. Preregister which one is primary. The other is a sensitivity analysis, and only the primary counts toward gate criteria.

### Quality tiers (§14)

Agreed. Add (MINOR): "Each source's tier is assigned and recorded before any outcome-dependent result using that source is inspected. A later re-tier is a dated record with its evidence, and every earlier result is re-reported under both tiers."

### S-9 (MAJOR): mixing archive and receipt rows in one development pool

**Why "report separately" is not enough.**
- Archive rows are chronologically older and receipt rows are newer. Any difference between them confounds four things:
  1. archive artifacts: synthetic availability, end-of-life metadata, no books, candle semantics;
  2. market evolution: participation, maker programs, fees, efficiency;
  3. regime;
  4. sampling noise.
- A walk-forward fold that trains on archive and validates on receipt measures all four at once.
- Shift risks that are specific to this mixture:
  - Book features exist only on receipt rows. A model trained on the mixture either drops them, or learns from structurally missing values that are perfectly correlated with the data domain.
  - `SYNTHETIC_ARCHIVE` features are systematically staler or fresher than live features, depending on `L`.
  - Archive universes are activity-selected (S-16).

**Repair [RECOMMENDATION].**
1. **Overlap calibration window.** Choose a development period, before `T0 − m`, that PMV captures live **and** later acquires from the same archive sources. The same contracts then exist in both representations. The paired comparison per contract measures:
   - the archive artifact: L, missing markets, candle-close semantics, print coverage;
   - the difference in model output between the two representations, without the calendar-time confound.

   This is the only design that identifies the archive artifact. It is outcome-dependent development work, so it stays in the development pool. It needs H-2 release, the H-7 acquisition approval, and a declared development subset.
2. **Covariate-shift diagnostic** (no outcomes needed). A classifier two-sample test on feature vectors (archive vs receipt, in matched calendar periods where possible). Large separability means pooled results do not transfer.
3. **Selection on RECEIPT only.** Any fold whose result chooses features, model family, hyperparameters, calibration, thresholds, or policy validates on `RECEIPT` and `PIT_CAPTURED` rows. Archive-validated folds are discovery only.
4. **`availability_class` and `metadata_pit_class` are never model features.** Live is always `RECEIPT`, so a domain indicator learns an offset that never applies at decision time.
5. **Ablation:** receipt-only training vs archive + receipt training, both validated on receipt folds. Archive data stays in the candidate's training set only if it improves the receipt-validated paired loss beyond its block-bootstrap interval.

**Proposed wording** (replaces the last bullet of "The split"):

> - **A cycle's development data may mix historical archive rows and PMV-captured rows. Mixing is governed by these rules:**
>   - Every result reports `RECEIPT` and `SYNTHETIC_ARCHIVE`, and `PIT_CAPTURED` and `POST_HOC`, separately.
>   - Any validation result used for selection is computed on `RECEIPT` + `PIT_CAPTURED` rows only.
>   - `availability_class` and `metadata_pit_class` are never model inputs.
>   - Archive rows stay in the candidate's training set only if a preregistered ablation shows improvement on receipt-validated folds.
>   - Archive artifacts are quantified on an overlap calibration window, captured live and acquired from archive, before `T0 − margin`.
>   - Covariate shift between the classes is tested on features alone.
>   - After-cost EV claims rest on `RECEIPT` rows with live books.

---

## 4. H-1 holdout formation under the new process

### Options

- **(a) Mechanical partition of an unexamined historical snapshot.**
  - The newest part of the snapshot is quarantined.
  - Its rows would be `SYNTHETIC_ARCHIVE` / `POST_HOC` with no books. The holdout would then test a data representation the live system never sees. It could not support after-cost EV (batch 2 §5).
  - It is contaminated by F-06 wherever it precedes an agent model's training cutoff. Current agent models have a cutoff around mid-2026. Coarse knowledge of BTC and gold paths (major rallies, crashes, volatility episodes) is plausibly in model weights. Precise 15-min paths are unlikely to be memorized. Regime knowledge is what biases filter, regime, and threshold design, though, and that is exactly the kind of influence a holdout must exclude.
  - It also consumes the most recent, and most live-relevant, historical data as a one-shot test.
- **(b) Prospective protected period from `T0`.**
  - It is the only formation that can carry receipt times, live books, and PIT metadata.
  - It is the only one guaranteed to postdate **current** agent models' training data.

### S-10 (MAJOR): (b) is necessary but not sufficient for F-06

1. **Model upgrades.** If any agent model used in development before the holdout opens has a training cutoff after `T0`, the prospective period is no longer unknown to development. Holdouts can take a year or more to accumulate (S-5), so this is likely, not hypothetical.
2. **Real-time incidental exposure.** During accumulation, agents doing web research, and the owner in conversation, will meet current BTC and gold prices and news. Fine-grained intra-window paths (what reconstructs a 15-min outcome) are avoidable. Coarse levels and regime news are not. The embargo should say which granularity it guarantees.
3. **A third route:** the protected data could leak through derived development work. Example: a monitoring dashboard built during accumulation that summarizes live capture. The guard already covers this. It is noted here for completeness.

**Proposed conditions [RECOMMENDATION]:**
- **Model-cutoff register.** Record each agent model's documented training cutoff in every development session record and in the cycle's gate record. A model with a cutoff later than `T0 − m` may not be used for development of that cycle's candidate. If it is used, a contamination event is recorded under HOLDOUT_ACCESS_LOG.md. This is a governance addition and needs owner approval.
- **Embargo granularity.** Agents must not request, fetch, or derive any price, index, or contract data for `[T0 − m, E + m + lag)`. Incidental exposure to coarse daily-level news is a disclosed limitation. Any **regime-conditional** design element (volatility filters, session filters, regime thresholds) must be justified from development data alone, and its first version recorded in the experiment ledger with its date. A regime element first proposed after `T0` is flagged for the auditor.
- **Optional, stronger:** freeze the candidate **search space** (feature families, model families, the regime variables allowed) at `T0`. Development after `T0` then tunes inside that space only.

### Optional historical lockbox (recommended in addition to (b))

- The newest historical slice before `T0 − m` (for example the last ~20% of the historical development span) can be reserved as an **outer-development lockbox** under Development-Validation Discipline. It is opened once, for preregistered selection control, before the audit candidate is fixed.
- Under P2 it is development data, never holdout, and it is consumed on use. It gives a pre-prospective check against overfitting to the historical pool (S-15).
- It shares the F-06 weakness, so it is evidence against overfitting, not against model-knowledge bias.

### S-11 (MAJOR): reading "~70/30"

START_HERE.md Phase 2 allows the allocation "across the planned collection span". When development is mostly historical (for example two years of archive and a few months of capture), applying 70/30 to the total makes the protected share arbitrary.

**Proposed reading** (owner interpretation; material, needs approval):
- The ~70/30 target applies to the **PMV-capture span** `[C0, T_end]`, where `C0` is the start of release-eligible PMV capture. So `T0 ≈ C0 + 0.7 (T_end − C0)`. Development receipt data then has about 2.3 times the protected span, enough to estimate `L`, book features, and ESS. Historical data before `C0` is additional development data and does not enter the ratio.
- **Power floor.** The protected span must also be at least the power-required span for the primary estimand (S-5). If the power floor binds, it governs, and the ratio is recorded as a deviation.
- **Fixed at `T0`, outcome-blind.** `T0`, the margin, and either a calendar `T_end` or an **outcome-blind stopping rule** are fixed in the gate record before `T0`. A stopping rule example: end when the trusted collector's count of eligible cells reaches `N_req`, counted without prices or outcomes, or at a calendar maximum. Extending the period after any protected outcome or derivative has been seen is optional stopping and is forbidden.

**Proposed wording** (replaces the "Sizing" bullet of "The split"):

> - **Sizing.**
>   - Under prospective formation, the "~70/30" target applies to the PMV-capture span `[C0, T_end]`, not to historical development data.
>   - The protected span must also meet the F-07 power requirement for the preregistered primary estimand. Where the two conflict, power governs and the deviation is recorded.
>   - `T0`, the margin, and either `T_end` or an outcome-blind stopping rule (an eligible-cell count from the trusted collector, with a calendar maximum) are fixed in the gate record before `T0`, and are never extended on protected information.

---

## 5. H-3 / H-4 / H-5 point-in-time proposal

### H-3: option D

Sound. It matches the batch 2 recommendation, which an earlier Statistician session authored. Gaps:
- **`METADATA_UNCERTAIN` is MNAR.** Lifecycle-stream gaps cluster in high-traffic periods. The ledger must count these exclusions by regime. Where possible, the sensitivity analysis must include the rows, using the last known version.
- **Snapshot `known_at` is upper-bounded by the poll interval.** Report the share of version changes first learned by poll rather than stream. A high share means `time_remaining` is often stale for live rows too. That is realistic, but it should be measured.
- The fix for S-7 (training-only exclusion) applies to `contract_terms_changed_before_reference`.

### H-4: admission of post-hoc metadata

- The selection-bias warning is correct and important. Excluding early-closed markets selects on an event correlated with the outcome. Report it and do not filter on it.
- **Additional risk.** For `POST_HOC` rows, we cannot know whether a `close_date_updated` was received before a decision. Some archive decision rows would have been `not_open_at_decision` live, and they are concentrated at early determination, which is near-outcome. **Rule:** in economics, any `POST_HOC` decision at or after the realized close gets zero fill, consistent with live order rejection. In training, those rows are excluded as `post_hoc_after_realized_close`. That uses future information, but only to **remove** rows a live system could not have traded on, never to create them, and the count is ledgered.
- **"Independent pre-decision evidence" needs a definition.** If its availability correlates with market activity (popular markets are archived by third parties), admission is itself activity-selected. Restrict it to:
  - (i) PMV's own earlier captures;
  - (ii) a verified series rule fixing the field;
  - (iii) a Q1/Q2 source with a documented `known_at`.
- **Constructive addition: an empirical bound on mutable-field change rates.**
  - From PMV's own lifecycle capture in the development period, estimate the per-series rate of strike, close-time, and tick-grid changes, with an upper 95% bound. This is metadata, not outcomes, but it still needs H-2 release.
  - Admit `POST_HOC` mutable fields for a series only if the upper bound is below a preregistered threshold **and** the archive period's rules version matches.
  - This turns an unverifiable assumption into a measured, bounded risk.
- **Should `POST_HOC` rows be in training at all?** Yes, with conditions [RECOMMENDATION]. Training contamination is self-revealing under RECEIPT-only selection and evaluation (S-9). A model that learns a leaky archive relationship performs **worse** on receipt folds. It does not show a false edge there. The danger is evaluating on `POST_HOC` rows, not training on them.

  **Proposed wording** (replaces "for training if the owner approves"): "admissible in training only when selection and evaluation are on `PIT_CAPTURED` + `RECEIPT` folds, and when the preregistered ablation (`docs/phase2.md` §The split) shows non-inferiority."

### H-5: synthetic availability and the choice of `L`

**S-8 (MAJOR; BLOCKING for archive-based EV or lead-lag claims).**
- **Relative latency creates the edge.** The core hypothesis is that prediction-market prices under-react to underlying velocity. That is a lead-lag claim. Its measured strength depends on the **difference** in effective latency between the underlying feed and the prediction-market feed. Suppose `L_underlying` is set too small relative to what PMV would experience live, or `L_pm` too large. The model then "sees" underlying moves before the market price could react, and that looks like an edge.
- **Rule.** For any feature combining sources, the preregistered `L` values must be conservative **in the direction that weakens the hypothesis**: underlying latency at a high quantile, and prediction-market price staleness at a low quantile. The asymmetry is stated explicitly.
- **Latency is not constant.** Latency spikes cluster in fast markets, which is where velocity edge would live. A constant median `L` is anti-conservative exactly there. Use a high quantile (for example the 99th percentile) of PMV's measured `received_at − event_time`. Once measured, condition it on an activity bucket computable at decision time.
- **Preregistered `L` sweep.**
  - Report the primary `L` and a fixed ladder, for example ×0.5, ×1, ×2, ×4 of primary.
  - An edge that decays steeply with `L` is presumed a timing artifact.
  - The curve also sets the execution latency budget.
  - Only the primary `L` counts toward conclusions. The ladder is logged as research degrees of freedom.
- **Execution price.** Archive prints are prices at which someone **else** traded, often an informed taker. A simulated fill at the print price, or at a candle close, is optimistic and selected on liquidity. Without books, archive rows support **predictive-information** claims only. No EV claim is made from them, and fill simulation on archive rows is labeled "indicative, not executable".
- **First cycle.** No PMV latency measurement exists yet. The default must be large and documented, for example the larger of a documented provider bound and a deliberately long default for streamed prints, and one full period's publication delay for candles. It is stated in the preregistration with its rationale. The numbers are illustrative; no value is proposed here without evidence.
- **Label availability for archive rows** (S-3): a synthetic finalization time, as in the Policy 3 wording.

**Proposed wording** (append to `docs/phase2.md` §4, "Availability"):

> Synthetic latencies are conservative in the direction that weakens the hypothesis under test:
> - underlying sources at a high quantile;
> - prediction-market price staleness at a low quantile;
> - asymmetries stated explicitly.
>
> Every archive-based result reports a preregistered `L` ladder. An effect that does not survive the ladder is treated as a timing artifact. Archive rows support predictive-information claims only, never executable-EV claims.

---

## 6. Missing controls that could make an apparent edge false

### S-12 (MAJOR): decision-time grid

- In archive studies the natural temptation is to create decision rows at trade or candle times.
- Trade arrival is information arrival. Rows created at trade times select on activity, and they treat the print as available and executable.
- **Proposed wording** (new item in Phase 2 eligibility): "Decision times are generated by a preregistered clock rule (for example every `k` seconds from listing, or at fixed times remaining). Event-triggered decision rules must use only past-only triggers that the live system would compute identically. Archive trade or candle times are never decision times by default."

### S-13 (MAJOR): structural breaks

Required strata, each with a preregistered test of the edge for heterogeneity across them:
- **Fee regimes.**
  - Kalshi: maker and combo fee changes around August 20–22, 2026 (batch 2 §7); applicability to BTC series is [UNVERIFIED].
  - Polymarket: a reported introduction of taker fees on short-horizon crypto markets [UNVERIFIED; check official docs].
  - Fees change both cost and **participant behavior**, so efficiency can change at the break. Pre-break edge does not transfer.
- **Tick-size regimes:** Kalshi `price_level_structure_updated`; Polymarket finer ticks near the extremes [UNVERIFIED].
- **Product maturity and edge decay.**
  - Early-life series are thin and inefficient, and edge found there is the most likely to have been arbitraged away.
  - Preregister a **trend test**: the slope of the per-block paired loss difference against calendar time, on development data.
  - A significantly decaying edge must be extrapolated to `T0`, not averaged.
- **Settlement-source or methodology changes** (reference index version), carried in `outcome_reference_event_id`.

### S-14 (MAJOR): reference-source basis

Three different quantities are easy to conflate:
- the model's underlying feature (for example a USDT spot venue);
- the contract's settlement reference (BRTI, Chainlink, Pyth, LBMA);
- the other venue's settlement reference.

Requirements:
- **Features near the strike** use the settlement source, or a modeled basis to it, under its own availability. Otherwise outcomes near the strike are mispredicted systematically, and the error correlates with volatility.
- **Cross-venue "arbitrage" or near-arbitrage** P&L must be computed with both legs settled on their **own** references. The basis-disagreement rate near the strike is reported. A model that profits mainly from cross-venue reference disagreements has a basis bet, not an arbitrage.
- **The disagreement rate between venue result and recomputed reference** (§12) is reported by distance to strike.

### S-15 (MAJOR): research degrees of freedom on a large historical pool

- "Use aggressively" means many experiments on the same development data.
- Required:
  - the experiment ledger (already required);
  - nested walk-forward;
  - the optional historical lockbox (§4);
  - a **policy freeze per pool**: exclusion, imputation, availability, and duplicate policies are frozen before the first outcome-dependent inspection of that pool. A later change is a new policy version, all prior results are re-run under it, and it is counted as a research degree of freedom.
- Agents' knowledge of historical regimes biases development choices toward fitting known history. Only the prospective holdout (§4) protects against this. Development performance on historical periods should be treated as optimistic by construction.

### S-16 (MAJOR, partly unresolved): universe survivorship

Sources of survivorship:
- Kalshi `is_provisional` removal;
- Polymarket markets hidden or removed from discovery APIs;
- vendor coverage that starts when a product became popular.

Bounding strategies:
- for on-chain venues, enumerate the universe from creation events (on-chain condition preparation), not from API listings;
- compare archive universe counts against PMV's lifecycle-enumerated universe on the overlap window (§3, S-9);
- report results on the subset where the universe is provably complete, as a sensitivity analysis.

If no bound is possible for a source, its archive universe stays discovery-only.

---

## 7. Recommendations for owner decisions (recommendations, not decisions)

- **H-1 (holdout formation): recommend (b) prospective, with conditions.**
  - Model-cutoff register and contamination rule (S-10).
  - Explicit embargo granularity.
  - `T0`, the margin, and `T_end` or an outcome-blind stopping rule fixed at `T0` (S-11).
  - ~70/30 read over the PMV-capture span, with a power floor (S-11).
  - Optionally, a historical outer-development lockbox.
  - Start capture as early as possible: the protected span is the binding constraint.
- **H-3 (point-in-time metadata): recommend option D**, with the `METADATA_UNCERTAIN` regime ledger, a poll-vs-stream `known_at` report, and the S-7 training-only exclusion.
- **H-4 (post-hoc metadata): recommend adopting it with amendments.**
  - Tighten the definition of "independent pre-decision evidence".
  - Admit mutable fields for a series only under an empirically bounded change rate from PMV lifecycle capture.
  - `post_hoc_after_realized_close` handling (zero fill in economics, excluded in training).
  - `POST_HOC` rows allowed in training only under RECEIPT-only selection and evaluation and a non-inferiority ablation.
- **H-5 (synthetic availability): recommend synthetic availability over forbidding archive rows**, with:
  - hypothesis-weakening asymmetric `L`;
  - a high quantile rather than a median;
  - a preregistered `L` ladder;
  - synthetic finalization time for labels;
  - no executable-EV claims from archive rows.
- **H-6 (unit of independence): recommend replacing `dependence_cluster_id`** with `outcome_cell_id` (fixed grid), `time_block_id` (calendar blocks), and contract-information-interval purge (S-1 to S-4). This is **blocking** for any split or cycle registration. After adoption it needs Independent Statistical Auditor review, because the development Statistician co-authored it.

## 8. Remaining uncertainty

- The actual contract rules (UR-4) remain unverified: reference windows, up/down vs fixed strike, averaging. The grid `G` and `Δ_label` depend on them.
- Whether short-horizon gold contracts exist is unverified (UR-5). The gold grid and block definitions are placeholders.
- Every numeric illustration here is an assumption, not data. Nothing in this review shows the presence or absence of an edge.
