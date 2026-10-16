# B06 Cold-Start Reconstruction Review (2026-10-16)

**Reviewer:** fresh-context cold-start reviewer (development subagent). This is a review record, not an owner decision or a gate record.

**Method:** read-only inspection of `/workspace` only (committed files plus the uncommitted B06 working tree), in the START_HERE.md "Repository Continuity" cold-start order. No network. Nothing under `~/pmv-protected` or any credential path was read. `./scripts/check.sh` and the test suites were not run.

**Git state seen:** branch `b06/governance-continuity-sync`, `HEAD` = `origin/b06/governance-continuity-sync` = `f9c5262`; `main` = `origin/main` = `ad169a2`; `a1752b4` is an ancestor of `HEAD`. Every head and merge commit in `docs/BRANCH_TIMELINE.md` (B00–B05) matches the local `origin/*` refs and the PR merge subjects. The working tree is **dirty**. Uncommitted edits: `docs/acquisition_readiness.md`, `docs/phase1.md`, `src/pmv/acquisition/{__init__,archive,quarantine}.py`, and two test files. Untracked files: `docs/release_tool_design.md`, `src/pmv/acquisition/receipts.py`, `tests/unit/test_acquisition_receipts.py`. The "B06 continuation" is therefore not yet in Git.

## 1. Fourteen reconstruction items

| # | Item | Rating | Evidence |
|---|---|---|---|
| 1 | Project objective | CLEAR | PROJECT_BRIEF.md:9 (mission), :72-76 (small, repeatable, positive-EV edge), :82-84 (P(win \| info at decision time)), :378-390 (success criterion); CLAUDE.md:1-3, :104-112 |
| 2 | Late-window strategy | CLEAR | PROJECT_BRIEF.md:56-70 (canonical); START_HERE.md:25-33; CLAUDE.md:99; owner records: batch 4 decision record :184-186, B06 C-5 (`docs/decisions/2026-10-16_b06_governance_continuity_sync.md`:32) |
| 3 | Price vs. edge (price bands never sufficient; payout-aware executable cost-adjusted break-even) | CLEAR | PROJECT_BRIEF.md:63-66 (`calibrated P(win) > executable break-even + margin`; no assumed $1 payout), :69 (tail calibration); CLAUDE.md:100, :130; START_HERE.md:30 |
| 4 | Assets, venues, horizons, current scope order | CLEAR (with stated open facts) | PROJECT_BRIEF.md:9, :43; `docs/phase1.md`:38-45 (Kalshi first, Polymarket deferred, BTC and gold, 15-minute first); START_HERE.md:34 (scope order; gold-contract existence unverified, F-16 and E-1); batch 2 D2 (`docs/decisions/2026-10-16_phase1_batch2_owner_decisions.md`:21-25); batch 3 P4 and P5 (`docs/phase1.md`:143-144) |
| 5 | Runtime LLM independence | CLEAR | PROJECT_BRIEF.md:13-37, :357-374; CLAUDE.md:65-89, :470-476; START_HERE.md:1-21 |
| 6 | Phase 0–12 roadmap, including 4.5 and 5.5 | CLEAR (one stale title reference; inconsistency 8) | START_HERE.md:70-90 (table), phase headings :186, :216, :283, :342, :378, :409, :466, :702, :789, :852, :920, :971, :998, :1065, :1101; PROJECT_BRIEF.md:396; CLAUDE.md:432; B06 C-3 |
| 7 | Protected-holdout rules (prospective H-1, `T0`, `m`, 70/30 semantics) | CLEAR (agent files still stale but explicitly overridden; inconsistency 10) | CLAUDE.md:171-210 (esp. :176-177, :182); PROJECT_BRIEF.md:172-196; START_HERE.md:118, :124-131, :310-318; batch 4 H-1 (decision record :13-30) |
| 8 | Acquisition and research restrictions (host-class rule, gate A-1..A-8) | CLEAR (one looser wording in the decision record; inconsistency 9) | CLAUDE.md:155-169; `docs/external_access.md`:13-35 (classes and rules), :81-90 (A-1..A-8), :98-121 (embargo); batch 4 O-3, O-5, O-6, O-9, H-7 |
| 9 | Approved owner decisions (batch 2, 3, 4; B06 C-1..C-7) | CLEAR (one precedence ambiguity; inconsistency 12) | Batch 2 D1–D3 (`…batch2_owner_decisions.md`:13-38); batch 3 P1–P6 (`docs/phase1.md`:139-145; batch 3 record); batch 4 H-1..H-8, O-3, O-5, O-6, O-9 and the rulings table (`…batch4_acquisition_safety_decisions.md`:13-110, :146-169); B06 C-1..C-7 (`…b06_governance_continuity_sync.md`:26-34) |
| 10 | Unresolved pre-T0 decisions P-1..P-4 | CLEAR | START_HERE.md:132-136; batch 4 decision record :171-182; `docs/release_tool_design.md`:11-12 (P-3 dependency) |
| 11 | Tax and after-tax EV requirement | CLEAR | PROJECT_BRIEF.md:122-129, :384; CLAUDE.md:132; START_HERE.md:81, :454-460, :638, :803, :1110, :1150-1151; B06 C-4 |
| 12 | Current active branch and continuity rule | CLEAR (self-designation wording and dirty-tree caveat; inconsistencies 2 and 13) | `docs/BRANCH_TIMELINE.md`:7-13, :25; START_HERE.md:40-66; CLAUDE.md:428-438; PROJECT_BRIEF.md:398; `git rev-parse HEAD` = `origin/b06/…` = `f9c5262` |
| 13 | Current phase and gate status | CLEAR in canonical docs (two stale Phase 0 docs; inconsistency 3) | START_HERE.md:76-77; `docs/phase1.md`:7-9; B06 record :47; Gate 0 PASS record `docs/decisions/gates/gate_0_20261014T152514.897404Z_…md`; `docs/BRANCH_TIMELINE.md`:19 |
| 14 | Next permissible action | CLEAR (minor gaps; inconsistencies 1, 14) | `docs/phase1.md`:27-34 (owner: merge the B06 PR, apply the F-09 and agent patches, backup policy A-3, licence terms; agents: close the remaining A-4 gaps without network on synthetic data, then a fresh Red-Team review; release tool waits on E-U1); `docs/acquisition_readiness.md`:43-51; `docs/release_tool_design.md`:42-54 |

## 2. Cross-document inconsistencies

Severity: **MAJOR** means a cold-start session could be misled about what exists or what is approved. **MINOR** means stale wording that a careful reader resolves from canonical text.

1. **MAJOR. The B06 continuation is uncommitted, and the docs describing it claim a review that does not exist.**
   - Location: `docs/acquisition_readiness.md`:38 (working tree).
   - Quoted text: "B06 continuation (2026-10-16): RT-B6-19 to RT-B6-22 were fixed … The round 4 re-verification is in the review file."
   - Why it conflicts: the review file has no round 4. `research/governance/b06_acquisition_tooling_red_team_review.md` is unmodified and ends at "Verdict (round 3)" (:146-149). Line 36 of the same doc also says "Any later change to `src/pmv/acquisition/` needs a fresh review", and the continuation changes `archive.py` and `quarantine.py` and adds `receipts.py` without one.
   - Further exposure: `docs/phase1.md`:25-26 (working tree) and `docs/acquisition_readiness.md`:22, :49 describe `receipts.py` and `docs/release_tool_design.md`. Both are untracked. If the docs are committed without them, or the session ends, Git will claim code and a design doc that do not exist. `docs/BRANCH_TIMELINE.md`:33-38 does not list the continuation (consistent only because it is uncommitted).
   - Fix: before committing, either run and append the round 4 Red-Team re-verification to the review file, or change :38 to "Round 4 re-verification: pending". Commit `receipts.py`, its test, and `docs/release_tool_design.md` together with the doc edits, then append the commit to the B06 commits table.

2. **MINOR. Branch-designation wording is inconsistent.**
   - Location: `docs/BRANCH_TIMELINE.md`:52.
   - Quoted text: "In this file, mark the previous branch 'Historical checkpoint', add the new row, and move the CURRENT ACTIVE GROUND-TRUTH BRANCH section to the new branch. Commit this on the new branch."
   - Why it conflicts: START_HERE.md:60 defines the active branch as the one "the owner has designated, by batch charter or decision record". As written, the procedure lets the creating session designate its own branch with no owner citation.
   - Fix: append "citing the owner's batch charter or decision record that designates it."

3. **MINOR. Phase 0 docs still say no gate has been recorded.**
   - Locations and quoted text:
     - `docs/gate0_readiness.md`:3: "No Gate 0 record exists."
     - `docs/gates.md`:5: "This step provides the tooling only. No gate decision has been recorded."
   - Why it conflicts: Gate 0 PASS is recorded in `docs/decisions/gates/gate_0_20261014T152514…md` (commit `db09acd`; `docs/BRANCH_TIMELINE.md`:19). `docs/phase1.md`:61 still cites `gate0_readiness.md` as a current source of deadlines.
   - Fix: add a dated status line to each doc, for example "Status (2026-10-16): Gate 0 PASS recorded at `docs/decisions/gates/gate_0_…md` (`db09acd`); this text describes the pre-decision state."

4. **MINOR. F-08 is still described as undecided in places.**
   - Locations and quoted text:
     - `docs/protected_information.md`:86: "F-08 must be decided **before agents are shown any real observation**." The same paragraph opens by saying F-08 was adopted as H-2.
     - `docs/protected_information.md`:84: "If the owner adopts F-08 … Until then they stay listed here and unresolved."
     - `docs/market_data.md`:5: "Real observations reach development only … after the F-06 and F-08 decisions."
     - `docs/raw_data.md`:29: "until the release architecture (Step 11 F-08) is decided and built."
   - Why it conflicts: F-08 is decided as H-2 (batch 4 :32-38; `docs/phase1.md`:67). What remains open is building, reviewing, and approving the release tool.
   - Fixes:
     - `docs/protected_information.md`:86: replace the sentence with "The H-2 release tool must be built, reviewed, and approved before agents are shown any real observation."
     - `docs/protected_information.md`:84: prefix "(Historical; F-08 adopted as H-2, see below.)"
     - `docs/market_data.md`:5: replace with "after H-1/H-2 (F-06/F-08, decided) and only through the H-2 per-row release tool, not yet built."
     - `docs/raw_data.md`:29: replace with "until the H-2 per-row release tool (F-08, decided) is built, reviewed, and approved."

5. **MINOR. F-09 status is consistent everywhere checked.** No change needed.
   - `docs/phase1.md`:71, `docs/external_access.md`:61-62, `docs/owner_actions/README.md`:10, and batch 4 :199 all say the policy is decided and the denies are not committed.
   - The only stale claims are in dated or immutable records: `docs/gate0_readiness.md`:98 and the Gate 0 record's `f_09: non_blocking, open`.

6. **MINOR. E-2 and E-4 are still listed as open blockers after the owner decided H-3 and H-5.**
   - Locations and quoted text:
     - `docs/phase1.md`:124: "E-2: the point-in-time versioning decision" (Kalshi parser blocker).
     - `docs/phase1.md`:131: "E-4: an availability rule for historical archive rows".
     - `docs/phase1.md`:257 and :277: "blocked by E-2".
     - `docs/market_data.md`:224-227: "depends on the open identity-design decision".
   - Why it conflicts: `docs/phase1.md`:162 says "H-3 restates E-2. H-5 restates E-4", and batch 4 decided H-3 (Option D) and H-5 (decision record :40-65). A fresh session cannot tell whether the Kalshi spec builder is still blocked by E-2. The remaining blocker may be only the identity design (review m4), which H-3 does not obviously cover.
   - Fix: in the Batch 2 blocker list, annotate "E-2: decided as H-3 (Option D); identity design (market_data.md review m4) still open" and "E-4: decided as H-5". In `docs/market_data.md`:224, state whether m4 is still open after H-3.

7. **MINOR. A Statistician proposal reads as current after the owner adopted it.**
   - Location: `docs/phase1.md`:287-293.
   - Quoted text: "R1: unit of independence. *Current state.* No unit is defined … *Urgency.* Blocking before the first real protected scope or cycle (F-07)."
   - Why it conflicts: H-6 adopted the `outcome_cell_id` / `time_block_id` design (batch 4 :67-72; `docs/phase1.md`:68).
   - Fix: add under the section heading "Status: R1 adopted as batch 4 H-6; R2 is reflected in `docs/phase2.md` Policy 2. Kept as the historical proposal."

8. **MINOR. A stale phase title survives in START_HERE.md.**
   - Location: START_HERE.md:462.
   - Quoted text: "before the Phase 5 Independent Statistical Audit".
   - Why it conflicts: the Phase 5 title is now "Independent Statistical / Economic / Operational Audit" (START_HERE.md:82, :466; B06 C-3).
   - Fix: replace with "before the Phase 5 Independent Statistical / Economic / Operational Audit".
   - No occurrence of the old title "Final Protected 30% Evaluation", or of any other pre-B06 phase title, remains in a current doc. The only hit is the B06 record :41, which describes the rename.

9. **MINOR. The O-6 summary in the batch 4 record is looser than the governing rule.**
   - Location: batch 4 decision record :102.
   - Quoted text: "live market-data API hosts need explicit owner authorization if the batch charter forbids live observations".
   - Why it conflicts: read literally, the record would allow live hosts when a charter is silent. CLAUDE.md:161 ("denied unless an owner-issued batch charter … explicitly authorizes") and `docs/external_access.md`:17 ("If the charter forbids live observations, or is silent, explicit owner authorization is required") are default-deny. The governing docs win, and `docs/external_access.md` already states the stricter reading.
   - Fix: append to :102 "(or is silent; default deny, as stated in CLAUDE.md Host-Class Rule and `docs/external_access.md` §1)".

10. **MINOR, known and expected. The agent files still use the literal oldest-70% / newest-30% wording.**
    - Locations and quoted text:
      - `.claude/agents/statistician.md`:322: "The newest approximately 30% is the protected final holdout."
      - `.claude/agents/data-scientist.md`:253-254.
      - `.claude/agents/ml-engineer.md`:139-140, :150, :152, :208.
      - `.claude/agents/independent-statistical-auditor.md`:124, :135.
      - `.claude/agents/risk-performance-engineer.md`:121, :143, :258.
      - `.claude/agents/reliability-red-team.md`:534.
    - Why it is still worth noting: CLAUDE.md:182 and START_HERE.md:118 override this wording explicitly, so it is not a governing conflict. But fresh agents read these files first.
    - Fix: owner applies `docs/owner_actions/2026-10-16_agents_split_wording.patch` (already pending; `docs/phase1.md`:13).
    - The hash-pinned HOLDOUT_ACCESS_LOG.md:35, :38 text is correctly overridden by CLAUDE.md:182, START_HERE.md:118, and HOLDOUT_ACCESS_LOG.md:9, and is not flagged.
    - The newest-share wording in `research/historical_data/inventory_underlying_btc_gold.md`:242 sits in a dated historical research file that no canonical doc treats as current, and is not flagged.
    - No code under `src/pmv/` contains a 70/30 or newest-share split.

11. **MINOR. A design doc marked "not approved" imposes a prohibition.**
    - Location: `docs/release_tool_design.md`:3.
    - Quoted text: "Status: PROPOSED DESIGN. Not an approved requirement. No code exists, and none may be written until the prerequisites … are met."
    - Why it conflicts: a self-described non-approved document asserts a binding prohibition. The real basis is RT-B3-05 plus H-2 (cited at :10). Also, :9 cites "The B06 recovery charter asked for this tool", but the B06 decision record (:3-9, C-1..C-7) does not mention a release-tool task, so that charter instruction is not recorded in Git (C-2).
    - Fixes:
      - :3: "…none should be written until the prerequisites are met, because RT-B3-05 (adopted under H-2) requires the shared catalog first."
      - Add the release-tool charter item to the B06 record, or remove the attribution at :9.

12. **MINOR. It is unclear which text governs the batch 4 rulings.**
    - Location: batch 4 decision record :3.
    - Quoted text: "Until the B06 pull request is merged, the rulings as restated in the B06 charter govern development on the active branch. The owner confirms the record's final wording by merging."
    - Why it conflicts: the B06 charter text is not in Git; only C-6's summary is. Under C-2 (START_HERE.md:46), unrecorded charter wording cannot govern. C-6 (B06 record :33) says the rulings were checked and "found correctly recorded", so the record should govern.
    - Fix: replace the sentence with "Pending merge, the rulings table below, as verified against the B06 charter in B06 C-6, governs development on the active branch."

13. **MINOR. Whether the B06 pull request exists is not determinable from Git.**
    - Locations and quoted text:
      - B06 record :9: "open exactly one pull request".
      - B06 record C-7 (:34).
      - `docs/BRANCH_TIMELINE.md`:13: "Integration: one pull request into `main`".
      - `docs/phase1.md`:29: "review and merge the B06 pull request".
    - Why it is a gap: no file records whether the PR has been opened, or its number. A fresh session cannot tell whether the next owner action is "open" or "review".
    - Fix: add "PR status: not yet opened (agents have no PR credential); owner opens it" or "PR #N opened on …" to the B06 row of `docs/BRANCH_TIMELINE.md`.

14. **MINOR. The owner next-step list omits decisions that gate agent work.**
    - Location: `docs/phase1.md`:28-32.
    - Why it is a gap: the owner list (1–4) does not mention two things that gate agent work:
      - the E-U1 catalog decision, which `docs/phase1.md`:33 and `docs/release_tool_design.md`:46 make the first prerequisite for the release tool;
      - the preparation of P-1..P-4.
    - Fix: add "5. decide E-U1 (catalog expansion; `research/historical_data/inventory_underlying_btc_gold.md` §5); 6. commission the Statistician/Red-Team P-1..P-4 option papers when ready."

15. **MINOR. Batch labels are only partly B-numbered.**
    - Location: `docs/phase1.md`:104, :137, :235.
    - Why it is a gap: the section headings name batches 2–4 by old branch name without their B-numbers (B03, B04, B05). Batch 1 has one at :92.
    - Fix: add the B-numbers to the headings for consistency with `docs/BRANCH_TIMELINE.md`.

**Checked and found consistent:**
- every B00–B05 head, parent, and PR number in `docs/BRANCH_TIMELINE.md` against `git`;
- every module and test named in `docs/acquisition_readiness.md`, which exists on disk (but see item 1 for tracked status);
- `src/pmv/protected_scope.py` `CATALOG`, keyed by `(Provider, Family)`, matches `docs/release_tool_design.md`:10;
- no document claims Gate 1, A-4, or any later gate has passed: `docs/acquisition_readiness.md`:36, research review :149, and `docs/phase1.md`:21 all say A-4 is not satisfied;
- the P-1..P-4 lists in START_HERE.md and the batch 4 record are identical.

## 3. Verdict

**From committed Git alone (`f9c5262`), a fresh session can reconstruct the project state.** The cold-start order in START_HERE.md:48-56 leads in turn to:
- the active branch and HEAD;
- the late-window strategy and the price-vs-edge rule;
- the full 0–12 roadmap;
- the current phase and gate status (Phase 1 in progress; Gate 0 passed; Gate 1 undecided; no cycle, `T0`, split, or protected scope);
- the approved owner decisions and the open P-1..P-4 checklist;
- the host-class rule and acquisition gate, the tax requirement, and the next permissible actions.

All 14 items rate CLEAR. The canonical documents (PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md, `docs/phase1.md`, the decision records) do not contradict each other on any governing point. Every stale statement found is in a secondary doc, or is explicitly overridden by a canonical definitional clause.

**Condition.** The uncommitted B06 continuation is the one real continuity risk (item 1). Today Git does not contain `receipts.py`, its tests, or `docs/release_tool_design.md`, and the working-tree docs claim a round 4 Red-Team re-verification that is not recorded anywhere. Those files and a corrected review status must be committed together, and appended to the B06 commits table, before the next session relies on them. Items 3, 4, and 6 are the most likely to mislead a careful fresh reader, and should be fixed in the same commit if governance-edit approval allows.
