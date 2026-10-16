# Governing Principle

This is NOT an agentic trading bot.

Agents are temporary development staff.

The final production system must require zero LLM or agent inference to:
- collect data;
- validate data;
- generate features;
- run prediction;
- calibrate probabilities;
- calculate edge;
- size positions;
- execute;
- reconcile;
- monitor;
- pause;
- recover.

Agents succeed by encoding their work into standalone code, models, tests, configurations, mathematical rules, monitoring, and documentation.

---

# Project-Wide Controls

These controls apply to every phase. Later sections refer to them by name.

## Material Change and Material Authorship

A material change is a change reasonably capable of affecting data or label semantics, prediction output, calibration, eligibility, entry, or strategy behavior, risk or exposure behavior, execution behavior, timing or availability semantics, economic conclusions, validation conclusions, or the interpretation of protected evaluation evidence.

Material authorship is substantive design, implementation, or an adopted recommendation affecting the exact item under independent review.

If materiality is genuinely uncertain, treat the change as material until it has been reviewed and resolved. Never silently classify an uncertain change as non-material.

## Evaluation Cycles

Every protected evaluation belongs to an evaluation cycle with an immutable `cycle_id`. The `cycle_id` ties together the dataset and split identity, the development pool, the audit candidate, the protected evaluation set, the HOLDOUT_ACCESS_LOG.md events, and the evaluation result.

A new cycle begins only by an explicit, recorded decision. It never begins implicitly.

The `cycle_id` is created before the first outcome-dependent inspection for that cycle. At that point, record the split-formation method, the declared development or discovery subset, and the protected quarantine or prospective interval, in a gate record and in HOLDOUT_ACCESS_LOG.md.

No observation may become the protected evaluation set for a cycle after its values, outcomes, or outcome-dependent derivatives have been exposed to development. Data whose outcomes or results have been examined in exploration, shadow or live evaluation, or monitoring is not untouched evaluation data.

Each cycle's split must include any purge or embargo interval needed at both ends of its protected evaluation interval, including where labels or lookbacks could overlap an earlier consumed interval or a later future interval.

A consumed protected set may not be reused to repair or validate the candidate or cycle that consumed it. In a later, explicitly new cycle with a genuinely untouched future protected set, previously consumed data may be used as historical development data, but it remains permanently tagged as previously exposed or consumed and can never regain untouched-evaluation status.

## Protection of Holdout-Eligible Data

Before outcome-dependent inspection begins, the protected evaluation set must be fixed by one of:
- a mechanical partition of an unexamined snapshot, quarantined under a rule fixed before any inspection; or
- a prospective future protected period, quarantined as it accumulates.

The split-formation rule must be recorded before inspection and must not be selected after looking at candidate holdout outcomes.

Phase 1 may use only a declared development, discovery, or pilot subset for outcome-dependent work. Data inspected during Phase 1 is development-only for that cycle.

The primary protection for the final holdout is an information embargo. Protected observations, outcomes, and equivalent information capable of reconstructing them must remain unavailable to development agents until authorized final evaluation, regardless of source or representation.

Local protected plaintext must additionally remain outside ordinary development-agent-readable storage until an authorized Gate 6 release for the specific candidate, split, and cycle. Filesystem/path isolation is defense in depth and does not replace the information embargo.

Code-level loader restrictions alone are insufficient. Project data access must use the deterministic protected-scope/data-access controls. Development sessions may access holdout manifests, hashes, partition metadata, and other specifically whitelisted non-observation metadata.

Production or live-order credentials, wallet or private-key material, and equivalent secrets must never be exposed to Claude, LLM, or development-agent environments.

Claude Code permission rules in `.claude/settings.json` are defense-in-depth only and do not stop every shell or script read. Physical isolation is the primary control for secrets; for the holdout, the information embargo above is the primary control.

## Data and Contract Identity

Raw data is append-only, with provenance and chunk identities. Parser and schema versions and normalized-data versions are recorded. Every dataset or snapshot is identified by a content-addressed manifest.

Corrections and parser fixes create a new version. They never silently mutate a frozen snapshot.

The canonical prediction-market contract identity preserves, where applicable: venue and market ID; resolution-rule and resolution-source identity; threshold; relevant cutoff and settlement timestamps and timezone; rounding and tie semantics; void and cancellation treatment; and date-effective fee and rule information.

Supervised labels are determined by official resolution status.

## Research and Gate Records

Automatic experiment tracking must exist before the first experiment. It preserves successful, failed, and abandoned experiments, with their hypotheses, data, configuration, and code identities, searches, metrics, and decisions. It must not depend on retrospective self-reporting.

The experiment history is append-only or otherwise tamper-evident. Corrections create new records; they never silently rewrite history.

Every gate decision is recorded at `docs/decisions/gates/<gate_id>_<record_id>.md`, never overwritten or deleted, containing:
- gate ID;
- cycle ID and candidate ID where applicable;
- evidence identities;
- required reviewers and their conclusions;
- determination;
- unresolved findings;
- UTC timestamp and repository Git state;
- user approval, where that gate requires it.

User approval is required only where governance already requires it.

## Development-Validation Discipline

The same outer validation evidence must not be reused repeatedly without accounting for adaptive selection across feature selection, model architecture, hyperparameters, calibration, thresholds, and risk-policy design.

Before Phase 3, the Statistician defines nested chronological or walk-forward validation, or an equivalent outer-development lockbox or selection-control design. This is separate from, and does not replace, the protected final holdout.

---

# Phase 0 — Repository and Engineering Foundation

**Primary:**
- ML Engineer

**Review:**
- Reliability / Red-Team Engineer

**Create:**
- repository conventions;
- dependency management;
- Python environment;
- testing framework;
- logging;
- configuration;
- secret handling;
- CI;
- automatic experiment tracking, as required under Research and Gate Records;
- the gate-record format and location;
- the protected-information embargo and deterministic data-access controls for holdout-eligible data, and physical isolation of production credentials, as required under Protection of Holdout-Eligible Data;
- raw-data storage outside Git, with the provenance and versioning required under Data and Contract Identity;
- tamper-evident handling of HOLDOUT_ACCESS_LOG.md events;
- reproducibility conventions.

Do not build the trading model yet.

**Gate 0:** The repository must be reproducible, testable, and safe to extend, and the controls above must be in place before Phase 1 capture or any experiment begins. Gate 0 is decided only after a full Reliability/Red-Team-led audit of all Phase 0 requirements and implementation, and after the corrections approved from that audit. After Gate 0 and before any substantive Phase 1 work, the complete repository history must be pushed to a private remote, its secret and history hygiene verified, and the first hosted CI run must pass.

---

# Phase 1 — Data Feasibility and Live Collection

**Primary:**
- API / Execution Engineer

**Support:**
- Data Scientist
- Reliability / Red-Team Engineer

Research and verify current official documentation for:
- Kalshi;
- Polymarket;
- relevant BTC market/reference feeds;
- relevant gold/reference feeds.

Inventory existing historical data sources for the venues, BTC, gold, and their reference sources: coverage, granularity, timestamp semantics, contract metadata, outcomes, revisions, access, cost, licensing, provenance, and known gaps. Prefer verified existing historical data to waiting to regenerate equivalent observations, subject to the provenance, licensing, point-in-time, holdout, and source-quality requirements. Historical data exposed to development can never become protected holdout data.

Determine:
- historical depth;
- timestamp resolution;
- trade data;
- order-book data;
- market metadata;
- settlement metadata;
- rate limits;
- WebSocket behavior;
- sequence handling;
- authentication;
- latency characteristics.

Build ingestion architecture.

Preserve raw data.

Capture the contract identity required under Data and Contract Identity.

Before any outcome-dependent inspection, create the cycle_id and record the split-formation method, the declared development, discovery, or pilot subset, and the protected quarantine or prospective interval, as required under Evaluation Cycles and Protection of Holdout-Eligible Data. Outcome-dependent Phase 1 work uses only the declared subset.

Begin high-frequency live capture as early as practical, once the raw-data backup and retention policy listed under Required User Governance Inputs is in place and a representative backup and restore smoke test has succeeded.

Reliability review must examine:
- disconnects;
- reconnects;
- stale messages;
- duplicates;
- missing messages;
- sequence gaps;
- timestamp anomalies;
- persistence failures.

**Gate 1:** Do not proceed to expensive modeling until the team can demonstrate that the available data is sufficient to construct valid short-horizon training observations.

Gate 1 also requires, for each venue the project relies on, verification from current official sources of:
- API availability and permitted usage;
- account eligibility;
- jurisdiction and geographic eligibility;
- market access;
- authentication requirements;
- applicable terms and restrictions;
- relevant live-trading limitations.

Record sources and retrieval dates. Do not design around restrictions or assume historical venue access still applies. A venue that fails verification must not be relied on until the user decides how to proceed.

Gate 1 also requires the raw-data backup and retention policy to be in place, and a representative backup and restore smoke test to have succeeded, before or as part of commissioning the first irreplaceable live capture.

---

# Phase 2 — Dataset and Target Construction

**Primary:**
- Data Scientist

**Review:**
- Statistician
- API / Execution Engineer
- Independent Statistical Auditor — only when Gate 2 independence requires it

Perform general data cleaning and dataset engineering as designed in docs/phase2.md, for PMV captures and acquired historical data alike. That covers immutable raw preservation and provenance; schema, unit, and timestamp normalization; duplicates and cross-source reconciliation; missing data, staleness, and outliers; book and sequence continuity; point-in-time contract metadata and result revisions; reason-coded exclusions; source-quality tiers; deterministic derived datasets; split-safe fitted transformations; and the identity and dependence grouping that split isolation, purge and embargo, effective sample size, and uncertainty must respect.

Define:
- observation unit;
- feature lookback windows;
- prediction horizons;
- contract outcome targets;
- settlement logic;
- remaining-time representation;
- eligibility rules;
- missing-data handling;
- timestamp alignment.

Finalize the exact split manifest for the existing cycle, following the split-formation method recorded in Phase 1:
- reference the existing cycle_id;
- identify an immutable dataset snapshot or dataset version;
- record the snapshot creation/freeze time;
- allocate approximately 70% to development and approximately 30% to the protected holdout, from that snapshot or, under a prospective protected period, across the planned collection span;
- convert the allocation into explicit immutable partition boundaries, using UTC timestamp boundaries when appropriate to the data;
- explicitly identify any purge/embargo interval at both ends of the protected interval;
- hash or version the split definition;
- record the split definition in `research/splits/<split_id>.yaml` and in HOLDOUT_ACCESS_LOG.md.

Approximately 70/30 is the design target. The frozen partition boundaries are authoritative.

After the split is frozen, later-arriving data must not move the development/holdout boundary. Never recalculate "70/30" over an expanding dataset.

Data collected after the frozen holdout end belongs to a separate future-data pool. Its use is governed by Evaluation Cycles.

Implement purge/embargo logic.

Initialize and maintain HOLDOUT_ACCESS_LOG.md.

The protected holdout partition remains protected.

**Gate 2:** The development Statistician must review the dataset construction and leakage controls before serious model research begins.

If the development Statistician materially authored or co-authored the dataset, target, split, purge/embargo, or leakage-control design being approved, an Independent Statistical Auditor must independently review those affected components before Gate 2 passes.

If the development Statistician did not materially author those components, its normal review may satisfy the statistical-review requirement.

Material independence conflicts must be disclosed.

Independent Gate 2 reviews are saved at `research/audits/gate2/YYYY-MM-DD_<component>_<review_id>.md`, where `<review_id>` is a unique review identifier, and must never be overwritten or deleted.

Gate 2 also requires the validation design required under Development-Validation Discipline to be defined and reviewed before Phase 3 begins.

---

# Phase 3 — Baselines

**Primary:**
- Data Scientist

**Review:**
- Statistician
- Quant / Business Lead

Build simple baselines first.

Examples:
- market-price baseline;
- persistence/momentum baseline;
- logistic/statistical models;
- gradient-boosted trees.

Use only the development 70%.

Use walk-forward/rolling validation.

Evaluate:
- calibration;
- Brier score;
- log loss;
- directional metrics where useful;
- edge versus executable market price;
- simulated after-cost P&L;
- trade count;
- performance by horizon;
- performance by time remaining.

**Gate 3:** Do not proceed to expensive neural modeling unless there is credible evidence of incremental signal and plausible after-cost economics.

---

# Phase 4 — Advanced Velocity Models

**Primary:**
- Data Scientist
- ML Engineer

Evaluate justified architectures such as:
- TCN;
- temporal CNN;
- GRU;
- LSTM;
- other justified sequence models.

Every advanced model must compete against simple baselines.

Use only the development 70%.

Model selection must consider:
- predictive quality;
- calibration;
- after-cost economics;
- robustness;
- latency;
- inference cost;
- stability;
- implementation complexity.

**Gate 4:** Advanced complexity is accepted only if it improves the total economic and operational result.

---

# Phase 4.5 — Risk and Economic Policy Definition

**Primary:**
- Risk & Performance Engineer

**Review:**
- Statistician
- Quant / Business Lead

**Purpose:** Define the quantitative risk and sizing policy that will be used in all subsequent simulations, statistical audits, and the protected final holdout.

Using the user-approved risk-appetite values listed under Required User Governance Inputs as fixed governance inputs, define the following policy elements. Where empirical design or validation applies, use only the development 70%:
- position-sizing methodology;
- fractional-Kelly or other accepted sizing method;
- uncertainty adjustments;
- maximum per-trade exposure;
- maximum per-market exposure;
- maximum total exposure;
- correlated-position exposure limits;
- asset-specific exposure limits;
- limits on simultaneous or open positions;
- exposure accounting, counting resting orders at worst-case fill and unknown-state orders as live exposure until reconciled;
- drawdown thresholds;
- rolling loss limits;
- minimum acceptable net edge;
- confidence requirements;
- GREEN/YELLOW/ORANGE/RED policy;
- for PAUSE, KILL, YELLOW, ORANGE, and RED, including venue-unavailable and reconciliation-uncertain cases, the behavior of new orders, exposure-increasing resting orders, risk-reducing orders, and existing positions;
- the explicit meaning of automatic exposure reduction and automatic hard halt;
- manual-control governance: authorized operator roles, precedence over operating states, latching, clearing authority, whether automatic recovery may clear a manual control, restart and reboot behavior, notification and escalation, and audit logging;
- preliminary circuit-breaker thresholds;
- deterministic recovery and resume criteria.

These rules must be quantitative, deterministic, and suitable for standalone implementation without an LLM or agent.

An ORANGE policy that trades only extreme or high-confidence predictions requires dedicated evidence of tail calibration and robustness under degraded regimes. Without that evidence, ORANGE must not infer safety from extreme model confidence.

User risk appetite is a governance input, not a parameter optimized from historical returns. Existing positions may be automatically reduced or liquidated only when this policy explicitly requires it for the triggering condition.

They must be used during development simulations so that reported P&L, drawdown, and risk-adjusted performance reflect the strategy that is actually intended for deployment.

The Risk & Performance Engineer is defining policy here, not yet building the full production monitoring and execution implementation.

**Gate 4.5:** The sizing and risk policy must be defined before the Phase 5 Independent Statistical Audit and before anything is frozen for final holdout evaluation. Every input listed as required by Gate 4.5 under Required User Governance Inputs must be approved by the user before Gate 4.5 passes, including the frozen/adjustable classification and envelope for each risk-appetite input. The policy evaluated on the holdout must be the policy intended for deployment, including its user-approved inputs and manual-control governance.

---

# Phase 5 — Independent Statistical Audit

**Primary:**
- Independent Statistical Auditor

**Independent reviews:**
- Quant / Business Lead — economic assumptions
- Reliability / Red-Team Engineer — operational assumptions that could invalidate statistical conclusions

**Factual clarification only:**
- development Statistician

**Model:**
- use the highest-capability statistical/reasoning model available for this audit

## Audit Candidate

Phase 5 audits a single audit candidate, defined by an audit-candidate manifest at `research/audit_candidates/<candidate_id>.yaml`.

The manifest must identify, where applicable:
- exact Git commit;
- cycle_id;
- clean/dirty working-tree status;
- dataset version or immutable dataset identifier;
- date range;
- feature-set/schema version;
- target definition version;
- preprocessing configuration;
- model architecture;
- model hyperparameters;
- trained model artifact identifier/hash;
- calibration artifact or configuration;
- entry/strategy configuration;
- cost assumptions;
- execution assumptions;
- Phase 4.5 sizing/risk configuration;
- user-approved risk-appetite inputs, with each input's Gate 4.5 frozen/adjustable classification and envelope;
- state-behavior and protective-action policy;
- frozen split definition identifier and hash;
- the production-relevant scope declaration;
- the Holdout Evaluation Plan and its SHA-256;
- dependency/environment lock or version identifier.

Every material artifact referenced by the manifest that can change independently of the Git commit must be identified immutably. Where applicable, this includes:
- dataset artifacts;
- trained model weights/artifacts;
- calibration artifacts;
- generated feature/schema artifacts;
- preprocessing artifacts or external configuration;
- strategy configuration files;
- Phase 4.5 risk configuration files;
- the frozen split definition file;
- dependency/environment lockfiles;
- any other production-relevant artifact not fully determined by the Git commit.

For each such artifact, the manifest must contain one of:
- the complete immutable value or configuration itself;
- an immutable version identifier;
- a cryptographic hash (SHA-256) of the referenced artifact.

A pathname alone is not sufficient identity for a mutable artifact.

The manifest must contain a production-relevant scope declaration, made before Phase 5 begins and immutable as part of the manifest. Production relevance is not defined only by repository paths. The declaration identifies, where applicable:
- production-relevant path patterns;
- executable and runtime code;
- configuration;
- feature-generation logic;
- model and calibration artifacts;
- strategy logic;
- risk and sizing logic;
- execution and reconciliation logic;
- runtime dependencies and environment locks;
- schemas and contracts;
- generated artifacts;
- external components or resources whose identity or behavior can affect production;
- any other component category capable of changing prediction, strategy, risk, execution, state, timing, or economic behavior.

The declaration may also explicitly identify known non-production evidence and governance areas.

No uncommitted production-relevant code or configuration may contribute to the audited candidate. If production-relevant files are uncommitted, the candidate is not eligible for audit until they are committed and a new manifest is created.

The manifest is immutable once the audit begins. Any change produces a new manifest with a new candidate ID.

Phase 5.5 implementation work never modifies this manifest. It is recorded separately as an implementation overlay.

The audit candidate must not change during the audit.

`research/audits/<candidate_id>/STATISTICAL_AUDIT.md` must record the candidate ID and the SHA-256 hash of the manifest file. The convenience copy at `research/STATISTICAL_AUDIT.md` mirrors the current archived audit, but the candidate-specific archived copy is authoritative.

## Holdout Evaluation Plan

Before Phase 5 begins, each audit candidate must have an immutable, candidate-specific Holdout Evaluation Plan at `research/evaluation_plans/<candidate_id>.md`, identified in the manifest by its SHA-256. It contains at minimum:
- primary endpoints;
- exact metric definitions;
- economic and cost assumptions;
- the uncertainty method;
- effective-sample-size and minimum-evidence requirements;
- multiplicity treatment;
- PASS, FAIL, and INCONCLUSIVE criteria;
- handling of no-fills, voids, missing observations, and invalid markets;
- the exact identity and hash of the deterministic evaluation runner;
- each subgroup analysis, designated as either a preregistered decision criterion or descriptive-only.

Descriptive subgroup results must never be used to select a new deployable subgroup without a new untouched evaluation.

## Audit Independence

The Independent Statistical Auditor must have no material involvement in developing the methods being audited and must start in a fresh context.

The development Statistician must not serve as the primary final statistical reviewer of work it materially helped create. It may provide factual clarification during the audit but must not control the auditor's conclusions.

Development-time self-review is required but is never accepted as independent validation.

The Independent Statistical Auditor must disclose:
- any prior involvement with the work;
- any conflicts of independence;
- whether earlier Independent Statistical Auditor involvement, including Gate 2 reviews, materially shaped any component being audited;
- any information it could not independently verify.

The audit must identify which components had prior development-Statistician involvement.

The economic and operational reviews must also run in a fresh context and disclose any prior involvement in the assumptions they review.

A Phase 5 reviewer whose role materially authored the exact assumptions it is reviewing must disclose this item by item. Each affected item is marked as not independently reviewed.

For each item marked not independently reviewed, before Gate 5 passes, obtain a targeted cross-review by a fresh-context instance of another existing role that has relevant competence for that exact item and no material authorship of the exact assumption being cross-reviewed. Select the cross-reviewing role case by case; there are no fixed reviewer-role pairings.

If no sufficiently independent, competent existing role is available, record that limitation explicitly.

Save each cross-review or recorded limitation at `research/audits/<candidate_id>/CROSS_REVIEW_<review_id>.md`, where `<review_id>` is a unique review identifier. Never overwrite or delete it.

Explicit user acceptance of reduced independence may resolve a documented non-blocking material concern under Gate 5. It can never override an unresolved blocking finding.

The structural separation of the Independent Statistical Auditor is unchanged.

## Audit Inputs

The Independent Statistical Auditor receives:
- the audit-candidate manifest and its SHA-256 hash;
- the complete research record;
- successful, failed, and abandoned experiments;
- feature and target history;
- model-selection history;
- hyperparameter and threshold searches;
- calibration decisions;
- cost assumptions;
- execution assumptions;
- the Phase 4.5 sizing and risk policy;
- the Holdout Evaluation Plan;
- HOLDOUT_ACCESS_LOG.md;
- all relevant prior archived reviews from `research/audits/`, including Gate 2 reviews and the statistical, economic, and operational reviews of earlier audit candidates;
- the recommendations made in those reviews;
- which of those recommendations were adopted;
- how the candidate changed in response;
- relevant code, results, and raw evidence.

Review raw evidence directly rather than relying on persuasive summaries.

## Audit Scope

Independently assess:
- leakage;
- lookahead bias;
- repeated tuning;
- multiple testing;
- dependence;
- autocorrelation;
- overlapping labels;
- effective sample size;
- regime dependence;
- confidence intervals and uncertainty;
- calibration;
- economic-edge credibility and significance;
- sizing validity;
- drawdown behavior;
- risk of ruin;
- holdout-protection compliance;
- the Holdout Evaluation Plan;
- the Phase 4.5 sizing and risk policy, including sizing methodology, exposure limits, exposure accounting, drawdown thresholds, rolling loss limits, minimum net edge, confidence requirements, GREEN/YELLOW/ORANGE/RED policy, state behavior for resting orders and existing positions, circuit-breaker thresholds, and recovery criteria.

The auditor should assume the apparent edge is fake and try to disprove it.

Each Phase 5 reviewer assesses the completeness of the declared production-relevant scope for its domain. The Operational Assumptions Review explicitly challenges omissions.

The protected final 30% must not be accessed during Phase 5. It may be opened only after Gate 6.

## No Redesign During Audit

The Independent Statistical Auditor does not redesign the strategy.

It classifies findings as:
- acceptable;
- concern;
- major concern;
- blocking.

It may recommend repairs, additional research, or replacement research directions. Those changes return to the development process and must not be silently incorporated into the audit candidate or the frozen system.

Any material change resulting from the audit requires re-audit of the affected components.

## Required Outputs

Each Phase 5 review is archived per audit candidate:

```
research/audits/<candidate_id>/
    STATISTICAL_AUDIT.md
    ECONOMIC_REVIEW.md
    OPERATIONAL_ASSUMPTIONS_REVIEW.md
```

These are authored, respectively, by the Independent Statistical Auditor, the Quant / Business Lead, and the Reliability / Red-Team Engineer.

The candidate-specific archive is the authoritative historical record. Archived reviews must never be overwritten or deleted.

If the same candidate is reviewed more than once, save each later review as a new numbered file (for example `STATISTICAL_AUDIT_2.md`) rather than overwriting the earlier one.

These paths hold the current/latest copy of each review for convenience:
- `research/STATISTICAL_AUDIT.md`
- `research/ECONOMIC_REVIEW.md`
- `docs/failure_modes/OPERATIONAL_ASSUMPTIONS_REVIEW.md`

If a convenience copy differs from its archived review, the archived review is authoritative.

`STATISTICAL_AUDIT.md` may reference the economic and operational reviews but must not rewrite their conclusions as though they were the auditor's own work.

**Gate 5:** An auditor saying "approved" is never sufficient by itself. Gate 5 passes only when:
- all three Phase 5 reviews are complete and have been considered;
- there are no unresolved blocking findings in any of the three reviews;
- all required evidence has been reviewed;
- every item marked not independently reviewed has a targeted cross-review, or a recorded limitation whose resulting non-blocking concern the user has explicitly accepted;
- holdout protection remains intact;
- any material concerns have been resolved or explicitly accepted by the user after the concern, evidence, consequences, and alternatives have been surfaced.

---

# Phase 5.5 — Pre-Holdout Implementation Readiness

**Primary:**
- ML Engineer, API / Execution Engineer, and Risk & Performance Engineer, for their components

**Review:**
- Reliability / Red-Team Engineer

The protected holdout can be spent only once. Before it is opened, provide deterministic implementation, replay, integration, and failure-injection evidence that the audited candidate's operational assumptions hold in implemented or production-faithful form.

Phase 5.5 contains the production-faithful semantic implementation of risk and execution behavior needed to justify spending the holdout.

Provide evidence, at minimum, for:
- data timing and strategy-availability semantics;
- feature, inference, and calibration parity;
- strategy calculation;
- risk sizing and hard limits;
- the execution simulator or venue-faithful execution assumptions;
- order-state and reconciliation behavior;
- restart and recovery;
- PAUSE/KILL and operating-state controls;
- artifact and configuration identity;
- latency and cost assumptions;
- representative fault injection.

This does not require every final production integration detail to be live. Phase 10 remains the full-system reliability and red-team audit of the implemented system.

All implementation code, configuration, artifacts, simulators, and other materially relevant components used as evidence for Gate 5.5 must have immutable identities, recorded in the readiness review.

## Implementation Snapshot and Overlay

The Phase 5 audit-candidate manifest remains immutable and continues to identify the audited research and strategy candidate. It must never be rewritten to point at a later commit.

Phase 5.5 may change production-relevant implementation only through work that faithfully realizes already-audited behavior.

**Implementation snapshot.** Before the readiness review is finalized, create an immutable snapshot of the production-relevant implementation being reviewed. Record:
- the implementation snapshot Git commit, if Git is the identity used;
- immutable identities or hashes for all production-relevant code, configuration, dependencies, artifacts, simulators, and other implementation components.

The readiness review refers to this already-existing snapshot. It does not need to be part of the snapshot commit.

**Implementation overlay.** The implementation overlay is the exact set of production-relevant differences between the immutable audited candidate and the immutable implementation snapshot that Phase 5.5 reviewed and classified as implementation-only.

**Readiness review.** `IMPLEMENTATION_READINESS.md` is an audit and evidence artifact with its own SHA-256. It may be committed after the implementation snapshot without changing the identity of the implementation that was reviewed. Its hash identifies the approved review and overlay record, not the implementation snapshot.

The readiness review must record:
- the audited candidate ID;
- the audited candidate-manifest SHA-256;
- the audited base Git commit;
- the implementation snapshot identity;
- the complete Git diff for production-relevant paths and components between the audited base and the implementation snapshot;
- an inventory of every other repository difference between them, each explicitly classified as a non-production evidence or governance change;
- immutable identities or hashes for all production-relevant implementation code, configuration, artifacts, simulators, and dependencies in the snapshot;
- an item-by-item classification of every production-relevant change as implementation-only or semantically/materially relevant;
- evidence supporting each implementation-only classification;
- the Reliability / Red-Team Engineer's review conclusion.

Audit reports, governance documents, decision records, log records, and other non-production evidence added after the audited base commit are not implementation-overlay changes merely because they appear in a Git diff. They must remain auditable. No production-relevant difference may be classified as non-production.

Anything declared production-relevant in the audit-candidate manifest can never be reclassified as non-production during Phase 5.5.

Phase 5.5 may classify a repository difference as non-production only when it is outside the predeclared production-relevant scope and the Reliability / Red-Team Engineer has evidence that it cannot affect production behavior or audited conclusions.

If Phase 5.5 discovers that a path, dependency, artifact, component, or external resource outside the declared production-relevant scope can affect production behavior or audited conclusions, that is evidence that the audited scope was incomplete. Because the audit-candidate manifest is immutable, do not silently expand it. Return to the appropriate development and re-audit path with a new candidate and manifest. This applies even if the component lives under a directory previously thought to contain only documentation or tooling.

The audited manifest's dependency/environment lock remains immutable as part of the audited base. The implementation snapshot may use a different dependency/environment lock only if the readiness review records:
- the audited base lock identity;
- the implementation lock identity;
- the exact dependency/environment delta;
- why the change is required;
- evidence that it does not alter audited model semantics, calibration, feature semantics, strategy behavior, risk semantics, execution assumptions, data semantics, numerical behavior relevant to predictions, or economic conclusions;
- applicable parity, replay, integration, latency, and fault-injection evidence.

A dependency or environment change that cannot be demonstrated to be implementation-only is semantically or materially relevant and returns to the appropriate re-audit path.

A change is not eligible for the implementation overlay if it is semantically or materially relevant to the audited assumptions, strategy, model behavior, calibration, sizing or risk semantics, execution assumptions, data semantics, or economic conclusions. Such a change returns to the appropriate development and re-audit path.

The implementation overlay is not permission for arbitrary post-audit coding.

The protected holdout must not be accessed during Phase 5.5. Readiness evidence uses development and replay data only, never protected holdout observations.

Record the readiness review at `research/audits/<candidate_id>/IMPLEMENTATION_READINESS.md`. If the same candidate's readiness is reviewed more than once, save each later review as `IMPLEMENTATION_READINESS_2.md`, `IMPLEMENTATION_READINESS_3.md`, and so on. Never overwrite or delete an earlier readiness review.

**Gate 5.5:** The Reliability / Red-Team Engineer's review must show no unresolved blocking findings, and every production-relevant change in the implementation overlay must be classified as implementation-only with supporting evidence, before Phase 6.

---

# Phase 6 — Freeze Before Holdout

Freeze:
- dataset definition;
- frozen split definition;
- eligible markets;
- feature set;
- preprocessing;
- model architecture;
- model hyperparameters;
- calibration method;
- entry rules;
- cost assumptions;
- execution assumptions;
- position-sizing rules;
- risk parameters;
- user-approved risk-appetite inputs, with their frozen/adjustable classification and envelope;
- state-behavior and protective-action policy;
- manual-control governance;
- circuit-breaker parameters;
- the Holdout Evaluation Plan.

Freeze and record these identities:
1. the immutable audited candidate manifest and its SHA-256;
2. the immutable Phase 5.5 implementation snapshot identity;
3. the SHA-256 of the authoritative readiness review that approved the implementation overlay;
4. all production-relevant artifact, configuration, and dependency identities;
5. the final frozen production implementation identity.

The frozen system is the combination of the immutable audited candidate manifest and the approved Phase 5.5 implementation overlay.

Document the frozen configuration.

The frozen production implementation may differ from the audited candidate only by the exact implementation overlay reviewed in Phase 5.5. Later audit, governance, decision, log, and evidence files in the repository are not part of the production implementation identity, but every such difference must be explicitly classified as non-production. Any material change after the Phase 5 audit requires re-audit of the affected components before the final holdout may be opened.

If production-relevant code, configuration, or dependencies change after the Phase 5.5 review, Gate 6 fails until the appropriate readiness re-review or re-audit occurs.

Verify each component of the system being frozen against the audited manifest or, for components changed by the implementation overlay, against the identities recorded in the implementation snapshot. For every artifact the manifest identifies by hash, recompute the hash; for every artifact identified by an immutable version identifier, confirm that identifier; for every value stored in the manifest itself, confirm it matches. Confirm that the manifest file's SHA-256 hash matches the hash recorded in `research/audits/<candidate_id>/STATISTICAL_AUDIT.md`. Record the result of this check with the frozen configuration.

**Gate 6:** The final holdout may be opened only when all of the following hold:
- the freeze is complete;
- the audited candidate manifest is unchanged, and its SHA-256 matches the archived audit records;
- the production-relevant delta from the audited candidate to the implementation snapshot exactly matches the reviewed implementation overlay;
- the frozen production-relevant implementation exactly matches the implementation snapshot and the identities reviewed in Phase 5.5;
- every repository difference outside the implementation snapshot is a non-production evidence or governance change and has been explicitly classified as such;
- there are no unreviewed production-relevant differences;
- Gate 5.5 has passed;
- the Holdout Evaluation Plan is unchanged and its SHA-256 matches the audit candidate;
- the correlated-review meta-review is complete, or its unavailability has been explicitly dispositioned by the user;
- every item of the Gate 6 opening checklist in HOLDOUT_ACCESS_LOG.md passes;
- the holdout has not been consumed;
- the user has explicitly approved opening it for this specific candidate and frozen split.

Gate 6 does not require the entire repository diff from the audited base commit to the final HEAD to equal the implementation overlay.

Before Gate 6, the Phase 5 and Phase 5.5 audit package receives one additional meta-review by either a human reviewer or a materially different model family. This supplements, and does not replace, the three Phase 5 reviews. If no such review is available, the reviews must not be described as cognitively independent; the correlated-review limitation is surfaced for explicit user disposition and recorded in the gate record.

The technical checks are necessary but not sufficient. No agent, script, retraining system, audit process, or automatic workflow may open the holdout merely because the checks pass. Record the approval basis in HOLDOUT_ACCESS_LOG.md.

---

# Phase 7 — Final Protected 30% Evaluation

**Primary:**
- the deterministic frozen evaluation runner identified in the Holdout Evaluation Plan

**Independent verification:**
- Independent Statistical Auditor — verifies the statistical result against the plan
- Quant / Business Lead — verifies the economic result against the plan
- Reliability / Red-Team Engineer — verifies data, script, and artifact identity

**Technical clarification only:**
- ML Engineer — may provide technical clarification but does not control the one-shot evaluation

The deterministic evaluation runner may be started only by the user or an operator explicitly authorized by the user, after Gate 6. No development agent controls the evaluation.

Run the frozen system against the final 30% as the formal out-of-sample test, using exactly the deterministic evaluation runner and criteria in the Holdout Evaluation Plan.

Do not tune against the result.

Record the access, consumption, and exposure scope in HOLDOUT_ACCESS_LOG.md.

## Consumed Holdout

The protected holdout becomes consumed once outcome-dependent protected information is revealed to any person, agent, process, candidate-development workflow, or downstream artifact.

Outcome-dependent information includes, where applicable:
- labels or resolutions;
- predictions evaluated against protected outcomes;
- performance metrics;
- calibration results;
- P&L or EV results;
- error analyses;
- trade-by-trade success or failure information;
- any derived result capable of influencing model, strategy, risk, threshold, calibration, or candidate decisions.

Reading non-outcome metadata needed to verify immutable identity, partition boundaries, hashes, or access controls does not by itself consume the holdout, provided no protected observations or results are revealed.

Once consumed:
- the holdout remains evidence for the single frozen candidate evaluation for which it was authorized;
- it must never again be treated as untouched data for repairing, selecting, or re-evaluating a changed candidate;
- it must never be renamed development or validation data to avoid these rules;
- a materially changed candidate requires a genuinely untouched future evaluation set;
- the contamination and exposure-scope rules in HOLDOUT_ACCESS_LOG.md continue to apply.

Evaluate, as specified in the Holdout Evaluation Plan:
- probability calibration;
- Brier/log loss;
- net P&L;
- realized versus predicted edge;
- maximum drawdown;
- risk-adjusted results;
- trade count;
- performance by asset;
- performance by horizon;
- performance by time remaining;
- performance by confidence tier;
- execution assumptions.

**Gate 7:** The result is classified PASS, FAIL, or INCONCLUSIVE strictly by the Holdout Evaluation Plan's preregistered criteria.

Authorized Phase 7 evaluation consumes the protected holdout as soon as outcome-dependent protected information is revealed, whatever the result.
- PASS permits only the evaluated frozen candidate to continue to Phase 8.
- FAIL or INCONCLUSIVE blocks that candidate from deployment-track advancement. Work returns to development under Evaluation Cycles.

Do not repeatedly tune against the holdout. Descriptive subgroup results must not be used to select a deployable subgroup.

---

# Phase 8 — Risk and Monitoring System

**Primary:**
- Risk & Performance Engineer

**Review:**
- Statistician
- Reliability / Red-Team Engineer

Harden, integrate, and verify for production the reviewed Phase 5.5 implementation snapshot of the risk policy defined in Phase 4.5 and frozen in Phase 6, including:
- position-sizing methodology;
- uncertainty adjustments;
- maximum per-trade exposure;
- maximum per-market exposure;
- maximum total exposure;
- correlated-position exposure limits;
- asset-specific exposure limits;
- limits on simultaneous or open positions;
- conservative exposure accounting;
- drawdown controls;
- rolling loss limits;
- minimum acceptable net edge enforcement;
- confidence requirements;
- manual PAUSE;
- manual KILL;
- GREEN/YELLOW/ORANGE/RED states;
- state-specific behavior for new orders, resting orders, risk-reducing orders, and existing positions;
- manual-control governance;
- automatic circuit breakers;
- model-health monitoring;
- execution-health monitoring;
- recovery logic.

Phase 8 must preserve the frozen risk policy used in the final holdout.

Live monitoring benchmarks must record their provenance and must not present in-sample development results as out-of-sample expectations.

## Post-Holdout Implementation Deltas

Every production-relevant change made after Gate 6, in Phases 8–10, is classified under Material Change and Material Authorship as either:
- implementation-only — the component owner supplies an immutable identity and parity, replay, and integration evidence, but does not review its own change. A fresh-context Reliability / Red-Team Engineer determines implementation-only status. When the classification depends materially on another domain, a targeted fresh-context review is obtained from an existing competent role with no material authorship of the change. The result is recorded in a gate record; or
- semantic or material — the consumed holdout cannot validate the changed system, and the change returns to the appropriate new-evaluation path under Evaluation Cycles.

The risk engine must be able to reject or reduce a trade even when the predictor recommends it.

No LLM or agent may be required in the live risk path.

**Gate 8:** Risk controls must pass independent tests before live execution is permitted.

---

# Phase 9 — Execution Engine

**Primary:**
- API / Execution Engineer

**Review:**
- Reliability / Red-Team Engineer
- Risk & Performance Engineer

Harden, integrate, and verify for production the reviewed Phase 5.5 implementation snapshot of:
- order submission;
- cancellation;
- retries;
- idempotency;
- partial fills;
- ambiguous order states;
- reconciliation;
- position accounting;
- restart recovery;
- latency measurement.

Never assume that a failed or timed-out request means no order was accepted.

**Gate 9:** Execution state must remain recoverable and reconcilable under failure conditions.

---

# Phase 10 — Full-System Reliability / Red-Team Audit

**Primary:**
- Reliability / Red-Team Engineer

**Model:**
- use the highest-capability reasoning/research model available for major audits

Provide the complete repository.

Perform extensive external research into:
- venue failure modes;
- API quirks;
- WebSocket behavior;
- exchange outages;
- distributed-system failures;
- trading-system incidents;
- dependency failures.

Perform failure injection where practical.

Test:
- network partitions;
- disconnects;
- reconnect storms;
- stale data;
- duplicates;
- sequence gaps;
- out-of-order messages;
- malformed messages;
- clock drift;
- API schema changes;
- rate-limit changes;
- latency spikes;
- partial fills;
- rejected orders;
- cancellation/fill races;
- request timeouts after possible acceptance;
- duplicate submissions;
- exchange outages;
- local crashes;
- restarts;
- corrupt persisted state;
- disk/database failures;
- model-loading failures;
- NaN/Inf features;
- out-of-distribution inputs;
- extreme volatility;
- liquidity disappearance;
- bad settlement metadata;
- unreconciled positions;
- risk-control bypasses;
- manual pause failure;
- circuit-breaker failure.

**Maintain:** `docs/failure_modes/FAILURE_REGISTER.md`

**Gate 10:** Unresolved critical failure modes block advancement to Phase 11 shadow operation and to Phase 12 live trading.

A critical failure mode is a failure whose credible impact could cause uncontrolled or materially misbounded exposure, unrecoverable state or evidence loss, invalid production decisions, inability to enforce mandatory risk controls, or another outcome the user has defined as intolerable.

This definition does not map to or replace the Phase 5 classifications or the failure register's likelihood, impact, and detectability dimensions.

Post-holdout changes in Phases 8–10 follow Post-Holdout Implementation Deltas in Phase 8.

---

# Phase 11 — Shadow / Paper Trading

Before Phase 11 begins, freeze a Shadow Qualification Plan at `research/qualification_plans/<cycle_id>_<candidate_id>_shadow.md`, recording the cycle ID, candidate ID, and frozen production implementation identity, identified by its SHA-256 and reviewed in a gate record. It is never overwritten or deleted; a revised plan is a new file with a new SHA-256 and its own gate record. It defines:
- minimum time, opportunity, and sample evidence;
- operational error limits;
- allowable deviations from validation expectations;
- fixed-sample or sequential decision logic;
- when the qualification period restarts after a production-relevant change.

Shadow results may diagnose problems but must not silently tune frozen production behavior.

Run the complete production stack using live data.

The system should:
- ingest live data;
- validate it;
- generate features;
- run the standalone predictor;
- calculate probabilities;
- calculate edge;
- size hypothetical positions;
- generate hypothetical orders;
- simulate or record fills;
- monitor performance;
- exercise circuit breakers.

No live capital is risked.

Compare live shadow behavior with historical expectations.

Advance only as the Shadow Qualification Plan specifies.

**Gate 11:** Shadow performance and operational stability must meet the Shadow Qualification Plan before live capital is used. Every Required User Governance Input required by Gate 11 must be resolved, and all required durability policies and restore testing must be verified as in place, before Gate 11 passes.

---

# Phase 12 — Limited Live Pilot

Phase 12 is the earliest phase at which real-capital trading may begin. It requires explicit user approval; passing Gate 11 is not permission to deploy capital.

Start with deliberately limited capital and strict hard caps, using the user-approved starting capital and risk policy.

Before launch, verify:
- venue eligibility, terms, and live-trading restrictions, re-verified from current official sources;
- all Required User Governance Inputs are resolved and recorded;
- manual PAUSE;
- manual KILL;
- automatic circuit breakers;
- position limits;
- monitoring;
- reconciliation;
- restart recovery.

Do not increase capital merely to recover losses.

Increase exposure only when evidence supports it, and increase allocated capital only under the user-approved capital-scaling policy.

Before the initial live pilot, record preregistered real-fill, execution-quality, and scaling criteria at `research/qualification_plans/<cycle_id>_<candidate_id>_live.md`, identified by its SHA-256 in a gate record and never overwritten or deleted. Scaling beyond the initial pilot allocation requires meeting them, accounting for adverse selection, queue and fill uncertainty, and capacity.

---

# Required User Governance Inputs

These values are user decisions. Agents may research consequences and recommend options, but must not choose them. Until a value is explicitly defined and approved by the user, it is an unresolved required input and blocks the gate or step shown.

Record each approved value, with date and approver, in `docs/decisions/`.

Each risk-appetite value must include its semantic definition: bankroll basis; how starting capital relates to the bankroll; drawdown definition; ruin definition and horizon; loss-budget reset semantics; and the capital-scaling envelope. Starting live capital may not exceed the allocated bankroll.

| Input | Required by |
|---|---|
| Bankroll definition / capital allocated to the strategy | Gate 4.5 |
| Maximum acceptable drawdown | Gate 4.5 |
| Acceptable risk-of-ruin tolerance | Gate 4.5 |
| Absolute loss budget, if any | Gate 4.5 |
| Starting live capital | Gate 4.5 |
| Capital-scaling policy | Gate 4.5 |
| Frozen/adjustable classification and envelope for each risk-appetite input | Gate 4.5 |
| Authorized PAUSE/KILL operator roles | Gate 4.5 |
| Alert recipient / on-call role | Gate 11 |
| Acknowledgment and escalation expectations | Gate 11 |
| Backup scope and retention policy for raw captured market data | Before first live capture, and no later than Gate 1 |
| Backup scope and retention policy for each other class of irreplaceable artifact | Before the first irreplaceable artifact of that class is created |
| Restore-test cadence | Gate 11 |
| Incident-record ownership | Gate 11 |

Gate 11 remains the overall live-readiness verification that every required durability policy and restore test is in place. Retention durations are user decisions and are not set by this document.

## Risk-Appetite Change Envelope

At Gate 4.5, classify each user-approved risk-appetite input as either:
1. frozen — any later change is material; or
2. adjustable within an approved envelope — later changes are allowed only within explicitly defined deterministic bounds and rules.

For an adjustable input, Gate 4.5 must define:
- the permitted direction or directions of change;
- the permitted numerical or rule bounds, where applicable;
- why changes inside the envelope remain consistent with the audited risk policy;
- the conditions that make even an apparently conservative change material.

A later change is non-material only if all of the following hold:
- it stays inside the Gate 4.5 approved envelope;
- it does not loosen any hard risk limit unless that loosening was explicitly included in the audited envelope;
- it does not change model, strategy, calibration, threshold, state-behavior, or sizing methodology;
- it does not invalidate execution, liquidity, fee, minimum-order-size, capacity, or other economic assumptions;
- it does not increase risk beyond the audited envelope.

Starting with less capital is therefore not automatically non-material. It is non-material only if the envelope permits it and the resulting system remains inside the audited economic and operational assumptions.

Any increase, loosening, or other change is material unless it was explicitly permitted and bounded by the Gate 4.5 audited envelope and satisfies every condition for a non-material within-envelope change. Any out-of-envelope change, or any change that affects audited economics, behavior, risk semantics, capacity, liquidity, execution assumptions, or other audited conclusions, is material and follows the re-evaluation and re-audit rules.

Capital scaling therefore works only within the pre-approved envelope. Calling a change a capital increase does not make it non-material.

Record the classification and envelope with the risk-appetite decision in `docs/decisions/`, and include its immutable identity in the audit-candidate manifest and the Phase 6 freeze.

---

# Long-Term Retraining

Routine retraining should eventually be capable of operating without agents.

Retraining uses two tiers.

**1. Pre-approved deterministic retraining envelope.** Routine retraining may run without LLM or agent involvement only if it stays entirely inside rules that have been independently reviewed and approved by the user, covering:
- data eligibility;
- feature set;
- target;
- model family;
- calibration method;
- walk-forward evaluation;
- purge/embargo;
- performance, calibration, and economic thresholds;
- risk compatibility;
- challenger/incumbent acceptance;
- control of repeated challenger selection across retraining runs;
- artifact and version checks;
- rollback;
- drift bounds;
- deployment restrictions.

**2. Material-change path.** Any change outside the approved envelope returns to the appropriate development, audit, and freeze process before deployment. This includes new features, targets, model families, calibration designs, strategy logic, sizing logic, execution assumptions, material threshold methodology, data-source semantics, or any otherwise materially different candidate.

Preferred long-term flow:

```
New data
  → automated validation
  → candidate training
  → walk-forward evaluation
  → challenger vs incumbent comparison
  → statistical acceptance rules
  → deploy or reject
```

Automatic deployment of retrained models remains disabled until the envelope's deterministic acceptance rules have been independently reviewed and explicitly approved by the user.

Agents may periodically audit or investigate anomalies, but normal retraining must not require them. Production retraining and deployment must never require an LLM.

---

# Agent Cost Discipline

Use the strongest models where mistakes are expensive.

**High-capability reasoning models:**
- major statistical audits;
- major red-team audits;
- difficult architecture decisions.

**Strong general coding/reasoning models:**
- core engineering;
- research;
- architecture;
- implementation.

**Cheaper models:**
- repository exploration;
- documentation collection;
- repetitive scaffolding;
- straightforward refactors;
- low-risk delegated work.

Do not spend frontier-model inference on mechanical tasks unnecessarily.

---

# First Real Development Task

After all project-control files and agent definitions are completed and committed:

Begin Phase 0. Begin Phase 1 only after Gate 0 and the private-remote and hosted-CI verification that follows it (see Phase 0).

Do not build a predictive model yet.

First:
- establish the engineering foundation;
- verify current official data-source documentation;
- design ingestion;
- determine historical/live data coverage;
- begin replayable high-frequency collection;
- identify data gaps and failure modes.

The first major question is not:

> "Which neural network should we use?"

It is:

> "Can we obtain and preserve data good enough to test the velocity hypothesis honestly?"

---

# Final Principle

Agents build the machine.

The machine must eventually run without the agents.
