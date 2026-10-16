# B08: Phase 1 prospective-capture hardening (2026-10-16)

**Approver:** the project owner, in the B08 batch charter issued on 2026-10-16 in the isolated environment, after the post-B07 Phase 1 gap audit. The development session wrote this record. It is procedural: the system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

## Charter (summary of the owner's instructions)

- **Branch.** Create `b08/prospective-capture-hardening` directly from final B07 `9a6b212d191c68d177f63beb11d289c669639f92`, not from `main`, even though `main` contains B07 through merge commit `2a46ffd` (PR #6). Required chain: B05 → B06 → B07 → B08. B07 stays preserved. One branch, one eventual B08 → `main` pull request, opened only when ready. Claude does not merge, does not create B09, and does not delete B07.
- **Basis.** The post-B07 gap audit concluded:
  - no further generic historical-acquisition engineering is justified until a real source is selected and its owner-controlled prerequisites exist;
  - a coherent engineering-only batch exists on the prospective-capture side.
- **Objective.** Complete the source-neutral prospective-capture engineering that needs no real endpoint, credential, market observation, source approval, or new parser dependency:
  - F-11: capture segmentation and salvage;
  - F-12 with F-27: raw frame format v2 (monotonic receipt time, message direction, identity and versioning, ordering and provenance);
  - F-33: durability-ordering and crash-boundary tests;
  - F-37 and RT-4: test and demo boundaries, and refusal of the test environment;
  - order-book continuity: a rejected, malformed, missing, or invalid frame breaks book continuity;
  - normalized capture artifacts: a deterministic path from accepted raw frames to normalized artifacts, preserving raw bytes and provenance;
  - documentation: correct the stale post-B07 status.
- **Prohibited.** Everything in the charter's out-of-scope list, including:
  - acquiring data, or contacting any venue, provider, exchange, broker, vendor, archive, or trading host;
  - credentials, accounts, or spending;
  - inspecting real observations, beginning or authorizing live capture;
  - selecting a source, or any A-1, A-2, A-3, A-5, or A-6 decision;
  - a production historical transport, historical cursor pagination, or relaxing the query-string prohibition;
  - installing `pyarrow`, `databento-dbn`, or `zstandard`, or changing the Python-version policy;
  - deciding global versus per-source A-4 semantics, declaring A-4 satisfied, declaring Gate 1 PASS, declaring `T0`, or opening a holdout;
  - H-2 release code, predictive modeling, beginning Phase 2, and merging.
- **Reviewed acquisition code is protected.** `src/pmv/acquisition/` is not modified unless prospective-capture work genuinely cannot be done otherwise. In that case, stop and report first. Optional B07 MINOR findings are not fixed opportunistically.
- **Reviews.**
  - An independent Reliability / Red-Team review with no unresolved BLOCKING or MAJOR finding.
  - A read-only Statistician review if B08 changes statistical observation semantics, availability time, protected-data semantics, observation-family rules, `T0`, or split logic.
  - A repository-only cold-start review, persisted.

## Designation

Under this charter, B08 is the current active ground-truth branch (`docs/BRANCH_TIMELINE.md`): the charter places all work on `b08/prospective-capture-hardening` and directs that "future B09 must be created from final B08". B07 is a historical checkpoint, preserved, and merged by PR #6.

## Interpretations recorded by this batch, and the owner's decisions

Git records F-11, F-12, F-27, F-26, F-33, F-37, and RT-4 by title only (`docs/gate0_readiness.md`, "Deferred findings and deadlines"). The full Step 11 audit text is not in the repository. The implementation follows the titles and the rules Git does state. It records these readings, none of which changes an approved requirement:

| ID | Interpretation | Basis |
|---|---|---|
| B8-1 | **Salvage never resumes a capture.** Recovery quarantines every interrupted segment, as v1 does. Salvage is a separate, explicit, deterministic step, rule `longest_valid_frame_prefix_v1`. It copies only complete, fully valid frames into a new salvage artifact, records the original object's size and SHA-256 and what followed the prefix, and leaves the quarantined bytes unchanged. A salvaged segment ends its session's readable chain. | `docs/raw_data.md` ("Interrupted captures are quarantined by recovery, never resumed; a replacement gets a new ID"); CLAUDE.md "Do not silently repair" |
| B8-2 | **Environment identity is carried on every frame** (as modified by the owner; see "Owner decisions"). Every frame header of frame format v3 carries `venue_environment` and `deployment_environment`, which must equal the segment header's; any mismatch fails closed. *As originally proposed (superseded):* identity carried only by the hash-chained segment header, on the reasoning that a frame cannot be read without its segment. | `research/kalshi/red_team_review.md` RT-B2-09 ("Every raw frame header carries an environment identity") |
| B8-3 | **Venue sequence numbers are not raw-frame fields.** The raw layer never parses payloads, so a venue's own sequence stays inside the payload and is extracted by the normalizer. | `docs/raw_data.md`; CLAUDE.md "Preserve raw data" |
| B8-4 | **Raw format v1 no longer starts captures outside the `test` environment.** F-12 must be done before real collection, and v1 lacks monotonic time and direction. Reading and verifying v1 captures is unchanged. | `docs/gate0_readiness.md` (F-12 deadline) |
| B8-5 | **RT-4 "gate commands"** means the CLIs that create project records (`python -m pmv.gates create`, `python -m pmv.holdout_log record`). They refuse `--environment test`. Read-only verification commands are unchanged. | `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md` (RT-4) |
| B8-6 | **Demo data is protected like real data and never used as data.** Demo captures are written only inside the protected raw location, and every segmented-capture loader refuses them, for every use. v1 captures carry no environment identity, and v1 starts new captures only in `test` (B8-4), so v1 data is test data (RT-B8-08). | RT-B2-09; F-37 title ("demo data treated as real") |
| B8-7 | **Snapshots that answer a PMV command are never a recovery point** (`BookSnapshot.solicited`), until a recorded test proves such replies are sequence-consistent. | `research/kalshi/red_team_review.md` RT-B2-03 |

### Owner decisions (2026-10-16)

The owner reviewed B8-1 to B8-7 explicitly, before the B08 pull request, and decided:

| ID | Decision | Effect |
|---|---|---|
| B8-1 | **Confirmed** | Accepted governance |
| B8-2 | **Modified** | Environment identity must be carried explicitly on **every** raw frame header, not only on the segment header. Owner's reasons: RT-B2-09's wording is per frame; the storage overhead is negligible; per-frame provenance is stronger when frames are inspected, copied, recovered, or validated individually; and the permanent record should not rest on an interpretation weaker than the Red-Team wording when the literal implementation is cheap. Implemented as frame format v3 (below) |
| B8-3 | **Confirmed** | Accepted governance |
| B8-4 | **Confirmed** | Accepted governance |
| B8-5 | **Confirmed** | Accepted governance |
| B8-6 | **Confirmed for now** | Accepted, and revisitable only after an E-6 decision (classification of demo accounts and keys) or another governed demo-use policy. Any narrower demo use (for example falsifying venue semantics, RT-B2-04) needs that decision, a new data-use category, and review |
| B8-7 | **Confirmed** | Accepted governance. The exit condition stays in the wording: a recorded test proving solicited replies are sequence-consistent |

**Implementation of modified B8-2.** The change alters the closed frame schemas, so it is a new format version rather than a silent redefinition of version 2:
- **Frame format v3** (`PMVRAW3`, frame version 3). Payload and event headers gain `venue_environment` and `deployment_environment`.
- **Readers and salvage.** The reader refuses any frame whose values differ from its segment header's. Prefix scanning for salvage stops before such a frame, and `read_session` reports an integrity failure even if the manifest was rewritten to match.
- **The v2 draft.** It existed only on this branch and was never used for real data. It is recognised (`detect_format` returns 2) and refused with a named error, never reinterpreted. v1 is unchanged and separate.
- **Store layout.** It moved from `capture/v2/` to `capture/v3/`, and segment manifests record `format_version` 3.
- **Unchanged:** the segment-level checks, the hash chain, deterministic serialization, and the artifact key derivation. Artifact keys change only because segment hashes change.
- **No timing effect.** Timing, availability, observation semantics, and research eligibility are unchanged, so no new Statistician review was triggered (the owner's B8-2 instruction, item 5).
- **Review.** A focused Red-Team re-review of `b3e8269` is in `research/governance/b08_prospective_capture_red_team_review.md` ("B8-2 modification").
  - Verdict: proceed, with no BLOCKING and no MAJOR finding. Identity is fail-closed on every frame kind, nothing is reinterpreted, and nothing is weakened.
  - It found no change to timing, availability, observation semantics, or eligibility.
  - It raised MINOR RT-B8-15, which predates the change: a manifest's descriptive identity was never compared with its segment header. It is now fixed. `_verify_finalized` refuses a manifest whose environments, source, clock domain, session start, or segment ID differ from the verified header.

## Not changed

- No requirement in the holdout, protected-information, acquisition, risk, or real-capital rules was relaxed.
- `src/pmv/acquisition/` was not modified. The final B07 Red-Team verdict at `4170b3c` still covers it.
- No gate status changed: Gate 0 passed, and Gate 1 is undecided. No cycle, `T0`, split, or protected scope exists.
- No real market observation was accessed, no venue or data host was contacted, and no credential or account was used or created.
- PROJECT_BRIEF.md, START_HERE.md, CLAUDE.md, `.claude/`, and the hash-pinned HOLDOUT_ACCESS_LOG.md body were not modified.

## Outcome (2026-10-16)

### Reviews

- **Independent Reliability / Red-Team** (`research/governance/b08_prospective_capture_red_team_review.md`):
  - **Round 1** (`222a7e7`):
    - **BLOCKING** RT-B8-01: normalized artifacts had no content integrity. A changed price, a deleted rejection, or a relabelled environment loaded as valid.
    - **MAJOR** RT-B8-02: `dataclasses.replace` could re-issue a test `CaptureAuthorization` as production.
    - MINOR RT-B8-03 to RT-B8-11.
  - **Round 2** (`7190f7f`): RT-B8-01 and RT-B8-02 were fixed and verified, with no unresolved BLOCKING and no MAJOR finding. It raised MINOR RT-B8-12 (a reader's lock probe could end a live capture), RT-B8-13 (the real-capture protected-location check used a caller-supplied base; latent while the registry is empty), and RT-B8-14 (a crash window in quarantine).
  - **Round 3** (`6dc2b51`): RT-B8-12 to RT-B8-14 were fixed and verified, with no regressions. Verdict: proceed, with no unresolved BLOCKING and no MAJOR finding.
- **Statistician** (`research/governance/b08_statistician_review.md`; development self-review): **PASS WITH CONDITIONS.**
  - No look-ahead. Availability is still the wall-clock receipt time, and every new continuity rule is conservative.
  - No effect on protected data, `T0`, the split, or the holdout.
- **Cold-start review:** `research/governance/b08_cold_start_review.md`. Verdict: YES with conditions. Its nine MINOR documentation findings were fixed (see that file, "Coordinator dispositions").
- **Quality gate:** `./scripts/check.sh` passed on 2026-10-16: 2305 passed and 8 skipped before the owner decisions, and 2322 passed and 8 skipped after the B8-2 modification and RT-B8-15 (at `c2eca25`). The 8 skips are the owner-run sentinel probes in `tests/integration/test_information_embargo.py`.
- **Models used:** development and review used Claude Opus 5.5 (`claude-opus-5-5`). Nothing in B08 trains or selects a predictive model, and no cycle exists.

### Residuals and conditions (requirements carried forward, not decided here)

| ID | What | Must be done before |
|---|---|---|
| RT-B8-05 / B8S-03 | Plausibility checks on the caller-supplied `observed_at` and payload `monotonic_ns`: `observed_at` against `written_at`, queue delay, and a stamp taken at the socket read. Record clock-sync state (NTP or adjtimex error). The F-12 clock-offset measurement plan, with `max_clock_error` frozen before use | Live capture is authorized |
| RT-B8-06 | Memory bounds for long sessions: normalization and `verify_artifact` hold a whole session, and artifact writes have no size cap. Consider per-segment artifacts | Long real sessions are normalized |
| B8S-01 | Extend the M4 exclusion ledger to segmented-capture loss: unusable-book time by fault, rejection rate per parser version, and session status and unreachable segments, stratified by volatility, time remaining, venue, and period. Alert on a rising rejection rate | Real segmented-capture artifacts are used for research |
| B8S-02 | After any reset or rejected frame, treat trading status as unknown (the contract as not tradable) until the next status update. Flag feature windows that contain a reset | Feature or simulation code consumes segmented-capture artifacts |
| B8S-04 | A session that does not end `complete` needs an explicit end marker, or decision times capped at its last frame | Real segmented-capture artifacts are used for research |
| B8S-05 | Pin the parser version per experiment, and record every version that was generated | Experiments on segmented-capture artifacts |
| B8S-06 | Parser tests for the skip list and for identifying command replies (`solicited`) | A real venue parser (after AR-1 verification) |
| B8S-07 (note) | Concurrent connections in one session share book keys. That is conservative today; revisit if a session ever multiplexes feeds | A session multiplexes feeds |
| Artifact digest | Code that relies on an artifact records `artifact_digest` and loads with `expected_digest` | Experiments on segmented-capture artifacts |
| RT-B8-13 | Fixed: real captures always use the account's protected location. Re-review it with any registry change | Any `APPROVED_CAPTURE_ENDPOINTS` entry |
| RT-B8-12 (residual) | Under heavy lock contention a collector may wait up to about 1 s before it gives up on a new segment and ends the session. That failure is closed. Monitoring readers should not hold segment locks | Live capture is authorized |
| RT-B8-15 (residual) | A manifest missing its inner `time.session_started_at` raises `KeyError`, not an integrity error. This still fails closed. Map it to an integrity error at the next change to `capture_store` | Next `capture_store` change |
| RT-B8-01 (residual) | A local writer who rewrites all three artifact files consistently is detected only through a recorded `artifact_digest` (`expected_digest`) or `verify_artifact` | Experiments on segmented-capture artifacts |

## Open owner inputs carried forward

Unchanged by B08, and not decided here:

- **Historical-acquisition boundary** (post-B07 audit):
  - first historical source selection;
  - A-1 exact hosts and paths;
  - A-2 licence and terms (AR-3);
  - A-3 backup policy and a restore test on the real medium, plus confirmation of the B7-7 "size class" reading;
  - A-5 and A-6;
  - A-4 global-versus-per-source scope;
  - the production transport (B7-4);
  - paginated API support;
  - provider-checksum policy;
  - the Parquet, DBN, and zstd dependency decisions (B7-6).
- **Live capture** (still not authorized), which additionally needs:
  - F-16 eligibility, and E-1 (gold contracts);
  - E-3 and F-03: a market-data credential and its isolation;
  - E-6: classification of demo accounts and keys;
  - F-32: collector host and alert recipient;
  - F-21b: per-gate reviewer table;
  - F-26: storage-event claims and restore dependency;
  - the A-3 backup policy and smoke test;
  - an owner-approved entry in `pmv.capture_environment.APPROVED_CAPTURE_ENDPOINTS`, which is empty.
- **Release and pre-T0:**
  - E-U1 and the H-2 prerequisite chain;
  - P-1 (E-B4-2), P-2 (E-B4-5), P-3 (E-B4-7), and P-4 (E-B4-9(b));
  - the F-07 power floor;
  - cycle registration.
- **B6S-14** stays optional and unadopted.
