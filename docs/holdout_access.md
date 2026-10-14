# Protected-Holdout Access Log (Phase 0 Step 8)

Durable, tamper-evident evidence of every authorized or attempted interaction with the protected final holdout. Implementation: `src/pmv/holdout_record.py` (schema, chain, state machine, Markdown rendering) and `src/pmv/holdout_log.py` (tooling and command line). Schema document: `schemas/holdout_access_event_v1.json`. The Python validators are authoritative.

Step 8 is logging and integrity only. It never opens, reads, creates, or reveals protected holdout data; it handles identities, hashes, counts, timestamps, roles, and enumerated values. Physical isolation and enforcement of the reveal boundary are Step 9.

## Authority

- **`research/holdout_access/ledger.v1.jsonl`** is the authoritative record of event identity, order, hashes, authorization state, holdout and cycle state, and consumption. One canonical JSON event per line, hash-chained (`ledger_seq` from 0, `prev_entry_sha256`, `entry_sha256`); event IDs continue the existing numbering (`HAL-NNNN` = `ledger_seq` + 5). It lives in Git.
- **`HOLDOUT_ACCESS_LOG.md`** remains the required human-visible governance log. From HAL-0005 every ledger event has exactly one generated Access History entry (using the existing template's field names), and Current Status is generated from the ledger. HAL-0001 to HAL-0004, and every other byte of the file except the one approved Machine-Readable Ledger section, are pinned by hash in HAL-0005 (`log_initialized`) and never rewritten.
- The tool may change `HOLDOUT_ACCESS_LOG.md` only by inserting the approved section once (at initialization), regenerating Current Status, and appending generated entries. Never edit a generated entry or Current Status by hand.

## Events

| Event | Meaning | Consumes? |
|---|---|---|
| `log_initialized` | HAL-0005 only: pins the reviewed legacy file, its fixed parts, HAL-0001–0004, and the prior status | – |
| `cycle_registered` | `cycle_id`, split-formation method, development subset, protected interval; owner attested | – |
| `holdout_registered` | `holdout_id`, cycle, split definition (`research/splits/<id>.yaml`), snapshot-manifest, metadata, purge/embargo, and source-manifest hashes, observation count, time bounds; owner attested | – |
| `access_requested` | Exact candidate identity and its hash; requesting role | No |
| `access_authorized` | Owner authorization of a request, backed by a committed, current Gate 6 PASS record | No |
| `access_denied` | Owner denial of a request (closed reason) | No |
| `access_started` | Durable pre-reveal intent, after re-verifying Gate 6, the Gate 7 preregistration, the plan, and the candidate | **Yes — permanently** |
| `access_completed` / `access_failed` / `access_interrupted` | Closes a started access (no results or metrics, ever); each may carry a restricted evidence hash | Stays consumed |
| `access_attempt_refused` | Any refused start or request, recorded before the error is raised | No |
| `contamination_recorded` | Suspected or confirmed exposure (categories and roles, restricted evidence by hash) | **Yes** |
| `historical_reclassification` | Tags a consumed holdout as historical development data, given a new untouched holdout of another cycle | Stays consumed |
| `correction_recorded` | Annotative only; references a document by hash; never changes or reverses state | – |

## Consumption (strict v1)

`access_started` is the first consuming event. Once it is durable, the holdout is consumed for that holdout and cycle permanently — even if no metric is produced, the evaluation fails or crashes, exposure was partial or cannot later be proven, or the result is PASS, FAIL, or INCONCLUSIVE. A suspected or confirmed contamination also consumes. There is no "aborted before exposure, therefore untouched" exception: v1 deliberately prefers false consumption to accidental reuse of exposed evidence. Nothing can be requested, authorized, or started against a consumed holdout, an authorization is single-use, and retries are refused and logged.

## Candidate exactness

`access_requested` binds a closed candidate identity object (`schemas/holdout_access_event_v1.json`, `candidate_identity`): cycle, holdout, and candidate IDs; the project commit (tree must be clean); the experiment-ledger pin (`store_id`, `ledger_seq`, `entry_sha256`); and non-empty typed references for the candidate manifest, readiness review, model, feature definition, preprocessing, calibration, configs, cost assumptions, execution assumptions, input definition, evaluation plan (exactly one repository file), and deterministic runner. References are repository files (byte-identical at the project commit, at `HEAD`, and in the working tree) or Step 6 run artifacts (registered at or before the pin with the same hash, bytes re-verified).

The identity is recomputed at authorization, at `access_started`, and by `assert_started_committed`. It fails if any reference changed (`runner_mismatch`, `evaluation_plan_mismatch`, `candidate_changed`), if the project commit left `HEAD`'s history, or if anything other than the holdout ledger, its mirror, or gate records changed since the project commit. An authorization never survives a material candidate change.

## Gate 6 and Gate 7

- `access_authorized` requires a committed Gate 6 **PASS** record that is the current head of its lineage, is scoped to the exact cycle and candidate, and cites the candidate's evaluation plan (kind `plan`, same path and hash); plus owner attestation.
- Before `access_started` there must be a committed Gate 7 **PASS** record — the durable preregistration approval — that is the current head of its lineage, is scoped to the same cycle and candidate, cites the same evaluation plan, and (as every Step 7 v1 record) contains no protected-holdout evidence and carries owner attestation.
- Immediately before `access_started` is accepted, both records, the plan, and the candidate identity are revalidated. Any superseded, modified, missing, or mismatched record refuses the start and appends `access_attempt_refused`. Step 8 does not define post-holdout Gate 7 result semantics.

## The protocol and the reveal precondition

request → authorization (Gate 6) → Gate 7 preregistration → `access_started` → mirror consistent → Git commit → `assert_started_committed` → Step 9 reveal → closing event.

`python -m pmv.holdout_log assert-started-committed HAL-NNNN` (or `HoldoutLog.assert_started_committed`) reports ready only when: the ledger and mirror verify and agree; the `access_started` event exists and is open; the exact ledger and `HOLDOUT_ACCESS_LOG.md` bytes are in `HEAD` with working tree and index matching; the tree is clean; Gate 6 and Gate 7 are committed and current; and the candidate and runner identity still match. Step 9 must call it immediately before physical reveal. Step 8 itself never opens protected data.

## Writing

One writer lock (on `research/holdout_access/`) covers: full ledger verification; verification that the Markdown mirror agrees exactly; the ledger append (one write, rollback on a short write, fsync, read-back, repository/directory/ledger identity re-checked before and after, latch after any failure); and the Markdown rewrite (synced temporary file, atomic rename, read-back). If a crash leaves the mirror behind the ledger, every normal append refuses until `python -m pmv.holdout_log mirror` brings the Markdown forward; `mirror` derives only from the verified ledger and never changes it.

## Tamper evidence and its limits

- Readers detect altered, reordered, duplicated, gapped, malformed, and torn entries and broken links. A torn or malformed ledger fails closed. **There is no repair tooling** (`mirror` is not repair): recovery is to preserve evidence, inspect, and make an explicit owner decision.
- HAL-0005 is never trusted as self-asserted: every verification finds the reviewed legacy `HOLDOUT_ACCESS_LOG.md` in Git history by its SHA-256, re-derives the `log_initialized` fields from those bytes (preamble, fixed body with the approved section inserted, HAL-0001–0004, prior status table), requires exact equality, and requires the Markdown's fixed regions to match those hashes.
- **History is verified on every authoritative path.** The full Git-history verification runs inside the writer lock before every append (every event type, including refusals) and inside `assert_started_committed`. It walks every commit in `HEAD`'s history, including merges against every parent, ignores replace objects, and fails on shallow clones or `info/grafts`. Once created, the ledger is never removed and every committed version is a byte-prefix of every later one, so a committed `access_started` that is later reverted or rewritten *forward* makes every append and the reveal check fail: durable history that once held a consuming event dominates the current working tree.
- **Mirror at past commits and at `HEAD`.** At each past commit the mirror must be exactly the rendering of a prefix of that commit's ledger — it may lag after a legitimate partial commit, but never lead or diverge — and the number of events it shows never decreases, so the fixed governance text and HAL-0001–0004 stay byte-identical and generated history is append-only. At `HEAD` the mirror must show the whole ledger exactly, including Current Status: a ledger-only `HEAD` fails `verify-history` until the matching mirror is committed (no history rewrite is needed). The working tree must also agree exactly before any append.
- A hash chain alone cannot detect complete events removed from the end. An **uncommitted** tail event can be deleted without the chain noticing. Once committed, Step 8 detects deletion or modification **within the Git history it can currently observe**.
- **Local Git is not a complete external notarization mechanism.** A local hard reset, rebase, branch replacement, or other history replacement can erase the only local evidence of a committed event (including a committed `access_started`) if no independent copy or anchor exists; nothing inside the repository can detect that. Step 8 does not implement an external anchor.
- **Prerequisite — BEFORE ANY REAL PROTECTED-HOLDOUT REVEAL IN PHASE 7:** the committed `access_started` state must also be anchored outside the sole local repository. The exact mechanism will be finalized before real Phase 7 access; acceptable designs include a protected private remote branch whose history must contain the start commit, or another independently controlled append-only or write-once anchor. The private remote backup required after Phase 0 and before Phase 1 may serve as part of this anchor only if its protection and reachability requirements are explicitly verified at that time; merely having an ordinary remote is not sufficient.
- Every Step 7 gate record also pins the SHA-256 of `HOLDOUT_ACCESS_LOG.md`, so Gate 6 and Gate 7 records anchor the access-log head at their decision time, subject to the same local-history limit.
- Until Step 9 physically enforces the boundary, Step 8 cannot prove that a person or external process did not bypass the protocol and inspect protected data. Any known or suspected bypass must be recorded with `contamination_recorded`, which consumes the holdout.
- Attestations are explicit operator assertions, not cryptographic proof of identity.
- Clock skew that would record an event before its predecessor is refused.
- After every rename (the new ledger at initialization and each `HOLDOUT_ACCESS_LOG.md` rewrite), the configured path is re-walked from the repository root and must lead to exactly the file that was written before success is reported; otherwise the write outcome is unknown and the writer latches.

## Operating notes and recovery

- **Leftover temporary files.** A crash can leave `.holdout-log-*.tmp` in the repository root or `.stage-*` in `research/holdout_access/`. They make the tree dirty, so starts and reveal checks fail closed. Nothing deletes them automatically. Procedure: stop writes; run `python -m pmv.holdout_log verify` and `verify-history` to confirm the authoritative ledger and mirror; preserve any suspicious temporary file as evidence if relevant; determine whether it is merely abandoned (its content is never authoritative); remove it only by an explicit operator action after that verification.
- **Mirror behind.** If a crash leaves the mirror behind the ledger, run `python -m pmv.holdout_log mirror`, verify, and commit both files together.
- **Several open authorizations** can coexist for one holdout; Current Status then shows "Multiple open authorizations (N)" with their event IDs. Each is single-use, and the first `access_started` consumes the holdout, after which none can be used.
- **Command-line errors** are one fixed-text line with an error type; invalid enum or input values are never echoed, and no traceback, path, or subprocess output is printed.

## Command line

```
python -m pmv.holdout_log verify
python -m pmv.holdout_log verify-history
python -m pmv.holdout_log status
python -m pmv.holdout_log mirror
python -m pmv.holdout_log initialize            # once: creates HAL-0005
python -m pmv.holdout_log assert-started-committed HAL-NNNN
python -m pmv.holdout_log record --request action.json --config configs/<env>.toml --environment <env>
```

`record` reads a closed JSON request `{"action": ..., "arguments": {...}}` (unknown fields, duplicate keys, and floats rejected) for `register_cycle`, `register_holdout`, `request_access`, `authorize`, `deny`, `start`, `finish`, `record_contamination`, `reclassify`, or `correct`. The tool never stages, commits, or pushes; commit the ledger and `HOLDOUT_ACCESS_LOG.md` together, promptly, after every event.
