# Isolated autonomous development environment: activation (2026-10-15)

**Approver:** the project owner, who configured and tested the environment and instructed this record in the task that activated it.

**What this records:** the owner's activation of the isolated autonomous development environment and the task-branch checkpoint workflow in `docs/backup_and_recovery.md`. Those prerequisites must be verified and recorded in `docs/decisions/`.

**Limitation:** this record is procedural. The configuration it describes lives outside the repository, and the system does not cryptographically prove who approved it or that the configuration still holds (see F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`). The properties below are **owner-reported** unless marked as agent-observed.

**This is not a gate record.** It changes no gate, holdout, risk, credential, or data-access rule.

## Environment (owner-reported, implemented and tested)

- Isolated rootless Podman container. Host and owner-private files are unavailable inside it.
- The launcher and Claude Code managed settings are owner-controlled and live outside the repository.
- Default-deny network egress, with owner-approved domains only.
- Claude Code state and the Claude Code executable live in dedicated volumes.
- A repository-scoped GitHub deploy key is the only repository credential.
- The deploy key can push task branches. Direct pushes to `main` are blocked by the active GitHub ruleset "Protect Main".
- "Protect Main" requires a pull request with the "Quality gate" check, blocks force pushes, and has no bypass actors.

## Agent-observed at activation (consistent with the above; not a full verification)

- The session runs as an unprivileged user in a container (`/run/.containerenv` is present), with the repository at `/workspace`.
- `~/pmv-protected` and `~/pmv-credentials` do not exist in the container.
- `origin` is reached over SSH at `ssh.github.com:443`.
- Sandbox masking placeholders appear as untracked paths in `git status`.

The agent did not test the `main` ruleset, by design: attempting a push to `main` is forbidden.

## Decisions

1. The isolated autonomous execution model and its task-branch checkpoint workflow are **enabled** inside this environment only. The local model remains owner-controlled and unchanged.
2. Autonomy covers development work within an owner-approved batch charter: implementing, running `./scripts/check.sh`, committing explicitly staged paths, and pushing task branches. Opening pull requests and merging follow the charter and the owner's merge policy.
3. **Not authorized** by this decision: real venue credentials of any kind, real-money execution, and irreplaceable live-data capture. Each still requires its own explicit owner decision and the existing gates and controls.
4. The production runtime remains free of LLMs and agents (CLAUDE.md "Critical Runtime Independence").
5. Agents never use `git add -A`, `git add .`, or `git commit -a`, because sandbox masking placeholders appear as untracked paths. They stage intended files by explicit path.

## Follow-ups

- Confirm in the ruleset that deletion of `main` is blocked. The original prerequisite required it, and the owner report does not mention it.
- Task branches and tags are protected by policy only (`docs/backup_and_recovery.md` "Open risks").
