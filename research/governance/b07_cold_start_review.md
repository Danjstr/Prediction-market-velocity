# B07 Fresh-Context Cold-Start Review

- **Date:** 2026-10-16
- **Reviewer:** fresh-context cold-start reviewer (development agent; no prior conversation, memory, or chat context used; not part of any runtime).
- **Method:** reconstruction only from files committed in the current Git tree, following START_HERE.md "Repository Continuity" > "Cold start" (START_HERE.md:48-56) plus the reading list in the review brief: CLAUDE.md, PROJECT_BRIEF.md, START_HERE.md, `docs/BRANCH_TIMELINE.md`, `docs/phase1.md`, `docs/acquisition_readiness.md`, `docs/external_access.md`, `docs/protected_information.md`, `docs/release_tool_design.md`, `docs/exposure_register.md`, `docs/decisions/` (B07, B06, batch 4 records), `docs/owner_actions/README.md`, `docs/raw_data.md`, and `research/governance/b07_acquisition_pipeline_red_team_review.md`. Spot checks of `src/pmv/acquisition/confinement.py` and `isolation.py` to confirm the documented seccomp allowlist and `-I -S` launch. Read-only; no tests, no network, no protected or credential paths read. Untracked sandbox placeholders (`.bashrc`, `secrets`, `.claude/hooks`, …) ignored as noise.
- **Git state seen:**
  - branch `b07/phase1-acquisition-pipeline-hardening`, HEAD `597aebaa150cc07330e93042e9c3146276fa099f` ("B07: record final Red-Team verdict and update acquisition docs"); tracked tree clean;
  - `git log --oneline` (newest first): `597aeba`, `4170b3c`, `cd9ef17`, `ae693e2`, `b146099`, `f160647` (B07), then `c0d2a2b` (final B06), `8517fc2`, `aa62016`, …;
  - `git merge-base --is-ancestor c0d2a2b HEAD` returned 0 (final B06 is an ancestor);
  - local branches: `b06/governance-continuity-sync`, `b07/phase1-acquisition-pipeline-hardening`, `main`, four `phase1/*`; remotes additionally `origin/docs/activate-isolated-autonomy`;
  - `git diff --stat 4170b3c HEAD` touches only `docs/acquisition_readiness.md`, `docs/phase1.md`, and the Red-Team review, so the final Red-Team verdict at `4170b3c` still covers the current `src/pmv/acquisition/` code.
  - Remote tip not verified (no network); `docs/BRANCH_TIMELINE.md:19` requires `git ls-remote` for that.

## 18-item reconstruction table

| # | Item | Rating | Evidence |
|---|---|---|---|
| 1 | PMV objective | CLEAR | P(contract resolves in our favour \| info at decision time), positive after-cost EV: CLAUDE.md:104-112, 114-130; PROJECT_BRIEF.md §1, §4, §15 (PROJECT_BRIEF.md:378-390); START_HERE.md:25-33 |
| 2 | Late-window strategy and preliminary price hypothesis | CLEAR | Canonical PROJECT_BRIEF.md:56-68 (sweet spot ~$0.93–0.97, ~$0.85 candidate-generation floor, final few minutes, strata by price and time band); START_HERE.md:27-33; CLAUDE.md:97-101; B06 record C-5 (`docs/decisions/2026-10-16_b06_governance_continuity_sync.md:32`) |
| 3 | Price vs cost-adjusted edge | CLEAR | PROJECT_BRIEF.md:64-66 (`calibrated P(win) > executable break-even + margin`, no assumed $1 payout); CLAUDE.md:100-101, 118-130; START_HERE.md:30 |
| 4 | BTC/gold, 15 min–1 h scope | CLEAR | PROJECT_BRIEF.md:43, 202; CLAUDE.md:93-95; `docs/phase1.md:51-53` (Kalshi first, Polymarket deferred, 15-min first). Open fact, clearly flagged: whether in-scope gold contracts exist (START_HERE.md:34; `docs/phase1.md:78`, F-16/E-1) |
| 5 | Runtime LLM independence | CLEAR | CLAUDE.md:65-89, 470-476; PROJECT_BRIEF.md:13-40, 374; START_HERE.md:1-21; B07 record invariant (`docs/decisions/2026-10-16_b07_acquisition_pipeline_hardening.md:29`) |
| 6 | Phase 0–12 roadmap incl. 4.5 and 5.5 | CLEAR | START_HERE.md:70-90 (table) and headings at :186, :216, :283, :342, :378, :409, :466, :702, :789, :852, :920, :971, :998, :1065, :1101; CLAUDE.md:432; B06 C-3 |
| 7 | Current Phase 1 status | CLEAR | `docs/phase1.md:5-47` (Phase 1; no cycle/`T0`/split; no real observation; guard refuses all); START_HERE.md:77 ("In progress"), :1261 |
| 8 | Historical-development vs prospective-protected-holdout architecture | CLEAR | CLAUDE.md:171-208; PROJECT_BRIEF.md:168-196; START_HERE.md:106-138 (H-1, 70/30 reinterpretation at :118); batch 4 H-1; `docs/exposure_register.md:18` (binding rule) |
| 9 | Protected-information rules / A-7 / A-8 | CLEAR | CLAUDE.md:210-225 (five classes); `docs/protected_information.md:5, 60-92`; A-7/A-8 at `docs/external_access.md:89-90`; storage ≠ release at `docs/acquisition_readiness.md:38, 126, 164-166`, `docs/raw_data.md:49-62`, B7-3 (`b07` record:48) |
| 10 | Acquisition restrictions and F-09 host-class boundaries | CONTRADICTORY | Rules are clear (CLAUDE.md:155-169; `docs/external_access.md:9-35, 77-99`), but F-09 enforcement status conflicts: `docs/external_access.md:61` says the denies are "Not yet in place … Until the owner commits it, this policy is rule-governed only", while `docs/phase1.md:17, 84` and `docs/owner_actions/README.md:14` record them committed in `8517fc2` with the behavioral check passed (confirmed: `.claude/settings.json` at HEAD contains the WebFetch class denies). See I-1 |
| 11 | Approved owner decisions | CLEAR | Batch 4 H-1..H-8, O-3, O-5, O-6, O-9 and rulings (`docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md:11-170`); B06 C-1..C-7 (`b06` record:26-34); B07 charter (`b07` record:5-38); summarized in `docs/phase1.md:248-264` |
| 12 | Unresolved pre-T0 decisions P-1..P-4 | CLEAR | START_HERE.md:132-136; batch 4 record:171-180; `docs/phase1.md:31, 42`; `docs/release_tool_design.md:14, 58` |
| 13 | Tax / after-tax EV requirement | CLEAR | PROJECT_BRIEF.md:122-129, :384; CLAUDE.md:132; START_HERE.md:81 (Phase 4.5); B06 C-4 |
| 14 | Active branch and numbered-continuity rule (B08 from final B07) | CLEAR | `docs/BRANCH_TIMELINE.md:7-21` (B07 active; designation cited to the B07 record "Designation"; "every new development branch (B08) starts from this branch's final tip"), :80-85; B07 record:8-10, :36-38; START_HERE.md:58-66; CLAUDE.md:433-438. Minor gaps in the B07 commit list (I-4) |
| 15 | B07 work completed (G-1..G-6, RT-B6-26/27/28, Red-Team rounds) | AMBIGUOUS | Authoritative and consistent: `docs/acquisition_readiness.md:23-195`, B07 record B7-1..B7-8, Red-Team review final verdict (review:308-322, no BLOCKING/MAJOR at `4170b3c`). But `docs/phase1.md:271` still describes G-1 as "a seccomp denylist" (I-2), and the B07 record does not record the review outcome or the `-I -S`/`pmv`-only launch hardening (I-5) |
| 16 | A-4 gaps still open | CLEAR | `docs/acquisition_readiness.md:144-162` (Parquet/DBN/zstd readers pending B7-6; production transport B7-4; A-4 "satisfied" review record; provider checksums; G-7 owner inputs); `docs/phase1.md:18-29`; `docs/external_access.md:99`; Red-Team review:317-321 |
| 17 | Gate 1 status | CLEAR | Undecided: `docs/phase1.md:9`; `docs/BRANCH_TIMELINE.md:21`; B07 record:70; `docs/gates.md:5`; B06 record:47. Gate 1 requirements at START_HERE.md:266-279 |
| 18 | Next permissible action (owner and agent) | CLEAR | `docs/phase1.md:35-47` (owner: review/merge B07 PR, B7-6 dependency decision, A-3 policy and B7-7, licence terms/AR-3, E-U1, P-1..P-4, optional B6S-14; agents: only in a later owner-chartered batch, synthetic only, from the active branch: production-transport design (B7-4), approved readers, raw-format v2 / collector hardening); release-tool chain at `docs/release_tool_design.md:49-62`; branch procedure `docs/BRANCH_TIMELINE.md:80-85` |

No document claims that acquisition is authorized, that A-4 is satisfied, or that Gate 1 passed (searched across the tree; every hit is a negative statement or a code-level refusal message). No document names B06 as the current active branch: B06 appears only as parent / historical checkpoint.

## Cross-document inconsistencies and stale statements

### MAJOR

**I-1. F-09 enforcement status is stale in `docs/external_access.md` §1.4.**
- Location: `docs/external_access.md:61` (and the framing at :60).
- Quoted: "**Not yet in place:** deterministic WebFetch deny rules for the `live-data`, `live-display`, and `trading-private` classes in `.claude/settings.json` (Step 11 F-09). … An owner-appliable patch … is in `docs/owner_actions/` … Until the owner commits it, this policy is rule-governed only."
- Conflict: `docs/phase1.md:17` ("committed F-09 denies (done: `8517fc2`, behavioral check passed 2026-10-16)"), `docs/phase1.md:84`, `docs/acquisition_readiness.md:154`, and `docs/owner_actions/README.md:14` ("Status (2026-10-16): both patches applied") all say the denies are committed; `.claude/settings.json` at HEAD contains them. A session that reads `docs/external_access.md` (which CLAUDE.md:167 points to as the acquisition authority) gets the wrong picture of which controls exist.
- Fix: replace the "Not yet in place" bullet with: "**In place (B06, `8517fc2`, owner-applied 2026-10-16):** deterministic WebFetch and sandbox-network denies for the `live-data`, `live-display`, and `trading-private` host patterns in `.claude/settings.json`; behavioral check passed (`docs/owner_actions/README.md`). Verified limits remain: prefix patterns such as `api.*.*` bind WebFetch only; only exact hosts and leading `*.` patterns also bind the Bash sandbox; WebFetch rules cannot match paths; WebSearch cannot be domain-restricted. Rules 8–10 of §1.1 therefore stay rule-governed." Keep line 62 (requirement) as is.

**I-2. `docs/phase1.md` describes the G-1 worker filter as a denylist.**
- Location: `docs/phase1.md:271`.
- Quoted: "**G-1.** An isolated parse worker: rlimits applied by the parent, a seccomp denylist installed before input, and a framed protocol enforced by the parent."
- Conflict: B07 record B7-1 (`b07` record:46: "installs a seccomp **allowlist** … It was a denylist until Red-Team round 1 …"), `docs/acquisition_readiness.md:52-63`, and the code (`src/pmv/acquisition/confinement.py:14, 71-109`, `ALLOWED_SYSCALLS`, `_RET_ALLOW`) all say allowlist. `docs/phase1.md` is the cold-start step-4 working record (START_HERE.md:54), so a session reading it would conclude the RT-B7-01 BLOCKING fix was not applied. It also omits the `python -I -S` launch and `pmv`-only import finder (RT-B7-13/14), which `docs/acquisition_readiness.md:46` and `src/pmv/acquisition/isolation.py:175-176` document.
- Fix: "**G-1.** An isolated parse worker: rlimits applied by the parent; launched with `python -I -S`, an empty environment, and a `pmv`-only import finder; a seccomp **allowlist** (argument-filtered `fcntl`/`ioctl`) plus `no_new_privs` installed before input (replacing the round-1 denylist, RT-B7-01); a non-dumpable parent; and a framed protocol enforced by the parent."

### MINOR

**I-3. Batch 4 and B06 records still describe merged/applied items as pending, with no status pointer.**
- `docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md:3`: "Until the B06 pull request is merged, the rulings table below, as verified in B06 C-6, governs development on the active branch. The owner confirms the record's final wording by merging." B06 was merged by PR #5 (`2314326`, `docs/BRANCH_TIMELINE.md:27, 33`).
- Same record :196-199 ("Owner actions outside the sandbox") and `docs/decisions/2026-10-16_b06_governance_continuity_sync.md:38, 40` describe the agent-file and F-09 patches as unapplied; they were applied in `8517fc2`.
- Why: decision records are history and should not be rewritten, but a cold-start reader of "latest records first" (START_HERE.md:55) may read them as current.
- Fix: rather than editing the records' bodies, add a dated status line to each (or to the B07 record / `docs/phase1.md`): "Status 2026-10-16: B06 merged by PR #5 (`2314326`); both owner patches applied in `8517fc2` (`docs/owner_actions/README.md`)." Note that the batch 4 record is not a governance document under CLAUDE.md, but adding status lines to decision records should follow whatever append-only convention the owner prefers.

**I-4. B07 commit list in `docs/BRANCH_TIMELINE.md` is incomplete and skips a commit.**
- Location: `docs/BRANCH_TIMELINE.md:59-62`.
- Quoted: rows `f160647` then "(the commit adding this row)". The row was added by `ae693e2`, so `b146099` ("Red-Team round 1 remediation (RT-B7-01 to RT-B7-11)"), which lies between them, is omitted despite "Listed oldest first". `cd9ef17`, `4170b3c`, and `597aeba` are also unlisted (the text does say later commits are added at the next update).
- Why: a B08 creator verifying the "final B07 tip" has no recorded hash; the table understates the remediation history.
- Fix: at the next timeline update, list `f160647`, `b146099`, `ae693e2`, `cd9ef17`, `4170b3c`, `597aeba` (and the update commit), and state the reviewed code commit (`4170b3c`) separately from the branch tip.

**I-5. B07 decision record lacks the review outcome and the launch hardening.**
- Location: `docs/decisions/2026-10-16_b07_acquisition_pipeline_hardening.md:34` (Reviews: requirement only) and :46 (B7-1).
- Why: the record says what reviews are required but not their result (five rounds; round 1 BLOCKING RT-B7-01 and MAJOR RT-B7-02 fixed; final verdict at `4170b3c` no BLOCKING/MAJOR; A-4 not satisfied; no Statistician review triggered). B7-1 omits the `python -I -S` / empty-environment / `pmv`-only finder launch (RT-B7-13/14), which is a material part of the isolation model.
- Fix: add a "Review outcome" section pointing to `research/governance/b07_acquisition_pipeline_red_team_review.md` "Final verdict" with the facts above, and append to B7-1: "The worker is launched with `python -I -S`, no site processing, and an import finder that loads only `pmv`/`pmv.*` from the package root (RT-B7-13, RT-B7-14)."

**I-6. Open-owner-input lists are not aligned across the three B07 documents.**
- `docs/phase1.md:36-43` is the complete list: B7-6 dependencies, A-3 policy plus B7-7 size-class confirmation, AR-3 licence terms, E-U1, P-1..P-4, optional B6S-14 (plus PR merge).
- `docs/acquisition_readiness.md:154, 158-162` lists B7-6 and the A-3 policy/restore test, mentions E-U1 at :166, but never mentions that the A-3 restore-coverage check it implements (:111, "restore-test coverage under the backup policy") uses the **unconfirmed** B7-7 "size class" interpretation. P-1..P-4 and B6S-14 are absent (acceptable for a tooling doc, but not cross-referenced).
- The B07 record lists B7-6 and B7-7 as awaiting the owner and B6S-14 as optional (:51-52, :74-76), but A-3 and E-U1 appear only under "Prohibited" (:23) and P-1..P-4 not at all; there is no consolidated "Open owner inputs" section.
- Fix: in `docs/acquisition_readiness.md` G-7 row add "and owner confirmation or replacement of the B7-7 size-class interpretation used by the restore-coverage check"; in the B07 record add an "Open owner inputs after B07" list mirroring `docs/phase1.md:36-43`.

**I-7. `docs/protected_information.md` status heading still says "Phase 0".**
- Location: `docs/protected_information.md:60, 62` ("**Phase 0 is safe for:** …", "**Phase 0 is NOT yet safe for agent-facing real market observations.**").
- Why: the project is in Phase 1; the substance (registry empty, guard refuses all) is still correct, but the wording invites "this was a Phase 0 restriction" misreadings.
- Fix: "**Current status (Phase 1, 2026-10-16): not yet safe for agent-facing real market observations.** …" (and similarly for the "safe for" line).

**I-8. Small tension on when a new branch records itself in the timeline.**
- `docs/backup_and_recovery.md:163` ("Record the new branch in `docs/BRANCH_TIMELINE.md`") and START_HERE.md:66 ("Each new branch records itself, its parent, and its head") vs `docs/BRANCH_TIMELINE.md:85` ("Only when the owner has designated the new branch as active … add the new row … A session never designates its own branch as active").
- Why: a B08 session could read the first two as permission to add its row / mark itself active before owner designation.
- Fix: in `docs/backup_and_recovery.md:163` append "; mark it active only after owner designation (`docs/BRANCH_TIMELINE.md` procedure step 4)". START_HERE.md is governance and needs owner approval to edit; the BRANCH_TIMELINE procedure is the more specific rule and is consistent with START_HERE.md:60.

**I-9. Exposure register Part B and the B07 record do not record the model IDs used in B06/B07.**
- Location: `docs/exposure_register.md:35, 41-43` ("Each session and subagent record names the resolved ID it ran"); only M-1 (batch 4) exists; the B07 record names no model ID.
- Why: not blocking (no cycle exists, and the rule binds before use for a cycle's candidate), but the H-8 record becomes harder to reconstruct later.
- Fix: append Part B rows (or a line in the B07 record) naming the resolved model ID(s) used for B06/B07 sessions and reviewers, with the cutoff source.

### Checked and found consistent (no fix needed)
- B07 designation is cited in the timeline (`docs/BRANCH_TIMELINE.md:11` → B07 record "Designation", :36-38).
- B06 is described only as parent / preserved historical checkpoint (`docs/BRANCH_TIMELINE.md:12, 33`; `docs/phase1.md:10`; B07 record:38). No document describes B06-era A-4 status as current; `docs/acquisition_readiness.md:185` and `docs/release_tool_design.md:47` correctly scope B06 items.
- Seccomp allowlist and `-I -S` launch are accurately described in `docs/acquisition_readiness.md:46-63` and B7-1 (allowlist), and match the code. `research/governance/b07_acquisition_pipeline_red_team_review.md:19, 39, 87` say "denylist" but describe round 1 at `f160647`, which was accurate then.
- The final Red-Team verdict (`4170b3c`) still covers the acquisition code: `git diff 4170b3c HEAD` touches docs only.
- No claim anywhere that acquisition is authorized, A-4 is satisfied, or Gate 1 passed.

## Verdict

**Can a brand-new session reconstruct B07 correctly? YES, with conditions.**

From Git alone, a fresh session can correctly determine: the PMV objective and late-window strategy; the full Phase 0–12 roadmap; that the project is in Phase 1 with Gate 1 undecided, A-4 not satisfied, and acquisition not authorized; that B07 (`b07/phase1-acquisition-pipeline-hardening`, branched from final B06 `c0d2a2b`) is the owner-designated active branch and that B08 must start from B07's final tip; what B07 built and its review outcome; the open A-4 gaps; the pre-T0 checklist; and the next owner and agent actions.

Conditions:
1. Treat `docs/acquisition_readiness.md` and the B07 decision record, not `docs/phase1.md:271`, as authoritative on the G-1 isolation model (allowlist, `-I -S`) until I-2 is fixed.
2. Treat F-09 denies as committed (`8517fc2`, `.claude/settings.json`), notwithstanding `docs/external_access.md:61`, until I-1 is fixed.
3. Verify the B07 tip with `git ls-remote` before branching B08, because the timeline's B07 commit list is incomplete (I-4).
4. Read the batch 4 and B06 decision records as history: their "pending patch" and "until B06 is merged" statements are superseded (I-3).

None of the findings creates a path to unauthorized acquisition, data exposure, or a wrong branch point; I-1 and I-2 are MAJOR because they misstate which controls currently exist.

## Coordinator dispositions (2026-10-16, after this review)

Added by the development coordinator, not the reviewer. Every finding was fixed in documentation; no code changed.

| ID | Fix |
|---|---|
| I-1 (MAJOR) | `docs/external_access.md` §1.4 now says the F-09 denies are in place (`8517fc2`, behavioral check passed). The stated limits are kept. |
| I-2 (MAJOR) | `docs/phase1.md` B07 section now describes the allowlist, the `-I -S` launch, the `pmv`-only finder, `no_new_privs`, and the non-dumpable parent. |
| I-3 | Dated status notes were added to the batch 4 and B06 decision records. History was not rewritten. |
| I-4 | `docs/BRANCH_TIMELINE.md` lists every B07 commit, names `4170b3c` as the final reviewed code, and states that later commits change documentation only. |
| I-5, I-6, I-9 | The B07 decision record gained "Outcome" (review rounds, final verdict, model used) and "Open owner inputs after B07". `docs/acquisition_readiness.md` now flags the B7-7 dependency. |
| I-7 | `docs/protected_information.md` gained a Phase 1 status line. |
| I-8 | `docs/backup_and_recovery.md` now defers the timeline row to the owner's designation. START_HERE.md was not edited, because it is governance. |
