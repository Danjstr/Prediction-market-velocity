# Branch Timeline

This file numbers the project's development branches in verified Git ancestry order and names the **current active ground-truth branch**. The rule that governs it is in START_HERE.md "Repository Continuity" (owner direction, 2026-10-16; record `docs/decisions/2026-10-16_b06_governance_continuity_sync.md`). CLAUDE.md "Repository Continuity" carries the invariant.

Old branches keep their original names. Their B-numbers are assigned here only; renaming them requires separate owner authorization.

## CURRENT ACTIVE GROUND-TRUTH BRANCH

**`b08/prospective-capture-hardening` (B08)**

- **Designation:** the owner's B08 batch charter of 2026-10-16 (`docs/decisions/2026-10-16_b08_prospective_capture_hardening.md`, "Designation").
- **Parent:** B07 `b07/phase1-acquisition-pipeline-hardening`, at its final commit `9a6b212d191c68d177f63beb11d289c669639f92`. B08 was branched directly from that commit, not from `main`, even though `main` already contained B07 through merge commit `2a46ffd` (PR #6).
- **Purpose:** Phase 1 prospective-capture hardening, on synthetic data only:
  - F-11: segmentation and salvage;
  - F-12 with F-27: raw frame format v2;
  - F-33: durability ordering;
  - F-37 and RT-4: test and demo boundaries;
  - order-book continuity after rejected frames;
  - normalized capture artifacts.
- **Head:** the pushed tip of `origin/b08/prospective-capture-hardening`. A commit cannot contain its own hash, so the "Last recorded" head below is the newest commit recorded at the last timeline update. Verify the tip with `git ls-remote origin refs/heads/b08/prospective-capture-hardening`.
- **Integration:** one pull request into `main`, opened when the batch is ready. Merging is the owner's decision, with a normal merge commit (not squash or rebase), and B08 is not deleted afterwards.
- **Status:**
  - Gate 1 is undecided, A-4 is not satisfied, historical acquisition is not authorized, and live capture is not authorized.
  - Until the owner designates a successor, every new development branch (B09) starts from this branch's final tip.

## Timeline

| ID | Branch | Parent ID | Head commit | Status | Purpose |
|---|---|---|---|---|---|
| B00 | `main` | — | baseline `a07fc29` (Gate 0 PASS at `db09acd`); `main` is now at `2a46ffd` (B07 merged, PR #6) | Integration branch. Advances only by merged pull request. | Canonical historical baseline: Phase 0 foundation, Gate 0, backup and recovery |
| B01 | `docs/activate-isolated-autonomy` (remote only) | B00 | `0dd40ca` | Historical checkpoint. Merged by PR #1 (`4eec20c`) | Activation of the isolated autonomous environment |
| B02 | `phase1/kalshi-data-foundation` | B01 (branched at `4eec20c`) | `899dae6` | Historical checkpoint. Merged by PR #2 (`856083e`) | Phase 1 batch 1: venue-neutral market-data foundation |
| B03 | `phase1/kalshi-venue-verification` | B02 (branched at `856083e`) | `4ca18e0` | Historical checkpoint. Merged by PR #3 (`c074e9b`) | Phase 1 batch 2: Kalshi venue verification (documentation) |
| B04 | `phase1/historical-data-strategy` | B03 (branched at `c074e9b`) | `012afa0` | Historical checkpoint. Merged by PR #4 (`ad169a2`) | Phase 1 batch 3: historical data strategy |
| B05 | `phase1/acquisition-safety-decisions` | B04 (branched at `ad169a2`) | `a1752b4` | Historical checkpoint. Pushed; no PR; not merged. Wholly contained in B06 and integrated through B06's pull request | Phase 1 batch 4: owner decisions on acquisition safety and holdout formation |
| B06 | `b06/governance-continuity-sync` | B05 (branched at `a1752b4`) | `c0d2a2b` (final) | Historical checkpoint, preserved. Merged by PR #5 (`2314326`) | Recovery of the interrupted batch 4 follow-up; owner rulings; strategy objective; phase roadmap; tax requirement; branch continuity; Phase 1 acquisition-readiness tooling |
| B07 | `b07/phase1-acquisition-pipeline-hardening` | B06 (branched at final `c0d2a2b`) | `9a6b212` (final) | Historical checkpoint, preserved. Merged by PR #6 (`2a46ffd`) | Phase 1 acquisition pipeline hardening (G-1 to G-6), synthetic data only |
| B08 | `b08/prospective-capture-hardening` | B07 (branched at final `9a6b212`) | Last recorded: see "B08 commits"; tip = timeline-update commit | **CURRENT ACTIVE GROUND-TRUTH BRANCH** | Phase 1 prospective-capture hardening (F-11, F-12/F-27, F-33, F-37/RT-4, book continuity, normalized artifacts), synthetic data only |

PR numbers come from the merge-commit subjects on `main`.

### B06 commits

Listed oldest first, and appended at each timeline update.

| Commit | Content |
|---|---|
| `25da6a4` | Governance continuity sync and interrupted-session recovery |
| `8310db3` | Cold-start reconstruction fixes |
| `acc8e2b` | Phase 1 acquisition-readiness tooling (synthetic data only) |
| `f9c5262` | Timeline update |
| `18240ae` | Acquisition tooling Red-Team rounds 4 and 4b remediation (continuation) |
| `de1fecf` | H-2 release-tool design and governed deferral |
| `a978a77` | Continuation record and cold-start review fixes |
| `aa62016` | Timeline update (continuation commits and PR status) |
| `8517fc2` | Owner-applied agent split wording and F-09 host-class denies |
| `c0d2a2b` | Status refresh after owner validation (final B06 commit) |

### B07 commits

Listed oldest first, and appended at each timeline update.

| Commit | Content |
|---|---|
| `f160647` | G-1 to G-6 acquisition pipeline hardening (synthetic data only) |
| `b146099` | Red-Team round 1 remediation (RT-B7-01 to RT-B7-11) |
| `ae693e2` | Round 2 follow-ups (RT-B7-12, RT-B7-13, RT-B7-04 residual) and B07 documentation |
| `cd9ef17` | Round 3 follow-ups (RT-B7-14, `stage_failed`) |
| `4170b3c` | RT-B7-14 closed (`pmv`-only finder). **Final reviewed acquisition code:** Red-Team round 5 verdict, no BLOCKING and no MAJOR finding |
| `597aeba` | Final Red-Team verdict recorded in the docs (`check.sh` passed: 2123 passed, 8 skipped) |
| `cfd3e54` | Cold-start review and its fixes (docs), plus a collision-proof content-leak assertion in one integration test |
| `9a6b212` | Real-mode Git-fact tests made environment-independent (tests only; the CI fix). **Final B07 commit**, merged by PR #6 (`2a46ffd`) |

After `4170b3c`, no production code changed: `git diff 4170b3c 9a6b212 -- src` is empty, so the final Red-Team verdict covers the code at final B07. The only later test change makes the sentinel values in `test_report_journal_and_record_carry_no_file_content` impossible to collide with a timestamp or hash.

### B08 commits

Listed oldest first, and appended at each timeline update.

| Commit | Content |
|---|---|
| (the commit adding this row) | Post-B07 status correction (PR #6, final B07 `9a6b212`), the B08 charter record, and B08 designation. Its hash is a B08 commit; see `git log` |

## Ancestry verification for B08 (2026-10-16)

Verified before B08 was created, in the isolated sandbox, after `git fetch origin`:
- the local `b07/phase1-acquisition-pipeline-hardening` and `origin/b07/phase1-acquisition-pipeline-hardening` were both at `9a6b212d191c68d177f63beb11d289c669639f92`;
- `git merge-base --is-ancestor c0d2a2b 9a6b212` returned 0 (B06 → B07), and `git merge-base --is-ancestor 9a6b212 origin/main` returned 0 (B07 is in `main` through `2a46ffd`);
- `git diff 9a6b212 2a46ffd` was empty: `main`'s tree equals final B07's;
- B08 was created from final B07 with `git switch -c`, and `git merge-base --is-ancestor 9a6b212 HEAD` returned 0;
- B08 was pushed with an explicit `git push origin b08/prospective-capture-hardening`, and `git ls-remote` showed it at `9a6b212` before the first B08 commit.

## Ancestry verification for B07 (2026-10-16)

Verified before B07 was created, in the isolated sandbox:
- the local `b06/governance-continuity-sync` and `origin/b06/governance-continuity-sync` were both at `c0d2a2b04e7ad3aee5d170aa21071d615bd5c318`, and B07 was created from it with `git switch -c`;
- `git merge-base --is-ancestor` returned 0 for `c0d2a2b` (B06), `a1752b4` (B05), and `012afa0` (batch 3) against the B07 head;
- `origin/main` contained merge commit `2314326`.

The local and remote B07 heads were equal at creation.

## Ancestry verification (2026-10-16)

Verified read-only from the B06 working tree before B06 was created:
- `git merge-base --is-ancestor <c> a1752b4` succeeded for every one of `a07fc29`, `0dd40ca`, `4eec20c`, `899dae6`, `856083e`, `4ca18e0`, `c074e9b`, `012afa0`, and `ad169a2`.
- First parents: `a1752b4` → `ad169a2` (the merge of B04 into `main`); `012afa0` → `c074e9b`; `4ca18e0` → `856083e`; `899dae6` → `4eec20c`; `0dd40ca` → `a07fc29`. Each branch was cut from `main` immediately after its predecessor was merged, so the history is linear and cumulative, with no fork.
- `git ls-remote --heads origin` listed exactly the six branches above, at the heads shown, before B06 was pushed.

## Procedure for the next branch

1. Confirm that the current branch is the active branch above, and that its HEAD equals the pushed tip.
2. `git merge-base --is-ancestor <active-branch-tip> HEAD` must succeed. If it fails, stop and escalate.
3. `git switch -c bNN/<short-purpose>` from the active branch's final tip, where `NN` is the next number. Do this even when `main` already contains that branch through a merged pull request: the numbered branch, not `main`, is the predecessor.
4. Only when the owner has designated the new branch as active (by a charter or decision record, cited in the new row), mark the previous branch "Historical checkpoint", add the new row, and move the CURRENT ACTIVE GROUND-TRUTH BRANCH section to the new branch. Commit this on the new branch. A session never designates its own branch as active (START_HERE.md "Repository Continuity").
