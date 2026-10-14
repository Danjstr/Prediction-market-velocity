# Holdout Access Log

This is the append-only audit trail for the protected final chronological holdout.

It records every attempt to access, and every actual access to, the protected holdout, including accidental access.

Each event records the evaluation cycle it belongs to. The Current Status section summarizes the current cycle; earlier cycles remain in the append-only history.

This log does not define or change project governance. The holdout rules are set by PROJECT_BRIEF.md, CLAUDE.md, and START_HERE.md. If this log and those documents ever conflict, those documents govern and the conflict must be surfaced to the user.

---

## Current Status

| Item | Value |
|---|---|
| Current cycle | N/A — no evaluation cycle is registered in the machine ledger (HAL-0005). |
| Holdout status | No protected holdout is registered in the machine ledger (HAL-0005). |
| Protected holdout ever opened | No repository evidence of protected-holdout access (no access_started event; HAL-0001 to HAL-0004 record none); activity outside the governed repository and protocol is not knowable from this log (HAL-0005). |
| Known contamination | None recorded in the machine ledger; prior status none known (HAL-0005). |
| Gate currently authorized to open it | None — opening requires an access_authorized event backed by a committed Gate 6 PASS record and, before access_started, a committed Gate 7 preregistration PASS record. |
| Consumed | No consuming event in the machine ledger; prior status not known to be consumed (HAL-0005). |
| Authoritative split definition | N/A — no holdout is registered for the current cycle. |
| Dataset identity / version / hash | N/A — no holdout is registered for the current cycle. |
| Last event | HAL-0005 |

The status section summarizes the history below. It may change only together with an appended event that justifies the change, and every change must cite that event's ID. If the status section and the history ever disagree, the history is authoritative.

---

## Holdout Rules

These restate the governing documents for convenience. They do not replace them.

- The oldest approximately 70% of the chronological data is for development and training, and the newest approximately 30% is the protected final holdout, as fixed by the frozen immutable partition boundaries defined in START_HERE.md Phase 2.
- Later-arriving data never moves the frozen boundaries; "70/30" is never recalculated over an expanding dataset.
- Never randomly shuffle the time series.
- Development uses chronological walk-forward or rolling validation only inside the development 70%.
- Purge and/or embargo rules apply where required by feature lookbacks, overlapping labels, or forecast horizons.
- The protected holdout must not be used for:
  - feature selection;
  - model selection;
  - architecture selection;
  - hyperparameter tuning;
  - calibration selection;
  - threshold selection;
  - strategy design;
  - risk-parameter tuning;
  - audit-candidate repair.
- Phase 5 independent reviews and Phase 5.5 readiness work must not open the protected holdout.
- The holdout may be opened only after Gate 6, once the frozen system has been verified to match the audited candidate manifest plus the reviewed Phase 5.5 implementation overlay and the user has explicitly approved opening it for that specific candidate and frozen split.
- No observation may become protected evaluation data after it has been exposed to development; see Evaluation Cycles in START_HERE.md.
- Protected holdout observations are stored outside development-agent-readable storage until authorized release.
- Every holdout access is deliberate, explicit, and logged here.
- Repeated peeking is prohibited.
- Premature or accidental opening is a contamination event. It must be logged and escalated, never hidden.
- The protected holdout must never be silently redefined after its results have been seen.
- A contaminated holdout must not be relabeled as development data to erase the event.
- Once outcome-dependent protected information is revealed, the holdout is consumed as defined in START_HERE.md Phase 7, and must never again be treated as untouched data or relabeled as development or validation data.

---

## Gate 6 Opening Checklist

Before any authorized opening, verify and record each item. If any item fails, access must not proceed.

- [ ] Phase 5 Statistical Audit complete.
- [ ] Phase 5 Economic Review complete.
- [ ] Phase 5 Operational Assumptions Review complete.
- [ ] No unresolved blocking findings in any of the three reviews.
- [ ] All material concerns accepted by the user are recorded.
- [ ] The audit-candidate manifest is immutable.
- [ ] The frozen production implementation matches the Phase 5.5 implementation snapshot and differs from the audited candidate only by the reviewed implementation overlay.
- [ ] All production-relevant code, configuration, and artifacts have immutable identities.
- [ ] The candidate-manifest SHA-256 matches the archived audit records.
- [ ] Git state and commit requirements are satisfied.
- [ ] The holdout split identity is frozen before opening.
- [ ] No previous unauthorized exposure of the holdout.
- [ ] Gate 5.5 implementation readiness passed.
- [ ] The holdout has not been consumed.
- [ ] Explicit user approval recorded for this specific candidate and frozen split.
- [ ] The Holdout Evaluation Plan is unchanged and its SHA-256 matches the audit candidate.
- [ ] The correlated-review meta-review is complete, or its unavailability has been explicitly dispositioned by the user.

---

## Accidental or Premature Access

If the protected holdout is opened, read, or evaluated before it is authorized:

1. Stop further holdout use.
2. Preserve all evidence.
3. Append a contamination event to this log.
4. Identify exactly what information was exposed.
5. Identify which people, processes, and candidates were exposed to it.
6. Do not tune or repair any candidate using the exposed information.
7. Escalate to the user for a decision on whether a replacement untouched holdout is required.
8. Never erase the contamination history.

The log must record enough information to establish the scope of an exposure without unnecessarily propagating protected results. If reproducing exact holdout values, predictions, metrics, rows, or outputs in this broadly visible log would widen contamination, preserve the exact evidence in an appropriately restricted evidence artifact and record its immutable reference here instead. The log should still identify what categories of information were exposed and to whom.

---

## Immutability

The Access History section is append-only.

Existing records must never be deleted, rewritten, renumbered, or silently corrected.

A correction must be a new correction record that references the original event ID and states what is being corrected and why.

Commit each new event to Git promptly, so that Git history provides tamper evidence.

---

## Machine-Readable Ledger

From HAL-0005 onward, every event in this log is first recorded in the hash-chained machine ledger `research/holdout_access/ledger.v1.jsonl` by `python -m pmv.holdout_log`. The machine ledger is authoritative for event identity, order, hashes, authorization state, and holdout state. The tool then appends the event's generated Access History entry and regenerates Current Status. `python -m pmv.holdout_log verify-history`, which is part of `scripts/check.sh`, requires the generated history and Current Status to agree exactly with the machine ledger.

HAL-0001 through HAL-0004 predate the machine ledger and are pinned by exact-byte hash in the `log_initialized` event.

Generated entries contain only controlled identities, hashes, counts, timestamps, roles, and enumerated values. Exact protected observations, protected outcomes, metrics, model outputs, and narrative details must not be stored in this log. Restricted evidence may be referenced only by approved identity/hash.

`access_started` and its generated Markdown mirror must be committed in Git before any protected observation can be exposed.

Never edit a generated Access History entry or Current Status by hand.

---

## Event Schema

Every event records, at minimum:

| Field | Description |
|---|---|
| Event ID | Sequential, never reused: HAL-0001, HAL-0002, … |
| UTC timestamp | ISO 8601, UTC |
| Actor / process | Who or what performed or attempted the access |
| Access type | attempted / authorized / accidental / completed, or N/A for non-access records with the reason stated |
| Reason | Why the access occurred or was attempted |
| Project phase and gate | Phase and gate in START_HERE.md at the time |
| Cycle ID | Evaluation cycle the event belongs to |
| Candidate ID | From `research/audit_candidates/` |
| Candidate-manifest SHA-256 | Hash of the candidate manifest file |
| Implementation snapshot identity | Git commit and/or immutable identity of the Phase 5.5 implementation snapshot |
| Implementation readiness review SHA-256 | SHA-256 of the authoritative readiness review that approved the implementation overlay |
| Git commit | Full repository HEAD commit hash at the time of the event |
| Working-tree cleanliness | Clean, or the specific uncommitted files |
| Dataset identity / version / hash | Immutable identifier or hash of the dataset |
| Exact chronological split definition | The split boundaries in force |
| Split freeze timestamp | Record the authoritative value when defined by project governance |
| Development boundary | Record the authoritative value when defined by project governance |
| Purge / embargo definition | Record the authoritative value when defined by project governance |
| Protected holdout boundary | Record the authoritative value when defined by project governance |
| Exact rows / timestamps / partition requested | What was requested |
| Protected data actually exposed | Yes / No, and what |
| Exposure scope | People, agents, sessions, processes, candidates, or downstream artifacts that received or could have received protected information |
| Authorization basis | The gate, checklist, and explicit user approval relied on, including who approved, when, and for which candidate and frozen split |
| Pre-access verification results | Results of the Gate 6 checklist or other checks |
| Operation performed | What was run |
| Metrics / results revealed | What was learned; if exact values would widen contamination, record the exposed metric/result categories and reference the restricted evidence artifact rather than reproducing the values here |
| Downstream decision changed | Whether any decision changed because of the result |
| Contamination status | none known / suspected / confirmed |
| Holdout consumed by this event | Yes / No, with the outcome-dependent information that consumed it |
| Required remediation / escalation | Actions required |
| Evidence / artifact references | Paths, hashes, logs |

Where a field does not apply, state why explicitly, for example `N/A — no audit candidate exists yet`. Never use an invented placeholder value.

Template for new events:

```
### HAL-NNNN — <short title>

- Event ID:
- UTC timestamp:
- Actor / process:
- Access type:
- Reason:
- Project phase and gate:
- Cycle ID:
- Candidate ID:
- Candidate-manifest SHA-256:
- Implementation snapshot identity:
- Implementation readiness review SHA-256:
- Git commit:
- Working-tree cleanliness:
- Dataset identity / version / hash:
- Exact chronological split definition:
- Split freeze timestamp:
- Development boundary:
- Purge / embargo definition:
- Protected holdout boundary:
- Exact rows / timestamps / partition requested:
- Protected data actually exposed:
- Exposure scope:
- Authorization basis:
- Pre-access verification results:
- Operation performed:
- Metrics / results revealed:
- Downstream decision changed:
- Contamination status:
- Holdout consumed by this event:
- Required remediation / escalation:
- Evidence / artifact references:
```

---

## Access History (append-only)

### HAL-0001 — Log initialization

- Event ID: HAL-0001
- UTC timestamp: 2026-10-07T06:53:23Z
- Actor / process: Claude Code development session, at the user's request
- Access type: N/A — initialization record, not an access event
- Reason: Initialize the holdout access log before any dataset or protected holdout exists
- Project phase and gate: Pre-Phase 0 project setup; no gate reached
- Candidate ID: N/A — no audit candidate exists yet
- Candidate-manifest SHA-256: N/A — no audit candidate exists yet
- Git commit: 7cb1d9d85a72b53ed13842741dedcc50f041bcdb (HEAD at initialization; contains only removed practice files)
- Working-tree cleanliness: Not clean — PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md, HOLDOUT_ACCESS_LOG.md, and .claude/ are untracked and not yet committed
- Dataset identity / version / hash: N/A — no project dataset was found in the inspected repository at initialization
- Exact chronological split definition: N/A — no split has been defined yet
- Split freeze timestamp: N/A — no authoritative split has been defined yet
- Development boundary: N/A — no authoritative split has been defined yet
- Purge / embargo definition: N/A — no authoritative split has been defined yet
- Protected holdout boundary: N/A — no authoritative split has been defined yet
- Exact rows / timestamps / partition requested: N/A — no access requested
- Protected data actually exposed: No repository evidence of protected-data exposure was found; no protected holdout dataset or split was found in the inspected repository
- Exposure scope: N/A — no repository evidence of protected information exposure was found during initialization inspection
- Authorization basis: CLAUDE.md requirement that every holdout access be recorded here; START_HERE.md Phase 2 requirement to initialize and maintain this log
- Pre-access verification results: Inspection of this repository found no data files of any common data format, no code, and no split definition. All project directories under configs/, docs/, research/, src/, and tests/ were empty. The repository's Git history contains only two commits, which added and then removed practice files (.gitignore, practice.py, test_practice.py). Every repository reference to the holdout, final 30%, Phase 7, or Gate 6 is in governance documentation, not in data, code, or results.
- Operation performed: Created this log
- Metrics / results revealed: None
- Downstream decision changed: No
- Contamination status: none known from the inspected repository
- Required remediation / escalation: None
- Evidence / artifact references: Repository inspection performed at 2026-10-07T06:47:47Z. Evidence consists of the repository file inventory and Git history at that time. This record covers only the inspected repository.

### HAL-0002 — Governance update

- Event ID: HAL-0002
- UTC timestamp: 2026-10-07T07:20:13Z
- Actor / process: Claude Code development session, at the user's request
- Access type: N/A — governance record, not an access event
- Reason: Coordinated governance update adding explicit user approval to open the holdout, the consumed-holdout definition, the immutable split freeze, and the Gate 5.5 readiness requirement; updates the status table and Gate 6 checklist and adds the "Implementation snapshot identity", "Implementation readiness review SHA-256", and "Holdout consumed by this event" fields. HAL-0001 predates these fields.
- Project phase and gate: Pre-Phase 0 project setup; no gate reached
- Candidate ID: N/A — no audit candidate exists yet
- Candidate-manifest SHA-256: N/A — no audit candidate exists yet
- Implementation snapshot identity: N/A — no implementation snapshot exists yet
- Implementation readiness review SHA-256: N/A — no readiness review exists yet
- Git commit: 7cb1d9d85a72b53ed13842741dedcc50f041bcdb (HEAD at update; project-control documents not yet committed)
- Working-tree cleanliness: Not clean — PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md, HOLDOUT_ACCESS_LOG.md, and .claude/ are untracked and not yet committed
- Dataset identity / version / hash: N/A — no project dataset was found in the inspected repository
- Exact chronological split definition: N/A — no split has been defined yet
- Split freeze timestamp: N/A — no authoritative split has been defined yet
- Development boundary: N/A — no authoritative split has been defined yet
- Purge / embargo definition: N/A — no authoritative split has been defined yet
- Protected holdout boundary: N/A — no authoritative split has been defined yet
- Exact rows / timestamps / partition requested: N/A — no access requested
- Protected data actually exposed: No repository evidence of protected-data exposure was found
- Exposure scope: N/A — no repository evidence of protected information exposure was found
- Authorization basis: User-approved coordinated governance update to PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md, and this log
- Pre-access verification results: N/A — no access
- Operation performed: Updated log structure and status as described under Reason
- Metrics / results revealed: None
- Downstream decision changed: No
- Contamination status: none known from the inspected repository
- Holdout consumed by this event: No
- Required remediation / escalation: None
- Evidence / artifact references: The coordinated governance patch to PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md, and this log, recorded in the same change

### HAL-0003 — Governance update

- Event ID: HAL-0003
- UTC timestamp: 2026-10-07T08:10:16Z
- Actor / process: Claude Code development session, at the user's request
- Access type: N/A — governance record, not an access event
- Reason: Coordinated governance update adding evaluation-cycle semantics and the "Cycle ID" field, the Phase 5.5 prohibition, overlay-aware opening wording, Holdout Evaluation Plan and correlated-review meta-review checklist items, the repository-HEAD-at-event Git commit definition, and the prompt-commit tamper-evidence rule. HAL-0001 and HAL-0002 predate the "Cycle ID" field.
- Project phase and gate: Pre-Phase 0 project setup; no gate reached
- Cycle ID: N/A — no evaluation cycle has been defined yet
- Candidate ID: N/A — no audit candidate exists yet
- Candidate-manifest SHA-256: N/A — no audit candidate exists yet
- Implementation snapshot identity: N/A — no implementation snapshot exists yet
- Implementation readiness review SHA-256: N/A — no readiness review exists yet
- Git commit: 7cb1d9d85a72b53ed13842741dedcc50f041bcdb (repository HEAD at the time of the event; project-control documents not yet committed)
- Working-tree cleanliness: Not clean — PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md, HOLDOUT_ACCESS_LOG.md, .claude/, and research/sources.md are untracked, and .gitignore has uncommitted changes
- Dataset identity / version / hash: N/A — no project dataset was found in the inspected repository
- Exact chronological split definition: N/A — no split has been defined yet
- Split freeze timestamp: N/A — no authoritative split has been defined yet
- Development boundary: N/A — no authoritative split has been defined yet
- Purge / embargo definition: N/A — no authoritative split has been defined yet
- Protected holdout boundary: N/A — no authoritative split has been defined yet
- Exact rows / timestamps / partition requested: N/A — no access requested
- Protected data actually exposed: No repository evidence of protected-data exposure was found
- Exposure scope: N/A — no repository evidence of protected information exposure was found
- Authorization basis: User-approved coordinated governance update to PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md, the agent files, and this log
- Pre-access verification results: N/A — no access
- Operation performed: Updated log structure and status as described under Reason
- Metrics / results revealed: None
- Downstream decision changed: No
- Contamination status: none known from the inspected repository
- Holdout consumed by this event: No
- Required remediation / escalation: None
- Evidence / artifact references: The coordinated governance patch recorded in the same change

### HAL-0004 — Correction of HAL-0001

- Event ID: HAL-0004
- UTC timestamp: 2026-10-07T08:10:16Z
- Actor / process: Claude Code development session, at the user's request
- Access type: N/A — correction record, not an access event
- Reason: Correction of HAL-0001's Reason field, which states "before any dataset or protected holdout exists". That is a global claim beyond the inspected repository. It should read: initialize the holdout access log before any project dataset or protected holdout was found in the inspected repository. HAL-0001 is not modified.
- Project phase and gate: Pre-Phase 0 project setup; no gate reached
- Cycle ID: N/A — no evaluation cycle has been defined yet
- Candidate ID: N/A — no audit candidate exists yet
- Candidate-manifest SHA-256: N/A — no audit candidate exists yet
- Implementation snapshot identity: N/A — no implementation snapshot exists yet
- Implementation readiness review SHA-256: N/A — no readiness review exists yet
- Git commit: 7cb1d9d85a72b53ed13842741dedcc50f041bcdb (repository HEAD at the time of the event; project-control documents not yet committed)
- Working-tree cleanliness: Not clean — PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md, HOLDOUT_ACCESS_LOG.md, .claude/, and research/sources.md are untracked, and .gitignore has uncommitted changes
- Dataset identity / version / hash: N/A — no project dataset was found in the inspected repository
- Exact chronological split definition: N/A — no split has been defined yet
- Split freeze timestamp: N/A — no authoritative split has been defined yet
- Development boundary: N/A — no authoritative split has been defined yet
- Purge / embargo definition: N/A — no authoritative split has been defined yet
- Protected holdout boundary: N/A — no authoritative split has been defined yet
- Exact rows / timestamps / partition requested: N/A — no access requested
- Protected data actually exposed: No repository evidence of protected-data exposure was found
- Exposure scope: N/A — no repository evidence of protected information exposure was found
- Authorization basis: Immutability rules of this log: corrections are made by new correction records
- Pre-access verification results: N/A — no access
- Operation performed: Recorded a correction to HAL-0001
- Metrics / results revealed: None
- Downstream decision changed: No
- Contamination status: none known from the inspected repository
- Holdout consumed by this event: No
- Required remediation / escalation: None
- Evidence / artifact references: HAL-0001 in this log

### HAL-0005 — Machine ledger initialized

- Event ID: HAL-0005
- UTC timestamp: 2026-10-14T05:39:37.482150Z
- Actor / process: `python -m pmv.holdout_log` (log_initialized)
- Access type: N/A — not an access event
- Reason: Initialize the machine-readable holdout access ledger; not an access event
- Project phase and gate: Phase 0 Step 8; no gate reached
- Cycle ID: N/A — not recorded by log_initialized events
- Candidate ID: N/A — not recorded by log_initialized events
- Candidate-manifest SHA-256: N/A — not recorded by log_initialized events
- Implementation snapshot identity: N/A — not recorded by log_initialized events
- Implementation readiness review SHA-256: N/A — not recorded by log_initialized events
- Git commit: `65ddbb1a0dbe382f431cae146bd45353726df4c9`
- Working-tree cleanliness: Not clean — dirty-tree fingerprint `330b22f2f1d1bee4ef5c396f7c4c231d4779aca59b200268e8463537a849a7c3`
- Dataset identity / version / hash: N/A — not recorded by log_initialized events
- Exact chronological split definition: N/A — not recorded by log_initialized events
- Split freeze timestamp: N/A — not recorded by log_initialized events
- Development boundary: N/A — not recorded by log_initialized events
- Purge / embargo definition: N/A — not recorded by log_initialized events
- Protected holdout boundary: N/A — not recorded by log_initialized events
- Exact rows / timestamps / partition requested: N/A — not recorded by log_initialized events
- Protected data actually exposed: No
- Exposure scope: N/A — not recorded by log_initialized events
- Authorization basis: N/A — not recorded by log_initialized events
- Pre-access verification results: N/A — not recorded by log_initialized events
- Operation performed: Created the machine ledger, inserted the approved Machine-Readable Ledger section, and generated Current Status
- Metrics / results revealed: None — this log never records protected results
- Downstream decision changed: No
- Contamination status: none recorded by this event
- Holdout consumed by this event: No
- Required remediation / escalation: None
- Evidence / artifact references: Legacy file `faf41f5f1e00bfc555aee1f34ac4dec38b024469aec8a56aae440e10620f5db7`; HAL-0001 to HAL-0004 bytes `87eb78ec72babd73b946dcd200fe83ee61961efe32954f617fbaeda27f91bee6`; prior status table `d85f21a0e9a72e0dbdfc23e9e4c1369384e1d018903cf422d76abc6df6d9dc33`; machine ledger seq 0, entry `db6eaf5d557eaed25d9f1d815a719d3d4579ab61083784ef2e6e3e7ff57de862`
