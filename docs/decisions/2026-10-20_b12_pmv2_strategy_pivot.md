# Owner decision: PMV 2.0 strategy pivot, approved with review modifications (2026-10-20)

**Approver:** the project owner. The owner issued "OWNER DECISION — APPROVE PMV 2.0 WITH REVIEW MODIFICATIONS / BEGIN B12 STRATEGY AMENDMENT + REVISED BTC FEASIBILITY PILOT" on 2026-10-20, after reviewing the eight-specialist "PMV 2.0 FULL AGENT ASSESSMENT". The development session wrote this record. It is procedural: the system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

**What this record authorizes:** strategy and governance amendment, and bounded development feasibility work only.

**What it does not authorize:** real-money trading, protected evaluation, paid data, unrestricted bulk acquisition, GCP provisioning, production deployment, or automatic capital scaling. It is not a gate record, a capture approval, a licence determination, or a `T0` declaration. The owner directed this task to stop before fetching Kalshi observation rows, starting Kraken acquisition, prospective capture, GCP provisioning, or any paid resource.

**History is preserved.** The settlement-focused late-window strategy recorded in `docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md` ("Strategy objective") and PROJECT_BRIEF.md §3 is **superseded as the primary objective**. It is **not deleted**: its text stays in place, annotated, and it continues as a nested settlement arm and control (PV-4, PV-14). No earlier decision record is rewritten.

Decision IDs in this record are **PV-1** to **PV-23** ("PMV 2.0"), numbered after the owner's sections 1 to 23.

## Background: the review the decision rests on

- **The proposal.** "OWNER STRATEGY REVIEW — PMV 2.0 VELOCITY / ORDER-FLOW PIVOT" (2026-10-20). It proposed replacing settlement prediction held to settlement with a forecast of short-horizon (about 30–120 s) **executable** prediction-market prices, entry and exit before settlement, dynamic exits, an independent deterministic hard-loss limit, controlled A/B/C feature ablation, a tiered banking architecture, and a commercial-viability review. It was a proposed redesign with conditional research authorization only.
- **The review.** All eight existing PMV specialist roles reviewed it independently and read-only:
  - Quant / Business Lead;
  - Data Scientist;
  - Statistician;
  - ML Engineer;
  - API / Execution Engineer;
  - Risk & Performance Engineer;
  - Reliability / Red-Team;
  - Independent Statistical Auditor, in a fresh-context challenge.
- **Verdicts.** All eight returned **GO WITH CONDITIONS** for "a limited PMV 2.0 BTC feasibility program". They agreed it should be measurement-first, not modeling-first. The Auditor, the Quant / Business Lead, and the Red-Team each said their prior is that neither strategy has a durable net edge at PMV's latency and cost.
- **Review record.** A summary of the eight reviews and their main quantitative findings is in `research/governance/b12_pmv2_specialist_reviews.md`.
- **Evidence limits.**
  - No Kalshi observation has been fetched (B12 status: blocked on AR-B12-1 and AR-B12-2).
  - Every Kalshi liquidity, spread, and depth figure is UNKNOWN.
  - Every fee-dependent number in the reviews used an unverified illustrative taker formula, 0.07·P·(1−P). The owner directed that those numbers are not canonized (PV-21).

## Owner decisions (verbatim, list formatting condensed; each followed by the record's notes)

### PV-1. Preserve current B12 work; reuse the existing branch

> A local branch already exists: `b12/btc-kalshi-pilot`. It was correctly cut directly from final B11: `c986f49227a47b855a547db96e65356f3674a9b8`. It has no commits beyond B11 and is not on origin.
>
> DO NOT delete it. DO NOT create another numbered B12 branch. DO NOT branch from the B11 merge commit. Reuse this branch.
>
> Before modifying the existing uncommitted work: 1. inspect every existing tracked/untracked B12 change; 2. confirm there are no raw observations, credentials, secrets or unsafe artifacts; 3. determine which existing pilot tooling remains valid; 4. preserve useful work rather than rewriting it gratuitously.
>
> If existing work is suitable for preservation as an initial B12 commit, propose the exact explicit staging set before committing. Do not silently discard pre-pivot work.

**Record.** `docs/BRANCH_TIMELINE.md` names B12 as the active branch under this direction. The owner's direction is the designation; the session does not designate its own branch (START_HERE.md "Repository Continuity").

### PV-2. Canonical strategy decision

> The previous settlement-focused strategy is SUPERSEDED AS THE PRIMARY OBJECTIVE. It is NOT deleted.
>
> The new primary question is: Given all information demonstrably available at decision time, what is the probability distribution of future EXECUTABLE prediction-market prices over a short horizon, and can a position be entered and exited with positive expected NET economic value?
>
> Initial research horizons: approximately 30 seconds; approximately 60 seconds; approximately 120 seconds. These are bounded research hypotheses, not permanent settings.
>
> BTC remains the active POC. Gold remains shelved. Polymarket remains deferred.

### PV-3. Correction to the original pivot rationale

> Do NOT document: "the old strategy is invalid because one 0.95 loss offsets nineteen wins" as the mathematical reason for abandonment. The specialist review corrected this.
>
> For a binary contract, ignoring costs: expected P&L = p_true - acquisition price. The payoff ratio alone does not make a high-price trade negative EV.
>
> The real weaknesses of the original strategy are:
> - tail calibration precision relative to a small edge;
> - volatility/jump misspecification;
> - regime dependence;
> - small effective independent sample sizes;
> - clustered outcomes;
> - absence of a clearly articulated counterparty-error mechanism;
> - settlement exposure;
> - uncertainty that any small mispricing survives costs.
>
> Record this correction explicitly. Historical project decisions are preserved as part of the research record.

**Record (the correction, as reasoned by the reviewers; INFERENCE, illustrative).**
- **Why the payoff ratio is not the flaw.** The per-trade P&L standard deviation is √(p(1−p)), which is small at high prices. At the same absolute edge, a 0.95 contract has a higher per-trade Sharpe ratio than a 0.50 contract.
- **What the requirement really is.** A 3-percentage-point tail error (estimate 0.97, truth 0.94) is equivalent to about a 21% error in the 1–3-minute volatility forecast, because Φ⁻¹(0.97)/Φ⁻¹(0.94) ≈ 1.21.
- **How regimes erase the edge.** A 10% mixture of 1.5×-volatility days can erase a 1-point edge.
- **Overall judgement:** "difficult, not statistically unrealistic" for edges of 2 points or more, and unrealistic for a first cycle at edges of 0.5–1 point.
- **The old strategy has never been tested.** No Kalshi row has yet been observed.

### PV-4. Hold-to-settlement kept as a nested arm

> Do NOT remove the settlement strategy entirely. The future decision policy should be capable, subject to risk rules, of comparing: NO TRADE; ENTER / EXIT BEFORE SETTLEMENT; CONTINUE HOLDING; HOLD TO SETTLEMENT.
>
> Settlement is no longer the default monetization path. It remains: a benchmark; an old-strategy control; a potential action if evidence supports it; the residual failure state if an intended exit becomes impossible.
>
> Existing tail calibration and settlement-label work therefore remains useful.

### PV-5. Two-stage model target architecture (working design)

> STAGE 1 — POLICY-INDEPENDENT FORECAST. Estimate a calibrated distribution of future executable prices. At minimum consider: future executable bid; future executable ask; favorable/adverse movement distribution; first-passage probabilities over a SMALL PRE-REGISTERED barrier grid; uncertainty. Do not bake arbitrary stop/target policies into the ML target.
>
> STAGE 2 — DETERMINISTIC ECONOMIC SIMULATOR. Convert Stage-1 forecasts into expected trading economics using: current executable entry; latency; depth; spread; fees; slippage; partial-fill assumptions; exit policy; hard risk constraints. The simulator, not the ML label, handles alternative policies.

**Record.**
- **Settlement probability.** P(contract resolves in our favor | information at decision time) stays a required intermediate output. It anchors the B0 fair value and serves the settlement arm and the failed-exit risk.
- **Policy-dependent labels.** A label of the form "E[P&L | policy]" is not used as the primary learned target, because every change to a stop or target would redefine the label (a leakage and multiple-testing channel). It may appear only as a secondary, preregistered ablation.

### PV-6. Primary execution baseline: taker only

> Until real fill behavior can be measured: BASELINE ECONOMICS = TAKER ONLY. Historical or prospective research may not claim an edge based on assumed maker fills.
>
> Use: latency-shifted quotes; executable bid/ask; depth walking where known; two-sided fees where applicable; realistic spread treatment; stressed slippage. Maker execution may be studied later but may not create the baseline edge.

**Record (structural limit surfaced by the review).**
- Real orders are barred until Phase 12, and demo liquidity is not representative.
- So passive fills, queue position, adverse selection of resting orders, and PMV's own market impact cannot be validated before the protected evaluation (Phase 7).
- A PMV 2.0 protected evaluation can therefore **bound** executable EV, not confirm it.
- This is recorded in START_HERE.md Phase 4.5 and Phase 6.

### PV-7. Statistical unit and trial budget

> Do NOT treat every high-frequency row as independent.
>
> Working inference framework: Training observation: decision instant, with dependence-aware weighting. Validation block: calendar day. Bootstrap: whole-day / stationary block bootstrap. Significance: per-day aggregate statistics with dependence-aware uncertainty. Economics: daily net P&L series. Trades and overlapping horizons are never assumed independent.
>
> Pre-register a finite trial budget. Limit the first feasibility research to no more than: 3 primary forecast horizons and a small frozen exit/barrier grid. Record every attempted configuration.

**Record.** The detailed rules are in `docs/phase2.md` "PMV 2.0 executable-price targets, dependence, and trial budget".

### PV-8. Feature comparison: factorial

> Retain controlled feature-family testing. Prefer the review's factorial interpretation:
> - A: price / volatility / threshold / time baseline;
> - A + PM: add prediction-market microstructure;
> - A + BTC: add underlying BTC order flow / microstructure;
> - A + PM + BTC: combined model.
>
> This avoids automatically crediting one source family for another's signal. Use identical opportunity sets and comparable tuning budgets. Do not claim value from a feature family unless it adds out-of-sample executable economic value.

### PV-9. Banking architecture: owner baseline preserved

> Retain the owner's current governance levels:
> - LEVEL 1: Total strategy-equity milestone approximately $500; maximum active trading pool approximately $100.
> - LEVEL 2: Total strategy-equity milestone approximately $5,000; maximum active trading pool approximately $1,000.
> - LEVEL 3: Total strategy-equity milestone approximately $50,000; maximum active trading pool approximately $10,000.
>
> These are governance/research ceilings. They are NOT real-capital authorization. They do NOT determine individual order size.
>
> Actual exposure remains bounded by: min(level allowance, liquidity capacity, exit capacity, risk limit, economic/model sizing limit).
>
> Record the agent recommendation for intermediate approximately 2–3× capacity steps, such as: $100 -> ~$300 -> $1,000 -> ~$3,000 -> $10,000 as a PROPOSED refinement to evaluate. Do NOT silently replace the owner's L1/L2/L3 structure.

**Record.**
- **Status.** The L1/L2/L3 structure is the owner baseline. The 2–3× sub-steps are a **PROPOSED refinement**, not adopted.
- **Relation to Gate 4.5.** The levels map onto the six Gate 4.5 risk-appetite inputs (bankroll, starting live capital, maximum drawdown, risk-of-ruin tolerance, absolute loss budget, scaling policy), but they do not satisfy them. Those inputs still need the owner's explicit approval at Gate 4.5, with their frozen/adjustable classification.
- **Real capital.** Real capital remains Phase 12 only, with explicit owner approval.

### PV-10. Banking purpose

> Banking does not create trading EV. Its role is: capital isolation; finite loss budgeting; protection of realized/reconciled gains; controlled exposure growth.
>
> Reserve replenishment must be finite. Unlimited or automatic reserve refills are prohibited. The reserve must not become disguised active trading capital.
>
> Preserve the concept of realized-profit sweeps, but do not yet freeze: the $100 -> $250 trigger; exact sweep frequency; exact hysteresis; exact refill count; exact promotion sample requirements. Those must be evidence based.
>
> Maintain a separate tax-reserve concept for future analysis; tax reserves do not count as tradeable reserve capital.

**Record (review findings, synthetic simulation only).**
- **What protects capital.** The protection comes from the static active-pool cap plus a finite absolute loss budget, not from the sweep.
- **What sweeps do.** Sweeps reduce compounding, and they *raise* the active pool's depletion frequency.
- **The risk dial.** Replenishment rules are the dominant risk dial: unlimited refills turn the reserve into trading capital.
- **How ruin is defined.** Ruin is therefore defined on **total strategy equity against the absolute loss budget**, never on active-pool depletion alone.
- **Rules the record applies:**
  - every refill is booked as a realized strategy loss;
  - the drawdown high-water mark is never reset by a sweep or a promotion;
  - sweeps use only realized, reconciled, finalized cash;
  - no runtime key ever holds a transfer permission.
- **Where these rules live.** START_HERE.md Phase 4.5.

### PV-11. Commercial objective

> Remove approximately "1–2% daily compounded capital growth" as a formal PMV requirement. It may be retained historically as an aspirational thought experiment.
>
> The principal commercial measure becomes: expected net cents per contract × realistically executable contracts per day, with uncertainty intervals and capacity curves.
>
> Also report: opportunity frequency; turnover; drawdown; infrastructure cost; data cost; maintenance burden; tax scenarios; capacity.
>
> Do not declare a strategy commercially viable merely because percentage returns appear large at tiny capital.

**Record.** No canonical document contained the 1–2% daily figure: a repository search found none. It existed only in the owner's proposal. This record is the place it is retired as a requirement.

### PV-12. Data priorities

> Historical sources that remain useful: Kalshi market metadata; Kalshi settlements; Kalshi 1-minute bid/ask candles; Kalshi historical trades; fee-change history; Kraken historical trades.
>
> Prospective development data now becomes CRITICAL:
> - KALSHI: book snapshots; book deltas; sequence information; trades; lifecycle events; PMV receipt timestamps.
> - KRAKEN: book state; trades; checksum continuity; PMV receipt timestamps.
>
> Capture both feeds under one disciplined host clock when prospective capture is later authorized.
>
> BRTI 5 Hz rises in research priority because it may be closer to the reference information used by market makers. Do NOT purchase or subscribe to BRTI yet.
>
> Polymarket remains deferred. Tardis remains conditional. Coinbase remains deferred pending BRTI evidence.

### PV-13. Revised historical Kalshi pilot

> The existing Kalshi pilot remains useful but its purpose changes. It is no longer intended to validate PMV 2.0 by itself.
>
> It must establish: contract/label integrity; timestamp behavior; available history; spread behavior; quote staleness; trade activity; executable cost floors; whether coarse 60/120-second movement is large enough even in principle; whether historical lead/lag analysis is meaningful; an old-strategy settlement comparator.
>
> Keep the existing pre-registered P1–P9 where still valid. Before viewing new observations, add:
> - P10: spread at minute boundaries by time-remaining × price range;
> - P11: share of unchanged quotes per minute;
> - P12: trade-arrival rate and inter-trade gaps by time remaining; block-trade share where identifiable;
> - P13: trade timestamp precision and taker-side population;
> - P14: sub-minute trade-print volatility;
> - P15: COST-HURDLE / PERFECT-FORESIGHT CEILING. Descriptively estimate the fraction of historical decision points where the subsequent 60/120-second executable movement exceeds spread + entry fee + exit fee under explicitly labeled fee scenarios. No profitability claim may be made from this;
> - P16: whether any lead/lag relationship is measurable against aligned Kraken trades at the available timestamp precision.
>
> Also profile: early-close incidence; pause incidence.

**Record.** The amended, pre-registered protocol is `research/kalshi/b12_btc_kalshi_pilot.md` §5.

**P16 is split** because this task may not start Kraken acquisition:
- P16a is the Kalshi-side measurability check, run in the pilot;
- P16b is the aligned Kraken cross-correlation, pre-registered now and run only once the DR-3 Kraken archive file exists.

### PV-14. Old-strategy control

> Run the original strategy as a cheap nested control. At minimum: market tail calibration by executable ask band × time remaining; day-blocked confidence intervals; B0 analytic/digital fair value versus executable ask where feasible; implied versus realized volatility.
>
> If the settlement strategy independently demonstrates credible evidence, it continues on its own merits. Do not suppress positive evidence merely because PMV 2.0 is now primary.

**Record.**
- **C1, market tail calibration,** is implemented in the pilot profiler. At pilot scale it is descriptive only.
- **C2 (B0 fair value against the ask) and C3 (implied against realized volatility)** need Kraken prices and a strike knowable at decision time (P5). They are therefore pre-registered and run with P16b.
- **Inferential use** of C1–C3 happens on the development pool after bulk acquisition, under the protocol's pre-registered rules.

### PV-15. Historical pilot stop conditions

> Before seeing observations, define and record stop conditions. At minimum evaluate the specialist proposals:
> - if even a generous/perfect-foresight historical ceiling cannot clear realistic round-trip cost in liquid cells, stop the 30–120-second track;
> - if trade timestamps are too coarse for lead/lag measurement, historical lead/lag analysis stops and that question becomes prospective-only;
> - if candidate cells are overwhelmingly stale/unchanged or effectively untraded, remove those cells from the opportunity universe;
> - if contract/settlement metadata cannot be made point-in-time safe, stop;
> - if fees/terms cannot be established sufficiently for cost analysis, stop.
>
> Do not choose thresholds after seeing the results.

**Record.** The stop conditions and their thresholds are in `research/kalshi/b12_btc_kalshi_pilot.md` §5.6, written before any Kalshi row was seen. Each threshold is a development hypothesis that the owner may amend only **before** the pilot runs.

### PV-16. Future prospective capture: development only

> Do not begin capture in this task. But amend the roadmap so that prospective Kalshi + Kraken capture is the critical PMV 2.0 development dataset.
>
> Designate that future capture span as: DEVELOPMENT ONLY; NEVER PROTECTED.
>
> Do not register a protected T0 yet. Protected evaluation begins only after development capture has supported: target design; latency measurement; fill-model bounds; horizon selection; opportunity definition; power analysis.

**Record.**
- **Name.** The first prospective capture span is called **Span D** in the canonical documents.
- **Status.** Its rows are development-exposed and can never be promoted into a protected holdout.
- **The first protected cycle.** It is registered later, with `T0 − m` after the end of Span D and after every registered exposure and model training cutoff.
- **Cycle deferrals.** The Red-Team recommended a limit on how many times a cycle may be deferred, fixed before `C0`. It is recorded as an open item for cycle registration.

### PV-17. Risk design amendments (requirements for later phases; nothing implemented)

> The stop price is not the ultimate hard-loss bound. The ultimate bound is premium-at-risk / worst-case-position exposure.
>
> Future position sizing must satisfy BOTH: 1. intended stop + stressed slippage risk <= approved stop-risk budget; 2. full premium / failed-exit settlement loss <= approved catastrophic position-risk budget.
>
> Add future requirements for: no-new-entry cutoff before close; earlier forced-flat cutoff; deterministic exit ladder; unintended settlement exposure => RED; exit-failure monitoring; fill-ratio drift; stop-slippage drift; latency p99; depth/capacity stress; fee-change RED condition.
>
> Do not implement live execution yet.

### PV-18. Empty-bid policy: unresolved owner/risk design item

> Do NOT invent a permanent "sell at 0.01 no matter what" rule. Record this as an unresolved owner/risk design item: If the system reaches the forced-exit process and no acceptable executable bid exists, determine the deterministic hierarchy between: progressively more aggressive IOC liquidation versus residual explicitly governed settlement exposure.
>
> No live system may improvise this decision. The failed-exit worst case must already be survivable through the premium cap.

**Record.** This is open item **O-PV-1** below. It blocks Gate 4.5.

### PV-19. Documentation amendments

> Amend, while preserving historical context: PROJECT_BRIEF.md; CLAUDE.md; START_HERE.md; docs/phase2.md; and the relevant agent-role files identified in the PMV 2.0 assessment.
>
> Create a NEW decision record for the owner-approved PMV 2.0 pivot. Do not rewrite historical decision records to make it look as though PMV 2.0 was always the strategy. Annotate/supersede where appropriate.
>
> HOLDOUT_ACCESS_LOG.md remains unchanged unless its actual invariant requires a change.
>
> Update roadmap phase CONTENT but preserve the existing phase ordering unless a concrete incompatibility is discovered.

**Record.**
- **HOLDOUT_ACCESS_LOG.md is unchanged.** Its hash-pinned body contains no strategy-specific text, so no invariant requires a change.
- **Phase ordering is unchanged.** No concrete incompatibility was found. The fill-validation limit (PV-6) is a known constraint, not an ordering conflict: real-fill evidence arrives only in Phase 12, after Phase 7, and that is recorded.

### PV-20. Other review findings, recorded for later work

> Record for later work:
> - Kalshi OpenAPI specification changed between the recorded snapshot and the current public version;
> - P-5 should be completed for Kalshi/Kraken BTC families before prospective capture;
> - current managed domain allowlists deserve re-verification before capture;
> - failure_modes/ is currently empty and must eventually contain the formal failure register.
>
> Do not change sandbox/network policy in this task.

**Record (evidence; nothing was changed):**
- **OpenAPI.** `https://docs.kalshi.com/openapi.yaml` was fetched on 2026-10-20 at about 02:36 UTC (docs class) by the API / Execution review: 378,255 bytes, SHA-256 `25f07afd9c09a7b005b1ccbfc06ad94928aa7d43d837ad3e43b0db7b7fc0283e`, `info.version` 3.34.0. The snapshot recorded in `research/data_sources/schema_profiles/kalshi_markets.md` (2026-10-19T04:18:27Z) was 375,483 bytes, `bd0c218a…`. The specification changed within a day without a version bump. Schema-dependent parsers should pin and re-check the specification hash (logged in `research/sources.md`).
- **P-5.** P-5 (DR-11) is to be completed for the Kalshi and Kraken BTC families **before any prospective capture begins**, not merely before `T0 − m`. That is stricter than DR-11's timing, and it is recorded here as the owner's direction.
- **Managed allowlist.** The Red-Team review read `/etc/claude-code/managed-settings.json` and found venue hosts on the allowlist, including `external-api.kalshi.com`, `kalshi.com`, `api.kraken.com`, and `ws.kraken.com`. Separately, RT-B10-01 recorded that wildcard denies did not block `api.kraken.com`. In B12, the Kalshi data-host request was stopped by the permission classifier; whether the network layer would also have refused it is UNKNOWN. Re-verification is required before capture. No policy was changed.
- **Failure register.** `docs/failure_modes/` is empty. The formal failure register (`docs/failure_modes/FAILURE_REGISTER.md`) must exist before PMV 2.0 execution design begins. It is not created in this task.

### PV-21. Fees and terms

> The agent assessment used an UNVERIFIED illustrative Kalshi fee formula. Do not canonize those numerical cost estimates.
>
> The real current Kalshi fee schedule is still required. Likewise, current terms relevant to: automated access; storage; research/ML use; prospective capture must be classified before the corresponding acquisition/capture stage.
>
> No economics claim before the fee schedule is authoritative.

**Record.**
- **No fee formula is canonized.** The canonical documents state fee effects only qualitatively (two legs, a price-dependent schedule).
- **The pilot profiler takes fee scenarios as labelled parameters.** Its default is spread-only, the most generous cost floor. Every scenario is marked `SCENARIO_NOT_AUTHORITATIVE`.
- **DR-9 is unchanged and binding.**

### PV-22. Validation

> After amendments: run targeted tests for changed tooling; run full check.sh; run git diff --check; review staged files explicitly; verify no raw observations or secrets entered Git.
>
> No: git add . / git add -A / git commit -a / force push / amend / rebase.

### PV-23. Stop before external data access

> For this task: 1. preserve/review the existing B12 work; 2. amend the strategy/governance documentation; 3. amend the historical pilot protocol/tooling; 4. add deterministic tests where required; 5. prepare the exact proposed B12 commit set.
>
> STOP BEFORE: fetching Kalshi observation rows; starting Kraken acquisition; prospective capture; GCP provisioning; paid resources.
>
> Do not commit until owner review.

## Owner pre-commit review (2026-10-20, second direction)

**Source:** the owner's "B12 OWNER REVIEW — CONDITIONAL APPROVAL BEFORE COMMIT".

**Approved:** the PMV 2.0 strategy amendment; reuse of `b12/btc-kalshi-pilot`; **B12 as the ACTIVE numbered branch**; preservation of the old settlement strategy as a nested comparator; the two-stage target architecture; the revised P1–P16 historical pilot; and the four-commit structure, subject to the checks and fixes below.

### Fixes required before commit, and how they were resolved

1. **Duplicate JSON output.** The CLI must emit exactly one report.
   - **Not a real defect.** The working-tree file had a single `sys.stdout.write`, of `build_report(pilot, args.fee_scenario)`; the apparent double write was edit-display context in the transcript.
   - A deterministic CLI test now checks that exactly one JSON document is emitted, that custom scenarios appear, and that `spread_only` is always present.
2. **C1 contract uniqueness.**
   - **A real defect.** The per-side loop could put a YES row and a later NO row from one flipping contract into the same (band, ask band) cell, contradicting the documented claim.
   - **New rule, fixed before any data was seen:** at most one row per contract × band. It is the earliest minute at which either side qualifies. If both sides qualify in that minute, the higher ask is used, and YES on a tie. A later other-side qualification is counted and not used. Synthetic flip, same-minute, and tie tests were added.
3. **Timestamp resolution.**
   - **A real defect.** "Fractional digits present" was treated as sub-second timing: `.000` would have counted as sub-second.
   - P13 now separates no fraction, all-zero fraction, and non-zero fraction; reports the significant non-zero digits and same-timestamp cluster sizes; and derives `observed_resolution` (coarser than a second, sub-second, whole second, mixed, unknown) by pre-registered rules. The raw-string precision profile is kept.
   - P16a and S-2 now use the observed resolution and event dispersion, not formatting.
4. **S-1 semantics.**
   - **Changed.** An S-1 failure returns "HISTORICAL COST-HURDLE SCREEN FAILED — OWNER NO-GO REVIEW REQUIRED". It never advances automatically to prospective capture.
   - The owner may then terminate the 30–120-second path, enlarge the development-only historical sample under a new approved protocol, change the candidate strata for a principled reason, or stop PMV 2.0.
   - Failure of a generous perfect-foresight ceiling is strong negative evidence. No post-result threshold tuning is permitted.
   - A non-failure is not evidence of edge.

### Owner resolutions of the open items (verbatim, formatting condensed)

> **O-PV-1 — EMPTY BID / FAILED EXIT:** REMAINS OPEN. Do not invent a permanent rule in B12. It must be resolved before Gate 4.5 / any live execution design.
>
> **O-PV-2 — BANKING:** Preserve owner L1/L2/L3 baseline. Intermediate 2–3x capacity steps: PROPOSED ONLY. Exact sweep trigger: NOT FROZEN. Exact refill count: NOT FROZEN. Exact promotion evidence: NOT FROZEN.
>
> **O-PV-3 — TRIAL BUDGET:** APPROVE 324 AS AN ABSOLUTE MAXIMUM CEILING. This is NOT a target or allocation. Use fewer configurations whenever the scientific question permits. The exact model/horizon/barrier grid must still be preregistered before the relevant data are evaluated. Every attempted configuration counts against the ledger.
>
> **O-PV-4 — PROTECTED-CYCLE DEFERRALS:** REMAINS OPEN. Resolve when the first protected cycle is actually designed/preregistered.
>
> **B12 STATUS:** APPROVE B12 AS THE ACTIVE NUMBERED BRANCH. Commit 4 may update docs/phase1.md and docs/BRANCH_TIMELINE.md accordingly.

## Old-to-new strategy mapping

| Element | Before (2026-10-16 objective) | After (PMV 2.0, this record) |
|---|---|---|
| Primary question | P(contract resolves in our favor), held to settlement | Distribution of future executable prices over about 30/60/120 s, and whether a round trip has positive expected net value |
| Monetization | Settlement | Exit before settlement. Settlement is a nested arm, a control, and the residual failure state |
| Decision set | Trade / no trade at entry | NO TRADE; ENTER/EXIT BEFORE SETTLEMENT; CONTINUE HOLDING; HOLD TO SETTLEMENT (subject to risk rules) |
| Price region | ~$0.93–$0.97 sweet spot; ~$0.85 floor | No permanent band. The full price range is reported by strata. The tail region is kept for the settlement arm. |
| Time region | Final few minutes | The whole window, by remaining-time strata. The final minutes are reported separately (settlement averaging; exit-failure risk). |
| Learned target | Settlement probability | Stage 1: calibrated distribution of future executable bid/ask and first-passage on a small preregistered barrier grid. Settlement probability is kept as a required intermediate output. |
| Economics | Executable break-even probability at entry; one fee | Stage 2 deterministic simulator: taker-only, latency-shifted, two legs, depth-walked where known, stressed slippage |
| Calibration focus | High-probability-tail calibration | Calibration of executable-price distributions and first-passage probabilities. Tail calibration is kept for the settlement arm. |
| Statistical unit | `outcome_cell_id`, `time_block_id` (H-6) | Unchanged in principle. Decision-instant rows are dependence-weighted; day blocks; per-day aggregates; daily net P&L. ≤3 primary horizons; finite trial budget. |
| Feature comparison | Not specified | Factorial A, A+PM, A+BTC, A+PM+BTC |
| Hard loss bound | Premium (implicit) | Premium-at-risk cap **and** stop-plus-stressed-slippage cap. Stops are attempts, not bounds. |
| Data critical path | Historical Kalshi plus Kraken; capture in parallel | Historical for screening and the control; prospective Kalshi plus Kraken capture (Span D, development only) is the critical development dataset |
| Commercial measure | — (1–2%/day appeared only in the proposal) | Net cents per contract × executable contracts per day, with intervals and capacity curves |
| Banking | — | Owner L1/L2/L3 baseline as ceilings; finite refills; tax reserve separate; no EV claimed |

## What stays unchanged

- The BTC active POC, with gold shelved (DR-17).
- Polymarket deferred.
- The shared platform plus market-family-specific models (DR-20), with B0/B1 first (DR-21). Under PMV 2.0, B1 becomes the "no change in executable price" baseline, and B0 becomes BTC-driven fair-value repricing with a lag.
- No LLM or agent in the runtime.
- Chronological development only.
- The prospective protected evaluation (H-1) and the `T0`/`T0 − m` rules.
- Exposed observations are never protected.
- The exposure register and the Protected Information Rule.
- PAUSE / KILL; fail-closed circuit breakers; caps override model confidence.
- No real capital before Phase 12 and explicit owner approval.
- DR-9 (no economics claims before the fee schedule is versioned).
- The DR-8 capture list and preconditions.
- The phase order 0–12.

## Applied in this record's commit set (branch `b12/btc-kalshi-pilot`; proposed, not yet committed)

- `PROJECT_BRIEF.md` §1, §3, §4, §5, §7, §9, §11: annotated amendments. The late-window subsection is retained and marked superseded as primary.
- `CLAUDE.md` "Strategy Scope", "Prediction Objective", "Economics", "Risk": amended.
- `START_HERE.md` "Strategy at a Glance", Phase Roadmap rows 1–2, Phases 1, 2, 3, 4.5 and 6: amended content. The order is unchanged.
- `docs/phase2.md`: the PMV 2.0 targets, dependence, and trial-budget section; a settlement-comparator note on the strategy strata; PMV 2.0 strata; Gate 2 deliverables.
- `.claude/agents/data-scientist.md`, `statistician.md`, `risk-performance-engineer.md`: amended role text, with owner approval under PV-19.
- `research/kalshi/b12_btc_kalshi_pilot.md`: the amended protocol (P1–P16, C1–C3, stop conditions, trial budget).
- `src/pmv/pilot/kalshi_btc.py`, `tests/unit/test_pilot_kalshi_btc.py`: P10–P16a, lifecycle incidence, C1, labelled fee scenarios, and a defect fix (an absent `taker_outcome_side` no longer makes a trade malformed).
- `research/governance/b12_pmv2_specialist_reviews.md`: the review summary.
- `research/sources.md`: the 2026-10-20 documentation fetches.
- `docs/phase1.md` current status, and `docs/BRANCH_TIMELINE.md` (B12 row).
- Annotations, not rewrites, in `docs/decisions/2026-10-19_owner_data_readiness_decisions.md` (DR-2) and `docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md` (strategy objective).

## Open owner items after this record

- **O-PV-1 (PV-18): OPEN** (owner, 2026-10-20). The empty-bid forced-exit hierarchy: progressively more aggressive IOC liquidation versus residual, explicitly governed settlement exposure. B12 sets no rule. It must be resolved before Gate 4.5 and before any live execution design.
- **O-PV-2: PARTLY RESOLVED** (owner, 2026-10-20).
  - Resolved: the L1/L2/L3 baseline is preserved, and the 2–3× sub-steps are PROPOSED ONLY.
  - Still open and evidence-based: the sweep trigger, frequency, hysteresis, refill count, and promotion evidence, which are NOT FROZEN.
- **O-PV-3: RESOLVED** (owner, 2026-10-20).
  - **324 configurations is an absolute maximum ceiling, not a target or an allocation.** Fewer are used whenever the scientific question permits.
  - The exact model, horizon, and barrier grid is preregistered before the relevant data are evaluated.
  - Every attempted configuration counts against the ledger.
- **O-PV-4 (PV-16): OPEN** (owner, 2026-10-20). The protected-cycle deferral limit is resolved when the first protected cycle is designed and preregistered.
- **Carried forward, unchanged:**
  - AR-B12-1 (Kalshi host route; recommendation: owner-run option A);
  - AR-B12-2 (Developer Agreement and Terms of Service copies);
  - the B12 guard-exception confirmation (`research/kalshi/b12_btc_kalshi_pilot.md` §2.3);
  - DR-9 (fee schedule);
  - DR-3 (Kraken terms classification);
  - DR-8 capture preconditions;
  - P-5 for these families before capture (PV-20);
  - DR-22.
