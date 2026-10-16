# Gate Records (Phase 0 Step 7)

Every gate decision is recorded as an immutable, generated file at `docs/decisions/gates/<gate_id>_<record_id>.md`, as START_HERE.md requires. Implementation: `src/pmv/gate_record.py` (schema, rendering, lineage rules) and `src/pmv/gates.py` (tooling). Schema document: `schemas/gate_record_v1.json`. The Python validators are authoritative.

This step provides the tooling only. No gate decision had been recorded when this step was written. *Status (2026-10-16): Gate 0 PASS was recorded at `db09acd`; Gate 1 has not been decided (`docs/phase1.md`).* Gate 0's record is created only after the full Phase 0 audit (Step 11) and its approved corrections.

**Gate 7 is the final protected-holdout result** (PASS, FAIL, or INCONCLUSIVE; START_HERE Phase 7), not preregistration sign-off. The v1 holdout-access tooling still uses a Gate 7 PASS record as pre-reveal plan approval. That is a recorded mismatch (Step 11 F-18), described in `docs/holdout_access.md`, and must be fixed before the Phase 7 reveal.

## What is authoritative

- The whole Markdown file is generated: a fixed "do not edit" header, a deterministic summary, and one fenced canonical JSON record (sorted keys, ASCII, no floats). The verifier parses the JSON, re-renders the entire file, and requires byte equality, so any edit, including to the summary, fails verification.
- A record's authoritative hash is the SHA-256 of the exact file bytes. It is never stored inside the record.
- The record contains only enums, identifiers, hashes, timestamps, and repository paths. The primary secret protections are structural: closed schemas, restricted alphabets and types, pinned repository-relative paths, and no arbitrary prose or tool output. A redaction check on every string is defense in depth only; most secret formats cannot even be expressed in the allowed alphabets. Human rationale lives in separately tracked documents (for example review or audit Markdown under `docs/` or `research/`), referenced by path and SHA-256 and pinned to the recorded commit.
- There is no index and no separate gate ledger. Listing scans the directory. Git history is the durable history.

## Creating a record does not publish a decision

`create_gate_record()` (or `python -m pmv.gates create`) writes one new file and leaves it **untracked**. It never stages, commits, or pushes. The decision becomes part of durable project history only when the project owner reviews the file and commits it.

**Commit a gate record in a new commit. Never amend it into the commit whose state it records.** `project.commit` must stay in `HEAD`'s history and must be a strict ancestor of the commit that introduces the record; an amended or rewritten project commit fails verification.

## Record contents

| Field | Meaning |
|---|---|
| `record_id` | `YYYYMMDDTHHMMSS.ffffffZ_<32 hex>`; its timestamp equals `decided_at` |
| `gate_id` | `gate_0`, `gate_1`, `gate_2`, `gate_3`, `gate_4`, `gate_4_5`, `gate_5`, `gate_5_5`, `gate_6`, `gate_7`, `gate_8`, `gate_9`, `gate_10`, `gate_11` |
| `scope` | `cycle_id`, `candidate_id` (identifiers or null); with `gate_id`, the lineage key |
| `decision` | `pass`, `fail`, `inconclusive` |
| `reasons` | Fail reasons or inconclusive reasons (closed enums); empty for pass |
| `findings` | `finding_id`, `severity` (`blocking`/`non_blocking`), `status` (`open`/`resolved`/`accepted_by_owner`), optional document of kind `review` or `audit` |
| `reviews` | Recommendations: controlled `role`, `conclusion` (`recommend_pass`/`recommend_fail`/`recommend_inconclusive`), `independence`, optional document of kind `review` or `audit` |
| `final_decision` | Always `role: project_owner`, `approval_requirement: required`, `approval_attested: true` |
| `project` | Commit, dirty state and fingerprint (`dirty_tree_sha256` is set exactly when `tree_dirty` is true), the four governance files' hashes, every `configs/*.toml` hash |
| `experiment_ledger` | Pinned head: `store_id`, `ledger_seq`, `entry_sha256`, and the latest checkpoint at or before it |
| `evidence` | Runs, artifacts (each artifact's run must also be listed under runs), raw captures, documents (kinds `audit`, `checklist`, `plan`, `policy`, `review`), checks, and `holdout` (always empty in v1) |
| `supersedes` | The committed lineage head this record replaces, by `record_id` and whole-file SHA-256 |

## Decisions

- **PASS** applies only to the exact commit, configs, governance files, pinned ledger head, runs, artifacts, captures, and documents it names; it never carries over to a different model, code state, data, calibration, or execution semantics. It requires: every blocking finding `resolved` (`accepted_by_owner` never resolves a blocker); a clean project tree; a passing `check_sh` run by the tool; candidate and supporting runs completed and evidence-eligible as of the pin; every artifact coming from such a candidate or supporting run (an artifact from a `baseline`, `counter`, or `failed_attempt` run can never support a PASS); and no reasons.
- **FAIL** requires at least one fail reason: `criteria_not_met`, `blocking_review_finding`, `leakage_detected`, `negative_after_cost_economics`, `calibration_failure`, `data_insufficient`, `control_missing`, `integrity_failure`, `unresolved_critical_failure_mode`. Evidence stays referenced; nothing is deleted.
- **INCONCLUSIVE** is a real outcome and requires at least one reason: `insufficient_sample`, `missing_required_evidence`, `unstable_metric`, `unresolved_data_quality`, `execution_uncertainty`, `statistical_uncertainty`, `policy_not_defined`, `required_review_missing`, `review_not_independent`.
- No statistical thresholds are encoded here; they belong to each gate's plan documents, referenced as evidence.

## Recommendation versus decision

Reviewers recommend by role: `ml_engineer`, `data_scientist`, `statistician`, `independent_statistical_auditor`, `quant_business_lead`, `reliability_red_team`, `risk_performance_engineer`, `api_execution_engineer`, `meta_reviewer_human`, `meta_reviewer_other_model_family`. No personal names are stored.

The final decision is always the project owner's. In v1 **every gate decision, including Gate 0, requires explicit project-owner approval**; there is no gate-specific exception, and the request cannot choose otherwise. Every record has `approval_requirement: required` and `approval_attested: true`; creation refuses anything else. Agents and reviewers only recommend; their recommendations never substitute for the owner's decision. The attestation records the operator's explicit assertion that owner approval occurred.

This rule is stricter than START_HERE ("user approval is required only where governance already requires it"). The owner approved keeping it on 2026-10-14 (Step 11 F-42).

**Limitation:** owner approval is recorded procedurally. The system does not cryptographically prove that the owner personally set the flag or made the commit. Under the Phase 0 threat model (`docs/protected_information.md`) this is acceptable as a procedural control. Gate records are created by the owner from a normal terminal, not from an agent session. Commit signing is deferred (Step 11 F-14: before the first real protected scope or Gate 6 authorization).

## Binding to one repository state

1. Capture the project identity: `HEAD` commit, dirty state and fingerprint, governance and config hashes. "Clean" means clean apart from untracked, valid gate records in the gate directory; otherwise the Step 6 dirty-tree fingerprint (which covers the whole working tree) identifies the state.
2. Run `./scripts/check.sh` (output discarded; only `passed`/`failed` is recorded).
3. Capture the identity again; any difference refuses the record.
4. Verify evidence, build the record, and capture the identity once more immediately before writing; any difference refuses the record.
5. Write a temporary file in the gate directory, sync it, move it into place with `RENAME_NOREPLACE`, sync the directory, and read it back. An existing file is never replaced.

The record is written only after its project identity is pinned, so it cannot contaminate the identity it records.

## Evidence pinning

- **Documents** must be under `docs/` or `research/` (never the gate directory), tracked at `HEAD`, and byte-identical to `HEAD` with the referenced hash.
- **Experiment evidence** requires a pin `{ledger_seq, entry_sha256}` that matches the verified ledger; the record also stores the store's `store_id`. Every referenced run must be reserved and terminal at or before the pin; evidence after the pin is invisible. Each run's state and `eligibility_as_of(run_id, ledger_seq)` are evaluated at the pin only. Artifacts must be registered at or before the pin with the referenced hash, and their bytes are re-verified. Later supersession of a run never changes an existing record.
- **Run files are verified, not just the ledger (Step 11 F-13).** Every referenced run, and every run that produced one of its run-artifact inputs (transitively), must pass the experiment store's own `verify_run`: spec, `environment.json`, registered artifacts, and completion manifest. If a file is missing, tampered with, or inconsistent, the record is refused, even when the ledger says the run is eligible.
- Every artifact's producing run must be listed in `evidence.runs` and so is checked at the pin.
- **Eligibility by run version.** A v1 run is never evidence-eligible. A v2 `evidence_candidate` can be eligible (`docs/reproducibility.md`). However, **no real v2 experiment may count as evidence, and no gate may rely on one,** until the remaining execution-boundary items (Step 11 F-19: cached bytecode, working-directory shadowing) are resolved.
- Run roles are declarations made by the record's creator. Step 7 verifies their allowed semantics and the referenced evidence, but it cannot prove that a run was given the scientifically correct role (for example, that a run labelled `baseline` was not really the candidate). Methodological review remains responsible for that.
- **Raw captures** are verified with the Step 5 store and must match the referenced manifest hash.
- **Protected-holdout evidence** is rejected by evidence, not by gate number: any `evidence.holdout` entry and any `holdout_evaluation` document are refused. Linking Step 8 holdout-access events into gate records is not designed yet (Step 11 F-18, before the Phase 7 reveal). Gate 6 and Gate 7 records without such evidence are allowed. Step 7 never accesses the protected holdout.

## Lineage and supersession

A lineage is `(gate_id, cycle_id, candidate_id)`. Its first record is the root; each later record supersedes the current head by `record_id` and whole-file SHA-256. Records are never edited.

Creation refuses a second root for a lineage, and refuses a successor unless the predecessor is the current head, is tracked and in `HEAD` with exactly the committed bytes, matches the named SHA-256, and is older than the successor. A root may stay untracked until the owner commits it; it can be superseded only after it is committed.

## History verification

`python -m pmv.gates verify-history` (run by `scripts/check.sh` and therefore by CI) fails if:

- Git history shows any gate record modified, deleted, renamed, or replaced (only additions are allowed). The scan uses `--full-history -m`, so a merge commit's changes are checked against every parent: a merge cannot modify, delete, or replace a committed record, and neither can a side branch merged with the `ours` strategy;
- a record's `project.commit` does not exist, is not in `HEAD`'s history, or (for a committed record) is not a strict ancestor of the commit that introduced the record;
- the index or working tree differs from `HEAD` for a committed record, or a committed record is missing;
- any file in the gate directory is not a valid, exactly rendered record (including leftover temporary files);
- any lineage has more than one root, a fork (competing successors), a cycle, a dangling or cross-lineage reference, a stale or uncommitted predecessor, or a hash mismatch;
- the clone is shallow, `info/grafts` rewrites history, or any Git replace ref exists (Step 11 F-20). History is always read with `GIT_NO_REPLACE_OBJECTS=1`;
- a clean-tree record's governance or config hash, or its set of `configs/*.toml`, does not match the files at its recorded `project.commit` (Step 11 F-21). The pins are re-derived from that commit, not trusted. A dirty-tree record (only FAIL or INCONCLUSIVE can be one) cannot be re-derived, so it is checked only for canonical form.

**What history verification can and cannot catch.** It detects non-canonical, edited, moved, or deleted records, and records whose pins disagree with their commit. It cannot detect a record that was hand-made with correct pins but a false `check_sh` result or a false approval. That needs owner signatures (F-14) and the hosted-CI corroboration in Step 12.

It verifies the immutable record files and the Git history only. It does not re-evaluate mutable or live external evidence (the experiment store, raw captures, or documents as they are now); the hashes and the experiment-ledger pin preserve exactly what the gate referenced when it was decided. In particular, run files are verified with `verify_run` only when a record is created (F-13), not again by history verification. Whether history verification should also re-verify referenced experiment artifacts is deferred to an explicit design decision (Step 11 red-team RT-2), due before a gate relies on experiment evidence.

## Operating rules and recovery

- Make `scripts/check.sh` (and therefore `verify-history`) a required CI check before gate-record changes are merged into the eventual main branch. Two branches can each hold a valid successor of the same record; only verification of the merge result catches the fork.
- A forked lineage, a leftover `.tmp-*` file, or any record added or edited outside the tooling makes verification, and every later `create`, fail closed. That is intended. Recovery is an explicit operator decision after inspection (for example removing an uncommitted stray file, or reverting an unmerged branch); nothing is deleted or repaired automatically, and a committed record is never edited or removed.

Local Git is **not** an external or immutable anchor. These checks are integrity checks over the ancestry of the current `HEAD`: a local reset, rebase, or branch switch can remove a committed record without anything inside the repository noticing.

The Step 12 private remote adds an off-host backup copy and a second witness of history at push time. It is still not notarization: the owner or an administrator can force-push or delete. An external anchor for the holdout log and protected scopes is required before the first real protected scope and before the Phase 7 reveal (Step 11 S-1).

## Command line

```
python -m pmv.gates verify-history
python -m pmv.gates verify docs/decisions/gates/<file>.md
python -m pmv.gates list
python -m pmv.gates create --request request.json --config configs/<env>.toml --environment <env>
```

`create` reads a closed JSON request (every field required; unknown fields, duplicate keys, and floats rejected) with the fields `gate_id`, `decision`, `reasons`, `findings`, `reviews`, `approval_attested`, `cycle_id`, `candidate_id`, `experiment_ledger` (`{ledger_seq, entry_sha256}` or null), `runs`, `artifacts`, `raw_captures`, `documents`, `holdout`, `run_check_sh`, and `supersedes`. It opens the experiment store and raw store from the configuration only when the request references them.

Errors are reported as one line with an error type and a fixed message; configuration errors, `check.sh` timeouts, and operating-system errors never print tracebacks, paths, file contents, or subprocess output.

## Limits

- Attestation is an assertion, not proof of identity.
- The project-identity binding observes the repository at three points. A file changed and restored byte for byte between observations is not detected. Gitignored files (for example the virtual environment) are outside the identity unless separately pinned. A very small interval remains between the final identity capture and the physical creation of the record file.
- The dirty-tree fingerprint of a FAIL or INCONCLUSIVE record identifies the state but cannot reproduce it.
- Git history protection depends on the history itself being intact and complete.
