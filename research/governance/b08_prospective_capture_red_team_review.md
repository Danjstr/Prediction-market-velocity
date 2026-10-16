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

## Re-verification (round 2)

- **Subject:** commit `7190f7f`, reviewed against `222a7e7` (`git diff 222a7e7 7190f7f -- src tests docs`).
- **Data and scope:** synthetic only, with no network access. `src/pmv/acquisition/` is still untouched: the diff from `9a6b212` to `7190f7f` is empty.
- **Tests:** these targeted tests all passed (245 tests): the capture format, environment, store, replay, and crash-point tests, plus the books and v1 replay tests. I did not run `check.sh` or the full suite.
- **Reproductions:** I re-ran `$TMPDIR/rt8/r1_replace.py`, `r2_artifact.py`, and `r3_modes.py`, and added three new scripts there:
  - `r4_round2.py`: consistent rewrites of an artifact;
  - `r5_race.py`: a reader racing a writer's rollover;
  - `r6_base.py`: the protected-location check against a caller-chosen base.

### Dispositions of round-1 findings

| ID | Round-1 | Disposition | Evidence |
|---|---|---|---|
| RT-B8-01 | BLOCKING | **Resolved** (one residual, documented) | `r2`: changing a price in `observations.json` alone is refused ("an artifact file does not match its record"). `r4`: dropping a rejected frame together with its item is refused even when `artifact.json` is recomputed to match ("frames are not one contiguous sequence"). Relabelling the venue or deployment environment changes the derivation key, so `load_artifact` refuses it ("not stored under its own key"), and it is also cross-checked against `read_session`. Residual: a local writer who rewrites the observations and the record consistently is still ACCEPTED by `load_artifact` when no digest is passed. `expected_digest` refuses it and `verify_artifact` refuses it (`r4`). This residual is stated in the module docstring and in `docs/market_data.md`. It needs deliberate tampering plus a recomputed hash, the same class of attack as rewriting raw segments by hand, so I accept it. The bit-rot and partial-corruption path that made RT-B8-01 BLOCKING is now closed. |
| RT-B8-02 | MAJOR | **Resolved** (latent residual, see RT-B8-13) | `r1`: `dataclasses.replace` now raises `TypeError`. `start_session` re-runs `authorize_capture` using the store's own deployment environment and root, so a development or production store refuses synthetic data and refuses any endpoint not in the registry, which is empty. `_require_use` refuses data written by the `test` deployment for RESEARCH. The test deployment also refuses roots that resolve into the real `PROTECTED_RAW_BASE`. Forging is now possible only through private `object.__setattr__` or `object.__new__`, which is out of scope like other in-process tampering. |
| RT-B8-03 | MINOR | Resolved (crash window, see RT-B8-14) | `r3`: the quarantined directory is now 0o500 and its files 0o400. |
| RT-B8-04 | MINOR | Resolved (new race, see RT-B8-12) | `r3`: an abandoned session now reads as `truncated`. |
| RT-B8-05 | MINOR | Partly resolved; remainder deferred and documented | Stores outside `test` now require `clock_domain == read_clock_domain()`. Plausibility checks on `observed_at` and `monotonic_ns` are deferred: `r3` still accepts a year-ahead `observed_at` and a foreign monotonic value. This remains open for the Statistician and must be done before real collection. |
| RT-B8-06 | MINOR | Open (not addressed) | Unchanged. `verify_artifact` now holds two copies of a normalized session in memory, which makes the memory problem slightly worse. Carry this forward. |
| RT-B8-07 | MINOR | Resolved | `maintain()` rolls the segment over once its duration has elapsed, even with no new frames, and then syncs. A quiet feed now produces header-only segments, bounded by `MAX_SEGMENT_INDEX`. |
| RT-B8-08 | MINOR | Resolved (documented) | B8-6 is rescoped to v2. v1 data is test data. |
| RT-B8-09 | MINOR | Resolved | The reader now checks that every event naming a connection names an open one. The session reservation's clock domain, deployment environment, and segment policy are validated strictly. |
| RT-B8-10 | MINOR | Resolved (documented) | The collector contract is now in the `append_inbound` docstring and in `docs/raw_data.md`. |
| RT-B8-11 | MINOR | Open (expected) | `docs/phase1.md` and `docs/gate0_readiness.md` still list the items as Open. Update them when B08 closes. `docs/market_data.md` still says "content-addressed" and "a dropped … observation is detected", but the Integrity and Loading bullets now state the limits, so this wording is acceptable. |

### New findings introduced by, or visible after, the fixes

| ID | Severity | Location | Description | Synthetic reproduction | Recommended fix |
|---|---|---|---|---|---|
| RT-B8-12 | MINOR | `capture_store._is_live` (new), `CaptureSession._open_segment` | **A concurrent reader can end a live capture.** `read_session` now probes the lock of the next open segment with `flock(LOCK_SH \| LOCK_NB)`. If that probe overlaps the window between the writer's `mkdir` and its `flock(LOCK_EX \| LOCK_NB)` during rollover, the writer raises "another process holds the new segment's lock". The session is abandoned, which ends the capture. This fails closed: segment N stays finalized, the empty segment N+1 is quarantined by `recover()`, and the chain reads `truncated`. But a status read, such as monitoring or normalizing an open session, can interrupt live collection. `recover()` could already do this, but it is meant to run only at startup. The reverse case, a live writer reported as `truncated` during that window, is only a transient misreport. | `r5_race.py` holds the reader's shared lock across the writer's rollover. Result: "writer failed during rollover: CaptureIntegrityError another process holds the new segment's lock", and the session reads `truncated`. | In `_open_segment`, retry the `LOCK_EX` acquisition for a short bounded time. The identity check that follows still detects a concurrent quarantine. Alternatively, take the lock before the directory becomes visible in `open/`. Add a test where a reader probe overlaps the writer. |
| RT-B8-13 | MINOR (latent; must be fixed before any `APPROVED_CAPTURE_ENDPOINTS` entry) | `authorize_capture` (non-test branch), `CaptureStore.start_session` | **The protected-location check outside `test` uses a base the caller chooses.** The authorization carries the caller's `protected_base`, and `start_session` re-validates against that same base. With a registry entry present, a development or production session starts on a root outside the real `PROTECTED_RAW_BASE` if the caller simply passes a nearby base. `load_config` does enforce the real base for configs it loads, but `CaptureStore` accepts any `RawStorageConfig`. Today the empty registry refuses every such session, so this is latent. | `r6_base.py`, with a hypothetical endpoint monkeypatched into the registry: "production session started OUTSIDE the real protected base". | Outside `test`, ignore the caller's `protected_base` and check against `PROTECTED_RAW_BASE`; keep the parameter as a seam only for tests. Alternatively, have `CaptureStore.__init__` refuse a root outside the real protected location when the provenance environment is not `test`. |
| RT-B8-14 | MINOR | `CaptureStore._quarantine_locked` / `_make_read_only` | `_make_read_only` runs after the `quarantine.moved` fault point. A crash at that point leaves the quarantined segment at 0700/0600, and neither `reconcile()` nor `recover()` tightens or reports quarantined segments. Separately, `FsIntegrityError` from `_open_file` inside `_make_read_only` is not wrapped by `_fs_errors`, and it is raised after the move has already happened. | Code reading. The quarantine crash tests do not check modes. | Make the files read-only before the move, or have `reconcile()` tighten and report quarantined segments. Wrap the call in `_fs_errors`. Assert the modes in the quarantine crash-point tests. |

### Round-2 verdict

- **No unresolved BLOCKING? YES.** RT-B8-01 is resolved. Its residual (a consistent rewrite of all three files, detectable only with a recorded digest or by re-derivation) is documented and accepted.
- **MAJOR open? NO.** RT-B8-02 is resolved.
- **Open MINOR findings:**
  - carried forward or deferred: RT-B8-05 (timestamp plausibility), RT-B8-06 (memory), and RT-B8-11 (status documents);
  - new: RT-B8-12, RT-B8-13, and RT-B8-14.

  None of them lets ambiguous, corrupt, or unauthorized data be accepted.
- **Recommendation: proceed with conditions.**
  - B08 meets the charter's Red-Team bar.
  - These must be fixed before any live capture is authorized:
    - RT-B8-13, before any entry is added to `APPROVED_CAPTURE_ENDPOINTS`;
    - RT-B8-05, the remaining plausibility checks on `observed_at` and `monotonic_ns`;
    - RT-B8-12, before any process reads sessions while a collector is running.
  - RT-B8-06 and RT-B8-14 may be fixed now or carried forward, recorded in the failure register or the B08 decision record.
  - Callers that rely on an artifact should record `artifact_digest` and pass `expected_digest` when they load it.
  - Nothing here authorizes live capture or changes any gate status.

## Re-verification (round 3)

- **Subject:** commit `6dc2b51`, reviewed against `7190f7f`, source and tests only.
- **Data and scope:** synthetic only, with no network access. `src/pmv/acquisition/` is still untouched: the diff from `9a6b212` to `6dc2b51` is empty.
- **Tests:** the targeted capture tests all passed (169: format, environment, store, replay, and crash points). I did not run `check.sh` or the full suite.
- **Reproductions:**
  - I re-ran `r6_base.py`.
  - I did not re-run `r5_race.py`, because it holds the reader's lock indefinitely by design, so it would still fail. I replaced it with `$TMPDIR/rt8/r7_round3.py`, which holds the lock for a bounded time and also covers the quarantine crash windows.

| ID | Disposition | Evidence |
|---|---|---|
| RT-B8-12 | **Resolved** | With a reader's shared probe held for 0.05 s across the writer's rollover, the writer now succeeds after about 0.06 s and opens segment 1. A probe held for 3 s still ends the session after about 1.1 s (fails closed). That is acceptable: a real `_is_live` probe holds the lock for microseconds. If `recover()` takes the lock and quarantines the directory meanwhile, the writer's identity check (`same_entry`) still detects it after it gets the lock. Residual: a collector stalls for up to about 1 s under heavy contention. |
| RT-B8-13 | **Resolved** | `r6_base.py`, with a hypothetical registry entry and a caller-chosen base, is now refused: "real and demo captures are written only inside the protected raw location". The non-test branch reads the module-level `PROTECTED_RAW_BASE` at call time. The tests construct their own base with `monkeypatch` and do not depend on the real home directory. |
| RT-B8-14 | **Resolved** | Simulated crash at `quarantine.moved`: the directory is 0700 and the files are already 0400. `recover()` reports `tightened`, sets the directory to 0500, and is idempotent (a second run returns nothing). Salvage still works. Simulated crash at `quarantine.record_written`: `recover()` quarantines the segment, keeps the single existing `requested` record (it validates it rather than rewriting it), and ends with 0500/0400. Correction to my round-2 note: `capture_store._open_file` already wraps `_fs_errors`, so that part was not a defect. A non-owned or unexpected quarantine entry makes `recover()` raise, which fails closed. |

**No regressions found.**
- The writer's retry path keeps the identity check.
- The quarantine record is created exclusively or validated, never replaced.
- Making the files read-only before the move does not block the move.
- Salvage still reads the read-only quarantined objects.

**Decision record "Outcome" section** (`docs/decisions/2026-10-16_b08_prospective_capture_hardening.md`): it states my findings accurately. Severities, round-by-round dispositions, the latent nature of RT-B8-13, and the carried-forward residuals (RT-B8-05 and RT-B8-06, the artifact-digest condition, and RT-B8-13 re-review on any registry change) all match this review. Two small omissions, neither requiring a correction before merge:
- the bounded-wait residual of RT-B8-12 (a probe held longer than about 1 s still ends a capture);
- that the RT-B8-01 residual, a consistent rewrite of all three files, is caught only with `expected_digest` or `verify_artifact`. The "Artifact digest" row covers this implicitly.

### Round-3 verdict

- **No unresolved BLOCKING? YES.**
- **MAJOR open? NO.**
- **Open MINOR findings (carried forward):**
  - RT-B8-05: timestamp plausibility, before live capture is authorized;
  - RT-B8-06: memory bounds, before long real sessions are normalized;
  - the RT-B8-12 bounded-wait residual, which is informational.
- **Recommendation: proceed.** B08 meets the charter's Red-Team bar, subject to the conditions carried forward in the decision record. Nothing here authorizes live capture or changes any gate status.

## B8-2 modification (owner decision, frame format v3)

- **Subject:** commit `b3e8269`, reviewed against `43c4283` (`git diff 43c4283 b3e8269 -- src tests docs`).
- **Data and scope:** synthetic only, with no network access. `src/pmv/acquisition/` is still untouched.
- **Tests:** the capture suites all passed (182). These were `tests/unit/test_capture_*.py`, `tests/integration/test_capture_replay.py`, and `tests/failure_injection/test_capture_crash_points.py`.
- **New reproductions:**
  - `$TMPDIR/rt8/r8_v3.py`: hand-built v3 objects, including the v2 draft;
  - `$TMPDIR/rt8/r9_manifest.py`: relabelling the environment fields in a manifest.

**(1) Integrity coverage and fail-closed behaviour: satisfied.**
- Payload and event headers are closed schemas that now include `venue_environment` and `deployment_environment`, each validated against its enum.
- `SegmentReader` refuses any frame whose identity differs from its segment header. `r8`, all with consistent hashes, shows the reader refuses each of these:
  - payload with a different venue;
  - payload with a different deployment;
  - event with a different venue;
  - event with a different deployment.
- `scan_prefix` stops at the last good frame for each of those cases (tail `invalid_frame`), so salvage never includes a relabelled frame.
- The segment header is still checked against the session reservation for venue, deployment, source, clock domain, and start (`_check_chain`), and `iter_frames` re-checks the venue.
- The identity sits inside the canonical header bytes, so the segment SHA-256 and the hash chain cover it.
- Consistent-manifest forgery: a frame relabelled with its manifest's SHA-256 and size recomputed is refused, because `_verify_finalized` runs the same per-frame check (test `test_reading_refuses_a_relabelled_frame_even_with_a_consistent_manifest`).
- The writer passes the session's own environments, and the new writer test shows a mixed-environment segment cannot be finalized.

**(2) Versions and compatibility: satisfied.**
- The magic is `PMVRAW3`, the frame version 3, and the manifest `format_version` 3.
- `detect_format` returns 2 for `PMVRAW2`, and the only code that calls it is in `capture_format`.
- A v2-draft object is refused by name in `SegmentReader`. It is therefore refused in `summarize_segment`, finalization, `read_session`, and `iter_frames`, so it can never be normalized.
- `scan_prefix` returns no header for it, so `salvage` raises `SalvageRefusedError`.
- A v3-magic object containing frame-version-2 headers is refused by `_decode`.
- v1 still checks its own magic.
- The layout moved to `capture/v3/`, and nothing in `src` reads `capture/v2/`. A leftover draft-era tree is simply ignored, which is acceptable because the draft never held real data.
- Nothing is redefined silently.

**(3) No weakening found.**
- Segment-level checks, the hash chain, `RENAME_NOREPLACE` finalization, deterministic serialization, the artifact derivation key, and the artifact record are all unchanged.
- Artifact keys change only because segment bytes and hashes change.
- Headers grow by about 60 bytes per frame, far below `MAX_HEADER_BYTES`.

**(4) Timing, availability, observation semantics, research eligibility: no change.**
- `observed_at`, `monotonic_ns`, sequence order, the dispositions, and the loader rules (`_require_use`) are unchanged.
- The per-frame identity is redundant with the segment and session identity that loaders already use, and is checked to be equal to it.
- No Statistician review is triggered.

**(5) Regressions: none found** (182 tests passed).

**(6) Documentation: accurate**, with one qualification.
- The decision record's "Owner decisions" section, the frame-format section of `docs/raw_data.md`, and `docs/market_data.md` describe the change accurately: why it is v3, how the v2 draft is handled, the layout move, what is unchanged, and why there is no timing effect.
- Qualification: `docs/raw_data.md` says the identity is covered by "the segment SHA-256, the hash chain, and the manifest". That is true of the manifest's object SHA-256. But the manifest's own `venue_environment` and `deployment_environment` fields are never compared with the header (RT-B8-15).

| ID | Severity | Location | Description | Synthetic reproduction | Recommended fix |
|---|---|---|---|---|---|
| RT-B8-15 | MINOR (existed before this change) | `CaptureStore._verify_finalized` / `_parse_manifest` | A finalized manifest's descriptive fields (`venue_environment`, `deployment_environment`, and also `source`, `clock_domain`, `session_id` with its index) are not all cross-checked against the verified segment header and the reservation. Only `object`, `counts`, `chain`, `session_id`, `segment_index`, and the end type are checked. A manifest relabelled `production`/`production` on a synthetic test segment still passes `read_session` and `reconcile`. This fails closed for data use, because every reader and loader takes identity from the frame headers and the reservation, never from the manifest. A future tool that inventories manifests (backup, catalog, retention) would see a wrong label. | `r9_manifest.py`: "manifest env relabelled -> read_session ACCEPTED; session venue: synthetic". | In `_verify_finalized`, compare the manifest's environment, source, and clock-domain fields with the verified header (and the reservation), and refuse on any mismatch. Narrow the `docs/raw_data.md` wording, or rely on the fix. |

### Verdict on the B8-2 modification

- **No unresolved BLOCKING? YES.**
- **MAJOR open? NO.**
- **New MINOR:** RT-B8-15, which existed before this change and does not affect any loader. Earlier carried-forward MINOR findings (RT-B8-05, RT-B8-06) are unchanged.
- **Recommendation: proceed.** The owner's modified B8-2 is implemented faithfully and fails closed for every frame kind. RT-B8-15 may be fixed now (it is small) or carried forward before any tool consumes manifest fields.

## RT-B8-15 verification

**Disposition: RT-B8-15 resolved.** Subject: commit `c2eca25`, reviewed against `b3e8269`.

`_verify_finalized` now compares the following manifest fields with the verified segment header, and checks the header's session against the requested session:
- `segment_id`;
- `venue_environment` and `deployment_environment`;
- `clock_domain`;
- `source`;
- `time.session_started_at`.

Results:
- Re-running `$TMPDIR/rt8/r9_manifest.py` (a manifest relabelled `production`/`production` on a synthetic segment) now gives "refused: a manifest's identity does not match its segment header", where before it was accepted.
- The capture suites all pass (186: `tests/unit/test_capture_*.py`, `tests/integration/test_capture_replay.py`, `tests/failure_injection/test_capture_crash_points.py`), including the new `test_a_relabelled_manifest_is_refused`.
- No regressions found.

Hardening note, not a finding: the inner `time` object of the manifest is not itself schema-validated. A manifest with no `time.session_started_at` raises `KeyError` instead of `CaptureIntegrityError`. That still fails closed.

**Verdict:**
- No unresolved BLOCKING? YES.
- MAJOR open? NO.
- RT-B8-15 is closed. RT-B8-05 and RT-B8-06 remain carried forward as MINOR.
