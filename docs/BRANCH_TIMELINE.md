# Branch Timeline

This file numbers the project's development branches in verified Git ancestry order and names the **current active ground-truth branch**. The rule that governs it is in START_HERE.md "Repository Continuity" (owner direction, 2026-10-16; record `docs/decisions/2026-10-16_b06_governance_continuity_sync.md`). CLAUDE.md "Repository Continuity" carries the invariant.

Old branches keep their original names. Their B-numbers are assigned here only; renaming them requires separate owner authorization.

## CURRENT ACTIVE GROUND-TRUTH BRANCH

**`b07/phase1-acquisition-pipeline-hardening` (B07)**

- **Designation:** the owner's B07 batch charter of 2026-10-16 (`docs/decisions/2026-10-16_b07_acquisition_pipeline_hardening.md`, "Designation").
- **Parent:** B06 `b06/governance-continuity-sync`, at its final commit `c0d2a2b04e7ad3aee5d170aa21071d615bd5c318`. B07 was branched directly from that commit, not from `main`, even though `main` already contained B06 through merge commit `2314326` (PR #5).
- **Purpose:** Phase 1 acquisition pipeline hardening, on synthetic data only:
  - G-1: an isolated parse worker;
  - G-2, G-3, G-5: readers and bounded decoding;
  - G-4: fetcher semantics behind a synthetic transport;
  - G-6: the end-to-end pipeline into the protected raw store;
  - RT-B6-26, RT-B6-27, and the RT-B6-28 re-review.
- **Head:** the pushed tip of `origin/b07/phase1-acquisition-pipeline-hardening`. A commit cannot contain its own hash, so the "Last recorded" head below is the newest commit recorded at the last timeline update. Verify the tip with `git ls-remote origin refs/heads/b07/phase1-acquisition-pipeline-hardening`.
- **Integration:** one pull request into `main`. Merging is the owner's decision, with a normal merge commit (not squash or rebase), and B07 is not deleted afterwards.
- **Status:** Gate 1 is undecided, A-4 is not satisfied, and acquisition is not authorized. Until the owner designates a successor, every new development branch (B08) starts from this branch's final tip.

## Timeline

| ID | Branch | Parent ID | Head commit | Status | Purpose |
|---|---|---|---|---|---|
| B00 | `main` | — | baseline `a07fc29` (Gate 0 PASS at `db09acd`); `main` is now at `2314326` (B06 merged, PR #5) | Integration branch. Advances only by merged pull request. | Canonical historical baseline: Phase 0 foundation, Gate 0, backup and recovery |
| B01 | `docs/activate-isolated-autonomy` (remote only) | B00 | `0dd40ca` | Historical checkpoint. Merged by PR #1 (`4eec20c`) | Activation of the isolated autonomous environment |
| B02 | `phase1/kalshi-data-foundation` | B01 (branched at `4eec20c`) | `899dae6` | Historical checkpoint. Merged by PR #2 (`856083e`) | Phase 1 batch 1: venue-neutral market-data foundation |
| B03 | `phase1/kalshi-venue-verification` | B02 (branched at `856083e`) | `4ca18e0` | Historical checkpoint. Merged by PR #3 (`c074e9b`) | Phase 1 batch 2: Kalshi venue verification (documentation) |
| B04 | `phase1/historical-data-strategy` | B03 (branched at `c074e9b`) | `012afa0` | Historical checkpoint. Merged by PR #4 (`ad169a2`) | Phase 1 batch 3: historical data strategy |
| B05 | `phase1/acquisition-safety-decisions` | B04 (branched at `ad169a2`) | `a1752b4` | Historical checkpoint. Pushed; no PR; not merged. Wholly contained in B06 and integrated through B06's pull request | Phase 1 batch 4: owner decisions on acquisition safety and holdout formation |
| B06 | `b06/governance-continuity-sync` | B05 (branched at `a1752b4`) | `c0d2a2b` (final) | Historical checkpoint, preserved. Merged by PR #5 (`2314326`) | Recovery of the interrupted batch 4 follow-up; owner rulings; strategy objective; phase roadmap; tax requirement; branch continuity; Phase 1 acquisition-readiness tooling |
| B07 | `b07/phase1-acquisition-pipeline-hardening` | B06 (branched at final `c0d2a2b`) | Last recorded: see "B07 commits"; tip = timeline-update commit | **CURRENT ACTIVE GROUND-TRUTH BRANCH** | Phase 1 acquisition pipeline hardening (G-1 to G-6), synthetic data only |

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
| (the commit adding this row) | Documentation, B07 decision record, and timeline. Later commits are listed here at the next timeline update, and the tip is verified with `git ls-remote` |

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
