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

## Interpretations recorded by this batch (for owner confirmation)

Git records F-11, F-12, F-27, F-26, F-33, F-37, and RT-4 by title only (`docs/gate0_readiness.md`, "Deferred findings and deadlines"). The full Step 11 audit text is not in the repository. The implementation follows the titles and the rules Git does state. It records these readings, none of which changes an approved requirement:

| ID | Interpretation | Basis |
|---|---|---|
| B8-1 | **Salvage never resumes a capture.** Recovery quarantines every interrupted segment, as v1 does. Salvage is a separate, explicit, deterministic step, rule `longest_valid_frame_prefix_v1`. It copies only complete, fully valid frames into a new salvage artifact, records the original object's size and SHA-256 and what followed the prefix, and leaves the quarantined bytes unchanged. A salvaged segment ends its session's readable chain. | `docs/raw_data.md` ("Interrupted captures are quarantined by recovery, never resumed; a replacement gets a new ID"); CLAUDE.md "Do not silently repair" |
| B8-2 | **Environment identity is carried per segment.** RT-B2-09 asks that "every raw frame header carries an environment identity". In v2 a frame exists only inside its segment object, whose first frame (the hash-chained segment header) carries the venue environment. A frame cannot be read without it. | `research/kalshi/red_team_review.md` RT-B2-09 |
| B8-3 | **Venue sequence numbers are not raw-frame fields.** The raw layer never parses payloads, so a venue's own sequence stays inside the payload and is extracted by the normalizer. | `docs/raw_data.md`; CLAUDE.md "Preserve raw data" |
| B8-4 | **Raw format v1 no longer starts captures outside the `test` environment.** F-12 must be done before real collection, and v1 lacks monotonic time and direction. Reading and verifying v1 captures is unchanged. | `docs/gate0_readiness.md` (F-12 deadline) |
| B8-5 | **RT-4 "gate commands"** means the CLIs that create project records (`python -m pmv.gates create`, `python -m pmv.holdout_log record`). They refuse `--environment test`. Read-only verification commands are unchanged. | `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md` (RT-4) |
| B8-6 | **Demo data is protected like real data and never used as data.** Demo captures are written only inside the protected raw location, and every v2 loader refuses them, for every use. v1 captures carry no environment identity, and v1 starts new captures only in `test` (B8-4), so v1 data is test data (RT-B8-08). | RT-B2-09; F-37 title ("demo data treated as real") |
| B8-7 | **Snapshots that answer a PMV command are never a recovery point** (`BookSnapshot.solicited`), until a recorded test proves such replies are sequence-consistent. | `research/kalshi/red_team_review.md` RT-B2-03 |

## Not changed

- No requirement in the holdout, protected-information, acquisition, risk, or real-capital rules was relaxed.
- `src/pmv/acquisition/` was not modified. The final B07 Red-Team verdict at `4170b3c` still covers it.
- No gate status changed: Gate 0 passed, and Gate 1 is undecided. No cycle, `T0`, split, or protected scope exists.
- No real market observation was accessed, no venue or data host was contacted, and no credential or account was used or created.
- PROJECT_BRIEF.md, START_HERE.md, CLAUDE.md, `.claude/`, and the hash-pinned HOLDOUT_ACCESS_LOG.md body were not modified.

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
