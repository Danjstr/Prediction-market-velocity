# B08 cold-start review (repository-only reconstruction)

- **Reviewer:** fresh-context cold-start reviewer. No chat or session context; everything below is reconstructed from files committed in Git on the current branch. Code was spot-checked only to confirm documentary claims.
- **Date:** 2026-10-16.
- **Scope:** read-only. This file is the only file written. No commit, push, network access, test run, or `check.sh` run. No real observation, protected path, or credential was accessed. Untracked working-tree files (see "Working-tree note") were not opened.

## Git state at review

| Check | Result |
|---|---|
| `git status --short --branch` | `## b08/prospective-capture-hardening`; no tracked modifications; untracked files only (see "Working-tree note") |
| HEAD | `d52b46aea0ff92fb48d16eb6f7cd314bef5fef8a` ("B08: record Red-Team round 3 verdict and timeline commits") |
| `git log --oneline -12` | `d52b46a`, `6dc2b51`, `7190f7f`, `222a7e7`, `1aa6c52` (B08); then `9a6b212`, `cfd3e54`, `597aeba`, `4170b3c`, `cd9ef17`, `ae693e2`, `b146099` (B07) |
| `git merge-base --is-ancestor 9a6b212 HEAD` | `0` (final B07 is an ancestor) |
| `git diff 9a6b212 HEAD --stat -- src/pmv/acquisition` | empty (reviewed acquisition code unchanged since final B07) |
| Local remote-tracking refs (not refreshed; no network) | `origin/b08/prospective-capture-hardening` = `d52b46a` = HEAD; `origin/main` = `2a46ffd`; `9a6b212` is an ancestor of `origin/main` |
| `APPROVED_CAPTURE_ENDPOINTS` | `src/pmv/capture_environment.py:75` `frozenset()` (empty); refusal at `:215-219` "live capture is not authorized" |
| `PRODUCTION_TRANSPORTS` | `src/pmv/acquisition/pipeline.py:158` `frozenset()` (empty); real runs fail "G-4: no reviewed production transport" (`:728-730`) |

## Reconstruction table

| # | Item | Rating | Reconstruction and evidence |
|---|---|---|---|
| 1 | PMV objective | CLEAR | Autonomous quant system for ~15-min to 1-h BTC and gold prediction markets; late-window, high-confidence; output P(resolves in our favor \| info at decision time); price bands never sufficient. CLAUDE.md:1-3, :91-110; PROJECT_BRIEF.md:56-60 (§3 "Strategy objective"); START_HERE.md:25-34. Kalshi first, Polymarket deferred: docs/phase1.md:55-62. |
| 2 | Final runtime LLM independence | CLEAR | CLAUDE.md:65-89 (":74 No LLM or agent inference is permitted or required"); PROJECT_BRIEF.md:13-21, :374. |
| 3 | Current phase | CLEAR | Phase 1 in progress, Gate 0 passed: START_HERE.md:76-77; docs/phase1.md:5-9; docs/gates.md:5. |
| 4 | Branch continuity | CLEAR | B05→B06→B07→B08 chain with parents and heads: docs/BRANCH_TIMELINE.md:28-38. B08 from final B07 `9a6b212` (not `main`): BRANCH_TIMELINE.md:12, :88-95; B08 record:7. B09 from final B08: BRANCH_TIMELINE.md:24, :113-118; B08 record:36. Rules: START_HERE.md:58-66; CLAUDE.md:433-438. Git confirms ancestry (above). |
| 5 | Historical-development / prospective-holdout architecture | CLEAR | Historical data is development-only and never promotable; first cycle uses a prospective holdout starting at `T0` with margin `m`: CLAUDE.md:171-212; START_HERE.md:122-136; batch 3 record P1/P2 (docs/phase1.md:157-163); exposure register binding rule docs/exposure_register.md (Part A, X-1..X-3; Part B M-1). No cycle, `T0`, split, or scope exists: docs/phase1.md:7; B08 record:56. |
| 6 | Acquisition and capture authorization boundaries | CLEAR | "Historical acquisition is not authorized. Live capture is not authorized.": docs/phase1.md:9, :333; BRANCH_TIMELINE.md:23; B08 record:108-116; docs/external_access.md (§2 tooling status, "Acquisition is not authorized"); docs/raw_data.md:69 ("APPROVED_CAPTURE_ENDPOINTS, which is empty"). Code agrees (above). |
| 7 | Protected-information rules | CLEAR | Five observation classes, embargo, correlation rule, guard: CLAUDE.md:204-225; docs/protected_information.md:59-65 (guard refuses everything, registry empty); docs/external_access.md §1.6, §2 A-8, §3. Host-class rule: CLAUDE.md "Host-Class Rule". |
| 8 | B08 capture work and review outcome | CLEAR | Work: F-11, F-12/F-27, F-33, F-37/RT-4, book continuity, normalized artifacts, synthetic only: docs/phase1.md:292-313; docs/raw_data.md:65-140; docs/market_data.md:88-104, :149, :174. Interpretations B8-1..B8-7 recorded "for owner confirmation": B08 record:38-50. Review: Red-Team round 1 BLOCKING RT-B8-01 + MAJOR RT-B8-02, fixed in round 2; round-2 MINORs RT-B8-12..14 fixed and verified in round 3; final verdict "no unresolved BLOCKING, no MAJOR; proceed": b08_prospective_capture_red_team_review.md:176-184; B08 record:62-75. Statistician: PASS WITH CONDITIONS (self-review, not independent): b08_statistician_review.md:110-119. |
| 9 | Remaining acquisition/source boundary | AMBIGUOUS (minor) | Listed fully in B08 record:97-107 (source selection, A-1, A-2/AR-3, A-3 + B7-7, A-5, A-6, A-4 global-vs-per-source scope, transport B7-4, paginated API support, provider-checksum policy, Parquet/DBN/zstd B7-6). A-4 not satisfied: docs/acquisition_readiness.md:156-162, :195; docs/phase1.md:21. Ambiguity: the "A-4 global-versus-per-source scope" question and "paginated API support" are named only as labels (B08 record:24, :103, :105); no committed document states what the A-4 scope question is, and the link between the query-string refusal (docs/acquisition_readiness.md:27; `hosts.py:158`) and paginated APIs is not written down. See finding m-7. |
| 10 | Gate 1 status | CLEAR | Undecided, not passed: docs/phase1.md:9, :332; BRANCH_TIMELINE.md:23; B08 record:56; docs/gates.md:5. Only Gate 0 record exists in `docs/decisions/gates/`. Gate 1 criteria: START_HERE.md:266-279. |
| 11 | Carried-forward residuals/conditions | CLEAR in the decision record; AMBIGUOUS in docs/phase1.md | Authoritative table: B08 record:77-91 (RT-B8-05/B8S-03, RT-B8-06, B8S-01, B8S-02, B8S-04, B8S-05, B8S-06, artifact digest, RT-B8-13 re-review, RT-B8-12 and RT-B8-01 residuals). docs/phase1.md summarizes it incompletely and with inconsistent timing (findings m-1, m-2, m-3). B8S-07 (NOTE) is not carried forward (m-5). |
| 12 | Deferred governance | CLEAR | E-U1 and H-2 chain: docs/release_tool_design.md:12-16, :53-58; docs/phase1.md:33-37. P-1..P-4: START_HERE.md:132-136; batch 4 record:161-186. F-07 power floor: docs/phase1.md:85. Cycle registration: release_tool_design.md:58. B6S-14 optional and unadopted: B08 record:122; B07 record:107; release_tool_design.md:64. All restated as unchanged in B08 record:117-122. |
| 13 | Next owner action | AMBIGUOUS | docs/phase1.md:38-46 lists owner steps 1-7 (source selection + AR-3 terms, B7-6 dependencies, A-3 policy, E-U1, P-1..P-4, optional B6S-14). It does not list the immediate B08 actions: review B08, confirm interpretations B8-1..B8-7, and decide the B08 → `main` pull request. These appear only indirectly ("B08 (done, pending owner review)", docs/phase1.md:48; "opened when the batch is ready", BRANCH_TIMELINE.md:21; "for owner confirmation", B08 record:38). Whether the PR has been opened is not recorded. See finding m-4. |

## Cross-document inconsistencies and stale statements

No MAJOR finding. Nothing in Git says B07 is still active, that "merge B07" is pending, that B08 is "in progress", that live capture or acquisition is authorized, that A-4 is satisfied, or that Gate 1 passed. F-11/F-12/F-33/F-37 are no longer listed as plain "Open": docs/phase1.md:89, :91 and docs/gate0_readiness.md:107 qualify them as implemented in B08 with residuals (RT-B8-11 is therefore addressed).

### MINOR

| ID | Location | Quote | Problem | Proposed fix |
|---|---|---|---|---|
| m-1 | docs/phase1.md:49 | "before real v2 data is used: the exclusion-ledger and status-after-reset requirements B8S-01 and B8S-02, and the remaining capture items (RT-B8-05, RT-B8-06, B8S-03, B8S-04)" | Puts RT-B8-05 / B8S-03 under "before real v2 data is used", but the B08 record:81 and the Red-Team round 3 verdict make them conditions **before live capture is authorized**, which is earlier. | Split: "before live capture is authorized: RT-B8-05 and B8S-03 (and the RT-B8-12 residual); before long real sessions are normalized: RT-B8-06; before real v2 data is used for research or features: B8S-01, B8S-02, B8S-04, B8S-05, artifact digest." |
| m-2 | docs/phase1.md:89 | "Open before real collection: timestamp plausibility and clock-sync state (RT-B8-05, B8S-03), and memory bounds for long sessions (RT-B8-06)" | RT-B8-06's deadline in the B08 record:82 is "Long real sessions are normalized", not real collection. | Change to "...; and, before long real sessions are normalized, memory bounds (RT-B8-06)". |
| m-3 | docs/phase1.md:323-328 ("Still open") | lists RT-B8-05/B8S-03, RT-B8-06, B8S-01/02, B8S-04, F-26 | Omits B8S-05, B8S-06, the artifact-digest condition, the RT-B8-13 re-review on any registry change, and the RT-B8-12 / RT-B8-01 residuals that B08 record:86-91 carries. It cites the record, so this is incompleteness, not contradiction. | Add "and the other rows of the decision record's 'Residuals and conditions' table (B8S-05, B8S-06, artifact digest, RT-B8-13 re-review, RT-B8-12 and RT-B8-01 residuals)". |
| m-4 | docs/phase1.md:38-46 (Owner next steps) | list starts "1. select the first historical source ..." | The immediate owner actions for B08 are absent: review B08; confirm or reject interpretations B8-1..B8-7; decide on opening/merging the single B08 → `main` PR (normal merge, branch preserved). docs/phase1.md:89 and :91 mention B8-1..B8-3 and B8-4..B8-6 awaiting confirmation; **B8-7** (solicited snapshots never a recovery point) is not mentioned anywhere in phase1.md. | Insert "0. Review B08 (decision record 'Outcome'), confirm or reject interpretations B8-1 to B8-7, and decide the B08 → `main` pull request" at the top of the owner list, and add B8-7 to the line 91 parenthesis or a new line. Record PR status (opened or not) in BRANCH_TIMELINE.md when known. |
| m-5 | B08 record:77-91 vs b08_statistician_review.md:108 | "B8S-07 \| NOTE \| Multiple concurrent connections in one session share book keys" | B8S-07 is not carried forward in the decision record (B8S-06, also a NOTE, is). | Add a row: "B8S-07 \| record which connections carry which subscriptions; per-connection capture identity if one session multiplexes feeds (reviewed change) \| A real collector that multiplexes connections". |
| m-6 | docs/raw_data.md:88 | "`normalized/<session_id>/<key>/{observations.json,labels.json}   normalized artifacts`" | Since the RT-B8-01 fix, an artifact has a third file `artifact.json` (docs/market_data.md:100; `capture_replay.py:136`). Layout diagram is stale. | `normalized/<session_id>/<key>/{observations.json,labels.json,artifact.json}`. |
| m-7 | B08 record:24, :103, :105 | "deciding global versus per-source A-4 semantics"; "A-4 global-versus-per-source scope"; "paginated API support" | Open questions named without definition anywhere in Git; a new session cannot tell what "global vs per-source A-4" means (e.g. whether A-4 could be satisfied for a CSV/JSON-only source before Parquet/DBN/zstd and transport exist), or that the hosts.py query refusal (acquisition_readiness.md:27) currently makes cursor/query-paginated APIs impossible. | Add two sentences to docs/acquisition_readiness.md "Remaining A-4 gaps": (a) the scope question as an explicit owner decision with its two readings; (b) "URLs with queries are refused (§1.1), so paginated or query-parameter APIs cannot be acquired until a reviewed design and owner decision change that". |
| m-8 | docs/BRANCH_TIMELINE.md:86 | "(the commit adding this row) \| Round 3 record, cold-start review and its fixes, and this timeline update" | The commit that added this row is `d52b46a`, which contains only the round 3 record and timeline/decision-record edits (`git show --stat d52b46a`: 3 files, no cold-start review). The row pre-describes work not yet in that commit. Similarly B08 record:74 and docs/phase1.md:321 cite `research/governance/b08_cold_start_review.md`, which did not exist at `d52b46a` (dangling reference until this file is committed). | When this review is committed: record `d52b46a` as "Round 3 record and timeline commits", and add a new row for the cold-start commit (as the tip row). |
| m-9 | docs/protected_information.md:61 | "*Status (B07, 2026-10-16): the project is in Phase 1...*" | Batch label is stale (still accurate in substance). | Optional: "Status (B08, 2026-10-16)". |

### Out-of-Git notes (not findings against the repository)

- The user's auto-memory index still says "B07 acquisition hardening — active branch at cfd3e54". That is stale; Git (BRANCH_TIMELINE.md:7-24) governs and names B08. The memory entry should be updated by the owner/session that controls it.
- **Working-tree note.** The working tree contains many untracked, home-directory-like files (`.bashrc`, `.profile`, `.gitconfig`, `.gitmodules`, `.mcp.json`, `.idea`, `.vscode`, `.claude/commands`, `.claude/hooks`, `.claude/skills`, `secrets`, and others). None is tracked, so none affects reconstruction, and none was opened. They are a staging hazard: stage only by explicit path (CLAUDE.md "never use `git add -A`"); `secrets` must never be committed. Their presence in the repository root may merit owner attention.
- The pushed tip cannot be verified without network (`git ls-remote`); only local remote-tracking refs were checked.

## Verdict

**YES, with conditions.** A brand-new session can reconstruct B08 correctly from Git: the active branch, its parentage from final B07 `9a6b212`, the B09 rule, the completed capture work, the Red-Team and Statistician outcomes, and every "not authorized / not satisfied / undecided" boundary are stated consistently, and the code agrees (both registries empty; acquisition code unchanged since final B07). No statement overclaims authorization or gate status.

Conditions (all MINOR, documentation only):
1. fix the timing and completeness of the residuals summary in docs/phase1.md (m-1, m-2, m-3), and carry B8S-07 (m-5);
2. put the B08-specific owner actions (review, B8-1..B8-7 confirmation including B8-7, PR decision) into the owner next-step list (m-4);
3. correct the `d52b46a` timeline row and add the cold-start commit row when this file is committed (m-8);
4. optionally define the A-4 scope and pagination questions (m-7) and update the raw_data.md layout (m-6).

## Coordinator dispositions (2026-10-16, after this review)

Added by the development coordinator, not the reviewer. Every finding was fixed in documentation. No code changed.

| ID | Fix |
|---|---|
| m-1, m-2 | `docs/phase1.md`: RT-B8-05 and B8S-03 are due before live capture is authorized, and RT-B8-06 before long real sessions are normalized, matching the decision record |
| m-3 | `docs/phase1.md` B08 "Still open" lists every residual and condition, grouped by deadline, and points to the decision record as authoritative |
| m-4 | `docs/phase1.md` owner next steps start with reviewing B08: confirm B8-1 to B8-7, and decide and merge the single B08 pull request (the sandbox cannot open it) |
| m-5 | B8S-07 was added to the decision record's residuals table |
| m-6 | `docs/raw_data.md` layout lists `artifact.json` |
| m-7 | `docs/acquisition_readiness.md` "Remaining A-4 gaps" item 4 defines the A-4 scope question and the paginated-API limit of the query-string refusal |
| m-8 | `docs/BRANCH_TIMELINE.md` describes `d52b46a` accurately and adds a row for the cold-start commit |
| m-9 | `docs/protected_information.md` status line says B08 |
| Outside Git | Auto-memory and untracked sandbox placeholders are not Git governance. The placeholders are the known sandbox `/dev/null` mounts recorded in the B06 record; they were not opened, and staging is by explicit path only |
