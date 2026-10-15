# Repository Backup, Recovery, and Agent Execution Boundaries

This document covers four things: how the repository's code and history are backed up; the environments development agents may work in and the access boundary around them; how an approved batch of work becomes a verified checkpoint; and how to recover the repository if the local machine or container is lost. It covers the Git repository only. It does not provide a backup for raw market data, protected data, the experiment store, or credentials (see "Policy boundary").

Owner basis: Step 11 F-04 (`docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`); the Phase 0 Step 12 private-remote and restore verification completed after Gate 0; and the owner's operating-model decision for Phase 1 (2026-10-14), recorded in "Execution environments and access boundary" below.

## Authoritative locations

| Item | Value |
|---|---|
| Working repository | `~/prediction-market-velocity` on the owner's ChromeOS Linux container |
| Private remote | `origin` = `git@github-pmv:Danjstr/Prediction-market-velocity.git` (private GitHub repository `Danjstr/Prediction-market-velocity`) |
| SSH alias | `github-pmv` is a host alias in the owner's local `~/.ssh/config`. It, and the passphrase-protected key it names, exist only on the owner's machine and are never in the repository. |
| Integration branch | `main` is the authoritative integration branch unless a later approved policy changes it. |
| Reference point | Gate 0 PASS was committed as `db09acd91c909f787ea3acc4ece421d8de59af2d` ("Record Gate 0 PASS"); its record pins project commit `1b743781ff0179ff9194062f339b8b656648f3fd`. Later checkpoints move `main` forward from there. |
| Secondary local bundle | `~/pmv-backups/prediction-market-velocity-pre-gate0-1b743781.bundle`, SHA-256 `7b1440b9e7d859000ff68a3d03ce783369e7db320a69ac8bc21b44db92a21655`, outside the repository |

The bundle stops at the pre-Gate-0 commit `1b743781`. It does **not** contain the Gate 0 record or anything later. It is on the same physical device as the repository, and it is not a source of truth. The private GitHub repository is newer and is the primary recovery source.

The source of truth for the latest checkpoint is the verified `main` on GitHub, cross-checked against the commit SHA reported at the end of each checkpoint.

## Execution environments and access boundary

### Owner control at batch start

Each meaningful work batch begins with an owner-approved **objective, scope, acceptance criteria, and boundaries**. The owner approves the mission once. Routine implementation within that approved scope does not need repeated owner confirmation. Anything outside the approved scope, any material change as defined in START_HERE.md, and any governance change still needs explicit owner approval (CLAUDE.md "Development Behavior").

### Current model: local, owner-controlled (in force)

- Development runs in local Claude Code sessions on the owner's Chromebook container, under the project's Claude Code permissions and sandbox (`.claude/settings.json`).
- **Local sessions remain owner-controlled.** They are not approved for unattended autonomous execution. Ordinary local Claude Code sandboxing is not assumed to be enough for unattended work on the owner's personal machine.
- Local Claude cannot read `~/.ssh`. The owner makes every authenticated push and remote verification from a normal terminal.
- This model stays in force until an isolated autonomous environment is explicitly configured and approved by the owner.

### Future model: isolated autonomous execution (NOT YET ENABLED)

- Autonomous development is intended to run eventually in an isolated project environment: preferably a dedicated cloud, container, or VM session tied only to this private repository.
- That environment must not have access to the owner's general local filesystem, personal browser or session data, email, payment methods, password stores, Downloads, documents, or unrelated repositories.
- It may be allowed to authenticate to **only this private repository**, with a credential scoped to it, under the "Future isolated autonomous checkpoint workflow" below.
- **None of this is enabled.** No such environment, credential, or branch-push permission exists or is approved. Enabling it requires an explicit owner decision recorded in `docs/decisions/` and the prerequisites listed in that workflow.

### Filesystem boundary (both models)

- An agent's normal readable and writable scope is the project repository, plus explicitly approved project-specific runtime paths. Currently those are the session's temporary scratch directory and the pinned project tools under `~/.local/share/pmv-tools/`, which agents only execute through the project scripts.
- The protected-data path `~/pmv-protected` and the credential path `~/pmv-credentials` remain governed by `docs/protected_information.md`. They are denied to agents.
- Personal paths and credential paths are denied by default. Agents never deliberately inspect or traverse unrelated home-directory content.
- Outside scope: `~/.ssh`, browser profiles, email stores, password and key stores, financial information, Downloads, personal documents, and unrelated repositories or user files.
- No agent may weaken, remove, or work around this boundary on its own, including through changes to Claude Code permission settings, sandbox configuration, connectors, or project scripts.

### External services and financial actions (both models)

Development agents are not authorized to:

- access personal email;
- access banking or brokerage accounts;
- access saved payment cards;
- make purchases or create paid subscriptions;
- initiate financial transactions;
- connect personal cloud drives or unrelated services;
- install or authorize broad external connectors.

Any future external integration must be explicitly approved and narrowly scoped. Ordinary web research permitted by CLAUDE.md is unaffected. Trading credentials and trading execution are separate project controls with their own approved policy (CLAUDE.md "Real Capital and Venue Access", `docs/protected_information.md`); this section does not authorize them.

## What GitHub backs up

GitHub holds exactly what is committed to the repository, and nothing more. Repository policy already decides what may be committed; this document adds no new category.

**Allowed**, when it already satisfies repository policy:

- source code and tests;
- safe configuration (`configs/*.toml`, which never contain secrets; see `docs/conventions.md`);
- schemas;
- documentation and decision records;
- governance records: gate records, the holdout access ledger and its mirror, and the protected-scope registry (metadata only);
- experiment definitions and specifications that contain no protected observations;
- other metadata that repository policy already permits in Git (hashes, identifiers, enums).

**Forbidden**: never committed or pushed, including to preserve it:

- API keys, tokens, passwords, and any other credentials or secrets;
- SSH private keys, the SSH passphrase, and `~/.ssh` contents;
- `.env` files or other secret-bearing environment files (`env.example` holds names only);
- credential stores, wallets, keystores, and anything from `~/pmv-credentials`;
- raw market observations, which live only in the external raw store (`docs/raw_data.md`);
- protected holdout contents or outcomes, or information capable of reconstructing them (`docs/protected_information.md`);
- any dataset that policy places under `~/pmv-protected`;
- experiment-store data that policy keeps out of Git, and logs or other outputs that contain or may contain protected information;
- anything else prohibited by `.gitignore`, `scripts/scan_secrets.sh`, `docs/conventions.md`, or CLAUDE.md.

These exclusions are enforced first by policy and by keeping such material out of the working tree, then by `.gitignore`, the secret scan, and review. None of these is perfect. A pushed secret or protected observation is treated as exposed even if it is later removed: escalate immediately, and for protected information follow "Accidental exposure" in `docs/protected_information.md`.

Failed, unsafe, secret-bearing, or protected material is never pushed merely to back it up, in either model.

## Current local checkpoint workflow

This is the workflow in force now. A checkpoint is how a meaningful approved batch of work becomes a backed-up, verified state of `main`.

| # | Step | Command or check | Who |
|---|---|---|---|
| 1 | Inspect status | `git status --short --branch`: confirm the branch is `main` and every changed path is expected | Agent or owner |
| 2 | Security and repository checks | Covered by step 3: the secret scan (`scripts/scan_secrets.sh`, covering history and staged, unstaged, and untracked material), `check-config`, and the three `verify-history` commands. Also confirm by inspection that the diff and untracked files contain no forbidden material. | Agent or owner |
| 3 | Quality gate | `./scripts/check.sh` must pass | Agent or owner |
| 4 | Review the exact diff | `git diff` and `git diff --stat`. The owner reviews the batch result against its approved acceptance criteria. | Owner approves |
| 5 | Stage explicit paths | `git add -- <path> <path> ...`, listing only approved paths. **Never** `git add -A`, `git add .`, or `git commit -a`. Confirm with `git diff --cached --name-only`. | Agent (on instruction) or owner |
| 6 | Commit | `git commit` with a meaningful message stating what the batch establishes. Never amend a published commit. A gate record is always committed in a new commit (`docs/gates.md`). | Agent (on instruction) or owner |
| 7 | Verify status | `git status --short --branch` shows nothing staged or modified that belongs to the batch; `git log -1` shows the new commit | Agent or owner |
| 8 | Push | `git push origin main`: an explicit remote and branch, fast-forward only | Owner, from a normal terminal |
| 9 | Verify the remote | `git ls-remote origin refs/heads/main` must print exactly the output of `git rev-parse HEAD` | Owner, or an agent working from output the owner supplies |
| 10 | Verify hosted CI | The GitHub Actions "CI" run for that exact commit SHA completes successfully | Owner (GitHub web UI) |

Rules:

- **A failed check blocks the checkpoint.** If `./scripts/check.sh` or any step fails, do not stage, commit, or push. Fix the cause, or stop and report. No check is skipped, disabled, or worked around to obtain a backup.
- If anything changes after step 3, run `./scripts/check.sh` again before committing.
- **Inside a Claude Code sandbox**, `git status` can list masked placeholder paths (`.bashrc`, `.gitconfig`, `.mcp.json`, `secrets`, `.claude/skills`, and others) as untracked. They are not project files and must never be staged; explicit-path staging prevents that. A truly clean-tree check is run from a normal terminal (`docs/gate0_readiness.md`).
- **A checkpoint is complete only after steps 9 and 10 succeed.** If the remote head does not match, or hosted CI fails or does not run, the checkpoint is reported as incomplete, with the exact failure. It is never declared complete.
- **If a push is rejected** (for example as non-fast-forward), stop and report. Never force-push, never `pull --rebase` over published history, and never resolve a divergence of `main` without the owner. An unexpected divergence of the remote is an incident to investigate.
- Push only `main`, with `git push origin main`. Pushing other branches or tags, or using `--all`, `--mirror`, `--tags`, `--delete`, `--force`, `--force-with-lease`, or a `+` refspec, needs explicit owner approval for that specific push.

### Authentication

The SSH key behind `github-pmv` is passphrase-protected, and `~/.ssh` is denied to the Claude Code sandbox, so the push and `git ls-remote` run from the owner's own terminal. The owner supplies authentication interactively.

Agents never ask for, receive, store, log, echo, or embed the passphrase or any key material. They never copy, generate, or modify keys or `~/.ssh` configuration, and never work around the denial: no HTTPS tokens, no changed remote URL, no credential helper, no agent forwarding. When an agent cannot run a step, it gives the owner the exact command to run and waits for the result.

## Future isolated autonomous checkpoint workflow (NOT YET ENABLED)

This section describes an intended future operating mode. **It is not enabled.** No agent may push any branch under it, or describe autonomous branch pushing as available, until every prerequisite below is met and the owner has explicitly approved the mode.

**Prerequisites** (all required, each verified and recorded in `docs/decisions/`):

1. An isolated autonomous environment (a dedicated cloud, container, or VM session) is configured, tied only to this repository, and explicitly approved by the owner. It has none of the access excluded under "Execution environments and access boundary".
2. That environment has a credential that can reach **only this private repository**, with the minimum permissions needed to push task branches. It cannot change repository settings, visibility, rulesets, or other repositories, and it is never exposed to the owner's personal machine or to `~/.ssh`.
3. GitHub branch protection or rulesets on `main` are configured and verified. At minimum they block force-pushes and deletion, and require the CI check (and any owner-required review) before a merge. The owner decides whether agents may merge.
4. The CI trigger covers task branches as intended. Under the current `.github/workflows/ci.yml`, CI runs on `pull_request` and on pushes to `main` only, so a pushed task branch has no hosted CI until a pull request is opened. Any trigger change is a reviewed change to CI.
5. The owner has approved the batch charter (objective, scope, acceptance criteria, boundaries) under which the agent runs.

**Workflow** (once enabled):

1. Create a task branch from the current verified `main`. Agents do not commit directly to `main`.
2. Implement within the approved batch scope.
3. Run `./scripts/check.sh`. A failure blocks the checkpoint, exactly as in the current workflow.
4. Stage explicit paths only, then commit with a meaningful message.
5. Push only the task branch, fast-forward only, to `origin`.
6. Verify that the remote task-branch head equals the local head.
7. Obtain hosted CI for that exact commit (normally through a pull request into `main`).
8. Review and merge into `main` according to the owner's policy at that time. `main` advances only through that process.

Always forbidden, in this mode as in every other: force-pushing; rewriting published history; deleting `main` or other published branches without owner approval; changing repository visibility or settings; disabling or weakening CI or security controls; accessing other repositories unless the owner separately approves them; and pushing failed, unsafe, secret-bearing, or protected material.

## Normal checkpoints, incomplete work, and emergencies

- **Normal checkpoint.** Follow the applicable workflow above in full, after an approved batch passes every check.
- **Uncommitted or incomplete work.** It is not backed up by either workflow and is not pushed merely to preserve it. Work that fails checks, is unreviewed, or is half-finished stays local, or (once the future mode is enabled) stays unpushed in the isolated environment. Reduce the exposure by splitting work into smaller approved batches that can each reach a passing checkpoint. In the current model, pushing work-in-progress branches is not approved policy.
- **Emergency: the device may fail before the next normal push.** Commits on `main` that already passed a checkpoint's checks but were not yet pushed are pushed by the normal steps 8–10. If checks cannot pass, nothing is pushed to `main`. The owner may instead make a Git bundle of committed history from a normal terminal (`git bundle create <file> --all`, then `git bundle verify <file>`), stored outside the repository and off the device. A bundle contains only committed Git objects, never untracked or ignored files, but it is still subject to every exclusion above. Agents never initiate this on their own.
- **Emergency: the local repository is lost or corrupted.** Follow "Recovery procedure" below.

## Agent responsibilities

Development agents:

- work only within the owner-approved batch scope and the access boundary above;
- treat a verified checkpoint as part of finishing a meaningful approved work batch. They tell the owner when the batch is ready, giving the exact paths, the `./scripts/check.sh` result, and the proposed commit message;
- in the current local model, stage, commit, or push only when the owner instructs it for that batch;
- never force-push, never rewrite or amend published history, never delete the remote or its branches, never change repository visibility or settings, and never create or change remotes;
- never disable, weaken, or skip CI, the secret scan, `scripts/check.sh`, the access boundary, or any other security control;
- never commit or push secrets, credentials, or protected or raw market data;
- never bypass a failed check to obtain a backup;
- after a push, verify that the remote head equals the local head (directly, or from output the owner supplies), and confirm hosted CI for that SHA;
- report a CI failure, a mismatch, or a rejected push plainly, rather than declaring the checkpoint complete.

Owner approval and manual control remain wherever existing policy requires them (CLAUDE.md "Development Behavior", `docs/gates.md`, `docs/holdout_access.md`).

## Recovery procedure

### Primary: fresh clone from GitHub

Run these steps from a normal terminal on a machine where the owner has configured SSH access to the private repository. On a replacement device, set up a new key and the `github-pmv` alias out of band, never through the repository or an agent session.

1. **Clone the full history** into a new, empty location, not over a damaged copy (keep any damaged copy for inspection):
   `git clone git@github-pmv:Danjstr/Prediction-market-velocity.git ~/prediction-market-velocity-restore`
   Never use `--depth` or other shallow or partial clone options: the history verifiers fail on shallow clones.
2. **Verify the expected head.** On `main`, `git rev-parse HEAD` must equal the SHA of the last verified checkpoint, as given by the last checkpoint report, the GitHub web UI, and its CI run. A mismatch is an incident: stop and investigate.
3. **Check object integrity:** `git fsck --full --strict` must pass.
4. **Install the pinned tools and dependencies** with the project's locked mechanism: run `scripts/install_uv.sh` (and put the pinned uv on `PATH`) and `scripts/install_betterleaks.sh`, which verify the pinned archive hashes, then `uv sync --locked`. Never `pip install` (`docs/conventions.md`).
5. **Run the quality gate:** `./scripts/check.sh` must pass.
6. **Verify gate history.** `check.sh` already runs `python -m pmv.gates verify-history`, `python -m pmv.holdout_log verify-history`, and `python -m pmv.protected_scope verify-history`. Also confirm that `uv run --locked python -m pmv.gates list` shows the expected records, including Gate 0.
7. **Hosted CI.** Confirm that the latest CI run on GitHub for that SHA passed. Any new commit needed during recovery goes through the normal checkpoint workflow.
8. Only then move the restored clone into the working-repository path, or treat it as the working repository.

### Not recoverable from GitHub

GitHub does not hold, and recovery from it does not restore:

- raw captures, the protected area (`~/pmv-protected`), or any protected or holdout data;
- the experiment store;
- credentials (`~/pmv-credentials`), SSH keys, or `~/.ssh` configuration;
- ignored or untracked local files, including `.claude/settings.local.json`, the virtual environment, and installed tools (reinstalled in step 4);
- uncommitted or unpushed work;
- Claude Code session history and memory outside the repository.

Restore those only from a separately approved backup system for that data class, where one exists for the current phase. Where none exists, the data is not recoverable, and a recovery report must say so rather than imply otherwise.

### Secondary fallback: the local bundle

Use the bundle only if GitHub is unavailable or its history is in doubt. It ends at the pre-Gate-0 commit `1b743781` and is **older than GitHub**: it lacks the Gate 0 record and every later commit.

1. Verify the file: `sha256sum` must print `7b1440b9e7d859000ff68a3d03ce783369e7db320a69ac8bc21b44db92a21655`, and `git bundle verify <bundle>` must pass.
2. Clone it into a new, empty directory with `git clone <bundle> <new-directory>`. In the clone, `git rev-parse HEAD` must begin with `1b743781`.
3. Run `git fsck --full --strict`, then steps 4–6 of the primary procedure.
4. Treat the result as a partial, older recovery. Anything after `1b743781`, including the Gate 0 record, must be recovered from GitHub or another verified copy as soon as one is available. It is never recreated by hand.

A newer bundle made under "Emergency" above is restored the same way, after verifying its own recorded hash.

## Policy boundary

- Private GitHub is currently the **primary off-device backup and recovery source for the repository's code and Git history**.
- It is **not** an immutable archive, notarization, or external anchor: the owner or an administrator can force-push, delete, or change visibility. By itself it does not satisfy the external-anchor prerequisites in `docs/holdout_access.md` and `docs/protected_information.md` (S-1). Those must be designed and verified separately before the first real protected scope and before any Phase 7 reveal.
- It is **not** a backup for protected datasets, raw market data, the experiment store, or credentials.
- The GitHub remote does not replace the separately required backup and retention policies for raw captured market data (before first live capture, and no later than Gate 1), the experiment store (before its first real run), and other irreplaceable artifact classes (START_HERE.md "Required User Governance Inputs").
- Disaster recovery is not claimed for any data that has never been backed up and restore-tested.
- Before irreplaceable live market capture begins, the separately approved raw/protected-data backup policy must be implemented, and its backup-and-restore smoke test must succeed (`docs/raw_data.md`, START_HERE.md Gate 1).

## Open risks

- **Branch protection is unverified.** No GitHub branch protection or ruleset on `main` has been verified, so a force-push or deletion of `main` is not known to be technically blocked. Configuring and verifying it (blocking force-pushes and deletion, and requiring CI before merge) is recommended now, and is a **prerequisite** before any autonomous agent may push task branches.
- **One off-device copy.** GitHub is the only off-device copy of the history; the bundle is on the same device.
- **Untested end-to-end drill.** This procedure combines commands verified during Step 12; it has not been run end to end as a written restore drill.
