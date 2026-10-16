# Protected Information (Phase 0 Step 9)

*Established in Phase 0 Step 9 and in force in every later phase. Later owner decisions are noted inline. For current status, see `docs/phase1.md`.*

The final holdout is protected **information**, not just a file. Protected observations, outcomes, and any equivalent information that could reconstruct them stay unavailable to development agents until authorized final evaluation, whatever the source or representation. This is the primary control. Filesystem isolation is defense in depth only. Governing text: START_HERE.md (Project-Wide Controls) and the Protected Information Rule in CLAUDE.md.

Implementation:
- `src/pmv/protected_scope.py`: the scope record, the registry, widen-only supersession, Git-history verification, and the equivalence catalog.
- `src/pmv/data_access_guard.py`: the deterministic guard, the local path check, and the settings check.
- Schema document: `schemas/protected_scope_v1.json`. The Python validators are authoritative.

## Why this design

The project owner directed this design. It replaced an earlier plan for a separate vault or container. The reason is that protecting only the holdout file does not stop leakage: the same information is available from many places. A protected BTC contract resolves on the BTC price, so Coinbase spot, a CF Benchmarks index, CME futures, a public dataset, or a web page for the protected window all reveal the outcome. The embargo therefore covers equivalent observables, not just the file.

## Threat model (owner-approved 2026-10-14, Step 11 F-05)

**In scope.** The project's controls are designed to prevent, or to detect and fail closed on:
- accidental data leakage;
- honest operator mistakes;
- ordinary agent and tool mistakes;
- accidental exposure of protected information;
- unsafe project configuration;
- implementation defects that ordinary project controls can reasonably detect;
- accidental Git, history, or configuration mistakes;
- contamination from normal data and API use.

**Out of scope as a security guarantee.** The project is not designed as a security boundary against:
- intentionally malicious root-capable processes;
- kernel compromise;
- deliberate sandbox escape or exploitation;
- a hostile process using passwordless sudo or disk-level access (the development user is in the `sudo` and `disk` groups);
- a malicious local administrator, against whom no cryptographic defense is offered.

**Sandbox behavior is not irrelevant.** Unexpected Claude Code sandbox behavior (for example masked paths that appear as `/dev/null` devices in one session and as zero-byte files in another) stays something the project tests and fails closed around where practical. The claim above is only that the project is not designed to resist an intentionally malicious privileged process.

**Governed by rules, not code.** These are recorded when they happen:
- General web browsing. Agents may freely research code, papers, documentation, and methodology online, under the host-class rule in `docs/external_access.md` (batch 4 O-6) and, during a protected interval, the research embargo there (O-9). The guard does not intercept web research, and no domain filtering is claimed to enforce the embargo (deterministic network and WebFetch denies for the host classes are Step 11 F-09, not yet committed, and required before Phase 1 real collection and before any agent web research after a cycle's `T0 − m`).
- A human, or a process outside Claude Code, that bypasses the protocol.
- Knowledge the model already had from training (relevant to how the holdout is formed: Step 11 F-06).

**"Tamper-evident" means accident-resistant.** Wherever this project says "tamper-evident", it means detection of accidental or ordinary-tool changes. In practice that is hash chains plus integrity checks over the ancestry of the current Git `HEAD`. Local history can be reset or replaced, so nothing is stronger than that without an off-host anchor (S-1).

**Raw captures are holdout-eligible plaintext** (Step 11 F-01).
- Real raw market data must live inside `~/pmv-protected/raw` (`docs/raw_data.md`). It is denied to the Read and Edit tools and to the Bash sandbox.
- The deterministic collector runs outside Claude Code, writing observations that agents cannot inspect.
- `load_config` and `check-config` enforce the location for every non-test configuration.

**Credentials (owner decision, 2026-10-14, Step 11 F-03).**
- **Current state:** no credential exists, and the project possesses none.
- **Deadline:** credential isolation must be in place **before any venue credential exists, including a credential needed only for public-data or WebSocket collection** (Kalshi requires authentication even for public channels).
- **Approved minimum architecture:**
  - the collector runs outside Claude and agent sessions;
  - the credential lives only in the Claude-denied `~/pmv-credentials/` (denied to Read, Edit, and the Bash sandbox, and checked by `check-config`);
  - the collector receives it directly;
  - it is never copied into repository files, logs, configuration artifacts, or agent context.
- **Least privilege:** use the least privilege the venue supports, and prefer a genuinely data-only or read-only credential. If a venue requires broader permissions, stop for explicit owner approval before creating or using it.

## What is safe now (Phase 0, and Phase 1 until the release path exists)

*Status (B08, 2026-10-16): the project is in Phase 1. Everything said here about Phase 0 still applies to Phase 1 until the H-2 release path exists.*

**Phase 0 is safe for:** synthetic fixtures, methodology research, API documentation, open-source research, and deterministic infrastructure development.

**Phase 0 is NOT yet safe for agent-facing real market observations.** The committed registry is empty, so the guard refuses every real request (`PROTECTED_SCOPE_NOT_DECLARED`). It must stay that way until every prerequisite below is resolved. This does not fail Gate 0, provided Gate 0 records these prerequisites and Phase 1 exposes no real observation to agents early.

**Prerequisites before any agent-facing real market data** (each is **MUST FIX BEFORE PHASE 1 AGENT-FACING REAL-DATA ACCESS** unless stated otherwise):
1. **Trusted endpoint / source catalog** (Red-Team S-2). Provider, family, semantics, identifier kinds, endpoint type, the timestamp that bounds a window, and the information span of each record must come from a catalog controlled by project code, never from a caller. Today every one of them is caller-asserted, which is acceptable for synthetic tests only. Responses also need a post-fetch check that nothing outside the approved request was returned, because one endpoint can mix historical, state, and result fields.
2. **Trusted contract-lifecycle catalog** (S-1, whole-venue semantics). Listing, close, settlement, and finalization times, with no outcomes, so the guard can tell which contracts actually overlap the protected interval. It replaces the temporary blanket refusal for non-historical requests, and the permanent refusal of bulk requests on a venue with protected contracts, wherever safe exclusion can be proven. It must also handle disputes, amendments, and late finalization, which a single `resolution_lag_seconds` per observable does not.
3. **Combined reconstruction sources** (S-5). Individually allowed inputs can reconstruct a protected observable. ETH/BTC with ETH/USD gives BTC/USD exactly; XAU/XAG with silver gives gold. The final rule must tell apart mere correlation (allowed), a direct equivalent observable (refused), and deterministic or near-deterministic reconstruction from combinations (refused). Correlation alone is not a reason to block, and no general combinatorial engine is wanted. Missing direct sources must also be catalogued, including Kalshi's CF Benchmarks feed (BRTI), Chainlink streams named in Polymarket's resolution rules, on-chain resolution data, and tokenized gold. Treating ETH as allowed by default is an owner decision still to be made. **On the Step 11 audit list.**
   - **Owner ruling E-B4-7 (2026-10-16).** Correlation alone never puts a source inside the protected-information boundary. A source belongs inside it only when it is itself a protected observable, a direct equivalent observable (including settlement-reference inputs), or permits deterministic or near-deterministic reconstruction or inference of the protected observation or label, alone or in combination with other allowed information. ETH, crypto indices, futures, ETFs, metals, and other features are not embargoed merely because they are correlated. The quantitative meaning of "near-deterministic" is not yet fixed: before `T0`, the Statistician proposes a criterion, from development data only, at the protected label's native granularity, and the owner approves it (pre-T0 checklist P-3). ETH and similar cases are then measured under that criterion, not decided categorically. Until then, the guard's existing fail-closed behavior for undeterminable requests is unchanged.
4. **Scope-composition leakage** (S-3). The registry names exact protected contracts, their aliases, and the interval. Contract tickers can encode dates and strikes. An agent-readable registry could therefore reveal holdout composition, and possibly the protected price level. Step 11 must decide whether enforcement metadata is separated from ordinary agent-visible context. **MUST RESOLVE BEFORE THE FIRST REAL PROTECTED SCOPE. On the Step 11 audit list.**
5. **Phase-ordering conflicts** (S-6; recorded for Step 11, not changed here). **MUST RESOLVE BEFORE PHASE 1 AGENT-FACING REAL DATA.**
   - START_HERE.md Phase 1 ("Determine: historical depth; timestamp resolution; trade data; order-book data; market metadata; settlement metadata …") can be read as agents inspecting real observations before the split exists. The approved rule (below) forbids that.
   - START_HERE.md Phase 1 requires the cycle and protected interval to be declared "before any outcome-dependent inspection". A v1 scope, however, needs a split definition, which is a Phase 2 artifact. No placeholder split hash may be used to bridge the gap: the guard refuses a committed scope whose split file is missing or different.
6. **Binding to the holdout log and an external anchor** (S-1). A committed scope is not yet tied to a Step 8 `cycle_registered` or `holdout_registered` event, and declared scopes are not anchored outside the local repository (see "Limits of Git-history verification"). **MUST RESOLVE BEFORE THE FIRST REAL PROTECTED SCOPE.**
7. **Historical requests trust the caller-asserted provider and family** (S-2). Rule 3 below uses the family the caller names. A BTC ticker sent under a gold family, or BTC data requested as `eth_spot`, is judged as the asserted family. The fix will be reviewed together with the trusted endpoint/source catalog (item 1), not added as another temporary rule. **MUST RESOLVE BEFORE PHASE 1 AGENT-FACING REAL MARKET DATA.**
8. **Identifier kinds are caller-asserted** (M-2). A caller-supplied kind cannot prove the identifier was labelled honestly. A Polymarket question ID or negative-risk ID labelled as a condition ID, an event slug labelled as a slug, or a Kalshi multivariate ticker labelled as a market ticker is checked as the asserted kind. The trusted endpoint/catalog (item 1) must supply kinds before real data. **MUST RESOLVE BEFORE PHASE 1 AGENT-FACING REAL MARKET DATA.**
9. **Recorded contracts only** (M-3). Rule 1 below protects contracts recorded in a scope. A whole-venue scope without contract records cannot refuse post-interval history of unlisted protected-period contracts. That needs the lifecycle catalog (item 2). **MUST RESOLVE BEFORE PHASE 1 AGENT-FACING REAL MARKET DATA.**

**Step 11 dispositions (F-08 since decided as H-2; see "Batch 4" below).** Items 1, 2, 3, 7, 8, and 9 assume agents request market data through the guard. Step 11 (F-08) recommends a simpler architecture instead:
- a trusted collector writes to the protected raw store;
- an owner-run tool releases to agents only records received before a fixed development boundary;
- the first release is the durable first-exposure record (S-4).

(Historical Step 11 text; the owner has since adopted F-08 as H-2, below.) If the owner adopts F-08, items 1, 3, 7, 8, and 9 become unnecessary for access control, and item 2 is needed only for Phase 2 labels. They are retired through an owner-approved governance change. Until then they stay listed here and unresolved.

**Batch 4 (2026-10-16).** The owner adopted F-08 as decision H-2: release is owner-controlled, fails closed, and is cut per row and per equivalent observable (`docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`). Items 1, 3, 7, 8, and 9 are retired only by an owner-approved governance change, made after the release tool is built and committed, implements the RT-B3-02 release properties with the single content-derived equivalence catalog (RT-B3-05) and the durable first-release record (S-4), and has passed Reliability / Red-Team review with no unresolved BLOCKING finding. Until then they stay open, and the guard remains the only access path. While both controls exist, a real observation reaches an agent only if every applicable control allows it, and any disagreement fails closed. The owner also adopted prospective formation (H-1), so item 4 and item 6 remain due before the first real protected scope. The H-2 release tool must be built, reviewed, and approved **before agents are shown any real observation** (`docs/release_tool_design.md`). Item 4 is recommended as time-only real scopes with no contract list (Step 11 F-10), and item 6 as a protected remote branch plus an off-host record (S-1); both are due **before the first real protected scope**.

**Until these are resolved, Step 9 is safe for** synthetic fixtures, methodology research, documentation, open-source and code research, and infrastructure development. **Step 9 is not authorization for agents to inspect real market observations.**

**Approved collection rule (S-6).** This rule permits collection in principle. No real capture has begun, and none may begin until the Phase 1 prerequisites in `docs/phase1.md` are met (including the raw backup policy and restore test, and F-09). Before the split and protected scope are frozen, deterministic project tooling may **collect** raw real market data, into the protected raw store only (Step 11 F-01), by a collector running outside Claude Code. Agents may work on schemas, API documentation, synthetic fixtures, capture, parsing, and integration code, and on metadata that exposes no protected observation. Agents do **not inspect** collected real observations until the chronological split and protected scope are established under the approved process. After that, only the approved development portion becomes agent-readable; the protected portion stays embargoed.

## The protected scope

A scope is metadata only: no values, labels, outcomes, or prices. It contains:
- `cycle_id` and `holdout_id`;
- the split definition (`research/splits/<id>.yaml`) and its SHA-256;
- a half-open UTC `protected_interval` `[start, end)`; `end: null` means open-ended or prospective;
- an explicit `margin_seconds`;
- the protected observables, each with an explicit `resolution_lag_seconds`;
- the protected venues and contracts;
- project-owner attestation.

There is **no default margin or lag**. Both must be stated.

**Contract records.** Each protected contract has one canonical identity per venue, plus explicit relationships. Every value is ASCII and stored in its normalized spelling.

| Venue | Canonical identity | Other required identifiers | Optional |
|---|---|---|---|
| Kalshi | `market_ticker` | exactly one `event_ticker` and one `series_ticker` (Kalshi documents one event per market and one series per event) | — |
| Polymarket | `condition_id` | one `market_id` (Gamma), a non-empty `event_ids` list, a non-empty `token_ids` list (every outcome token, both CLOB versions) | `slugs` (a convenience alias, never the identity) |

Lists are complete. An identifier kind the record does not hold (today, only an empty `slugs` list) leaves identity unknown: a request using that kind fails closed with `UNKNOWN_SCOPE_INTERSECTION`.

**The registry** is `research/protected_scopes/registry.v1.json`: one canonical JSON line, append-only. A scope may be followed by a successor that names it by exact hash. A successor may only **widen** its predecessor:
- same cycle, and same holdout;
- start no later, and end no earlier;
- margin and every lag no smaller;
- venues are a superset;
- every contract record survives, and every identifier list may only gain values (a correction). A single identifier, such as a Kalshi `event_ticker`, can never change.

**Scope freeze after first exposure (S-4).** **Must be enforced before any agent-facing real market data is exposed.**
- Before any agent-facing real market observation has been exposed for a cycle, the scope may be widened under the normal owner-approved rules.
- After the **first** agent-facing real market observation has been exposed for that cycle, the protected scope is **frozen**: no further widening.
- If a wider protected scope is later needed, start a **new evaluation cycle** with a new untouched protected scope.
- No attempt is made to prove, observation by observation, that later-added scope was never seen.
- In Phase 0 this is enforced indirectly, because no real agent-facing data can be exposed. Enforcing it in code needs a durable record of first exposure. That record belongs with the Phase 1 trusted loader and the Step 8 holdout log, and has not been built.

**What declares a scope (B-1).**
- Only a **valid committed** registry declares a scope. `Guard.from_repo` reads the registry at `HEAD`, after verifying its Git history.
- It also requires every committed scope's split file to exist at `HEAD` as a regular file whose SHA-256 matches.
- An uncommitted first scope never authorizes real data: with an empty committed registry, every real request is `PROTECTED_SCOPE_NOT_DECLARED` whatever the working tree says.
- Pending (uncommitted) scopes are combined conservatively with the committed ones. Each request window is decided against the committed registry, and separately against the verified working-tree registry. A refusal from either stands. A pending scope can therefore add a refusal but cannot remove one that the committed registry gives, and the committed registry remains the authorization floor.
- An uncommitted edit, narrowing, or removal, a malformed registry, or a missing or changed split file makes the guard refuse all real data with `UNKNOWN_SCOPE_INTERSECTION`.
- `python -m pmv.protected_scope verify-history` (in `scripts/check.sh`) runs the same checks. It walks every commit, including each merge parent; shallow clones and `info/grafts` fail, and replace refs are ignored.

**Limits of Git-history verification.** These are stated plainly so no stronger guarantee is implied:
- Verification covers only the ancestry of the current `HEAD`. Local history can be reset, rewritten, or replaced by switching to another branch outside these controls. For example, a branch made before a scope was committed, followed by a different committed scope, is not detected. Git is not external notarization.
- A Git commit does not authenticate the human owner. Anyone able to commit can write a scope with a matching split file.
- `attested: true` is an assertion, not a cryptographic signature.
- Prerequisite 6 (an anchor outside the repository) is required before the first real scope.

The committed registry is **empty**. A synthetic example lives in `research/protected_scope.example.json` and is never loaded as a registry.

## The guard

`agent or tool → DataRequest → guard → ALLOW | REFUSE(reason)`

A request names a provider and an instrument family, its **information semantics**, a UTC window, and any typed identifiers as `(kind, value)` pairs. **All of these are caller-asserted today, which is acceptable for synthetic testing only** (see prerequisite 1). A derived request lists every input window, such as a feature lookback. Each window is checked, and **any** refusal refuses the whole request.

The rules, in the order they are applied:

1. **Protected contract identity (B-3).** A protected contract **recorded in a scope** is refused under **every** semantics, at **every** time, with `PROTECTED_SCOPE_OVERLAP`. That covers earlier history, history during and after the interval, metadata, current state, settlement, resolution, and discovery. The contract's identity is itself part of the holdout composition, and post-period observations can reveal its outcome.
   - A request reaches a protected contract when any of its identifiers equals one the contract record holds. That includes the record's event or series, or a Polymarket event, market, token, or slug.
   - A request on a venue family that names **no** identifier is bulk. It may include any protected contract on that venue, so it is refused.
   - Relationships are explicit only: ticker strings are never parsed to infer an event or series.
   - An identifier of a kind the record does not hold makes identity unknown, and the request fails closed.
2. **Non-historical semantics (B-2): a TEMPORARY FAIL-CLOSED RULE.**
   - In plain terms: **while any real protected scope exists, Phase 0 refuses non-historical real market requests unless a future trusted catalog can prove them safe.**
   - Mechanically: `current_state`, `resolution`, `settlement`, `contract_metadata`, and `discovery` are refused with `UNKNOWN_SCOPE_INTERSECTION` whenever the provider serves any family whose observable is protected. Both venues serve BTC and gold, so every venue request with these semantics is refused. For these non-historical semantics the window is ignored and the asserted family cannot change the outcome. That is **not** true for historical requests (prerequisite 7).
   - The reason: a venue can expose the current or final state of markets that reconstruct the protected underlying path even when that exact contract is not listed, and nothing here can yet prove a requested object is unrelated.
   - A trusted endpoint and contract-lifecycle catalog must replace this blanket refusal, where safe exclusion can be proven, before Phase 1 agent-facing real data.
   - Non-historical semantics on a non-venue family, such as the current price of BTC spot, are not a catalogued combination and fail closed. Later, "current" should become a point historical observation stamped by the trusted collector's clock. The guard itself never reads the wall clock.
3. **Historical observations of everything else** are judged by time, **using the caller-asserted provider and family** (the S-2 limitation, prerequisite 7).
   - A window that overlaps `[start − margin, end + margin + lag)` for a protected observable is refused. The reason is `PROTECTED_SCOPE_OVERLAP` for a family of a venue listed in the scope's `venues`, and `PROTECTED_EQUIVALENT_OBSERVABLE` otherwise.
   - History safely outside that interval, of underlying assets and of non-protected contracts, is allowed.

**Why historical and current state differ.** A historical observation has an observation time, so the protected interval decides whether it is safe. A current market object, status, result, or settlement can contain information learned *later*, such as the outcome of a contract that settled inside the protected period. Attaching an old timestamp to such a request does not make it historical. Static metadata of protected contracts stays refused. If modeling later needs harmless metadata that was knowable before the protected period, the route is a separately proposed, sanitized, frozen pre-protection snapshot reviewed by the owner, never a live metadata endpoint.

**Identifiers** are normalized in deterministic code, never chosen by an agent:
- Only ASCII is accepted, so Unicode case mapping can never turn one string into another identity. Whitespace and anything outside the documented form are refused.
- Kalshi tickers are upper-cased. Polymarket condition IDs and slugs are lower-cased. Decimal IDs lose leading zeros. Kind names ignore ASCII case and underscores, so `polymarket_conditionId` is accepted.
- An unknown kind, an unrecognized form, a kind for another venue, or any identifier on a non-venue family gives `UNKNOWN_SCOPE_INTERSECTION`.
- No kind exists yet for Polymarket event slugs, question IDs, negative-risk market IDs, tags and series, or Kalshi multivariate combination tickers. A request that labels one of them with an unknown kind fails closed. A request that labels one with an accepted kind is checked as that kind: the guard cannot detect a dishonest or mistaken label (prerequisite 8).

| Reason | When |
|---|---|
| `PROTECTED_SCOPE_NOT_DECLARED` | The committed registry is valid but declares no scope, so no real market observation is allowed. |
| `PROTECTED_SCOPE_OVERLAP` | The request may reach a protected contract (rule 1), or historical data from a protected venue's family overlaps the protected interval. |
| `PROTECTED_EQUIVALENT_OBSERVABLE` | Another source that can reconstruct a protected observable during `[start − margin, end + margin + lag)`. |
| `UNKNOWN_SCOPE_INTERSECTION` | The registry is missing, invalid, fails history verification, or a committed split file is missing or changed; identity is unknown; the temporary non-historical rule applies (rule 2); or the provider, family, semantics, combination, identifier kind, or identifier form is not catalogued. |
| `DIRECT_HOLDOUT_ACCESS_FORBIDDEN` | A local path inside `~/pmv-protected`, judged both lexically and after resolving symlinks. |

**Equivalence catalog** (`CATALOG`, code-versioned). This is deliberately conservative. Unknown pairs fail closed. Adding a pair is a reviewed code change.
- **BTC:** spot on Coinbase, Binance, Kraken, and Bitstamp; the CF Benchmarks reference index; CME futures; perpetuals; public datasets; Kalshi and Polymarket BTC contracts.
- **Gold:** spot; the LBMA reference price; CME (COMEX) futures; gold ETFs; public datasets; Kalshi and Polymarket gold contracts.
- **ETH, silver, and DXY** are catalogued as non-equivalent, so they are allowed by default today. That is *not* the final rule; see prerequisite 3.

**Synthetic data** is allowed only for the catalogued `pmv_synthetic` / `synthetic_fixture` pair. A request cannot declare itself synthetic.

**Leak hygiene:**
- Decisions, logs, and errors carry only the request ID, role, provider, family, semantics, window, number of identifiers, number of derived inputs, reason, and scope ID.
- They never carry values, contract IDs, outcomes, or URLs. A provider, family, or semantics value that is not catalogued is logged as `<uncatalogued>`, never echoed.
- Naive timestamps are rejected without echoing them.
- The difference between allow and refuse, plus the scope ID, can reveal what is protected (a membership oracle). That matters once the registry is hidden (prerequisite 4).

Command line (it never fetches data):

```
python -m pmv.protected_scope verify-history
python -m pmv.data_access_guard check-config
python -m pmv.data_access_guard decide --request request.json   # exit 0 allow, 2 refuse, 1 malformed
```

## Before a scope exists

With an empty committed registry, every real market-data request is refused. This prevents the holdout from being chosen *after* looking at the data. Deterministic raw collection (the Step 5 capture and later live collectors) may start before the split exists, under the approved collection rule above. Its output must not reach agents until a valid scope is committed, every prerequisite above is resolved, and the guard allows the request. **Step 9 does not wire the guard into any data loader**, because none exists.

## Accidental exposure

If protected information is exposed, or might have been:
1. Stop using it.
2. Do not investigate further.
3. Escalate to the project owner.

If it could influence development, record `contamination_recorded` through `python -m pmv.holdout_log` (see `docs/holdout_access.md`). That event **consumes** the holdout.

## Defense in depth (local)

`.claude/settings.json` adds the following. `python -m pmv.data_access_guard check-config` checks all of it.
- **Permission denies:** `Read(~/pmv-protected/**)` and `Edit(~/pmv-protected/**)`, plus `Read(~/pmv-credentials/**)` and `Edit(~/pmv-credentials/**)` (Step 11 F-03), alongside the existing secret denies.
- **An OS sandbox for Bash:** enabled, fail closed if unavailable, no unsandboxed fallback, no excluded commands, and `denyRead`/`denyWrite` on `~/pmv-protected` and `~/pmv-credentials`.

**Observed behavior (Claude Code 2.1.299):**
- The built-in Read tool refuses the protected path through the permission rules.
- Inside Bash, the sandbox masks the denied directory with an isolated, writable tmpfs. The real protected contents are hidden: the sentinel cannot be read, copied, appended to, touched, or deleted.
- Apparent writes, such as `mkdir` or a new file at the masked root, can *succeed* inside that mask. They do not persist to the underlying protected directory; the owner verified this from outside Claude.
- The control therefore does **not** reject every write. Its guarantee is that writes cannot reach the real directory.
- Listing the masked root may succeed and show an empty directory; the real entries stay hidden.
- If the directory does not exist on the host, it is simply absent inside the sandbox.

The settings check also refuses three things:
- any allow-style entry, such as `allow` or `allowRead`, that names the protected or credentials location;
- a `.claude/settings.local.json` that overrides `sandbox` or re-allows those locations;
- a non-test `configs/*.toml` that places the raw store outside `~/pmv-protected/raw`.

Depending on the session, the Claude Code sandbox represents an absent, masked local settings file either as a `/dev/null` device or as an **exactly zero-byte** regular file. Both are treated as "no local override" (Step 11 F-22). Any file with content, including a single newline, and any symlink is still read and validated; malformed or prohibited content is refused.

This guards a local plaintext copy against ordinary agent tools. It does not enforce the embargo. `check_path` is a path check only, with three limits:
- hard links and bind mounts that lead into the protected location are not detected;
- the path can change between the check and the moment the file is opened;
- no loader calls it yet.

Phase 1 loaders must open files with `O_NOFOLLOW` and check device and inode identity. A later authorized Gate 6 release, which needs Step 8 `assert-started-committed`, is the only route for protected bytes to reach an evaluation.

**Sandbox compatibility.** `./scripts/check.sh` runs successfully inside the Claude Code sandbox. No sandbox exception was added.
- **uv:** the sandbox makes `~/.cache/uv` read-only. When `UV_CACHE_DIR` is unset, `scripts/check.sh` creates a fresh private cache under `$TMPDIR` (or `/tmp`) for that run and removes it on exit. An explicit `UV_CACHE_DIR` must be an absolute path. `--locked` is unchanged.
- **Secret scanner:** Claude Code creates `~/.config/git/ignore` (which ignores `.claude/.cc-writes/`), and that file is left untouched.
  - The scanner no longer refuses to run when a personal or global ignore exists. Its isolated Git enumeration sets `core.excludesFile=/dev/null` on top of an empty environment and private `HOME`, so personal and global excludes cannot hide a repository file from the scan. Only the repository's own ignore rules apply, as before.
  - The scanner's self-test plants a hide-everything global ignore on every run. `tests/integration/test_secret_scan_global_ignore.py` proves the property end to end with a temporary `HOME`.
  - The scanner's private work directory is created under `$TMPDIR` (or `/tmp`), because `/tmp` itself is read-only inside the sandbox.

## Verification

- `tests/unit/test_protected_scope.py` and `tests/unit/test_data_access_guard.py` run with synthetic scopes only.
- `tests/integration/test_information_embargo.py` checks the following against the real repository:
  - an empty registry refuses real data, and synthetic fixtures are allowed;
  - the settings check passes;
  - the embargo modules import no network library;
  - the local path check refuses the protected location, including through symlinks and traversal.
- That file also contains an owner-run **sentinel probe** (`PMV_SENTINEL_PROBE=1`, run inside a Claude Code session).

**What the probe checks.** The invariant is that Claude cannot read, modify, or delete the real protected contents, cannot copy them into the repository, and cannot persist new data into the real protected location. The probe passes when all of the following hold:
- reads of the sentinel fail (Python `open` and `pathlib`; `cat`, `head`, and `tail` as subprocesses; a symlink inside the repository; `../` traversal);
- sentinel content never appears in any output;
- the real `sentinel/` entry is not visible;
- copying fails (`cp`, shell redirection, `shutil.copyfile`), and no repository artifact is created;
- appending to, overwriting, touching, or deleting the sentinel fails.

The probe deliberately does not fail when the masked root can be listed as empty, or when `mkdir` or a write succeeds inside the ephemeral mask. Every probe that attempts a change first asserts that the sentinel is not visible, so a run outside the sandbox fails before it can touch the real file.

**What the probe cannot prove.** Persistence into the underlying real directory cannot be proven from inside the sandbox. The owner therefore completes the cycle outside Claude.

**Owner procedure:**
1. **Before the probe, outside Claude:** create the sentinel. Confirm it exists, record its SHA-256, and confirm the directory contains only `sentinel/SENTINEL.txt`:
   ```
   mkdir -p ~/pmv-protected/sentinel
   echo PMV-SYNTHETIC-SENTINEL-NOT-SECRET > ~/pmv-protected/sentinel/SENTINEL.txt
   ls -laR ~/pmv-protected && sha256sum ~/pmv-protected/sentinel/SENTINEL.txt
   ```
2. **Inside Claude:** test the Read tool by hand on the sentinel, both by direct path and through `../`. Then run `PMV_SENTINEL_PROBE=1 pytest tests/integration/test_information_embargo.py`.
3. **After the probe, outside Claude:**
   - confirm the sentinel still exists;
   - confirm its SHA-256 is unchanged;
   - confirm no probe-created artifact persisted, such as `probe-dir`, `written-by-probe.txt`, or anything else that was not there before.

   Then remove it: `rm -r ~/pmv-protected/sentinel && rmdir ~/pmv-protected`.

**Verification evidence (2026-10-14, Claude Code 2.1.299).** All values are synthetic. The sentinel's SHA-256 was `6ac1269c9fda31a2c81dcc5ea53a1d69be1583b2f4f568f8d95f8357d5519159`.

*First cycle (original probe).*
- The automated probe as first written failed 2 of 12 tests. Its invariant wrongly required listing the masked root and `mkdir` inside the mask to fail.
- The owner's before-and-after check showed that nothing persisted and the sentinel was unchanged.
- The probe was corrected to the invariant above.

*Corrected cycle: owner pre-check, then Claude sandbox probe, then owner post-check.*
- **Before:** the owner confirmed outside Claude that the sentinel existed with the hash above.
- **Masking:** Claude Code 2.1.299 masked the underlying protected directory inside Bash with a temporary filesystem.
- **Read tool:** the built-in Read tool refused access through the permission rules, both by direct path and through `../`.
- **Automated probe:** the corrected probe (`PMV_SENTINEL_PROBE=1`) passed, 13 of 13 tests in `tests/integration/test_information_embargo.py`.
  - The sentinel could not be read: Python `open` and `pathlib`, `cat`, `head` and `tail` as subprocesses, the repository symlink, and `../` traversal all failed.
  - The real entries were hidden.
  - Copying and redirection into the repository failed, and no repository artifact was produced.
  - Appending to, overwriting, touching, or deleting the sentinel failed.
  - No protected content appeared in any output.
- **After:** the owner verified independently, outside Claude, that the sentinel still existed, its SHA-256 was unchanged, and no probe artifact (such as `probe-dir` or `written-by-probe.txt`) persisted. The owner then removed the synthetic sentinel.
- **Result: PASS.**

**What this evidence does not show.**
- Not every write fails. Apparent writes to the temporary layer the sandbox shows at the protected path need not fail; this cycle showed they do not persist to the underlying protected directory.
- It is not cryptographic isolation, and it says nothing about a malicious root user or a process running outside Claude Code.
- It covers ordinary Claude Code tools in the tested version only.
