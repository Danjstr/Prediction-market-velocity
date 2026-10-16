# Batch 4 wording review: development Statistician (2026-10-16)

**Status:** development Statistician review, documentation only. **Not an independent audit.** Model ID: `claude-opus-5-5`. Documented cutoff: "knowledge cutoff June 2026" per this session's system context. A separate training-data cutoff is not stated there (see B4S-5).

**Disclosure.** Earlier development-Statistician sessions wrote S-8 to S-16 and co-authored the H-6 dependence design in `docs/phase2.md`. Where this review touches those items it is self-review, and it does not replace the Gate 2 independent audit that H-6 requires.

**Scope.** Wording only, for statistical correctness, internal consistency, and loopholes. The batch 4 working tree on `phase1/acquisition-safety-decisions` (git diff, plus `docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`, `docs/exposure_register.md`, `docs/external_access.md`). No network access, no real data, no test runs. The owner's decisions are not re-argued. Each finding is tagged:
- **[KEEPS]**: a wording fix that keeps the owner's decision;
- **[KEEPS, owner confirm]**: keeps the owner's stated principle but edits text attributed to the owner, so the owner should confirm it;
- **[ESCALATION]**: would change or add to an owner decision. Raised for the owner to decide, not proposed as a wording fix.

## Summary

| # | Severity | Area | Tag |
|---|---|---|---|
| B4S-1 | **BLOCKING** | H-5's "toward later availability, never earlier" is anti-conservative for the prediction-market side of a lead-lag hypothesis | KEEPS, owner confirm |
| B4S-2 | MAJOR | Latency ladder: "conservative rung" vs "primary `L`"; the ladder scales only one side; no survival criterion; block-time interval has no designated headline end | KEEPS |
| B4S-3 | MAJOR | A revision of `L` must rest only on outcome-blind latency measurements | KEEPS |
| B4S-4 | MAJOR | H-4 vs the RECEIPT + PIT_CAPTURED selection rule: no conflict, but clarification is needed; metadata justification is necessary but not sufficient for EV | KEEPS (escalation only if the owner intended archive-based selection) |
| B4S-5 | MAJOR | H-8: knowledge cutoff vs training-data cutoff; model aliases; per-subagent records; what "use" means; "review" is in the register but not in the decision record | KEEPS |
| B4S-6 | MAJOR | Embargo granularity omits highly informative proxies; search queries; O-9 decision text is narrower than §3 | KEEPS |
| B4S-7 | MAJOR | "Preferably prospective" in the governing documents vs H-1 "is prospective; formation (a) is not used for the first cycle"; CLAUDE.md omits `m` and the cutoffs | KEEPS |
| B4S-8 | MAJOR | Change control for `T0`, `m`, `C0`, `T_end`, and the stopping rule: "never changed on protected information" leaves other grounds open, and the owner is not embargoed | KEEPS, owner confirm |
| B4S-9 | MAJOR | Power-floor timing: recorded "before any release", but `σ_s` is to come from development RECEIPT data, which do not exist yet | KEEPS + optional ESCALATION |
| B4S-10 | MAJOR | The CLAUDE.md definition does not cover the agent files' "newest approximately 30%" / "oldest approximately 70%" | KEEPS |
| B4S-11 | MINOR | "Genuinely unexamined" (formation (a)) is undefined | KEEPS |
| B4S-12 | MINOR | The binding rule in H-1 and in Part A omits the Part B cutoffs (START_HERE includes them) | KEEPS |
| B4S-13 | MINOR | Precision and inequality handling in the register; the summary line conflicts with append-only | KEEPS |
| B4S-14 | MINOR | H-1 "every admissible observation before `T0 − m`" needs the contract-interval eligibility rule for labels | KEEPS |
| B4S-15 | MINOR | "No exposed **historical** period": PMV-captured released data should be covered too | KEEPS |
| B4S-16 | MINOR | H-6 summary wording; the `time_block_id` gold example contradicts the single global grid; "same side" needs `m ≥ G` | KEEPS |
| B4S-17 | MINOR | X-1 is already an outcome-dependent inspection of part of the historical pool; a lockbox must exclude or disclose it | KEEPS |
| B4S-18 | MINOR | HOLDOUT_ACCESS_LOG restatement omits the power floor; Part A routing after registration; S-10 regime-element flag not carried over; owner as an exposure channel | KEEPS |
| B4S-19 | — | Default consequence of an H-8/O-9 contamination event; S-10 search-space freeze | ESCALATION (optional) |

There is no conflict that blocks the batch as a governance batch apart from B4S-1. B4S-1 should be fixed before merge, because the decision record currently mandates a rule that would manufacture the S-8 lead-lag artifact. Nothing here blocks synthetic-fixture work.

---

## 1. Prospective holdout (H-1) and the split restatements

### B4S-7 (MAJOR): "preferably prospective" is weaker than H-1 [KEEPS]

H-1 says "The protected holdout is **prospective**" and "[Formation (a)] is not used for the first cycle." CLAUDE.md, PROJECT_BRIEF §7, START_HERE ("The preferred formation"), and the HOLDOUT_ACCESS_LOG restatement all say "preferably". Read alone, PROJECT_BRIEF (the authoritative document) would allow formation (a) in the first cycle. CLAUDE.md also says the interval begins "after every registered prior exposure", which drops the margin `m` and the model cutoffs.

**CLAUDE.md, Holdout Protection, third bullet. Replace with:**
> - the final protected evaluation is prospective for the first evaluation cycle, and preferably prospective thereafter (owner decision H-1): a protected interval beginning at a declared future start `T0`, with margin `m`, such that `T0 − m` is later than every registered prior exposure of the protected observable families and every recorded development-model training cutoff (`docs/exposure_register.md`). It accumulates through PMV capture;

**PROJECT_BRIEF.md §7 table, second row, "Segment" cell. Replace with:**
> Protected evaluation set: a **prospective** protected interval for the first cycle (preferred thereafter), beginning only after a declared future start `T0`

**PROJECT_BRIEF.md §7 Holdout protection. Replace "The prospective protected period is the preferred formation." with:**
> The prospective protected period is required for the first cycle and is the preferred formation thereafter (H-1).

**START_HERE.md Protection of Holdout-Eligible Data. Replace "The preferred formation is the prospective protected period (owner decision H-1, ...)." with:**
> The prospective protected period is the required formation for the first cycle and the preferred formation thereafter (owner decision H-1, `docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`).

**HOLDOUT_ACCESS_LOG.md restatement, first bullet. Replace "is preferably a prospective protected interval" with:**
> is a prospective protected interval for the first cycle (preferably thereafter)

### B4S-8 (MAJOR): change control for the cycle conditions [KEEPS, owner confirm]

H-1 says the conditions are "never changed on protected information". Four problems:
1. **It permits changes on other grounds**, for example "development results look weak, so extend the holdout". That is optional stopping driven by development, and the auditor cannot prove that a change was free of protected information.
2. **The owner is not embargoed.** The owner lives through the protected interval and sees BTC and gold prices. Any discretionary change made after `T0` by an unembargoed person may be informed by protected outcomes, whatever the stated reason.
3. **`C0` is not in the list of recorded conditions**, but the 70/30 target is defined over `[C0, T_end]`. A `C0` fixed afterwards could be chosen to manufacture the ratio.
4. **What happens at the calendar maximum is undefined** if the eligible-cell count has not been reached.

This keeps the owner's principle (no change on protected information) and closes the route by which it could be evaded. It edits owner-attributed text, so the owner should confirm it.

**Decision record H-1, "Recorded before release" list. Replace the first sub-bullet and add two:**
> - `T0`, `m`, and `C0` (the start of release-eligible PMV capture);
> - (unchanged items: embargo granularity; `T_end` or the stopping rule; power floor; register hash);
> - the preregistered outcome if the calendar maximum is reached before the eligible-cell count. Default: evaluate once at the calendar maximum against the unchanged PASS / FAIL / INCONCLUSIVE criteria, with the power shortfall recorded;
> - the preregistered technical contingencies (for example collector outage) under which the end date may move, and the mechanical rule for moving it. The rule depends only on the trusted collector's outcome-blind eligible-cell count.

**Decision record H-1. Replace "and never changed on protected information" with:**
> and never changed on protected information. After `T0 − m` they are not changed at all, except mechanically under a preregistered technical contingency. Any amendment, including one before `T0 − m`, is a logged HOLDOUT_ACCESS_LOG.md event giving its reason and the information it used. A discretionary change after `T0 − m` is treated by the auditor as potentially informed by protected outcomes.

**docs/phase2.md "The split", Sizing, third sub-bullet.** Replace "They are never extended on protected information." with "They are never extended or shortened on protected information, and after `T0 − m` only under a preregistered technical contingency (H-1)." Add `C0` to the list.

### B4S-9 (MAJOR): power-floor timing [KEEPS + optional ESCALATION]

H-1 records the power floor "before any release to agents". `docs/phase2.md` Policy 6 says "`σ_s` and the ESS ratio are estimated on development `RECEIPT` data only." In the first cycle no RECEIPT data have been released before registration, so the instruction cannot be followed as written. The likely outcome is an undocumented guess, or a later "re-estimate" that B4S-8 would treat as an amendment.

**Wording fix [KEEPS]. docs/phase2.md Policy 6, replace the sentence above with:**
> `σ_s` and the ESS ratio are estimated on development `RECEIPT` data available at cycle registration. Where none exist, as in the first cycle, the gate record states assumed values, their sources, and a sensitivity table, chosen conservatively (larger `σ_s`, smaller ESS ratio, smaller `Δ`). Historical-archive estimates may inform the assumption but are labeled as such.

**Optional [ESCALATION]: a blinded re-sizing point.** The owner could allow exactly one preregistered re-estimation of `N_req`, using development RECEIPT data only, at a date fixed at registration that falls before `T0 − m`. It could only **increase** `N_req` or the calendar maximum, never move `T0`, and would be logged. This is standard blinded sample-size re-estimation. It adds flexibility to H-1, so it needs the owner's approval.

**Clarification of "power governs" [KEEPS].** As written, "power governs" could be read as allowing the protected span to be cut below the ~30% target once power is reached. S-11 meant a floor. Proposed text (decision record H-1 Sizing, CLAUDE.md, PROJECT_BRIEF §7, START_HERE Phase 2, docs/phase2.md):
> The power requirement is a floor. The protected span is at least the power-required span. It is lengthened (by a later `T_end` or a larger stopping count, never by an earlier `T0`) where the ~30% target falls short of power, and the deviation from 70/30 is recorded.

The parenthesis protects the development RECEIPT span, which RECEIPT-only selection (B4S-4) and the `L` estimate depend on. If the owner prefers to allow an earlier `T0` instead, that is an [ESCALATION].

### B4S-10 (MAJOR): the agent-file phrases are not all covered [KEEPS]

The CLAUDE.md and START_HERE definitions cover "the development 70%", "the protected 30%", and "the final 30%". `.claude/agents/statistician.md` (and the other files listed) also say "The newest approximately 30% is the protected final holdout" and "oldest approximately 70%". Those phrases are not covered. An agent reading literally could treat the **newest 30% of the historical pool**, which is already exposed, as a protected holdout. That is exactly the promotion the no-promotion rule forbids.

**CLAUDE.md, replace the "Elsewhere in the project documents..." paragraph with:**
> Elsewhere in the project documents, including the agent files, every statement of the split as an oldest/newest approximately 70%/30% division (for example "the development 70%", "the oldest approximately 70%", "the protected 30%", "the final 30%", "the newest approximately 30%") means the cycle's development pool and protected evaluation set as fixed by its frozen split, whatever their actual shares. It never designates the newest share of a historical dataset as protected. See START_HERE.md Evaluation Cycles and `docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`.

Use the same text in the START_HERE.md Evaluation Cycles paragraph.

### B4S-11 (MINOR): "genuinely unexamined" is undefined [KEEPS]

Any historical period before a development model's training cutoff (currently through at least 2026-06) is already known to the agents through their training. Gold coarse levels and BTC are also in Part A up to 2026-10-16. Without a definition, formation (a) could later be claimed for a snapshot the models already know.

**Decision record H-1, last bullet. Append:**
> A snapshot is genuinely unexamined only if its whole period, including margins, satisfies the same binding rule as a prospective `T0`: it begins more than `m` after every registered exposure of its observable families and every recorded training cutoff of the models used, and no row or equivalent observable from it has been released.

### B4S-12 (MINOR): the binding rule is stated in three different ways [KEEPS]

The decision record H-1 binding rule and the exposure register Part A binding rule mention only exposures. START_HERE adds "every development model's training cutoff". H-8 handles cutoffs as a contamination event at the time of use. These are compatible, but the record should say so.

**Decision record H-1, Binding rule. Append:**
> It is also later than the training cutoff (Part B, `docs/exposure_register.md`) of every model planned for development of the cycle's candidate at registration. A model adopted later is governed by H-8.

Make the matching edit to the Part A binding rule in `docs/exposure_register.md` (cross-reference Part B).

### B4S-14 (MINOR): H-1 "every admissible observation" vs contract eligibility [KEEPS]

"Every admissible observation before `T0 − m` ... may become development data." A contract whose decision-time rows fall before `T0 − m` may resolve after `T0 − m`. Its label falls inside the embargo. Policy 2 purges it.

**Decision record H-1, Historical data. Replace the first sentence with:**
> Every admissible observation before `T0 − m`, historical or captured, may become development data for the cycle, subject to the contract-interval eligibility rule in `docs/phase2.md` (Policy 2): a labelled contract is development-eligible only if `ref_end + Δ_label < T0 − m`, and the label's own observation or receipt time also precedes `T0 − m`.

### B4S-15 (MINOR): "historical" period is too narrow [KEEPS]

The no-promotion rule in H-1, CLAUDE.md, PROJECT_BRIEF, START_HERE, and the HOLDOUT_ACCESS_LOG restatement says "no historical period that has been exposed to development". PMV-captured rows released before `T0 − m` are equally barred (PROJECT_BRIEF's general rule already covers them, but the new bullet invites a narrow reading).

**Replace in each place with:**
> no period or observation that has been exposed to development, historical or PMV-captured, may later be promoted into a protected holdout.

---

## 2. Dependence units (H-6)

### B4S-16 (MINOR): H-6 summary wording and two inherited inconsistencies [KEEPS]

1. **Negative implication.** "Cross-venue contracts that share the same underlying economic or reference event ... are statistically dependent" can be read as saying that only such pairs are dependent. The adopted policy also treats as dependent: overlapping information intervals (an hourly contract and the 15-minute contract ending at the same time), serial dependence within a `time_block_id`, and cross-asset dependence (common block grid). "Same economic event" is also not operational. Policy 1 uses `outcome_cell_id`.

   **Decision record H-6 and the docs/phase2.md section header. Replace the two sub-bullets with:**
   > - Contracts on different venues whose `ref_end` falls in the same `outcome_cell_id`, including those on different reference sources, remain separate venue observations (separate `venue_contract_id`s; never dropped as duplicates).
   > - They are one dependence unit for split, purge and embargo, uncertainty, power, effective sample size, and correlated-exposure aggregation (Phase 4.5). This does not limit dependence to same-cell pairs. Overlapping information intervals, serial dependence within and across `time_block_id`s, and cross-asset dependence are handled by Policies 2, 4, and 5 of `docs/phase2.md`.

2. **`time_block_id` grid.** The definition says "one global UTC grid shared by all underlyings and venues", and Policy 5 requires "the **same** calendar blocks for every asset". The example column gives "a declared session-day (gold)", which is a different grid. **docs/phase2.md, identity table, `time_block_id` example. Replace with:**
   > A UTC day for all underlyings. Gold session structure is a reporting stratum, not a block boundary.

   If gold blocks need session alignment, the global grid must be chosen to suit both assets. That is a Gate 2 design choice for the independent auditor, not a wording fix.

3. **"Same side" needs a condition.** Policy 2 says contracts in one `outcome_cell_id` "fall on the same side, or are purged together". That holds only if the purge gap is at least the grid width. **docs/phase2.md Policy 2. Append:**
   > This requires `m + Δ_label ≥ G`, which is checked when the split is frozen.

---

## 3. Historical availability (H-5) and the latency ladder

### B4S-1 (BLOCKING): the direction clause in H-5 is wrong for one side of the hypothesis [KEEPS, owner confirm]

H-5 says: "**conservative against the hypothesis**, so that an uncertain delay is resolved toward later availability, never earlier."

For a lead-lag hypothesis ("prediction-market prices under-react to underlying velocity"), the clause after "so that" is right for predictor inputs (the underlying). It is **wrong** for the prediction-market price used as the market baseline or comparator, which is the reference in the primary estimand (paired loss against the executable-price-implied probability). If PM prints are made available later, the model is compared with a staler market price. The market then looks slower, and the apparent under-reaction, the edge, grows. This is exactly the S-8 / RT-B3-07 artifact (block-time stamping makes PM moves appear late). It also contradicts `docs/phase2.md` §4, which correctly says "prediction-market price staleness a low [quantile]", and RT-B3-07's "an effect that appears only at the late end is a timing artifact".

The owner's governing principle, "conservative against the hypothesis", is correct. Only the explanatory clause contradicts it. The fix keeps the principle and corrects the clause. Because the clause is owner-attributed, the owner should confirm it.

**Decision record H-5, third bullet. Replace with:**
> - **conservative against the hypothesis**: each uncertain delay is resolved in the direction that weakens the claim under test. For a lead-lag claim, information the model uses as a predictor (the underlying and other inputs) is made available **later**. The prediction-market price used as the market baseline, comparator, or response is made available **earlier**, meaning less stale. Where one series plays both roles, each role gets its own conservative time. The asymmetry is stated in the preregistration;

**docs/phase2.md §4 Availability. Replace "conservative against the hypothesis, and evaluated over..." in the parenthesis with:**
> conservative against the hypothesis in each role, per S-8: later for predictor inputs, earlier for the prediction-market baseline; and evaluated over...

### B4S-2 (MAJOR): what the ladder is, and which rung is the headline [KEEPS]

H-5 says "the headline result is the preregistered conservative rung, never the best rung". `docs/phase2.md` §4 says "Only the primary `L` counts toward conclusions" and gives the ladder "×0.5, ×1, ×2, ×4". Problems:
- If the primary is ×1, is the "conservative rung" ×1 or ×4? The two texts identify different headlines.
- RT-B3-07 notes that the ladder scales only the underlying `L`, so it cannot probe the PM-side bias. What drives a lead-lag effect is the **relative** delay.
- The ×0.5 rung is anti-conservative. It must never be quotable.
- "Survive the ladder" has no preregistered criterion, so it is a forking path.
- The block-time interval is "reported at both ends" with no designated headline end.

**docs/phase2.md §4, replace the ladder sub-bullet with:**
> - every archive-based result reports a preregistered ladder over the **relative** latency: each rung lengthens predictor-input delays and shortens prediction-market staleness (including taking the early end of any PM information interval) by preregistered factors. The **primary rung** is preregistered at the conservative end of plausible latency (high quantile for predictor inputs, low for PM staleness). It is the headline result (owner decision H-5) and the only rung that counts toward conclusions. Rungs more favorable to the hypothesis than the primary are diagnostics, never cited as evidence. Rungs less favorable are stress tests. An effect is "surviving" only if a preregistered criterion holds at the stated stress rung (for example, the block-bootstrap lower bound of the primary estimand stays above zero at the ×2 stress rung). Otherwise it is treated as a timing artifact. The ladder is logged as research degrees of freedom.

**docs/phase2.md §4, coarse timestamps. Replace "archive lead-lag results are reported at both ends (Red-Team RT-B3-07)" with:**
> archive lead-lag results are reported at both ends. The headline uses the end that is least favorable to the hypothesis in each role (the early end for the PM baseline or response), and an effect present only at the favorable end is a timing artifact (Red-Team RT-B3-07).

### B4S-3 (MAJOR): revising `L` [KEEPS]

H-5 says "fixed before the experiment", which leaves `L` free to be revised between experiments. The first cycle starts with a deliberately long default (S-8), which will be revised once PMV measures latency. If a revision can be informed by archive results, the ladder becomes a garden of forking paths.

**docs/phase2.md "Research degrees of freedom" bullet. Append:**
> A revision of a synthetic availability policy (`L`, `D_max`, `L_vendor→PMV`, the ladder) may use only outcome-blind latency measurements (distributions of `received_at − event_time` or `received_at − source_send_time` from PMV capture, and overlap-window timing comparisons). It never uses an outcome-dependent result. Each revision is a new `policy_id`. Earlier results are re-run, and the revision is counted.

---

## 4. Research embargo (O-9, `docs/external_access.md` §3) and the training-cutoff register (H-8, Part B)

### B4S-6 (MAJOR): embargo granularity and proxies [KEEPS]

The embargo covers "equivalent observables". Statistically, partial information is enough to contaminate. Intraday ETH returns are strongly correlated with BTC returns, so the ETH path over a protected window largely reveals the sign of the BTC move. The same holds for BTC futures, ETFs, and crypto indices, and for gold futures, ETFs, spot XAU, and closely related metals. §3 also lists only "news about BTC, gold, or BTC/gold prediction markets". The decision-record O-9 says "outcomes or labels", while §3 says "outcomes, labels, or equivalent observables". Separately, web search engines often show live price widgets or snippets for any query that names an asset, even a methodology query.

**Decision record H-1, embargo-granularity sub-bullet. Replace with:**
> - the embargo granularity: the protected observable families, the equivalent observables they include, and **highly informative proxies** (for example ETH and crypto indices, BTC futures and ETFs for BTC; gold futures, ETFs, spot XAU, and closely related metals for gold), together with the granularity the embargo guarantees (no intra-window path or outcome information for any listed family or proxy) and the disclosed limitation (incidental coarse daily-level news, S-10);

**Decision record O-9.** Replace "that could reveal the protected interval's outcomes or labels" with "that could reveal the protected interval's outcomes, labels, equivalent observables, or listed proxies". Replace "embargoed or otherwise prevented from contaminating the protected evaluation" with "embargoed under the controls in `docs/external_access.md` §3".

**docs/external_access.md §3. Replace the fourth list item and add a sixth:**
> - papers, preprints, blog posts, and news about BTC, gold, BTC/gold prediction markets, or any proxy listed in the cycle's embargo granularity, that cover the interval;
> - search queries that name a protected family, a listed proxy, or a protected venue's products (for example "bitcoin", "BTC", "gold price", "Kalshi", "Polymarket") are treated as possibly returning interval content, and are avoided or routed only through a deterministic control that strips values.

### B4S-5 (MAJOR): what a "training cutoff" is, and what "use" means [KEEPS]

1. **Knowledge cutoff vs training-data cutoff.** M-1 records a "knowledge cutoff". Vendors may document a reliable-knowledge cutoff that is earlier than the training-data cutoff. H-8 needs the latest date of training data. A documentable upper bound is the release date of a pinned model snapshot.
2. **Aliases.** Agents and subagents can run under aliases (for example "opus", "sonnet", agent frontmatter `model:`) that resolve to newer models without notice. A subagent may also run a different model from its parent. M-1's "Batch 4 development session and its specialist reviews" assumes they all ran the same model.
3. **Scope of "use".** The decision record says "develop or select". Part B says "develop, select, or review". Neither covers the owner's use of other LLMs (CLAUDE.md names ChatGPT) to advise on the candidate. A Phase 5 auditor whose recommendations return to development can affect the candidate.

**docs/exposure_register.md Part B. Replace the rules list with:**
> - Each model used for development, research, review, or audit is recorded here by its **resolved, pinned model ID** (never an alias), before it is used for a cycle's candidate. Each session and subagent record names the resolved ID it ran.
> - The cutoff used for H-8 is the **latest** of: the documented training-data cutoff, the documented knowledge cutoff, and, where no training-data cutoff is documented, the snapshot's documented release date (an upper bound). An undocumented cutoff is **unknown**.
> - A cutoff stated to a day, month, quarter, or year is read as the last instant (UTC) of that period. It is compliant only if that instant is strictly earlier than `T0 − m`.
> - "Use" means any inference whose output can affect, directly or through a person, the cycle's data or label semantics, features, model, hyperparameters, calibration, thresholds, filters, sizing, evaluation plan, or review or audit conclusions, from cycle registration until the holdout is consumed. This includes models the owner consults outside Claude Code. Running a frozen evaluation mechanically is not use.
> - Using a model whose cutoff is later than `T0 − m`, or unknown, is a contamination event for that cycle, recorded in HOLDOUT_ACCESS_LOG.md.

**Part B, M-1 row. Replace the "Documented training cutoff" cell with:**
> Knowledge cutoff 2026-06 (read as 2026-06-30T23:59:59Z); training-data cutoff and snapshot release date not recorded

Add a note that subagent model IDs for this batch's specialist reviews should be confirmed.

**Decision record H-8. Replace "to develop or select a cycle's candidate" with "to develop, select, review, or audit a cycle's candidate (as defined in `docs/exposure_register.md` Part B)".** This aligns the record with the register, which is the stricter text. It is within the intent of H-8. If the owner meant to exclude review, that is an [ESCALATION].

### B4S-13 (MINOR): register mechanics [KEEPS]

- **Part A rows record dates only.** Add the rule: "A date or period end is read as the last instant (UTC) of the stated day or period, and the binding inequality is strict."
- **"Latest end per family" is a summary line** that must be edited whenever a row is added, which contradicts "rows are appended, never edited". Replace it with: "The latest end per family is derived from the rows when a cycle is registered, and is stated in the `cycle_registered` event. This file keeps no edited summary."
- **Routing after registration.** The Status paragraph says that exposures touching the protected scope go to HOLDOUT_ACCESS_LOG.md. It should add: "Exposures that do not touch a registered cycle's protected scope continue to be appended to Part A. They matter for later cycles and for development-pool degrees of freedom (S-15)."

### B4S-17 (MINOR): X-1 already inspected part of the development pool [KEEPS]

X-1 exposed aggregate outcome statistics (win rate against entry price) for KXBTC15M over 2026-01-10 to 2026-10-04. That is an outcome-dependent inspection, about the hypothesis itself, of a period that will be development data. Two rules are affected. H-5 and the docs/phase2.md degrees-of-freedom rule ("frozen per data pool before that pool's first outcome-dependent inspection") cannot be met for that pool. And the optional historical lockbox ("the newest historical slice before `T0 − m`") will overlap X-1 and X-2.

**docs/phase2.md "Research degrees of freedom". Append:**
> Periods and families listed in `docs/exposure_register.md` Part A count as already outcome-inspected. Policies for them are disclosed as fixed after exposure, and a historical lockbox must either exclude them or be disclosed as partially exposed.

---

## 5. H-4 vs the RECEIPT + PIT_CAPTURED selection rule

### B4S-4 (MAJOR): no conflict, but clarification is needed [KEEPS]

**Finding: they do not conflict.** H-4 sets **admissibility**: what POST_HOC rows may be used for (discovery, cleaning, pilot modeling, historical predictive research). The docs/phase2.md rule sets **which rows may produce the validation evidence that selects the audit candidate**. H-4 does not say archive-validated folds may select the candidate, and it explicitly denies POST_HOC rows the status of EV proof. The docs/phase2.md rule already keeps archive rows in training (subject to the ablation) and treats archive folds as discovery.

**The tensions that remain** need wording:
1. "Historical predictive research" can produce findings ("velocity adds information beyond price in the 2025 archive") that then choose feature families. That is selection by another name. It is legitimate as hypothesis generation, but only if it is counted.
2. H-4's exception ("unless decision-time availability of each field used can be justified") can be read as: justify the metadata fields, then claim EV. But docs/phase2.md §4 independently says archive rows (no books, synthetic availability) never support executable-EV claims. Metadata justification is necessary, not sufficient.
3. In practice, the first cycle may have few RECEIPT rows when the candidate is selected. That shortage must not become a reason to select on archive folds silently.

**docs/phase2.md "The split", mixing rules. Insert after "Any validation result used for selection ... Archive-validated folds are discovery only.":**
> - Owner decision H-4 admits `POST_HOC` metadata for discovery, data cleaning, pilot modeling, and historical predictive research. Under this design:
>   - `POST_HOC` and `SYNTHETIC_ARCHIVE` rows may be used in training, in pilot models, and in historical predictive-information studies, with results labelled by class;
>   - such results may generate hypotheses (feature families, model families, regimes). Each hypothesis carried forward is logged in the experiment ledger as a research degree of freedom;
>   - the comparison that selects among candidate features, model families, hyperparameters, calibration, thresholds, or policy for the audit candidate is computed on `RECEIPT` + `PIT_CAPTURED` folds;
>   - field-level justification of decision-time availability (H-4) is necessary but not sufficient for an executable-EV claim, which also requires `RECEIPT` rows with live books (§4);
>   - if `RECEIPT` + `PIT_CAPTURED` data at selection time are too few for a powered comparison, that is raised to the owner. It is never a reason to select on archive folds.

**[ESCALATION], only if applicable.** If the owner meant "pilot modeling and historical predictive research" to include choosing the audit candidate's features, hyperparameters, or thresholds on archive-validated folds, that would change the docs/phase2.md rule. I would recommend against it. Archive folds carry the S-8 timing artifact, post-hoc metadata leakage, activity selection, and survivorship (S-16), and a leaky relationship inflates archive validation scores, whereas it only degrades RECEIPT-fold scores (S-9). That choice should be an explicit owner decision, not a reading of H-4.

---

## 6. Other

### B4S-18 (MINOR) [KEEPS]

- **HOLDOUT_ACCESS_LOG.md restatement, first bullet.** After "not to historical development data;" add: "where that target conflicts with the power floor for the preregistered primary estimand, power governs and the deviation is recorded;".
- **The S-10 regime-element flag was not carried over.** S-10's recommendation that "a regime element first proposed after `T0` is flagged for the auditor" does not appear in the batch 4 documents. **docs/phase2.md "Research degrees of freedom". Append:** "Any regime-conditional design element (volatility, session, or liquidity filters or thresholds) is justified from development data alone. Its first version is dated in the experiment ledger, and one first proposed after `T0` is flagged for the auditor (S-10)."
- **The owner is an exposure channel.** **docs/external_access.md §3 Controls. Add:** "Market information conveyed to agents by the owner after `T0 − m` (prices, news, outcomes) is an exposure under this section. Owner-originated design changes to the candidate dated after `T0` are listed for the auditor."
- **CLAUDE.md freeze sentence.** "The chronological split is frozen once, in Phase 2" alongside H-1's "recorded before any release" (cycle registration may come in Phase 1). Append: "For a prospective holdout, `T0`, `m`, `C0`, and `T_end` or the stopping rule are fixed at cycle registration, before any release. The Phase 2 manifest reproduces them and never changes them."

### B4S-19 [ESCALATION, optional]

1. **Consequence of an H-8 or O-9 contamination event.** Today the HOLDOUT_ACCESS_LOG procedure leaves it to the owner to decide whether a replacement holdout is needed. Model upgrades are near-certain over a holdout accumulation of about 500 days (S-5, S-10). The owner may want a preregistered default, for example: "a confirmed H-8 or O-9 contamination of the candidate's development makes a PASS reportable only as 'PASS, contaminated', and the owner, with the independent auditor, decides whether it can support Phase 7 or later."
2. **S-10's search-space freeze at `T0`** (feature families, model families, and allowed regime variables), so that work after `T0` only tunes inside a fixed space. It reduces the cost of item 1. It is optional, not adopted, and would need owner approval.

---

## Remaining uncertainty

- These are wording proposals. Whether each fix is placed in the decision record or only in subordinate documents is for the coordinator and the owner. Owner-attributed text (B4S-1, B4S-8) should change only with the owner's confirmation.
- The proxy list in B4S-6 is illustrative. The correlation threshold that makes a proxy "highly informative" should be set per cycle, from development data, at registration.
- This review did not re-check the parts of docs/phase2.md that batch 4 left unchanged, beyond the items above.
