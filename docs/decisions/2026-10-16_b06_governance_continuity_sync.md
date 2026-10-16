# B06: governance continuity sync and recovery (2026-10-16)

**Approver:** the project owner, in the B06 recovery charter issued on 2026-10-16 in the isolated environment. The charter instructed this session to:
- recover the interrupted batch 4 follow-up;
- verify the branch timeline;
- create one new numbered cumulative branch;
- record the decisions below in the governance documents (PROJECT_BRIEF.md, START_HERE.md, CLAUDE.md), which it explicitly authorized editing;
- continue Phase 1 acquisition readiness without real data;
- open exactly one pull request, without merging.

The development session wrote this record.

**Limitation:** this record is procedural. The system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

## Recovery of the interrupted session

A terminal closure interrupted the previous session while it was recording the owner's rulings on the batch 4 reviews. The repository state was inspected before anything changed:
- unstaged edits to 9 tracked files and a new untracked `docs/owner_actions/` directory, all on `phase1/acquisition-safety-decisions` at `a1752b4`;
- nothing staged, no new commit, no new remote branch, no stash;
- other untracked paths (`.bashrc`, `secrets`, `.claude/hooks`, and similar) were sandbox `/dev/null` placeholders, not work.

The partial work was kept, carried onto B06, verified against the charter item by item, and completed. Nothing was discarded.

## Decisions recorded

| ID | Decision | Where recorded |
|---|---|---|
| C-1 | **Branch continuity.** Every new development branch is created from the newest approved cumulative branch, never from `main` or an older branch. The newest numbered branch is the ground truth for current development, and older branches are historical checkpoints. Sessions and subagents work on the designated active branch. A session verifies the branch name and HEAD before substantive work, and escalates if the predecessor is not an ancestor. Branches are named `bNN/<short-purpose>`. Old branches keep their names, with B-numbers assigned in documentation only. | START_HERE.md "Repository Continuity"; CLAUDE.md "Repository Continuity"; `docs/BRANCH_TIMELINE.md`; `docs/backup_and_recovery.md` |
| C-2 | **Git is the durable project memory.** Conversations, model memory, scratchpads, recaps, and session state are never sufficient governance. Material decisions, requirements, threshold hypotheses, phase changes, safety rules, gate requirements, and unresolved mandatory decisions must be in Git before sessions rely on them. A cold-start reading order is defined. | START_HERE.md "Repository Continuity"; CLAUDE.md; PROJECT_BRIEF.md §16 |
| C-3 | **Canonical phase roadmap.** Phases 0, 1, 2, 3, 4, 4.5, 5, 5.5, 6, 7, 8, 9, 10, 11, 12, with the owner's titles and scopes. The detailed phase sections keep every stricter requirement already in force. Phase headings were renamed to the owner's titles. No gate requirement was removed. | START_HERE.md "Phase Roadmap" and phase headings |
| C-4 | **Tax and after-tax economics.** No fixed tax classification is assumed. Reports show pre-tax EV, the tax scenarios, and after-tax EV side by side. A pre-tax result is never presented as deployable on its own. Tax assumptions are frozen for protected evaluation, or reported as sensitivity scenarios. Before real-money scaling, authoritative verification and, where appropriate, qualified advice are required. | PROJECT_BRIEF.md §5 and §15; START_HERE.md Phase 4.5, Phase 5 Audit Scope, Phase 6 freeze, Phase 12, Required User Governance Inputs; CLAUDE.md Economics |
| C-5 | **Strategy objective, re-stated.** A late-window, high-confidence strategy. Sweet spot about $0.93–$0.97; candidate-generation floor about $0.85; price never triggers a trade. Entry requires calibrated P(win) above the executable break-even plus a margin, computed from the actual entry price and payout, never an assumed $1. The trade distribution is never imposed. Results are stratified by price band and time band, with tail calibration a core criterion. All thresholds are development hypotheses. | PROJECT_BRIEF.md §3 (canonical); START_HERE.md "Strategy at a Glance"; CLAUDE.md Strategy Scope and Economics; `docs/phase2.md` "Strategy evaluation strata" |
| C-6 | **Batch 4 rulings re-confirmed.** The charter restates B4S-1 and B4S-8 (confirmed), E-B4-1, E-B4-3, E-B4-4, E-B4-6, E-B4-8, E-B4-9(a) (approved, some modified), E-B4-5 (approved as an analysis requirement), E-B4-7 (original rejected, reconstruction principle adopted), E-B4-2 and E-B4-9(b) (deferred, mandatory before `T0`), and the four review tightenings. Each was checked against `docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md` ("Owner rulings on the batch 4 reviews") and found correctly recorded. | Batch 4 record; START_HERE.md pre-T0 checklist (P-1..P-4) |
| C-7 | **One branch, one pull request.** This recovery run produces exactly one numbered branch (B06) and one pull request into `main`. Claude does not merge. | This record; `docs/BRANCH_TIMELINE.md` |

## Stale contradictions

- **Agent files (`.claude/agents/`, six files).** These still use the literal "oldest ~70% / newest ~30%" wording. The sandbox mounts them read-only, so this session cannot write them, and it did not try to bypass that. The CLAUDE.md and START_HERE.md definition governs how they are read. An owner-applicable patch, verified on 2026-10-16 to apply cleanly to B06 and to leave no stale term, is in `docs/owner_actions/`.
- **HOLDOUT_ACCESS_LOG.md Holdout Rules.** These are hash-pinned (HAL-0005) and were not changed. CLAUDE.md "Holdout Protection" and START_HERE.md "Evaluation Cycles" state that the current prospective-holdout semantics govern how that historical restatement is read.
- **`.claude/settings.json` (F-09).** The file is read-only in the sandbox. An owner-applicable patch, based on Claude Code permission semantics verified on 2026-10-16, is in `docs/owner_actions/`. It still applies cleanly to B06 and yields valid JSON.
- **START_HERE.md and PROJECT_BRIEF.md.** The remaining "development 70%", "final 30%", and "Final Protected 30% Evaluation" wording was replaced with "development pool", "protected evaluation set", and "Protected Evaluation". The ~70/30 design-target sentences, which are correct, were kept.
- **`docs/backup_and_recovery.md`.** The isolated workflow said "create a task branch from the current verified `main`", which conflicts with C-1. It now names the active ground-truth branch.

## Not changed

- No requirement in the holdout, protected-information, acquisition, risk, or real-capital rules was relaxed.
- No gate status changed. Gate 0 passed; Gate 1 has not been decided. No cycle, `T0`, split, or protected scope exists.
- No real market observation was accessed, and no live, market-data, or trading host was contacted.

## B06 continuation (2026-10-16, after context exhaustion)

The owner issued a continuation charter after the session that wrote the commits above ran out of context. It directs work to stay on B06 (no new branch) and in one pull request, and authorizes:
- recovery from Git;
- completing the acquisition-tooling Red-Team remediation;
- auditing the full source-neutral Phase 1 acquisition-readiness scope, implementing what is safe without real data, and recording governed deferrals for the rest. This includes the owner-controlled per-row release tool "where implementation is permitted before cycle/T0 registration";
- a fresh cold-start review, with fixes for genuine inconsistencies;
- owner-applicable patches for sandbox-read-only files.

It authorizes no real data, live or trading hosts, credentials, purchases, `T0`, holdout access, model development, or merge.

Recovery finding: the tracked tree was clean at `f9c5262`, matching `origin`, and every interrupted-session edit was already committed (`acc8e2b`).

Work done:
- RT-B6-19 to RT-B6-22 fixed;
- a durable receipt journal added (RT-B6-12);
- the release-tool design and deferral (`docs/release_tool_design.md`), with Statistician review;
- Red-Team round 4;
- cold-start review fixes.

The release tool's code is deferred under RT-B3-05/H-2 until the owner decides E-U1. No requirement was relaxed, and no gate status changed.
