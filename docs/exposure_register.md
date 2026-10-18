# Exposure Register

This register is append-only. It records information that could bind the formation of a protected holdout but that HOLDOUT_ACCESS_LOG.md cannot record, either because no evaluation cycle exists yet or because it concerns the development models themselves.

**Owner basis:** batch 4 decisions H-1 and H-8 (`docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`). Part A carries forward the pre-cycle exposure register in `docs/decisions/2026-10-16_phase1_batch3_historical_data_strategy.md` (Red-Team RT-B3-09), which stays the original record.

**Status:** this file is not part of HOLDOUT_ACCESS_LOG.md and does not change its structure. Once a cycle is registered, exposures that touch that cycle's protected scope are contamination events in HOLDOUT_ACCESS_LOG.md, not entries here. Exposures that do not touch a registered cycle's protected scope continue to be appended to Part A; they matter for later cycles and for development-pool degrees of freedom. The cycle's `cycle_registered` event cites this file by hash. This file is governance evidence that cannot be recreated, and is inside the verified-checkpoint backup scope (`docs/backup_and_recovery.md`).

**Rules:**
- Rows are appended, never edited or deleted. A correction is a new row that names the row it corrects.
- No value, outcome, price, or statistic is recorded. Only the source, observable family, period, and granularity are.
- A date or period end is read as the last instant (UTC) of the stated day or period, and every binding inequality is strict.

## Part A: pre-cycle incidental exposure

Incidental exposure of development agents to real observations, through public research, before a cycle exists.

**Binding rule (H-1).** A cycle's protected interval start `T0` satisfies `T0 − m` > the latest end of any Part A row for each protected observable family, and `T0 − m` > the cutoff of every Part B model planned at registration for the cycle's development.

Opening a page whose subject is data or statistics of a protected observable family counts as exposure for the period it covers, whether or not a value was noticed (CLAUDE.md, class 2). Periods listed here count as already outcome-inspected for development-pool degrees of freedom (`docs/phase2.md`).

| # | Date (UTC) | Who | Source | Observable family | Period covered | Granularity |
|---|---|---|---|---|---|---|
| X-1 | 2026-10-16 | Two batch 3 research agents (prediction-market and open-data inventories) | HF dataset card `DegenHedge/kalshi-btc-15m` README (`research/sources.md`, batch 3) | BTC: KXBTC15M outcomes, and through them the BTC path | 2026-01-10 to 2026-10-04 | Aggregate: win rate against entry price, strike and price ranges, window anomalies |
| X-2 | 2026-10-16 | Batch 3 research agents | Web search summaries and paper abstracts | BTC and BTC prediction markets; gold price levels | Up to 2026-10-16 | Aggregate claims and coarse recent levels |
| X-3 | 2026-10-16 | Underlying-data research agent | `www.cfbenchmarks.com` BRTI page | BTC reference index | 2026-10-16 (one live value) | Point |
| X-4 | 2026-10-18 | B09 prediction-market research agent | Web-search summaries for a KXGOLD15M settlement query (third-party news snippets) | Gold: Kalshi gold contracts, and through one example window the gold reference (Pyth GOLD) | Aggregate: September 2026. Point: one window around August 2026 (date not stated) | Monthly aggregate volume and fees; one window reference value |
| X-5 | 2026-10-18 | B09 prediction-market research agent | Web-search summaries (vendor and news snippets on Polymarket datasets) | BTC prediction markets (Polymarket, including BTC up/down) | Undated; treated as up to 2026-10-18 | Aggregate row counts and volume totals |
| X-6 | 2026-10-18 | B09 gold research agent | Web-search summary of a Pyth gold-index methodology query, citing the Pyth Terminal | Gold reference (`Metal.Index.GOLD/USD`, `Metal.Index.1OZGOLD/USD`) | One undated snapshot, after 2026-06; treated as 2026-10-18 | Point |

The latest end per family is derived from the rows when a cycle is registered, and is stated in its `cycle_registered` event; it is not maintained by editing. As of row X-3: BTC 2026-10-16; gold 2026-10-16. Later summaries are appended as new lines that name the last row they cover.

As of row X-6: BTC 2026-10-18; gold 2026-10-18. No value from rows X-4 to X-6 was recorded in any PMV file; the research agents reported the events without values (`docs/decisions/2026-10-18_b09_cloud_native_data_strategy.md` §5.2).

## Part B: development-model training cutoffs (H-8)

Prospective formation protects against knowledge the development models already hold only while no model's training cutoff is later than `T0 − m` (Statistician S-10).

**Rules:**
- Each model used for development, research, review, or audit is recorded here by its **resolved, pinned model ID** (never an alias), before it is used for a cycle's candidate. That includes subagent models and any model a tool uses to process fetched content. Each session and subagent record names the resolved ID it ran.
- The cutoff used for H-8 is the **latest** of: the documented training-data cutoff and the documented knowledge cutoff. Where no training-data cutoff is documented, an upper bound is used: the snapshot's documented release date, or failing that the date of the model's first recorded project use. A cutoff with none of these is **unknown**.
- A cutoff stated to a day, month, quarter, or year is read as the last instant (UTC) of that period. It is compliant only if that instant is strictly earlier than `T0 − m`.
- "Use" means any inference whose output can affect, directly or through a person, the cycle's data or label semantics, features, model, hyperparameters, calibration, thresholds, filters, sizing, evaluation plan, or review or audit conclusions, from cycle registration until the holdout is consumed. This includes models the owner consults outside Claude Code. Running a frozen evaluation mechanically is not use.
- Using a model whose cutoff is later than `T0 − m`, or unknown, is a contamination event for that cycle, recorded in HOLDOUT_ACCESS_LOG.md. As approved, H-8 records this; it does not block it. Whether to add a prevention control (model-cutoff enforcement and pinning) is a mandatory owner decision before `T0` (pre-T0 checklist P-1, owner ruling E-B4-2). The preregistered consequence of a confirmed contamination is set at cycle registration (owner ruling E-B4-9(a)): by default a passing result is reported as "PASS, contaminated".

| # | Recorded (UTC) | Model ID | Documented training cutoff | Source of cutoff | Used for |
|---|---|---|---|---|---|
| M-1 | 2026-10-16 | `claude-opus-5-5` | Knowledge cutoff 2026-06 (read as 2026-06-30T23:59:59Z). Training-data cutoff and snapshot release date not recorded; bounded above by first recorded project use (on or before 2026-10-16) | System context of the batch 4 development session, and the self-reports of both batch 4 specialist subagents (Statistician, Reliability / Red-Team), each stating `claude-opus-5-5` with the same knowledge cutoff | Batch 4 development session and both specialist reviews |
