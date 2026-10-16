# Branch Timeline

This file numbers the project's development branches in verified Git ancestry order and names the **current active ground-truth branch**. The rule that governs it is in START_HERE.md "Repository Continuity" (owner direction, 2026-10-16; record `docs/decisions/2026-10-16_b06_governance_continuity_sync.md`). CLAUDE.md "Repository Continuity" carries the invariant.

Old branches keep their original names. Their B-numbers are assigned here only; renaming them requires separate owner authorization.

## CURRENT ACTIVE GROUND-TRUTH BRANCH

**`b06/governance-continuity-sync` (B06)**

- Parent: B05 `phase1/acquisition-safety-decisions` at `a1752b4`.
- Head: the pushed tip of `origin/b06/governance-continuity-sync`. A commit cannot contain its own hash, so the "Last recorded head" below is the newest commit recorded at the last timeline update. Verify the tip with `git ls-remote origin refs/heads/b06/governance-continuity-sync`.
- Integration: one pull request into `main`. Merging is the owner's decision.
- PR status (2026-10-16): **not yet opened.** The sandbox has no `gh` or GitHub credential, so the owner opens the single B06 → `main` pull request in the GitHub UI. Owner-applied patches from `docs/owner_actions/` join this same branch and pull request. Until the owner designates a successor, every new development branch starts from this branch's tip.

## Timeline

| ID | Branch | Parent ID | Head commit | Status | Purpose |
|---|---|---|---|---|---|
| B00 | `main` | — | baseline `a07fc29` (Gate 0 PASS at `db09acd`); `main` is now at `ad169a2` | Integration branch. Advances only by merged pull request. | Canonical historical baseline: Phase 0 foundation, Gate 0, backup and recovery |
| B01 | `docs/activate-isolated-autonomy` (remote only) | B00 | `0dd40ca` | Historical checkpoint. Merged by PR #1 (`4eec20c`) | Activation of the isolated autonomous environment |
| B02 | `phase1/kalshi-data-foundation` | B01 (branched at `4eec20c`) | `899dae6` | Historical checkpoint. Merged by PR #2 (`856083e`) | Phase 1 batch 1: venue-neutral market-data foundation |
| B03 | `phase1/kalshi-venue-verification` | B02 (branched at `856083e`) | `4ca18e0` | Historical checkpoint. Merged by PR #3 (`c074e9b`) | Phase 1 batch 2: Kalshi venue verification (documentation) |
| B04 | `phase1/historical-data-strategy` | B03 (branched at `c074e9b`) | `012afa0` | Historical checkpoint. Merged by PR #4 (`ad169a2`) | Phase 1 batch 3: historical data strategy |
| B05 | `phase1/acquisition-safety-decisions` | B04 (branched at `ad169a2`) | `a1752b4` | Historical checkpoint. Pushed; no PR; not merged. Wholly contained in B06 and integrated through B06's pull request | Phase 1 batch 4: owner decisions on acquisition safety and holdout formation |
| B06 | `b06/governance-continuity-sync` | B05 (branched at `a1752b4`) | Last recorded: `a978a77`; tip = timeline-update commit | **CURRENT ACTIVE GROUND-TRUTH BRANCH** | Recovery of the interrupted batch 4 follow-up; owner rulings; strategy objective; phase roadmap; tax requirement; branch continuity; Phase 1 acquisition-readiness tooling |

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
| (the commit adding this row) | Timeline update. Its hash is the branch tip; see `git ls-remote` |

## Ancestry verification (2026-10-16)

Verified read-only from the B06 working tree before B06 was created:
- `git merge-base --is-ancestor <c> a1752b4` succeeded for every one of `a07fc29`, `0dd40ca`, `4eec20c`, `899dae6`, `856083e`, `4ca18e0`, `c074e9b`, `012afa0`, and `ad169a2`.
- First parents: `a1752b4` → `ad169a2` (the merge of B04 into `main`); `012afa0` → `c074e9b`; `4ca18e0` → `856083e`; `899dae6` → `4eec20c`; `0dd40ca` → `a07fc29`. Each branch was cut from `main` immediately after its predecessor was merged, so the history is linear and cumulative, with no fork.
- `git ls-remote --heads origin` listed exactly the six branches above, at the heads shown, before B06 was pushed.

## Procedure for the next branch

1. Confirm that the current branch is the active branch above, and that its HEAD equals the pushed tip.
2. `git merge-base --is-ancestor <active-branch-tip> HEAD` must succeed. If it fails, stop and escalate.
3. `git switch -c bNN/<short-purpose>`, where `NN` is the next number.
4. Only when the owner has designated the new branch as active (by a charter or decision record, cited in the new row), mark the previous branch "Historical checkpoint", add the new row, and move the CURRENT ACTIVE GROUND-TRUTH BRANCH section to the new branch. Commit this on the new branch. A session never designates its own branch as active (START_HERE.md "Repository Continuity").
