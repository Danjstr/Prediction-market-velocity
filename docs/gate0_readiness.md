# Gate 0 Readiness Evidence (Phase 0 Steps 10–11)

**This is readiness evidence for the Gate 0 decision. It is not the Gate 0 decision.** No Gate 0 record existed when this file was written. *Status (2026-10-16): Gate 0 PASS was recorded at `db09acd` (`docs/decisions/gates/`). The deferred findings below remain the current deadline list.*

**Roadmap.** Step 10 → Step 11 (a full Reliability/Red-Team-led audit, then the approved corrections and a narrow re-audit) → owner Git-bundle backup and restore test → Gate 0 decision → Step 12 (a private remote holding the full-history backup, a fresh-clone restore test, then the first hosted CI run and its verification) → Phase 1.
- The roadmap and the Gate 0 criterion are defined in START_HERE.md (Phase 0, Gate 0).
- Gate-record rules are in `docs/gates.md`.
- Owner decisions from Step 11 are in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`.
- The Gate 0 record is created only after the corrections, the narrow re-audit, and the bundle restore test. It is made with `python -m pmv.gates create`, with explicit project-owner approval, from a normal terminal with no Claude session open.

This checklist does not restate requirements. Where it summarizes one, the referenced document is authoritative.

Every check is a deterministic, offline command, run from the repository root. `pmv` commands run through the locked environment, for example `uv run --locked python -m pmv.gates verify-history`; the tables shorten this to `python -m …`.

## Phase 0 controls (START_HERE.md, Phase 0 "Create")

| Control | Step | Commit | Verification | Authoritative document |
|---|---|---|---|---|
| Project controls and agent definitions | baseline | `faec572` | `git merge-base --is-ancestor faec572 HEAD` | PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md |
| Repository conventions, dependency management, Python environment, testing framework | 1, 11 | `c131321`, Step 11 | `./scripts/check.sh` (includes `tests/unit/test_repository_layout.py`: no source or control tree is ignored) | `docs/conventions.md` |
| Logging and configuration | 2, 11 | `6f4d657`, Step 11 | `./scripts/check.sh` (`tests/unit/test_config.py`, `test_log.py`) | `docs/conventions.md` |
| Secret handling | 3a, 3b | `22ea934`, `d67c42d` | `scripts/scan_secrets.sh`, which prints `RESULT: CLEAN` | `docs/conventions.md` (Secrets) |
| CI (configured locally; never run hosted) | 4 | `8fe7a7f` | `tests/unit/test_ci_workflow.py`; `./scripts/check.sh` is the CI gate | `.github/workflows/ci.yml` |
| Raw-data storage outside Git, with provenance; real raw data only in `~/pmv-protected/raw` | 5, 11 | `decb987`, Step 11 | `./scripts/check.sh` (`test_raw_*`, `test_config.py`); `python -m pmv.data_access_guard check-config` | `docs/raw_data.md` |
| Automatic experiment tracking | 6, 10, 11 | `cba9606`, `80ef955`, Step 11 | `./scripts/check.sh` (`test_experiment*`) | `docs/experiments.md` |
| Gate-record format and location | 7, 11 | `65ddbb1`, Step 11 | `python -m pmv.gates verify-history` (pins re-derived; replace refs refused). Run files are verified at `create`, not by history verification (RT-2) | `docs/gates.md` |
| Tamper-evident HOLDOUT_ACCESS_LOG.md events (against accidental change; see the threat model) | 8 | `0bdd2d0` | `python -m pmv.holdout_log verify-history` | `docs/holdout_access.md` |
| Protected-information embargo and deterministic data-access controls | 9, 11 | `6b8cda6`, Step 11 | `python -m pmv.protected_scope verify-history`; `python -m pmv.data_access_guard check-config` | `docs/protected_information.md` |
| Physical isolation of production credentials | owner decision (F-03) | Step 11 | No credential exists. `~/pmv-credentials/` is denied to agents, and `check-config` verifies that. Isolation must be in place before **any** venue credential exists | `docs/protected_information.md` (Credentials) |
| Reproducibility conventions | 10 | `80ef955` | `python -m pmv.reproducibility verify` | `docs/reproducibility.md` |

## Invariants to confirm

| Check | Command | Expected |
|---|---|---|
| Expected commits present | `for c in faec572 c131321 6f4d657 22ea934 d67c42d 8fe7a7f decb987 cba9606 65ddbb1 0bdd2d0 6b8cda6 80ef955; do git merge-base --is-ancestor $c HEAD \|\| echo missing $c; done` | No output |
| Clean tree | `git status --porcelain`, run in a normal terminal | No entries. Inside a Claude Code sandbox, masked paths can appear as untracked placeholders (`.bashrc`, `.gitconfig`, `.mcp.json`, `.claude/settings.local.json`, `secrets`, and others): either non-regular `/dev/null` devices or zero-byte regular files, depending on the session. On 2026-10-14 the owner confirmed from a normal terminal that those five paths did not exist on disk. The sandbox has left at least one real zero-byte file, `.git/config.worktree`; check `.git/config.lock` and `.git/config.worktree` before Step 12. |
| Full local quality gate | `./scripts/check.sh` | Exit 0 |
| Secret scan | `scripts/scan_secrets.sh` | `RESULT: CLEAN` |
| Gate history | `python -m pmv.gates verify-history` | `gate history verified: 0 record(s)` |
| No gate records yet | `ls docs/decisions/gates 2>/dev/null \| wc -l` | `0` |
| No Git replace refs | `git for-each-ref refs/replace` | No output |
| Holdout history | `python -m pmv.holdout_log verify-history` | `holdout log: 1 event(s), last HAL-0005` and `history verified` |
| Protected registry empty | `python -m pmv.protected_scope verify-history` | `0 scope(s), 0 active, 0 committed` |
| Protected-information settings | `python -m pmv.data_access_guard check-config` | `protected-information settings verified`. Covers `~/pmv-protected` and `~/pmv-credentials` denies, committed configs, and the local settings file. A zero-byte masked `settings.local.json` is accepted (F-22). |
| No real holdout observations | Registry empty (above); no raw store or experiment root is configured (`[raw_storage]` and `[experiments]` are unset in `configs/`); the guard refuses every real request | Confirmed by the commands above |
| No live credentials | `scripts/scan_secrets.sh`; no `.env*` file is tracked (`git ls-files \| grep -c '\.env'` prints `0`; the committed template is `env.example`); `~/pmv-credentials/` is not created | Clean |
| Reproducibility | `python -m pmv.reproducibility verify`, then `python -m pmv.reproducibility fingerprint` twice | Exit 0, and the same fingerprint both times |
| Git bundle backup (F-04) | Owner, from a normal terminal: create a full bundle of the corrected HEAD and restore-test it in a separate temporary directory | Bundle verifies; clone from it passes `git fsck --full` and all three `verify-history` commands |

## Step 11 corrections applied

| Finding | Correction |
|---|---|
| F-01 | Real raw data must live in `~/pmv-protected/raw`, enforced by `load_config` for non-test environments and by `check-config` |
| F-02 | `.gitignore` patterns `/data/` and `/logs/` are anchored; a test prevents any source or control tree being ignored |
| F-03 | Owner credential decision recorded; `~/pmv-credentials/` denies added and checked |
| F-04 | Owner backup policy recorded; the bundle step is pending, as the owner's own step |
| F-05 | Threat model made explicit; "tamper-evident" qualified; stale and overstated claims corrected |
| F-13 (M-5) | Gate tooling verifies every referenced run's files, and those of its input producers, with `verify_run` |
| M-4 | Closed with no format change; verification is a tested control-flow precondition |
| F-18 | Documentation: Gate 7 is the final result; the tooling's use of a Gate 7 PASS as plan sign-off is a recorded mismatch to fix before Phase 7 |
| F-20 | Replace refs, grafts, or a shallow history make code identity unknown; gate history refuses replace refs |
| F-21 | Gate history re-derives clean-tree governance and config pins from the recorded commit |
| F-22 | An exactly zero-byte `settings.local.json` mask counts as no override |
| F-42 | "Every gate requires owner approval" kept; its procedural limitation documented |
| RT-1 (F-20) | Raw-capture provenance (`raw_storage._git_identity`) also ignores replace objects and reports an unknown identity under replace refs, grafts, or a shallow history |
| RT-3 | The protected locations come from the account's password-database home, never `HOME`; an unknown home refuses every real raw root and every guarded path |
| RT-5 | Remaining `.gitignore` directory and data-extension patterns anchored to the repository root |
| RT-8 (FIFO) | Settings files are opened non-blocking and must be regular files, so a FIFO fails closed instead of hanging `check-config` |
| RT-6, RT-7 | F-18 wording residue corrected (except the byte-verified `HOLDOUT_ACCESS_LOG.md` render); duplicate F-21 identifier renamed F-21b |

## Explicitly pending, and not Gate 0 blockers

- **Hosted CI.** CI is configured locally, and hosted CI has never run. **Hosted CI has not yet run. This is intentionally deferred to Phase 0 Step 12 and is a mandatory prerequisite to Phase 1, not a prerequisite to the Gate 0 decision.** Step 12 creates the private remote, pushes the full history, verifies it remotely, performs a fresh-clone restore test, runs the first hosted CI, and verifies its result. That includes the GitHub runner's user-namespace behavior for the secret scan, which has not been verified.
- **The private remote** is a backup and a second witness of history. It is **not** notarization or an immutable anchor.

## Deferred findings and deadlines

These are recorded, **not** resolved. Each must be done before the event named.

**Phase 1 entry decisions** (the first agenda items at Phase 1 start; Phase 1 starts only after Step 12):

| Finding | Must be resolved before |
|---|---|
| F-16 venue and jurisdiction eligibility (and gold-contract existence) | Any venue account or credential is created, or any real venue collection or trading integration is used |
| F-06 prospective holdout formation | Agents are shown any real observation |
| F-08 release architecture (trusted collector plus release by receipt time) | Agents are shown any real observation |
| F-07 power-based holdout size and unit of independence | The first real protected scope or cycle is registered |
| F-17 minimum economic thresholds and kill criteria | Substantive strategy or model development on real data, and certainly before paper or live trading |

**Other deferred findings:**

| Deadline | Findings |
|---|---|
| Before Step 12 | Pre-flight from a normal terminal (`.git/config.lock`, `.git/config.worktree`, `git fsck`, replace refs, grafts, scan); F-23 binary-file secret scanning and `.env*` ignores; F-24 CI-neutering test; F-25 build-backend (hatchling) pin; F-28 rule for tracked changes after Gate 0 |
| Before any venue credential exists | F-03 deadline (above); RT-8 broader local-settings permission hardening (`additionalDirectories`, `defaultMode`, broad `Read` globs, and other allow rules that do not name the protected locations) |
| Before Phase 1 real collection | F-03 credential implementation; F-09 network and WebFetch denies for market-data hosts; F-11 capture segmentation and salvage; F-12 frame v2 timing and direction (with F-27); F-26 storage-event claims and restore dependency; F-32 collector host and alert recipient; F-33 durability-ordering tests; F-37 demo data treated as real; RT-4 collector and gate commands refuse the test environment (with F-37); F-21b per-gate scope and minimum-reviewer table (follow-up to F-21); raw-data backup policy and smoke test |
| Before agents are shown real observations | F-06, F-08 (above); F-15 loader-to-run binding; F-24 skip accounting; F-30 telemetry and real-data fixtures; Step 9 S-2, S-4, S-6 per F-08 |
| Before the first real protected scope | F-07 (above); F-10 time-only immutable scopes, embargo open until reveal, scope hash bound to `cycle_registered`; S-1 external anchor; F-14 owner signatures (or before the first Gate 6 authorization); F-29 pilot placement; F-09 materiality rule |
| Before real experiment evidence | F-19 single evidence launcher (Step 10 M-1 cached bytecode, M-2 working-directory shadowing, environment variables, entrypoint); F-15 `cycle_id`, fold manifest, and out-of-sample vectors; F-31 target and labels; experiment-store backup policy |
| Before a gate can rely on experiment evidence | F-13 is done; also F-19 above, plus a committed checkpoint and `verify-evidence` (F-13 follow-ups); RT-2 explicit design decision on whether history verification re-verifies referenced experiment artifacts |
| Before the Phase 7 reveal | F-18 Gate 7 tooling (separate plan approval from the result; reveal runner calling `assert_started_committed`); cross-cycle α control; F-35 encryption at rest at the latest; S-1 anchor for `access_started` |
| Before Phase 4.5, Phase 8, and live trading | F-39 sizing and monitoring; re-verify venue terms; separate trading-credential environment |
| Later / non-blocking | F-34 duplicated helpers; F-36 launcher exclusion; F-38 cycle abandonment; F-41 audit process; Python patch-version pin |

The complete audit, with every finding's evidence, is the Step 11 synthesis kept outside the repository. Step 9's own deferred register is in `docs/protected_information.md` ("Phase 0 status").

## Known boundaries carried into Gate 0

- **Fingerprint boundary.** The environment fingerprint does not cover the standard library, system libraries, kernel, CPU, or timezone data (`docs/reproducibility.md`). Re-hashing every installed file takes about 0.8 s for `fingerprint` and about 2.5 s for `verify`.
- **Not yet authorized for real use.** No real v2 `evidence_candidate` may count as evidence, and no gate may rely on one, until F-19 is resolved.
- **Silent demotion remains for dirty trees.** An `evidence_candidate` with a dirty tree is still demoted to exploratory under the Step 6 dirty-tree policy; only a reproducibility-verification failure refuses the start.
- **Procedural owner approval.** Owner approval is recorded procedurally, not cryptographically (F-42, F-14).
