# Gate 0 Readiness Evidence (Phase 0 Step 10)

**This is readiness evidence for Step 11. It is not the Gate 0 decision.**

**Roadmap:** Step 10 → Step 11 (a full Reliability/Red-Team-led audit of every Phase 0 requirement and its implementation) → approved Step 11 corrections → Gate 0 decision → Step 12 (a private remote holding the full-history backup, then the first hosted CI run and its verification) → Phase 1.
- The roadmap and the Gate 0 criterion are defined in START_HERE.md (Phase 0, Gate 0).
- Gate record rules are in `docs/gates.md`.
- No Gate 0 record exists. It is created only after Step 11 and its approved corrections, with `python -m pmv.gates create` and explicit project-owner approval.

This checklist does not restate requirements. Where it summarizes one, the referenced document is authoritative. Every check is a deterministic, offline command, run from the repository root. `pmv` commands are run through the locked environment, for example `uv run --locked python -m pmv.gates verify-history`; the tables shorten this to `python -m …`.

## Phase 0 controls (START_HERE.md, Phase 0 "Create")

| Control | Step | Commit | Verification | Authoritative document |
|---|---|---|---|---|
| Project controls and agent definitions | baseline | `faec572` | `git merge-base --is-ancestor faec572 HEAD` | PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md |
| Repository conventions, dependency management, Python environment, testing framework | 1 | `c131321` | `./scripts/check.sh` | `docs/conventions.md` |
| Logging and configuration | 2 | `6f4d657` | `./scripts/check.sh` (`tests/unit/test_config.py`, `test_log.py`) | `docs/conventions.md` |
| Secret handling | 3a, 3b | `22ea934`, `d67c42d` | `scripts/scan_secrets.sh`, which prints `RESULT: CLEAN` | `docs/conventions.md` (Secrets) |
| CI (configured locally) | 4 | `8fe7a7f` | `tests/unit/test_ci_workflow.py`; `./scripts/check.sh` is the CI gate | `.github/workflows/ci.yml` |
| Raw-data storage outside Git, with provenance | 5 | `decb987` | `./scripts/check.sh` (`test_raw_*`) | `docs/raw_data.md` |
| Automatic experiment tracking | 6, 10 | `cba9606`, Step 10 | `./scripts/check.sh` (`test_experiment*`) | `docs/experiments.md` |
| Gate-record format and location | 7 | `65ddbb1` | `python -m pmv.gates verify-history` | `docs/gates.md` |
| Tamper-evident HOLDOUT_ACCESS_LOG.md events | 8 | `0bdd2d0` | `python -m pmv.holdout_log verify-history` | `docs/holdout_access.md` |
| Protected-information embargo and deterministic data-access controls | 9 | `6b8cda6` | `python -m pmv.protected_scope verify-history`; `python -m pmv.data_access_guard check-config` | `docs/protected_information.md` |
| Physical isolation of production credentials | 9 (deferred) | — | Production credentials do not exist; credential infrastructure is deferred to the runtime phase | `docs/protected_information.md` (threat model) |
| Reproducibility conventions | 10 | Step 10 | `python -m pmv.reproducibility verify` | `docs/reproducibility.md` |

## Invariants to confirm

| Check | Command | Expected |
|---|---|---|
| Expected commits present | `for c in faec572 c131321 6f4d657 22ea934 d67c42d 8fe7a7f decb987 cba9606 65ddbb1 0bdd2d0 6b8cda6; do git merge-base --is-ancestor $c HEAD \|\| echo missing $c; done` | No output |
| Clean tree | `git status --porcelain`, run in a normal terminal | No entries. Inside a Claude Code sandbox, masked paths can appear as untracked placeholder entries (`.bashrc`, `.gitconfig`, `.mcp.json`, `.claude/settings.local.json`, `secrets`, and others), shown either as non-regular `/dev/null` devices or as zero-byte regular files depending on the session. They are not repository files: on 2026-10-14 the owner confirmed from a normal terminal that none of them exist on disk. |
| Full local quality gate | `./scripts/check.sh` | Exit 0 |
| Secret scan | `scripts/scan_secrets.sh` | `RESULT: CLEAN` |
| Gate history | `python -m pmv.gates verify-history` | `gate history verified: 0 record(s)` |
| No gate records yet | `ls docs/decisions/gates 2>/dev/null \| wc -l` | `0` |
| Holdout history | `python -m pmv.holdout_log verify-history` | `holdout log: 1 event(s), last HAL-0005` and `history verified` |
| Protected registry empty | `python -m pmv.protected_scope verify-history` | `0 scope(s), 0 active, 0 committed` |
| Protected-information settings | `python -m pmv.data_access_guard check-config` | `protected-information settings verified`. Known session issue: where the sandbox masks `.claude/settings.local.json` as a zero-byte regular file, `check-config` (and so `./scripts/check.sh`) reports it as invalid JSON. This is deferred to Step 11 (see below). In a normal terminal, or a session that masks it as a device, the check passes. |
| No real holdout observations | Registry empty (above); no raw store or experiment root is configured (`[raw_storage]`/`[experiments]` unset in `configs/`); the guard refuses every real request | Confirmed by the commands above |
| No live credentials | `scripts/scan_secrets.sh`; no `.env*` file is tracked (`git ls-files \| grep -c '\.env'` prints `0`; the committed template is `env.example`) | Clean |
| Reproducibility | `python -m pmv.reproducibility verify`, then `python -m pmv.reproducibility fingerprint` twice | Exit 0, and the same fingerprint both times |
| Deferred Step 9 prerequisites | `docs/protected_information.md`, "Phase 0 status" | Listed with deadlines and **unresolved** (below) |

## Explicitly pending, and not Gate 0 blockers

- **Step 11 audit:** pending. It is the next step, and Gate 0 is decided only after it and its approved corrections.
- **Hosted CI:** CI is configured locally, and hosted CI has never run. **Hosted CI has not yet run. This is intentionally deferred to Phase 0 Step 12 and is a mandatory prerequisite to Phase 1, not a prerequisite to the Gate 0 decision.** Step 12 creates the private remote, pushes the full history, verifies secret and history hygiene, runs the first hosted CI, and verifies its result. That includes the GitHub runner's user-namespace behavior for the secret scan, which has not been verified.
- **Deferred Step 9 prerequisites:** unresolved, each with its own deadline in `docs/protected_information.md`.
  - Before Phase 1 agent-facing real market data:
    - the trusted endpoint/source catalog;
    - the contract-lifecycle catalog;
    - S-2 (historical requests trust the caller's provider and family);
    - M-2 (identifier kinds);
    - M-3 (recorded contracts only);
    - S-5 (combined reconstruction sources);
    - S-6 (Phase 1 ordering conflict);
    - S-4 (enforcing the scope freeze after first exposure).
  - Before the first real protected scope: S-3 (registry composition leakage), binding scopes to holdout events, and S-1 (an off-host anchor).
  - These are explicit Step 11 review targets, not completed work.
- **Required user governance inputs:** each blocks only the gate START_HERE.md names for it. Backup policy is required before the first live capture and no later than Gate 1; risk-appetite values by Gate 4.5. None of them blocks Gate 0.

## Known Step 10 boundaries for Step 11 to challenge

- **The fingerprint boundary:** it does not cover the standard library, system libraries, kernel, CPU, or timezone data (`docs/reproducibility.md`).
- **The cost of re-hashing every installed file:** about 0.8 s for `fingerprint`, about 2.5 s for `verify`.
- **The v2 reproducibility mechanism is implemented and synthetically testable, but real evidentiary use is not yet authorized pending Step 11 resolution of the remaining execution-boundary issues.**
- **M-1, cached bytecode:** cached or tampered `__pycache__` bytecode remains a known execution-boundary limitation (`docs/reproducibility.md`). **MUST RESOLVE BEFORE ANY REAL v2 `evidence_candidate` MAY COUNT AS EVIDENCE.** Deferred to Step 11.
- **M-2, working-directory shadowing:** shadowing through the working directory or `sys.path` remains a known execution-boundary limitation. **MUST RESOLVE BEFORE ANY REAL v2 `evidence_candidate` MAY COUNT AS EVIDENCE.** Deferred to Step 11.
- **M-3, failed start then retry:** **resolved in Step 10.** A retried start that cannot capture the environment beside an earlier `environment.json` is refused, and a differing `environment.json` refuses the start.
- **M-4, recording that `verify` passed:** a successful reproducibility verification is currently established by control flow and testing, not by a separately persisted `verified` field. Step 11 decides whether a persisted attestation is needed.
- **M-5, gate run evidence:** gate tooling (`python -m pmv.gates create`) checks a referenced run's ledger eligibility but does not yet independently verify its `environment.json` or other files (`verify_run`). **MUST RESOLVE BEFORE ANY GATE RELIES ON v2 EXPERIMENT EVIDENCE.** Deferred to Step 11.
- **Zero-byte `settings.local.json` mask:** Claude Code may represent a nonexistent, masked `.claude/settings.local.json` differently across sessions: as a `/dev/null` device, or as a zero-byte regular file that `check-config` reports as invalid. This is not solved; it is deferred to Step 11.
  - On 2026-10-14 the owner confirmed from a normal terminal that `.bashrc`, `.gitconfig`, `.mcp.json`, `.claude/settings.local.json` and `secrets` were all absent on disk.
  - `./scripts/check.sh` passed in the Step 10 session.
- **Other silent demotion:** an `evidence_candidate` with a dirty tree is still demoted to exploratory under the Step 6 dirty-tree policy. Only reproducibility-verification failure was changed to refuse the start.
