# B08 prospective-capture hardening: independent Reliability / Red-Team review

- **Subject commit:** `222a7e7` ("B08: prospective-capture hardening (synthetic data only)"), reviewed against its parent `1aa6c52`. The docs commit `1aa6c52` was also reviewed for consistency.
- **Branch:** `b08/prospective-capture-hardening`.
- **Reviewer:** Reliability / Red-Team agent, fresh context. I did not design or write any of the reviewed code.
- **Date:** 2026-10-16.
- **Data:** synthetic only. No network host was contacted. No real observation, credential, or protected path was touched.

## Method

1. I read the charter and interpretations B8-1..B8-7 (`docs/decisions/2026-10-16_b08_prospective_capture_hardening.md`), the new v2 section of `docs/raw_data.md`, the changes to `docs/market_data.md`, and the full source of `capture_format.py`, `capture_store.py`, `capture_environment.py`, and `market_data/capture_replay.py`.
2. I read the diffs to `books.py`, `events.py`, `validation.py`, `replay.py`, `synthetic.py`, `timing.py`, `raw_storage.py`, `gates.py`, and `holdout_log.py`, plus the helpers in `safe_fs` that they rely on.
3. I ran these targeted tests, and nothing else: `tests/unit/test_capture_{format,environment,store}.py`, `tests/integration/test_capture_replay.py`, `tests/failure_injection/test_capture_crash_points.py` (155 passed), the changed market-data, replay, and raw-storage tests (211 passed), and the new RT-4 CLI tests in `test_gates.py` and `test_holdout_log.py` (7 passed). I did not run `./scripts/check.sh` or the full suite.
4. I wrote synthetic reproductions under `$TMPDIR/rt8/`, outside the repository:
   - `r1_replace.py`: authorization forging;
   - `r2_artifact.py`: normalized-artifact corruption and relabelling;
   - `r3_modes.py`: quarantine modes, status of a dead session, unchecked caller clocks.
5. `git diff 9a6b212 222a7e7 -- src/pmv/acquisition` is empty.

## Findings

| ID | Severity | Location | Description | Synthetic reproduction | Recommended fix |
|---|---|---|---|---|---|
| RT-B8-01 | **BLOCKING** | `market_data/capture_replay.py` `decode_artifact`, `load_artifact`, `_check_items`; `CaptureStore.read_artifact` | **Normalized artifacts have no content integrity.** The "key" hashes the *derivation* (driver, parser, session, segment hashes, status). It does not hash the artifact bytes, and no file SHA-256 is stored anywhere. Decoding checks only that the data is canonical and self-consistent. Three things are therefore accepted as valid with no error: (a) a changed observation value (corruption or a digit flip); (b) a removed frame entry together with its items and the adjusted count, for example deleting a `rejected` frame and its `frame_rejected` event, which silently removes a book break; (c) relabelling `venue_environment`, for example synthetic→production or demo→production, which defeats `require_data_use`. That field is not bound to the key, and `load_artifact` never checks it against the raw session. Frame-list sequence continuity and uniqueness are not checked either. Raw v2 detects bit-rot through payload and segment SHA-256s, but the layer that research consumes does not. The docs call this "content-addressed" and say a dropped observation "is detected", which overstates it. This lets corrupt data be accepted as valid. | `r2_artifact.py`: the price changed 40→49 and loaded as ACCEPTED; the rejected frame and its event were dropped and it loaded as ACCEPTED (0 rejected frames); relabelled `production` loaded as ACCEPTED for `DataUse.RESEARCH`. | (1) Store the SHA-256 and size of each artifact file in a closed-schema record (or make the directory name a hash over the derivation plus the file hashes), and verify it on every read. (2) In decoding, require frame sequences to be exactly the contiguous range covered by the listed segments, with no duplicates. (3) Bind `venue_environment` (and the deployment environment) to the derivation key. In `load_artifact`, cross-check against `read_session(session_id)`: environment, segment list, and status. (4) Correct the "content-addressed" wording. |
| RT-B8-02 | **MAJOR** | `capture_environment.CaptureAuthorization`; `CaptureStore.start_session` | **`CaptureAuthorization` can be forged with a public stdlib call.** `dataclasses.replace(auth, ...)` re-runs `__init__` with the existing `_token`, so a legitimate *test* authorization can be re-issued as `development`/`production` without touching any private name or monkeypatching anything. `start_session` checks only that the deployment matches provenance, that the root path is equal, and that the endpoint ID is equal. It does not re-apply the rules: approved endpoint, root inside or outside the protected location, and test deployment means synthetic only. Nothing downstream refuses a `deployment_environment = test` session or a root outside the protected location. Result: synthetic bytes from a `.example` host, written outside the protected location, are recorded as `venue_environment = production` and accepted by `normalize_session(..., use=RESEARCH)`. The docstring claim that "`authorize_capture` is the only producer; the capture store accepts nothing else" is materially overstated. I rate this MAJOR rather than BLOCKING because the bypass needs deliberate code, and writing v2 bytes by hand is an equivalent out-of-scope forgery (`docs/raw_data.md` "Not proven by tests"). | `r1_replace.py`: forged `development`/`production` authorization; session written under `$TMPDIR`; research normalization ACCEPTED. | Make `_token` `field(init=False)` and set it only inside `authorize_capture` (so `replace` fails). Better still, have `start_session` re-validate the authorization by re-running the same rule function against `protected_base` and the registry. Add defense in depth in the loaders: refuse research use when the session's `deployment_environment` is `test`. Optionally, refuse a non-test store root outside the protected location in `CaptureStore.__init__`. Add a test that `replace()` is refused. |
| RT-B8-03 | MINOR | `CaptureStore._quarantine_locked` | Quarantined segments stay mutable: the directory is 0700 and the object and record are 0600. Finalized and salvaged data is 0400/0500. "Quarantined bytes immutable" holds only in the sense that the tool never writes them. A modification before the first salvage is undetectable. A later change is detected only when salvage is repeated. | `r3_modes.py` prints 0o700/0o600/0o600. | After the quarantine record is written, `fchmod` the object and record to 0400 and the directory to 0500, and sync. Have `reconcile` check this. |
| RT-B8-04 | MINOR | `CaptureStore.read_session` | A crashed writer's unlocked segment in `open/` is reported as `SessionStatus.OPEN` until `recover()` runs, so a dead session looks live. It fails closed: only finalized bytes are read. | `r3_modes.py`: an abandoned session reads as `open`. | Probe the lock (non-blocking flock) and report a distinct `orphaned` or `truncated` status, or require `recover()` before reads. |
| RT-B8-05 | MINOR (flag for the Statistician) | `CaptureSession._append`; `CaptureStore.__init__` | The caller supplies `observed_at` and the payload `monotonic_ns`, and neither is checked. `observed_at` can be later than the store's `written_at`: a future receipt time, and with `available_at = observed_at` a mis-wired collector that passes source time would introduce lookahead. Payload `monotonic_ns` can come from a different clock than the store's (headers, events, and rollover use the store's). `clock_domain` is injected by the caller, not read, and `read_clock_domain` has no test or caller. | `r3_modes.py`: `observed_at` one year ahead and `monotonic_ns = 10**18` were accepted. | Refuse `observed_at > written_at + tolerance`, or record it as an anomaly. Refuse payload `monotonic_ns` greater than the store's current monotonic time or below the segment header's. Outside `test`, derive `clock_domain` from `read_clock_domain()` and test it. |
| RT-B8-06 | MINOR | `normalize_session`, `encode_artifact`, `MAX_ARTIFACT_FILE_BYTES`, `salvage` | Resource bounds. Normalization holds an entire session's observations as Python objects, and a session's size is unbounded. Writing an artifact has no size cap, but reading caps each file at 1 GiB, so an oversize artifact is written and then permanently unreadable (fails closed). Salvage peaks at about twice one object (roughly 400 MB), which is acceptable on the ~2.7 GB host but should be stated. An OOM in a co-hosted normalizer could kill the collector. | Analytical. | Bound sessions for normalization (or normalize per segment range). Refuse at write time any artifact that exceeds the read cap. Run normalization in a separate, memory-limited process from the collector. |
| RT-B8-07 | MINOR | `CaptureSession._maybe_rollover`, `sync` | The duration bound is evaluated only when the next frame is written, and nothing syncs periodically. On a quiet or stalled feed (stall without disconnect), a segment stays open and unsynced indefinitely. This contradicts "no stream is ever an indefinitely open mutable file". | Analytical. | Specify a collector timer that calls a time-based rollover check and `sync()`, or document it as a collector obligation in `docs/raw_data.md`. |
| RT-B8-08 | MINOR | `market_data/replay.py` (v1 path); `raw_storage.start_capture` | B8-6 says "every loader refuses" demo, and synthetic data is for tests only. The v1 normalization path has no data-use check: v1 captures, now test-only, can be normalized for any use. The v1 refusal is keyed on self-declared `RuntimeProvenance.environment`. | Code reading. | Have v1 replay refuse non-`TEST` uses of captures whose provenance environment is `test`, or scope the B8-6 wording to v2. |
| RT-B8-09 | MINOR | `CaptureStore.iter_frames`; `read_session_record` | Reading does not check that `gap` or `rate_limit` events name an open connection. The writer enforces this, the reader does not. The reservation's `deployment_environment` and `segment_policy` are loosely validated. | Code reading. | Enforce the writer's rules on read. Validate the reservation fields against their enums and types. |
| RT-B8-10 | MINOR | `CaptureSession._maybe_rollover` / `_open_segment` | If finalization of segment N succeeds and opening N+1 then fails, `append_*` raises even though the frame was accepted, so the outcome is ambiguous for the caller. Likewise a frame is written and then a regression-event write fails. | Code reading. | Document the collector contract: an exception from `append_*` does not mean the frame was lost. Never retry into the same session; start a new one. |
| RT-B8-11 | MINOR (docs) | `docs/phase1.md` line 88; `docs/gate0_readiness.md` | F-11, F-12, F-33, and F-37/RT-4 are still listed as Open. That is acceptable before review, but they should be updated when B08 closes, with RT-B8-01 and RT-B8-02 cited. Skipped frames do not break books, and that rests only on parser discipline ("a parser must only skip messages that carry no book state"). | — | Update the status after the fixes. When a real parser is reviewed, add a test that it skips only stateless message types. |

## Assessment of items 1–10

1. **F-11 segmentation and salvage: sound.**
   - Segments are bounded by an explicit `SegmentPolicy` that has no defaults, and `MAX_SEGMENT_BYTES` caps them; see RT-B8-07 for the time bound.
   - `segment_id` is deterministic. The session ID is unique and reserved with `O_EXCL`.
   - Open and finalized states are distinct. A segment is accepted exactly when its directory has been renamed into `segments/` with `RENAME_NOREPLACE`.
   - Recovery never resumes. It flock-probes and then quarantines every unlocked `open/` entry. Live entries are left alone, and races between `mkdir` and `flock` are detected by identity checks.
   - Salvage uses only `longest_valid_frame_prefix_v1`. It copies whole valid frames, records the source size and SHA-256 and the tail disposition, and is idempotent with a comparison of derived fields.
   - A salvaged segment ends the chain: `read_session` stops there and `_check_chain` refuses a successor. Gaps are never bridged, and unreachable indices are reported.
   - There is no concatenation or replacement path.
   - Exception: quarantined bytes are not made read-only (RT-B8-03).
2. **F-12/F-27 v2 semantics: sound.**
   - All three header schemas are closed, with exact key sets.
   - `frame_version` must be 2. The v1 and v2 magics are distinct and each reader checks its own.
   - The first frame and only the first frame is the segment header. `session_closed` must be last, and no trailing bytes are allowed.
   - Direction is enforced: outbound frames carry no source time and no malformed flag.
   - One sequence runs across the whole session, checked within segments and again across segments in `iter_frames`.
   - The chain binds the previous segment's SHA-256 and last sequence, plus session, source, environments, clock domain, and start time to the reservation.
   - The monotonic clock domain is recorded and checked to be identical across segments.
   - Gaps: caller-supplied clocks are unvalidated, and the clock domain is injected (RT-B8-05).
3. **F-33 durability and crash ordering: sound for process crashes.**
   - Each step is synced before the next: object, re-read verification, rename, manifest (`write_new_file` syncs), rename, mode 0400, destination chain (`ensure_dir` syncs the parent on creation), identity check, `RENAME_NOREPLACE`, sync of both directories, then mode 0500.
   - Twenty-two named fault points are exercised by killing real child processes. Every pre-move crash reads as not accepted and is salvageable. Every post-move crash is accepted exactly once, and `reconcile` tightens any directory left 0700.
   - No window lets an ambiguous state read as valid, and no accepted segment can be lost (nothing deletes from `segments/`).
   - Power loss is honestly out of scope. File-mode changes are not separately synced, so after a power loss a finalized directory could hold 0600 files, which would make `_verify_finalized` fail closed.
4. **F-37/RT-4: rules correct, enforcement forgeable.**
   - The registry is empty, and the rules in `authorize_capture` are right: test means synthetic only and RFC 2606 hosts only, with the root outside the protected location both lexically and after symlinks; demo is development-only; real roots must be inside the protected location.
   - The authorization can be forged with `dataclasses.replace`, the store does not re-validate it, and loaders ignore `deployment_environment` (RT-B8-02, MAJOR).
   - The CLI refusals (`gates create`, `holdout_log record`) run before any input is read, and are tested.
   - v1 `start_capture` refuses environments other than test.
   - There is a small window between the root check in `authorize_capture` and `os.open` in the store, in which intermediate symlink components could be swapped. Re-validation in the store (RT-B8-02 fix) closes it.
5. **Order-book continuity: sound.**
   - `frame_rejected` (raw-malformed, schema, undecodable, rejected snapshot, rejected delta) and `connection_opened`/`connection_closed` reset every book in the capture. Sequence gaps, duplicates, and regressions are faulted.
   - A solicited snapshot keeps earlier faults and adds `unverified_snapshot`, and validation discards it as a recovery point.
   - Restarting after an uncertain last frame means a new session, which starts with no book.
   - Effective availability is a running maximum in sequence order, so a wall-clock regression cannot place a later delta before a rejection event. I checked this specifically.
   - Residual: skipped frames depend on parser discipline (RT-B8-11).
6. **Normalized artifact lineage, determinism, and idempotency: correct. Tamper and corruption detection: missing.**
   - Determinism holds: no creation time or commit is stored. Idempotency holds: a write compares the full bytes and refuses a differing artifact.
   - Integrity under corruption or tamper is missing, and the environment label is not bound (RT-B8-01, BLOCKING).
   - Data-use refusal works for honestly labelled v2 sessions and artifacts. It is absent on the v1 path (RT-B8-08).
7. **Raw bytes and A-7/A-8: sound.**
   - Payloads are stored byte-exact, with a SHA-256 per frame, and outbound frames are preserved.
   - Error and log messages are fixed text or carry identifiers, sizes, and hashes only. No payload or observation values appear.
   - Artifacts are written under the store root: the protected location for real environments.
8. **Crash, restart, idempotency, and resources: sound, with caveats.**
   - Recovery and salvage are idempotent and report stale staging directories without deleting them.
   - Resource caveats are in RT-B8-06 and RT-B8-07, and ambiguous append outcomes in RT-B8-10.
9. **Ambient-state test dependencies: none found.**
   - Every new test builds its own temporary root and passes an explicit `protected_base`.
   - The RT-4 tests write their own development config and use the temporary `repo` fixture.
   - The crash tests use `sys.executable -I` with a fixed environment, the same pattern as the existing B07 tests, so the package must be installed in the venv.
   - `REPO` is used only for the root-outside-the-working-tree check.
   - Tests do not read `/proc` boot IDs or the home directory. The trade-off is that `read_clock_domain` is untested (RT-B8-05).
10. **`src/pmv/acquisition/` is untouched.** The diff from `9a6b212` to `222a7e7` is empty.

## Verdict

- **No unresolved BLOCKING? NO.** RT-B8-01 is open: normalized artifacts accept corrupted or relabelled content as valid.
- **MAJOR open? YES.** RT-B8-02: `CaptureAuthorization` can be forged with `dataclasses.replace`, and neither the store nor the loaders re-validate it.
- **Recommendation: revise.** Fix RT-B8-01 and RT-B8-02, each with a regression test (the reproductions above translate directly into tests), then request a focused re-review. The MINOR findings may be fixed now or carried forward with an owner-visible note. RT-B8-05 should also go to the Statistician, because receipt-time availability depends on caller-supplied `observed_at`. Nothing in this review authorizes live capture, and no gate status changes.
