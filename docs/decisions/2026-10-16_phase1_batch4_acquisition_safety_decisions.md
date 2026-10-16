# Phase 1 batch 4: owner decisions on acquisition safety and holdout formation (2026-10-16)

**Approver:** the project owner, in the batch 4 charter given on 2026-10-16 (branch `phase1/acquisition-safety-decisions`). The charter states the decisions below as approved and instructs the governance edits listed under "Documents changed". The development session wrote this record. The owner should confirm its wording before merge.

**Limitation:** this record is procedural. The system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

**This is not a gate record.** It passes no gate. It declares no cycle, no `T0`, no split, and no protected scope. It authorizes no acquisition, download, credential, account, purchase, or release of any real observation. No real market dataset was acquired or inspected in this batch.

The decisions below were raised, not taken, in `docs/decisions/2026-10-16_phase1_batch3_historical_data_strategy.md`. The full analysis is in `research/historical_data/` (`feasibility_summary.md`, `point_in_time_metadata_architecture.md`, `statistician_review.md`, `red_team_review.md`). Where the owner's wording here differs from a batch 3 recommendation, **the owner's wording governs**.

## Decisions taken by the owner

### H-1. Prospective protected holdout

The protected holdout is **prospective**. It begins at a declared future start `T0`, after the existing pre-cycle exposure window. Its conditions are recorded before any release to agents.

- **Binding rule.** `T0 − m` (where `m` is the cycle's declared margin) is later than the end of every registered pre-cycle exposure of the protected observable families. Today that end is 2026-10-16 for BTC and gold (`docs/exposure_register.md`, X-1 to X-3). It is also later than the training cutoff (`docs/exposure_register.md` Part B) of every model planned at registration for developing the cycle's candidate. A model adopted later is governed by H-8. Dates are read as the last instant (UTC) of the stated period, and the inequality is strict.
- **Recorded at cycle registration, before any release, in the cycle's gate record and HOLDOUT_ACCESS_LOG.md `cycle_registered`:**
  - `T0`, `m`, and `C0` (the start of release-eligible PMV capture);
  - the embargo granularity (observable families, and the equivalent observables they include);
  - `T_end`, or an outcome-blind stopping rule (an eligible-cell count from the trusted collector, with a calendar maximum);
  - the power floor for the preregistered primary estimand;
  - a citation, by hash, of the exposure register (H-8 and the pre-cycle part);
  - the preregistered outcome if the calendar maximum is reached before the eligible-cell count. Default: evaluate once at the calendar maximum against the unchanged PASS / FAIL / INCONCLUSIVE criteria, with the power shortfall recorded;
  - the preregistered technical contingencies (for example a collector outage) under which the end may move, and the mechanical rule for moving it, which depends only on the trusted collector's outcome-blind eligible-cell count.
- **Change control** *(Statistician B4S-8; for owner confirmation, because it refines owner-attributed text)*. These conditions are never changed on protected information. After `T0 − m` they are not changed at all, except mechanically under a preregistered technical contingency. Any amendment, including one before `T0 − m`, is a logged HOLDOUT_ACCESS_LOG.md event giving its reason and the information it used. A discretionary change after `T0 − m` is treated by the auditor as potentially informed by protected outcomes.
- **Power floor.** Where no development `RECEIPT` data exist at registration, as in the first cycle, the floor uses documented, conservative assumed values with a sensitivity table (`docs/phase2.md` Policy 6).
- **Sizing (Statistician S-11, adopted by this decision).** The approximately 70/30 target applies to the **PMV-capture span** `[C0, T_end]`, where `C0` is the start of release-eligible PMV capture. It does not apply to historical development data. The power requirement is a floor: where the ~30% target falls short of it, the protected span is lengthened (by a later `T_end` or a larger stopping count, never by an earlier `T0`), and the deviation is recorded.
- **Historical data.** Every admissible observation before `T0 − m`, historical or captured, may become development data for the cycle, subject to the contract-interval eligibility rule in `docs/phase2.md` (Policy 2): a labelled contract is development-eligible only if `ref_end + Δ_label < T0 − m`, and the label's own observation or receipt time also precedes `T0 − m`. No period or observation that has been exposed to development, historical or PMV-captured, may later be promoted into a protected holdout (batch 3 P2).
- Formation (a), a mechanical partition of an existing historical snapshot, remains allowed by START_HERE.md for a later cycle only where the snapshot is genuinely unexamined. It is not used for the first cycle. A snapshot is genuinely unexamined only if its whole period, including margins, satisfies the same binding rule as a prospective `T0`: it begins more than `m` after every registered exposure of its observable families and every recorded training cutoff of the models used, and no row or equivalent observable from it has been released.

### H-2. Owner-controlled, fail-closed, per-row release

- Release of real observations to agents is **owner-controlled** and **fails closed**.
- Eligibility is cut **per row**, and per equivalent observable, by a deterministic trusted release tool. Cutting only by file, download, or request boundary is not sufficient (Red-Team RT-B3-02).
- This adopts the F-08 architecture: a trusted collector or acquisition tool writes into the protected raw store outside agent sessions, and an owner-run release step gives agents only rows whose observation time, and the time of every equivalent observable, falls before the declared development boundary. One mechanism serves live captures and historical acquisitions.
- **Until that tool is built, reviewed by Reliability / Red-Team, and committed, nothing is released.** The deterministic data-access guard stays the only access path, and with an empty registry it refuses every real request.
- The guard prerequisites in `docs/protected_information.md` that F-08 would make unnecessary (items 1, 3, 7, 8, and 9) are not retired by this record. They are retired only by an owner-approved governance change, made after the release tool is built and committed, implements the RT-B3-02 release properties with the single content-derived equivalence catalog (RT-B3-05) and the durable first-release record (S-4), and has passed Reliability / Red-Team review with no unresolved BLOCKING finding. While both controls exist, a real observation reaches an agent only if every applicable control allows it, and any disagreement fails closed.

### H-3. Point-in-time metadata: Option D

Adopt Option D from `research/historical_data/point_in_time_metadata_architecture.md`:
- **append-only metadata observations** keyed by PMV receipt time, as the source of truth;
- a **derived, versioned lookup or view** built from them;
- **periodic reconciliation snapshots**;
- later metadata **never** leaks backward into an earlier decision. A lookup for decision time `t` uses only observations received at or before `t`.

### H-4. Post-hoc archive metadata

Post-hoc archive metadata is **admissible** for:
- discovery;
- data cleaning;
- pilot modeling;
- historical predictive research.

It is **not**, by itself, proof of executable historical EV, unless decision-time availability of each field used can be justified. Rows that use it carry `metadata_pit_class = POST_HOC` and are reported separately (`docs/phase2.md`).

### H-5. Historical availability assumptions

Every availability assumption for an archive row without a PMV receipt time is:
- **explicit**, recorded with a `policy_id`;
- **fixed before the experiment**, before any outcome-dependent inspection of the data it applies to;
- **conservative against the hypothesis**: each uncertain delay is resolved in the direction that weakens the claim under test. For a lead-lag claim, information the model uses as a predictor (the underlying and other inputs) is made available **later**. The prediction-market price used as the market baseline, comparator, or response is made available **earlier**, meaning less stale. Where one series plays both roles, each role gets its own conservative time. The asymmetry is stated in the preregistration. *(Statistician B4S-1 corrected the explanatory clause in the first draft of this record, which said every uncertain delay resolves toward later availability; that would have manufactured the S-8 lead-lag artifact on the prediction-market side. The owner's principle is unchanged. For owner confirmation.)*
- **evaluated over a latency ladder**: a preregistered ladder over the relative latency, with results reported at every rung. The headline result is the preregistered conservative primary rung, never the best rung. Rungs more favorable than the primary are diagnostics only. Survival is judged by a preregistered criterion at a stated stress rung (`docs/phase2.md` §4).
- A revision of an availability policy uses only outcome-blind latency measurements, gets a new `policy_id`, re-runs earlier results, and is counted as a research degree of freedom.

### H-6. Dependence units

Adopt the Statistician's fixed `outcome_cell_id` / `time_block_id` design in `docs/phase2.md`.
- Cross-venue contracts that share the same underlying economic or reference event **remain separate venue observations**. Operationally: contracts on different venues whose `ref_end` falls in the same `outcome_cell_id`, including those on different reference sources, keep separate `venue_contract_id`s and are never dropped as duplicates.
- They are **statistically dependent**: one dependence unit for split, purge and embargo, uncertainty, power, effective sample size, and correlated-exposure aggregation (Phase 4.5). Dependence is not limited to same-cell pairs. Overlapping information intervals, serial dependence within and across `time_block_id`s, and cross-asset dependence are handled by Policies 2, 4, and 5 of `docs/phase2.md`.
- An independent statistical audit of this design is still required at Gate 2, because the development Statistician co-authored it.

### H-7. Per-source acquisition approval

Historical-data acquisition remains **approved per source**. Approval to research a source is not approval to acquire it, and is never approval to buy, subscribe to, or accept the licence of a paid or licensed corpus. Each acquisition needs its own owner approval (`docs/external_access.md`, "Historical acquisition gate").

### H-8. Model and agent training-cutoff register

Adopt the register in `docs/exposure_register.md` (Part B). Each development model's documented training cutoff is recorded. Using a model whose cutoff is later than `T0 − m` to develop, select, review, or audit a cycle's candidate (as defined in `docs/exposure_register.md` Part B) is a recorded contamination event for that cycle. An unknown cutoff is treated as later than `T0 − m` until it is documented. Models are recorded by resolved, pinned identifier, never by alias, including subagent models and models that tools use to process fetched content. H-8 as approved records; it does not block. A prevention control is open owner decision E-B4-2.

### O-3. Conditions for historical acquisition

Historical acquisition is allowed only after these conditions are satisfied for the source:
- required raw-data backup, with a restore test covering acquired files (RT-B3-01);
- safe-parsing controls (RT-B3-03);
- provenance capture;
- a licence determination (O-5);
- a source-quality determination.

The checklist is in `docs/external_access.md`.

### O-5. Licensing checked twice

Licensing is checked **separately at acquisition time (L-ACQ)** and **again before production or live-trading use (L-PROD)**. Every derived artifact and model carries the `licence_id`s of its inputs, so that an L-PROD failure can be traced to everything it affects.

### O-6 (as clarified by the owner). Host-class policy, not a blanket ban

The owner did **not** adopt a blanket ban on all data, API, and live-display hosts. Instead:
- public documentation and research hosts, and approved historical-data hosts, may be read under the sandbox allowlist;
- trading, order-entry, and private-account hosts remain denied unless separately owner-authorized;
- live market-data API hosts need explicit owner authorization if the batch charter forbids live observations;
- an `api.*` hostname is never assumed safe because it contains documentation;
- an ambiguous host classification fails closed and is raised for approval.

The policy is in `docs/external_access.md`. It responds to the `api.exchange.bullish.com` near miss (`research/historical_data/incident_2026-10-16_api_host_request.md`).

### O-9. Research embargo after a protected interval begins

From `T0 − m` until the holdout is consumed, web and research activity that could reveal the protected interval's outcomes, labels, or equivalent observables is **embargoed** under the controls in `docs/external_access.md` §3. Any such exposure is recorded as a contamination event in HOLDOUT_ACCESS_LOG.md (`docs/external_access.md`, "Research embargo during a protected interval").

## Wording conflicts resolved

These were raised as O-7 and RT-B3-12 in batch 3. The owner approved resolving them in this batch.

1. **CLAUDE.md "agents do not inspect real market observations at all".** Replaced by a rule that separates five classes:
   - approved historical and development data;
   - incidental public research exposure;
   - the prospective protected holdout;
   - live or real-time observations;
   - credentialed or private data.

   Historical real market observations may be used once specifically approved for development and released and logged correctly. The protected holdout, unauthorized live observations, and private observations stay prohibited.
2. **"Oldest ~70% / newest ~30%".** CLAUDE.md, PROJECT_BRIEF.md §7, and START_HERE.md now say:
   - development and validation stay chronological, with walk-forward validation, purge, and embargo;
   - historical development data may use chronological train and development partitions;
   - the final protected evaluation is preferably prospective, beginning only after a declared start;
   - no exposed historical period may later be promoted into the protected holdout.

   Phrases such as "the development 70%", "the oldest approximately 70%", "the protected 30%", and "the newest approximately 30%" elsewhere, including the agent files and the HOLDOUT_ACCESS_LOG.md Holdout Rules restatement, are defined in CLAUDE.md and START_HERE.md to mean the development pool and the protected evaluation set of the frozen split, never the newest share of a historical dataset.

   **HOLDOUT_ACCESS_LOG.md was not edited.** Its body, including the Holdout Rules restatement, is pinned by SHA-256 in the `log_initialized` event (HAL-0005) of the append-only machine ledger, and `python -m pmv.holdout_log verify-history` refuses any change to it. An edit made in this batch failed that check and was reverted; the ledger was not touched. The log states that the governing documents prevail over it on conflict, and this conflict is surfaced here. Updating the restatement would need an owner-approved, reviewed mechanism for amending the pinned body. That is a code and control change outside this batch.
3. **No access path without a host class.** CLAUDE.md now states a host-class rule, with the full policy in `docs/external_access.md`.

## Also recorded in this batch

- **Local resource discipline (owner instruction).** Specialist and research agents may run in parallel. Heavy full-repository quality-gate runs (`./scripts/check.sh`) wait until specialist and background work has finished. Multiple heavy test processes are not run at the same time on the owner's Chromebook unless there is a stated reason. Recorded in START_HERE.md "Agent Cost Discipline" and referenced from CLAUDE.md.
- **Exposure register.** The pre-cycle exposure register (X-1 to X-3) from the batch 3 record is carried into `docs/exposure_register.md` (Part A) unchanged, so that later incidental exposures have one append-only home. The batch 3 record stays the original source. Whether the register becomes a structural part of HOLDOUT_ACCESS_LOG.md is still an open owner decision. This batch does not change that log's structure.

## Specialist reviews

- **Statistician:** `research/governance/batch4_statistician_review.md` (development self-review, not an independent audit). 19 findings: 1 BLOCKING (B4S-1, fixed above), 9 MAJOR, 8 MINOR, 1 optional escalation. Every finding tagged KEEPS was applied. B4S-4 found no conflict between H-4 and the `RECEIPT` + `PIT_CAPTURED` selection rule, and its clarification was added to `docs/phase2.md`.
- **Reliability / Red-Team:** `research/governance/batch4_red_team_review.md`. No BLOCKING finding, 13 MAJOR, 8 MINOR, 6 owner escalations. The wording fixes were applied, including the four recommended before merge (RT-B4-01, 03, 08, 17). The parts that extend a decision are listed below and were not adopted.
- **Edits to owner-attributed text, for owner confirmation:** B4S-1 (the H-5 direction clause) and B4S-8 (H-1 change control).

## Open owner decisions raised by the batch 4 reviews (not taken)

| ID | Decision | Source |
|---|---|---|
| E-B4-1 | Whether a value viewed under a charter-authorized live view can never be development data unless it is also released through class 1. That would narrow O-6. The rest of RT-B4-02 (owner-issued charter, class 3 prevails, every view registered) was applied as consistency with existing rules | RT-B4-02 |
| E-B4-2 | Make H-8 preventive: from `T0 − m`, sessions check configured model IDs against Part B at start and refuse unregistered or late-cutoff models. Model pinning in settings is an owner action | RT-B4-13 |
| E-B4-3 | A preliminary L-PROD licence check before the Gate 6 freeze, so that a holdout is never spent on a candidate that cannot lawfully trade | RT-B4-12 |
| E-B4-4 (optional) | Allowlist-default WebFetch until F-09 is committed | RT-B4-21 |
| E-B4-5 (optional) | Weigh cycle length (S-5 suggests about 510 days) against the H-8 and O-9 burden; consider shorter or staged cycles | RT-B4-20 |
| E-B4-6 | During a protected interval: deterministic denies for dataset hosts, and post-`T0 − m` BTC and gold literature read only as owner-screened copies | RT-B4-07 |
| E-B4-7 | Extend the embargo granularity to highly informative proxies (ETH, crypto indices, BTC futures and ETFs; gold futures and ETFs, spot XAU, related metals). This interacts with the open ETH decision in `docs/protected_information.md` item 3, where correlation alone is currently not a reason to block | B4S-6 |
| E-B4-8 (optional) | One blinded, preregistered re-sizing before `T0 − m` that may only increase the required count | B4S-9 |
| E-B4-9 (optional) | A default consequence of a confirmed H-8 or O-9 contamination (for example, a PASS reportable only as "PASS, contaminated"), and S-10's search-space freeze at `T0` | B4S-19 |

## Not changed by this batch

- HOLDOUT_ACCESS_LOG.md and its machine ledger.
- The information embargo, the deterministic data-access guard, and its refusal of every real request while the registry is empty.
- Credential isolation (F-03), the real-capital rules, and Gate 6 plus explicit owner approval for opening a holdout.
- The frozen-boundary rule. Once a cycle's split is frozen, later data never moves it.
- `.claude/agents/` and `.claude/settings.json`. Both are read-only in this sandbox. Their needed edits are listed under "Owner actions".

## Owner actions outside the sandbox

1. **Agent files.** `data-scientist.md`, `ml-engineer.md`, `statistician.md`, `independent-statistical-auditor.md`, `reliability-red-team.md`, and `risk-performance-engineer.md` under `.claude/agents/` still say "oldest approximately 70%" and "the development 70%" or "the protected final 30%". The CLAUDE.md definition governs how they are read. Aligning their wording is recommended, but it is not blocking.
2. **Deterministic host-class denies (F-09).** `.claude/settings.json` cannot be edited from agent sessions. Committing WebFetch and network deny patterns for the trading, live-data, and live-display classes in `docs/external_access.md` would turn the policy from a rule into a deterministic control. This is **required before Phase 1 real collection and before any agent web research (WebFetch or WebSearch) after `T0 − m`**. It is strongly recommended before the next research batch.

## Documents changed

- CLAUDE.md: Data (host-class rule), Holdout Protection, Protected Information Rule, Development Behavior.
- PROJECT_BRIEF.md §7.
- START_HERE.md: Evaluation Cycles, Protection of Holdout-Eligible Data, Phase 2 allocation, Agent Cost Discipline.
- HOLDOUT_ACCESS_LOG.md: **not changed** (hash-pinned; see "Wording conflicts resolved").
- `docs/external_access.md` (new), `docs/exposure_register.md` (new), `docs/protected_information.md`, `docs/phase2.md`, `docs/phase1.md`, and a status note in the batch 3 decision record.
