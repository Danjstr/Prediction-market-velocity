# Experiment Tracking (Phase 0 Step 6)

Every research run is recorded in a tamper-evident, hash-chained ledger with its exact spec, code and environment identity, inputs, artifacts, metrics, and outcome. Implementation: `src/pmv/integrity.py`, `src/pmv/safe_fs.py`, `src/pmv/experiment_spec.py`, `src/pmv/experiment_ledger.py`, `src/pmv/experiments.py`. Schema documents: `schemas/experiment_ledger_entry_v1.json`, `schemas/experiment_run_spec_v1.json`, `schemas/experiment_run_manifest_v1.json`, `schemas/experiment_ledger_checkpoint_v1.json`. The Python parsers are authoritative; the JSON Schema files document them.

This step provides the store only. It runs no experiments, reads no market data, and never touches the protected holdout.

## Configuration

`[experiments]` in `configs/<environment>.toml`, optional and currently unset:

| Key | Meaning |
|---|---|
| `root` | Absolute path of the store. Must be outside the Git working tree and must not contain, or be inside, the raw-storage root. Owned by the current user, not writable by group or others. No default. |

The store refuses to open while `root` is unset, relative, a symlink, nested with the repository or raw root, or on a filesystem without `RENAME_NOREPLACE` and `flock`.

The ledger is created only when a store is opened for the first time and is pristine: no run reservation, no run directory, no repair evidence, no pending-repair marker, and no checkpoint. Creation first writes the permanent store identity `store.v1.json` (a random 128-bit `store_id`, read-only, closed schema `schemas/experiment_store_v1.json`), then the ledger. Ledger entry 0 is always the `ledger_created` genesis entry, which records that `store_id`; no other entry may be `ledger_created`, and every verification requires the genesis `store_id` to equal the store's record, so a ledger copied from another store is refused. Creation is atomic: the genesis line is staged, synced, and moved into place with `RENAME_NOREPLACE`, so the ledger never exists without entry 0. A missing ledger in a store with any prior history is an integrity failure and is never recreated, and an empty ledger is always an integrity failure. The ledger file's identity is pinned when the store opens; a ledger replaced while the store is open is refused, and a ledger naming runs that this store never reserved is refused.

## Layout

```
<root>/
  .run_ids/<run_id>                 permanent run-ID reservation
  runs/<run_id>/run_spec.json       immutable spec (0400); spec_sha256 = SHA-256 of these bytes
  runs/<run_id>/environment.json    canonical environment document (0400), present exactly when
                                    a fingerprint was recorded (docs/reproducibility.md)
  runs/<run_id>/artifacts/<name>    registered artifacts (0400)
  runs/<run_id>/.staging/           private temporary files; never trusted
  runs/<run_id>/manifest.json       completed runs only (0400); run directory then 0500
  ledger/experiments.v1.jsonl       AUTHORITATIVE global hash-chained ledger
  ledger/repair/torn-*.bin          immutable torn-tail repair evidence (0400)
  ledger/repair-pending-<store_id>-<evidence name>
                                    durable pending-repair marker: a copy of the torn bytes (0400)
  store.v1.json                     permanent store identity (0400), bound by ledger entry 0
```

Run IDs are `YYYYMMDDTHHMMSS.ffffffZ_<32 lowercase hex>`. A run is identified by `run_id`, `study_id`, and `spec_sha256`; there is no separate experiment ID. Reservations are permanent and IDs are never reused.

## Run spec

`run_spec.json` (closed schema `pmv.experiment.run_spec` v1, at most 1 MiB) holds the study, entrypoint, the `calibration`, `experiment`, `features`, `model`, and `validation` sections, seeds, inputs, splits accessed, `informed_by` (runs whose results informed this spec), and selection metadata. Section values are "safe values": no floats, free text, paths, or secret-like keys, nesting at most 8. Each section's SHA-256 is recorded in the execution identity.

Inputs are exact, hash-pinned references, and v1 has only two kinds:

- `raw_capture`: a Step 5 capture ID and its manifest SHA-256, verified against the configured raw store.
- `run_artifact`: a registered artifact of a **completed** run, by run ID, name, and SHA-256, verified against the bytes on disk and the ledger.

A derived dataset that cannot be expressed this way must not be used as an input until it can. `protected_holdout` is refused as a split in specs and metrics.

## Execution identity and eligibility

`run_started` records a closed execution-identity object and its SHA-256: spec hash, code commit, dirty flag and dirty-tree fingerprint, package version, `uv.lock` SHA-256, installed-environment SHA-256, application-config SHA-256, per-section SHA-256s, Python version, platform, and entrypoint. It never records a hostname or username.

- **Dirty-tree policy.** Dirty or unknown code, or a missing `uv.lock`, forces the effective run class to `exploratory` and makes the run ineligible. Git runs with a clean environment and fixed options; skip-worktree and assume-unchanged entries count as dirty. If the code identity differs at completion, the run is failed with `code_identity_changed`.
- **Temporal eligibility.** `effective_run_class_at_start` and `evidence_eligible_at_start` are computed once, from the ledger prefix before `run_started`, and never change. A run is eligible at start only if its class is `evidence_candidate`, an installed-environment fingerprint exists, every raw-capture input was produced by clean code, and every run-artifact producer is eligible as of that prefix.
- **As-of eligibility.** `eligibility_as_of(run_id, seq)` additionally requires the run to be completed and not superseded at `seq`, transitively through run-artifact inputs. Supersession changes later as-of answers, never history.
- **v1 limitation (Option B), unchanged for v1.** `installed_environment_sha256` must be null in a v1 execution identity, because `uv.lock` does not prove what is installed. The format enforces this, not only the writer: a v1 identity with a non-null value cannot be constructed or parsed, so a ledger containing one fails verification. **No v1 run can be evidence-eligible**, and v1 ledgers are still verified exactly that way.
- **v2 (Phase 0 Step 10).** Writers now emit ledger entry v2 with execution identity v2. Its `installed_environment_sha256` is the fingerprint of the installed environment (`docs/reproducibility.md`).
  - **Start:** an `evidence_candidate` start is refused, before anything is written, unless `python -m pmv.reproducibility verify` passes. It is never demoted to exploratory. The canonical document is written once as `environment.json`.
  - **Completion:** the fingerprint is recomputed; a change fails the run with `environment_changed`.
  - **Ledger checks:** a clean `evidence_candidate` start without a fingerprint is refused by the ledger verifier. Entry versions never go backwards.
  - **Other run classes** record a fingerprint when one can be computed and null otherwise; they are never eligible.

## Lifecycle

States: reserved → started → completed, failed, aborted, or interrupted. Completed runs may later be superseded by another completed run.

1. `reserve_run()` creates the reservation and `runs/<id>/`, takes the run's exclusive lock (held for its active life), and appends `run_reserved`.
2. `start(spec)` verifies inputs, writes `run_spec.json` once (a refused start may be retried with the identical spec), and appends `run_started`.
3. `write_artifact()` / `staging_path()` + `commit_artifact()` write into private staging, sync, move with `RENAME_NOREPLACE` into `artifacts/`, set 0400, and append `artifact_registered`. Artifacts are never overwritten.
4. `record_metric()` stores exact integer or decimal text (NaN and infinity refused); `record_warning()` stores an enumerated code.
5. `complete()` re-checks code identity, verifies inputs and every artifact, requires `artifacts/` to hold exactly the registered files and staging to be empty, writes the pre-terminal `manifest.json`, and appends `run_completed` with its SHA-256 using compare-and-append (the ledger must still end where the manifest says).
6. `fail()` records only the exception's type name, never its message. `abort()` records an enumerated reason.

The manifest is non-circular: it records the run's ledger prefix up to its last pre-terminal entry (`ledger_seq_last_preterminal`, `last_preterminal_entry_sha256`), and `run_completed` records the manifest's hash. Every ledger verification rebuilds each completed run's manifest from the ledger and requires its SHA-256 to equal `run_completed.manifest_sha256`; `verify_run()` additionally requires the on-disk manifest to equal those bytes exactly.

Every run-local durable step (spec, artifact, manifest) re-checks, after its files and directories are synced, that `<root>/runs/<run_id>` still names the locked run directory. Every ledger event of a locked run re-checks it again before the ledger lock, immediately before the write, and after the write and read-back. A detached or replaced run directory never yields a reported success.

## Ledger appends

Every authoritative append:

1. takes the ledger's exclusive `flock` (lock order: run lock, then ledger lock; bounded waits; readers take shared locks);
2. re-walks the configured root and confirms the root, ledger directory, repair directory, and ledger file are the ones in use (`st_dev`, `st_ino`);
3. verifies the entire ledger from byte 0, together with checkpoints and repair evidence (no incremental caching);
4. checks the file size is unchanged, writes one canonical line, and rolls back by truncation on any short or failed write;
5. reads the line back and re-walks identity again.

If anything fails after the write (read-back, size, root, ledger, or run-directory identity), the line may already be durable somewhere, so the error says the write outcome is unknown and the authoritative state must be re-verified; the store latches and refuses further writes until a new store re-verifies the ledger. A short or failed write that was rolled back was not recorded. If rollback itself fails, the damaged bytes stay in place and every later append is refused as a torn tail.

Entry 0 is always `ledger_created`, and only entry 0 may be. Each entry is version 1 (`schemas/experiment_ledger_entry_v1.json`) or version 2 (`schemas/experiment_ledger_entry_v2.json`); a version-1 entry may not follow a version-2 entry. Each entry carries `ledger_seq` (from 0, +1), `prev_entry_sha256` (null for the first), and `entry_sha256` (SHA-256 of the canonical entry without `entry_sha256`). Verification checks canonical bytes, closed per-event field sets, sequence continuity, every hash and link, the run state machine, and recomputes start eligibility.

## Checkpoints

`append_checkpoint()` appends `(ledger_seq, entry_sha256, recorded_at)` to `research/experiment-ledger-checkpoints.v1.jsonl` in the repository. Every ledger read requires each checkpoint to still be present in the ledger, which detects complete entries removed from the end **up to the latest checkpoint**. Checkpoints are never committed automatically; `checkpoint_status()` reports which local entries are also in the committed `HEAD`. Committing the file is an explicit operator action, and only committed checkpoints resist an attacker who can rewrite the working tree.

## Recovery

`recover()` tries a non-blocking lock on each run directory. Locked runs are active and untouched. Unlocked reserved or started runs get `run_interrupted`; their files are left in place and reported (staging leftovers, unregistered artifacts, an orphan manifest). Reservations without a ledger event are reported as `reserved_unrecorded`. Nothing is deleted, resumed, or rewritten. Interrupted runs are never resumed; a replacement gets a new ID.

## Torn-tail repair (operator only)

A ledger that ends without a newline (for example after a crash mid-write) blocks all reads and appends. `repair_torn_tail()` is the only way forward and is never called automatically:

1. The torn bytes are written to staging, synced, verified, and moved with `RENAME_NOREPLACE` to `ledger/repair/torn-<offset>-<length>-<original size>-<last seq|none>-<last sha|none>-<torn sha>.bin` (0400).
2. A pending-repair marker `ledger/repair-pending-<store_id>-<evidence name>` is created with `RENAME_NOREPLACE`: a read-only copy of the torn bytes whose name binds the store identity, the evidence name, and through it the evidence SHA-256, length, original ledger size, truncation offset, and last valid `ledger_seq` and `entry_sha256`. The file and its directory are synced.
3. All identities are re-walked (below), and only then is the ledger truncated to the last complete line and synced.
4. A `ledger_tail_repaired` event referencing the evidence is appended through the normal append path, read back, and identity-checked.
5. Only then is the marker removed and `ledger/` synced. The ledger event is the permanent record; a crash before or during removal leaves the marker, and `repair_torn_tail()` finishes the removal.

While any marker exists, the store is in a pending-repair state: every ordinary read and append (including `snapshot()` and `recover()`) refuses with "a ledger repair is pending", even though the truncated ledger itself verifies. Markers live in `ledger/`, not `ledger/repair/`, so moving or replacing the repair directory cannot hide a pending repair; and replacing `ledger/` itself removes the ledger, which a used store never accepts. On resume, evidence missing from `ledger/repair/` is re-created from the marker's exact bytes before the event is appended.

Immediately before truncating, repair re-walks the root, `ledger/`, `ledger/repair/`, and the evidence file from the configured path without following symlinks, requires the evidence to be the same file that was written (or verified, on resume), re-reads it and checks its length and SHA-256, and requires the ledger to still hold exactly the bytes it verified. If any check fails, the ledger is not truncated and the store latches. Normal appends refuse while evidence exists that no ledger event references. Repair resumes safely after a crash at any step, and a torn repair event is itself preserved and repaired. Repair refuses if the truncation would contradict a checkpoint, and a malformed complete line is never treated as a torn tail.

## Limits

- Tamper evidence is detection, not prevention; the owner can change or delete files.
- Deliberately deleting a pending-repair marker together with the repair evidence is undetectable without a checkpoint, like deleting complete entries from the end of the ledger.
- An older copy of this store's own ledger (a prefix) is detectable only by a checkpoint. Truncation of complete entries is detectable only up to the latest checkpoint, and only committed checkpoints are independent of the working tree.
- Crash tests kill real processes at each boundary; they demonstrate process-crash behavior, not host power loss.
- No v1 run is evidence-eligible. A v2 run's environment fingerprint has the limits listed in `docs/reproducibility.md` (it does not cover the standard library, system libraries, kernel, or CPU).
- The store records what runs did; it cannot prove a run read only its declared inputs.
