# Phase 0 Step 11: owner decisions (2026-10-14)

**Approver:** the project owner, in the Claude Code development session that applied the Step 11 correction batch.

**What this records:** the owner's decisions on the Step 11 comprehensive audit, as START_HERE requires ("Record each approved value, with date and approver, in `docs/decisions/`").

**Limitation:** this record is procedural. The system does not cryptographically prove who approved it (see F-42).

**This is not a gate record.** No Gate 0 record exists.

## Approved now

**F-01: real raw data lives in the protected area.**
- In every non-test environment, `[raw_storage].root` must resolve inside `~/pmv-protected/raw` (or a descendant), checked lexically and after resolving symlinks.
- Configuration loading and `check-config` enforce this.
- The low-level store stays testable with temporary roots.
- Details: `docs/raw_data.md`.

**F-03: credential isolation.**
- No credential exists, and none is created now.
- **Deadline:** before any venue credential exists, including one needed only for public-data or WebSocket collection.
- **Minimum architecture:**
  - the collector runs outside Claude and agent sessions;
  - the credential lives only in the Claude-denied `~/pmv-credentials/` (Read, Edit, and sandbox denies are in `.claude/settings.json` and checked by `check-config`);
  - the collector receives it directly;
  - it is never copied into repository files, logs, configuration artifacts, or agent context;
  - least privilege, preferring a genuinely data-only or read-only credential.
- If a venue requires broader permissions, stop for explicit owner approval before creating or using it.

**F-04: Git repository backup policy.**
- **A. Before Gate 0.**
  - Create a full Git bundle from the corrected repository and restore-test it from a separate temporary directory.
  - The owner does this from a normal terminal, not from Claude.
  - A bundle on the same physical device is a local copy, **not** an off-host or disaster backup.
  - It is never stored in the Git repository.
- **B. Step 12.**
  - Create the private remote and push the full history.
  - Verify the remote history.
  - Perform a fresh-clone restore test.
  - Run hosted CI.
- **C. Retention.** Keep the pre-Gate-0 bundle at least until both the Step 12 private remote and the fresh-clone restore have been verified. No time-based retention period is set.
- **Other artifact classes.** Backup policies for the experiment store (before its first real run) and for raw captured market data (before first live capture, and no later than Gate 1) remain required, under START_HERE "Required User Governance Inputs".

**F-05: threat model.**
- **In scope:** accidental leakage; honest operator mistakes; ordinary agent and tool mistakes; accidental protected-information exposure; unsafe project configuration; detectable implementation defects; accidental Git, history, or configuration mistakes; contamination from normal data and API use.
- **Out of scope as a security guarantee:** intentionally malicious root-capable processes; kernel compromise; deliberate sandbox escape; hostile sudo or disk-level access; cryptographic defense against a malicious local administrator.
- **Unexpected sandbox behavior** is still tested and failed closed around where practical.
- **"Tamper-evident"** means integrity checks over the visible ancestry of the current `HEAD`.
- Full text: `docs/protected_information.md`.

**F-42: every gate requires explicit owner approval.**
- The stricter rule is kept.
- **Limitation:** approval is recorded procedurally, not cryptographically. Under the Phase 0 threat model this is acceptable.
- Commit signing, PKI, and hardware keys are not added now (F-14 keeps its later deadline).
- Gate 0 will be created only after owner review, from a normal terminal.

**The correction batch.** F-02, F-13 (M-5), F-18 (wording only), F-20, F-21, and F-22 are approved and implemented. M-4 is closed without a format change.

## Deferred: Phase 1 entry decisions (first agenda items when Phase 1 starts)

Phase 1 does not start until Step 12 is complete. Each decision must be resolved before the real-world action named:

| Finding | Decision | Must be resolved before |
|---|---|---|
| F-16 | Venue and jurisdiction eligibility, including whether in-scope gold contracts exist | Any venue account or credential is created, or any real venue collection or trading integration is used |
| F-06 | Prospective (forward-looking) holdout as the default formation | Agents are shown any real observation |
| F-07 | Power-based holdout size, and the unit of independence | The first real protected scope or cycle is registered |
| F-08 | Release architecture: trusted collector plus release by receipt time | Agents are shown any real observation |
| F-17 | Minimum economic thresholds and kill criteria | Substantive strategy or model development on real data, and certainly before paper or live trading |

**The large Step 9 catalog plan is not built.** That plan is the endpoint/source catalog, the equivalence graph, the reconstruction engine, and the contract-lifecycle catalog for access control. It stays visible in `docs/protected_information.md` until F-08 is decided. If F-08 adopts the trusted-collector and time-release model, those requirements are retired through an owner-approved governance change. A lifecycle catalog may still be needed for labels.

## Deferred: later findings (IDs and deadlines kept visible)

The full list is in `docs/gate0_readiness.md` ("Deferred findings and deadlines"). This batch deliberately does not fix F-11, F-12, F-14, F-15, F-19, F-23, F-24, F-25, F-26, or the later quant and risk items.

## Correction re-audit (red team), 2026-10-14

A narrow Reliability/Red-Team re-audit of the correction batch returned PASS WITH FIXES. Its findings are numbered RT-1 to RT-8. The project owner, in the Claude Code development session, approved a final narrow correction round without changing gate semantics, experiment formats, or the approved security architecture.

**Fixed in this round:**
- **RT-1 (F-20 residual).** `raw_storage._git_identity` now runs Git with `GIT_NO_REPLACE_OBJECTS` and reports an unknown identity under replace refs, grafts, or a shallow history, as `experiments.collect_git_identity` already did.
- **RT-3.** The protected raw base and the guard's protected root come from the account's password-database home (`pmv.config.account_home`), never `HOME`. `~` in guarded paths means the same home. An unknown home refuses every real raw root and every guarded path.
- **RT-5.** `/.venv/`, `/venv/`, `/keystore/`, `/secrets/`, and the data-extension patterns are anchored to the repository root.
- **RT-8 (hang only).** Settings files are opened non-blocking and must be regular files after symlinks; a FIFO or directory fails closed.
- **RT-2 (wording), RT-6, RT-7.** The readiness overclaim about history verification is corrected; F-18 residue is reworded; the duplicate F-21 identifier is renamed F-21b. The `HOLDOUT_ACCESS_LOG.md` render text "Gate 7 preregistration PASS record" is left unchanged, because rewording it changes a byte-verified governance mirror; it is part of the F-18 fix.

**Deferred, with deadlines:**

| Finding | Deferred work | Must be done before |
|---|---|---|
| RT-4 | Real collectors and gate commands refuse the test environment (with F-37) | Phase 1 real collection |
| RT-2 | Explicit design decision on whether gate history verification re-verifies referenced experiment artifacts | A gate relies on experiment evidence |
| RT-8 | Broader local-settings permission hardening: `additionalDirectories`, `defaultMode` (for example `bypassPermissions`), broad `Read` globs, and other allow rules that do not name the protected locations | Any venue credential exists (the F-03 deadline) |
