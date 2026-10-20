# Branch Timeline

This file numbers the project's development branches in verified Git ancestry order and names the **current active ground-truth branch**. The rule that governs it is in START_HERE.md "Repository Continuity" (owner direction, 2026-10-16; record `docs/decisions/2026-10-16_b06_governance_continuity_sync.md`). CLAUDE.md "Repository Continuity" carries the invariant.

Old branches keep their original names. Their B-numbers are assigned here only; renaming them requires separate owner authorization.

## CURRENT ACTIVE GROUND-TRUTH BRANCH

**`b12/btc-kalshi-pilot` (B12)**

- **Designation:**
  - the owner's direction of 2026-10-20, "OWNER DECISION — APPROVE PMV 2.0 WITH REVIEW MODIFICATIONS / BEGIN B12 STRATEGY AMENDMENT + REVISED BTC FEASIBILITY PILOT", which directed "Reuse this branch" (PV-1);
  - the owner's pre-commit review of 2026-10-20, which said: "APPROVE B12 AS THE ACTIVE NUMBERED BRANCH".
  - Record: `docs/decisions/2026-10-20_b12_pmv2_strategy_pivot.md`.
- **Parent:** B11 `b11/btc-poc-owner-decisions`, at its final commit `c986f49227a47b855a547db96e65356f3674a9b8`. B12 was branched directly from that commit on 2026-10-19, not from the `main` merge commit `92e46c1` (PR #11).
- **Purpose:**
  - the PMV 2.0 strategy and governance amendment (PV-1 to PV-23);
  - the revised BTC Kalshi historical feasibility pilot: protocol P1–P16, old-strategy control C1–C3, and stop conditions S-1 to S-6, with offline tooling on synthetic data.
  - No Kalshi rows fetched, no Kraken acquisition, no capture, no cloud, no paid resources, no `T0`.
- **Head:** the pushed tip of `origin/b12/btc-kalshi-pilot`, once pushed. Verify with `git ls-remote origin refs/heads/b12/btc-kalshi-pilot`.
- **Integration:** one pull request into `main` when the owner directs. Merging is the owner's decision, with a normal merge commit, and B12 is not deleted afterwards.
- **Status:**
  - PMV 2.0 is the primary research direction, and the settlement strategy is a nested arm.
  - The pilot is blocked on AR-B12-1 (Kalshi host route), AR-B12-2 (terms copies), the guard-exception confirmation, and DR-9 (fee schedule).
  - Owner items: O-PV-1 and O-PV-4 are open; O-PV-2 is partly resolved; O-PV-3 is resolved (324 as an absolute maximum).
  - Until the owner designates a successor, every new development branch (B13) starts from this branch's final tip.

## Timeline

| ID | Branch | Parent ID | Head commit | Status | Purpose |
|---|---|---|---|---|---|
| B00 | `main` | — | baseline `a07fc29` (Gate 0 PASS at `db09acd`); `main` is now at `92e46c1` (B11 merged, PR #11) | Integration branch. Advances only by merged pull request. | Canonical historical baseline: Phase 0 foundation, Gate 0, backup and recovery |
| B01 | `docs/activate-isolated-autonomy` (remote only) | B00 | `0dd40ca` | Historical checkpoint. Merged by PR #1 (`4eec20c`) | Activation of the isolated autonomous environment |
| B02 | `phase1/kalshi-data-foundation` | B01 (branched at `4eec20c`) | `899dae6` | Historical checkpoint. Merged by PR #2 (`856083e`) | Phase 1 batch 1: venue-neutral market-data foundation |
| B03 | `phase1/kalshi-venue-verification` | B02 (branched at `856083e`) | `4ca18e0` | Historical checkpoint. Merged by PR #3 (`c074e9b`) | Phase 1 batch 2: Kalshi venue verification (documentation) |
| B04 | `phase1/historical-data-strategy` | B03 (branched at `c074e9b`) | `012afa0` | Historical checkpoint. Merged by PR #4 (`ad169a2`) | Phase 1 batch 3: historical data strategy |
| B05 | `phase1/acquisition-safety-decisions` | B04 (branched at `ad169a2`) | `a1752b4` | Historical checkpoint. Pushed; no PR; not merged. Wholly contained in B06 and integrated through B06's pull request | Phase 1 batch 4: owner decisions on acquisition safety and holdout formation |
| B06 | `b06/governance-continuity-sync` | B05 (branched at `a1752b4`) | `c0d2a2b` (final) | Historical checkpoint, preserved. Merged by PR #5 (`2314326`) | Recovery of the interrupted batch 4 follow-up; owner rulings; strategy objective; phase roadmap; tax requirement; branch continuity; Phase 1 acquisition-readiness tooling |
| B07 | `b07/phase1-acquisition-pipeline-hardening` | B06 (branched at final `c0d2a2b`) | `9a6b212` (final) | Historical checkpoint, preserved. Merged by PR #6 (`2a46ffd`) | Phase 1 acquisition pipeline hardening (G-1 to G-6), synthetic data only |
| B08 | `b08/prospective-capture-hardening` | B07 (branched at final `9a6b212`) | `5806d8c` (final) | Historical checkpoint, preserved. Merged by PR #7 (`a6b5411`) | Phase 1 prospective-capture hardening (F-11, F-12/F-27, F-33, F-37/RT-4, book continuity, normalized artifacts), synthetic data only |
| B09 | `b09/kalshi-source-qualification` | B08 (branched at final `5806d8c`) | `8b4e026` (final) | Historical checkpoint, preserved. Merged by PR #8 (`bbcdd6b`) | Kalshi official historical source qualification and the A-1 to A-6 owner-decision packet; cloud-native data strategy, source inventory, procurement packet; documentation only |
| B10 | `b10/source-reconnaissance` | B09 (branched at final `8b4e026`) | `c028882` (final) | Historical checkpoint, preserved. Merged by PR #9 (`4019a75`) | Data-source reconnaissance: schema profiles, value matrix, source verdicts, minimum viable source set |
| B11 | `b11/btc-poc-owner-decisions` | B10 (branched at final `c028882`) | `c986f49` (final) | Historical checkpoint, preserved. Merged by PR #11 (`92e46c1`) | Owner data-readiness decisions DR-1 to DR-23: BTC active POC, gold shelved for now, market-family model policy, proxy-security compliance, exposure rows X-12 to X-14, Kraken correction, P-5, transcript-purge owner action. Governance only; no cloud provisioning |

| B12 | `b12/btc-kalshi-pilot` | B11 (branched at final `c986f49`) | Last recorded: see "B12 commits"; tip = latest pushed commit | **CURRENT ACTIVE GROUND-TRUTH BRANCH** | PMV 2.0 strategy amendment (owner decisions PV-1 to PV-23); revised BTC Kalshi historical feasibility pilot (P1–P16, C1–C3, S-1 to S-6) with offline tooling; no observations fetched |

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
| `1aa6c52` | Post-B07 status correction (PR #6, final B07 `9a6b212`), the B08 charter record, and B08 designation |
| `222a7e7` | Prospective-capture hardening: F-11, F-12/F-27, F-33, F-37/RT-4, book continuity, normalized artifacts (Red-Team round 1 subject) |
| `7190f7f` | Red-Team round 1 remediation (RT-B8-01 to RT-B8-10) and the Statistician review |
| `6dc2b51` | Round 2 follow-ups (RT-B8-12 to RT-B8-14) and B08 status docs (Red-Team round 3: no BLOCKING and no MAJOR finding) |
| `d52b46a` | Red-Team round 3 verdict recorded, residual rows, and timeline update |
| `43c4283` | Cold-start review and its documentation fixes, plus the `check.sh` result (state presented for the owner's review of B8-1 to B8-7) |
| `b3e8269` | Owner decisions on B8-1 to B8-7. Modified B8-2: per-frame environment identity, frame format v3 |
| `c2eca25` | Red-Team re-review of the B8-2 change recorded, and RT-B8-15 closed. **Final reviewed capture code** |
| `6fad8bd` | RT-B8-15 verification recorded, the `check.sh` result after B8-2 (2322 passed, 8 skipped), and timeline update |
| `5806d8c` | Cold-start refresh after the owner's B8 decisions and its documentation fixes (R-1 to R-4). **Final B08 commit**, merged by PR #7 (`a6b5411`) |

### B09 commits

Listed oldest first, and appended at each timeline update.

| Commit | Content |
|---|---|
| `703fd7f` | B09 charter record, source-qualification analysis, owner-decision packet, and status updates (the Red-Team review subject) |
| `f78d7e2` | Red-Team review recorded (no BLOCKING; MAJOR RT-B9-01 and RT-B9-02), its fixes in the documents, D-B09-9 added |
| `5b0106e` | Owner cloud-native direction (2026-10-18): master data-source inventory, cloud architecture review and cost model, advisory reviews with dispositions, exposure rows X-4 to X-6, decision record with D-B09-10 to D-B09-22. Documentation only |
| `2373174` | Owner consolidation direction: architecture consolidation, inventory completed (one row per source), Stage A/B wording, round 3 focused re-reviews (no BLOCKING) and their fixes. Documentation only |
| `b5b3bfb` | Canonical architecture rebuilt from scratch and replaced atomically; inventory checked complete; round 4 Red-Team re-review (RESOLVED) and its fixes. Documentation only |
| `a9a24a5` | Owner procurement packet: `research/data_sources/owner_source_action_sheet.md` (core matrix, prices, contacts, tiers, datasets, messages). Documentation only; nothing bought or downloaded |
| `9e6e34b` | Documentation sync of procurement conclusions with owner-verified facts; final tiers; outreach queue M1 to M5. Documentation only |
| `8b4e026` | Owner action sheet rebuilt from scratch as one canonical file (one row per source; canonical outreach numbering); pointers synced. Documentation only. Final B09 commit |

### B10 commits

Listed oldest first, and appended at each timeline update.

| Commit | Content |
|---|---|
| `05df35a` | B10 reconnaissance: charter record, connectivity pass, 19 schema profiles, value matrix, source verdicts, minimum viable source set, recon tools, exposure rows X-7 to X-11, reviews |
| `ba1fa9e` | Owner decisions B10-D1 to B10-D11 recorded; stale B09 Kraken/BRTI rows corrected; live-host egress refusal test; owner procedure for the egress-layer removal and proxy rotation (pending); round 2 re-reviews |
| `c028882` | Owner correction of the runtime-secret record: B10-D6 resolved by control hardening; B10-D10 removal timing moved to before `T0 − m`; permanent diagnostic rule (`docs/conventions.md`) with a static guard test; egress test credential hardening; owner Layer B probe no longer reads proxy variables; round 3 focused review. Final B10 commit |

### B11 commits

Listed oldest first, and appended at each timeline update.

| Commit | Content |
|---|---|
| (the commit adding this row) | Owner data-readiness decisions DR-1 to DR-23 recorded; BTC active POC and gold shelved for now (PROJECT_BRIEF, START_HERE, CLAUDE.md); market-family model policy; DR-10/DR-16 proxy-security compliance (egress test, WS and REST recon tools, static guard); exposure rows X-12 to X-14; Kraken timestamp correction; P-5; DR-22 owner action. Its hash is the branch tip; see `git ls-remote` |

### B12 commits

Listed oldest first, and appended at each timeline update.

| Commit | Content |
|---|---|
| `f70c45dc6e22473767a4d09e31415cc0f0fd0f91` | Preserve the pre-pivot Kalshi pilot state as delivered on 2026-10-19 (fetch tool, profiler, tests, P1–P9 protocol) |
| `242a2f831cb8a3202bb8f74cb19bf4b9fd591ab5` | Adopt the PMV 2.0 strategy and governance amendments (owner decisions PV-1 to PV-23 and the pre-commit review) |
| `cfe42a807e089c6c24a6cf70959e37e98949e13e` | Revise the BTC pilot for PMV 2.0 feasibility (P10–P16a, C1, stop screen, timestamp resolution, labelled fee scenarios) |
| (the commit adding these rows) | Mark the PMV 2.0 feasibility work active (`docs/phase1.md`, this timeline). Its hash is the branch tip; see `git log` or, once pushed, `git ls-remote` |

## Ancestry verification for B12 (2026-10-19 and 2026-10-20)

- **2026-10-19, at creation** (`research/kalshi/b12_btc_kalshi_pilot.md` §1):
  - on `b11/btc-poc-owner-decisions`, `git rev-parse HEAD` returned `c986f49227a47b855a547db96e65356f3674a9b8`;
  - `git ls-remote origin refs/heads/b11/*` returned the same hash, and no `b12/*` branch existed on `origin`;
  - B12 was created with `git switch -c b12/btc-kalshi-pilot`, and `git merge-base --is-ancestor c986f49 HEAD` returned 0.
- **2026-10-20, re-verified before the PMV 2.0 work:**
  - `git rev-parse HEAD` returned `c986f49227a47b855a547db96e65356f3674a9b8` on `b12/btc-kalshi-pilot`;
  - `git merge-base --is-ancestor c986f49227a47b855a547db96e65356f3674a9b8 HEAD` returned 0;
  - `git ls-remote origin 'refs/heads/b12/*'` returned nothing;
  - `origin/main` was `92e46c1`, a merge (PR #11) that contains `c986f49`.

## Ancestry verification for B11 (2026-10-19)

Verified when B11 was created, in the isolated sandbox:
- `git ls-remote origin refs/heads/b10/source-reconnaissance` was `c0288820748e21f606f7dd258c95d7711b69e15a`; `origin/main` was `4019a75`, a merge commit (PR #9) whose second parent is `c028882`;
- no `b11/*` branch existed on `origin`;
- B11 was created with `git switch -c b11/btc-poc-owner-decisions` at HEAD `c028882` (the final B10 tip); `git rev-parse HEAD` returned `c0288820748e21f606f7dd258c95d7711b69e15a`, and `git merge-base --is-ancestor c028882 HEAD` returned 0.

## Ancestry verification for B10 (2026-10-19)

Verified before B10 was created, in the isolated sandbox, after `git fetch origin` (`origin/main` advanced `a6b5411..bbcdd6b`):
- `git cat-file -t 8b4e026` returned `commit`, and `git merge-base --is-ancestor 8b4e026 origin/main` returned 0 (B09 is in `main` through `bbcdd6b`, PR #8);
- `origin/b09/kalshi-source-qualification` was at `8b4e0261fad30f978fac19c6d81d11b7334d0c97`;
- no `b10/*` branch existed on `origin`;
- B10 was created with `git switch --detach 8b4e026` then `git switch -c b10/source-reconnaissance`; `git rev-parse HEAD` returned `8b4e026…`, and `git merge-base --is-ancestor 8b4e026 HEAD` returned 0.

## Ancestry verification for B09 (2026-10-16)

Verified before B09 was created, in the isolated sandbox, after `git fetch origin`:
- the local `b08/prospective-capture-hardening` and `origin/b08/prospective-capture-hardening` were both at `5806d8c83afc6c1788db438394c7a0b978b16350`;
- `git merge-base --is-ancestor 9a6b212 5806d8c` returned 0 (B07 → B08), and `origin/main` was at merge commit `a6b5411` (PR #7);
- no `b09/*` branch existed locally or on `origin`;
- B09 was created from final B08 with `git switch -c`, and `git merge-base --is-ancestor 5806d8c HEAD` returned 0;
- B09 was pushed with an explicit `git push origin b09/kalshi-source-qualification` before the first B09 commit.

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
