# Owner Actions: Patches Agents Cannot Apply

Agent sessions cannot write `.claude/agents/` or `.claude/settings.json`. Both are governance files, and the sandbox makes them read-only. This directory holds patches that the owner applies from a normal terminal, plus the procedure to validate each one. A patch here is a proposal until the owner applies and commits it.

**Owner basis:** batch 4 owner rulings, 2026-10-16 (`docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`, "Owner actions outside the sandbox").

| Patch | Purpose | Blocks |
|---|---|---|
| `2026-10-16_agents_split_wording.patch` | Replaces the literal "oldest ~70% / newest ~30%" split wording in six agent files with the prospective-holdout wording | Not blocking (the CLAUDE.md definition governs), but fresh agents read these files first. The owner directed the fix |
| `2026-10-16_settings_f09_host_class_denies.patch` | Adds deterministic F-09 host-class WebFetch denies | **Priority blocker.** Required before the first historical acquisition (A-1), Phase 1 real collection, and any agent web research after a cycle's `T0 − m` |
| §3 (no patch; owner terminal steps) | B10-D10 live-host removal from both egress layers (B10-D6 credential rotation: resolved by control hardening, no action) | **Required before any cycle's `T0 − m`**, not before B10 closure (owner correction, 2026-10-19). The refusal test must pass before any `T0 − m` |
| Proposed START_HERE.md P-5 (no patch yet; governance edit) | Add to the mandatory pre-T0 checklist: (a) both egress layers tightened, with the §3 step 4 Layer B check and the step 5 refusal test (all 10 checks passed) recorded; (b) every allowlist entry in both layers classified by host class, with live-data, live-display, and protected-observable hosts removed or justified (the refusal test passing is necessary, not sufficient); (c) owner confirmation or rejection of the egress test's in-memory proxy-authentication carve-out | **Pending owner approval** to edit START_HERE.md. Until then the requirement binds through `docs/decisions/2026-10-19_b10_source_reconnaissance.md` and `docs/external_access.md` §1.4 |

Both patches were generated against commit `a1752b4`. On 2026-10-16 both were re-checked on B06 (`b06/governance-continuity-sync`): each passes `git apply --check`; the agents patch leaves no stale split term; and the settings patch yields valid JSON. If either target file changes later, `git apply --check` fails, and the patch must be regenerated, not forced.

**Status (2026-10-16): both patches applied.** The owner applied and committed both on B06 in `8517fc2`; `git apply --reverse --check` passes for each. Validation in a new session started at `8517fc2`: no stale split term in `.claude/agents/`; `.claude/settings.json` is valid JSON; `check-config` reports "protected-information settings verified"; `./scripts/check.sh` passes; and the §2 behavioral check passed (all four synthetic `example.com` hosts were refused by a WebFetch deny rule, not by a DNS or connection error, and the `code.claude.com` positive control loaded). The refusal message names the denied domain, not the matched pattern. The procedures below are kept as the record of how the patches were applied and validated. Applying them satisfies only the F-09 part of G-7: A-4 is still not satisfied, and acquisition is still not authorized (`docs/acquisition_readiness.md`).

**Where to apply.** Apply on the current active ground-truth branch (`docs/BRANCH_TIMELINE.md`), not on `main` or an older branch, so the change joins that branch's pull request.

## 1. Agent-file split wording

**Changes.** `data-scientist.md`, `ml-engineer.md`, `statistician.md`, `independent-statistical-auditor.md`, `reliability-red-team.md`, `risk-performance-engineer.md`:
- the literal split lists become: historical development data in chronological train/development partitions; the protected holdout is a prospective interval from a declared `T0` for the first cycle (preferred thereafter), never the newest share of an already-exposed historical dataset; and no exposed period is ever promoted into a holdout;
- "the development 70%" becomes "the development pool";
- "the protected final 30%" becomes "the protected holdout".

**Apply and validate** (from the repository root, on the current active ground-truth branch in `docs/BRANCH_TIMELINE.md`, in a normal terminal):

```bash
git apply --check docs/owner_actions/2026-10-16_agents_split_wording.patch
git apply docs/owner_actions/2026-10-16_agents_split_wording.patch
# No stale split terms remain (expected output: nothing):
grep -rnE "approximately (70|30)%|development 70%|final 30%" .claude/agents/
./scripts/check.sh
git add .claude/agents/data-scientist.md .claude/agents/ml-engineer.md .claude/agents/statistician.md \
        .claude/agents/independent-statistical-auditor.md .claude/agents/reliability-red-team.md \
        .claude/agents/risk-performance-engineer.md
git commit -m "Align agent files with the prospective-holdout split wording (batch 4)"
```

## 2. F-09 host-class denies in `.claude/settings.json`

### Verified permission semantics

Verified on 2026-10-16 against the official Claude Code documentation, retrieved as raw Markdown. These are the SHA-256 hashes of the retrieved bytes:
- `https://code.claude.com/docs/en/permissions.md`: `6a5645eccd12331ec4f0867ee7bbac42446c3f506d974021b260f5dfeb3efd75`;
- `https://code.claude.com/docs/en/sandboxing.md`: `f3feed627e09b91db74255475a605fd692a80e48b6b05be20b0b0b3efbfb378e`.

| Fact | Verbatim source |
|---|---|
| Rule form is `WebFetch(domain:<host>)`, matched against the hostname | "WebFetch rules use a `domain:` prefix and match against the hostname of the requested URL." (permissions) |
| An exact rule does not cover subdomains | "`WebFetch(domain:example.com)` matches requests to `example.com` only." (permissions) |
| A leading `*.` covers every depth, but not the apex | "`WebFetch(domain:*.example.com)` matches any subdomain at any depth … but not `example.com` itself" (permissions) |
| Any other `*` matches exactly one label | "In any position other than a leading `*.` or a bare `*`, the wildcard matches only the text between two dots." (permissions) |
| Wildcards need a minimum version | "Wildcards in `WebFetch` rules require Claude Code v2.1.172 or later to match fetches." (permissions) |
| Deny always beats allow | "Rules are evaluated in order: deny, then ask, then allow." and "An allow rule can't carve an exception out of a deny rule." (permissions) |
| `domain:` rules also reach the Bash sandbox, but only exact or leading `*.` forms | "In a `WebFetch(domain:...)` rule, the sandbox honors two wildcard forms: a leading `*.` … and a bare `*`. … A wildcard in any other position … still matches fetches but has no effect on sandboxed commands." (sandboxing) |
| Project deny rules apply without trust approval | "`deny` and `ask` rules aren't affected, since they only restrict." (permissions) |

**Not documented, so not relied on:**
- path-based WebFetch rules (the docs say rules cannot match the `url` field);
- WebSearch domain rules (WebSearch can only be denied as a whole);
- whether WebFetch permission checks apply to redirect targets.

`docs/external_access.md` §1.1 rules 8–10 (path patterns, data files on generic hosts, redirects) therefore remain **rule-governed**.

### Design (narrowest correct)

- **Layer A: prefix classes, WebFetch only.** `api`, `*-api`, `clob`, `ws`, `ws-*`, `stream`, `rpc`, `*-rpc`, each followed by one, two, or three single-label wildcards. For example, `api.*.*.*` matches `api.exchange.bullish.com`, the batch 3 near miss. These patterns do **not** reach Bash; the docs say so.
- **Layer B: named hosts, WebFetch and the Bash sandbox.** Exact or leading-`*.` rules for:
  - venue trading, live-data, and live-display hosts (`kalshi.com`, `www.kalshi.com`, `api.elections.kalshi.com`, `trading-api.kalshi.com`, `demo-api.kalshi.co`, `polymarket.com`, `www.polymarket.com`, `clob.polymarket.com`, `gamma-api.polymarket.com`, `data-api.polymarket.com`);
  - the batch 3 incident and live-value hosts;
  - `cfbenchmarks.com`, whose site terms bar automated access.
- **Deliberately not denied:**
  - documentation hosts such as `docs.kalshi.com` and `docs.polymarket.com`. A deny can never be overridden by an allow, so `*.kalshi.com` would block approved documentation;
  - generic `data.*` and `assets.*` prefixes, which would permanently block unrelated open-data documentation with no possible exception;
  - WebSearch. Before `T0 − m`, search is governed by `docs/external_access.md` §1.6.
- **Not exhaustive.** Layer B covers known hosts only. Unlisted hosts remain governed by the host-class rule and the sandbox proxy allowlist.

### Apply and validate

```bash
claude --version            # must be v2.1.172 or later for wildcard WebFetch rules
git apply --check docs/owner_actions/2026-10-16_settings_f09_host_class_denies.patch
git apply docs/owner_actions/2026-10-16_settings_f09_host_class_denies.patch
python3 -m json.tool .claude/settings.json > /dev/null && echo json-ok
uv run --locked python -m pmv.data_access_guard check-config   # expect: protected-information settings verified
./scripts/check.sh
git add .claude/settings.json
git commit -m "Commit F-09 host-class WebFetch denies (batch 4)"
```

**Behavioral check, in a new Claude Code session started after the commit.** None of these hosts is a market-data source. `example.com` subdomains are reserved by IANA and serve no market data. Ask Claude to fetch each URL with WebFetch and record the result:

| URL | Expected |
|---|---|
| `https://api.validation.example.com/` | refused by a deny rule (`api.*.*.*`) |
| `https://zz-api.example.com/` | refused by a deny rule (`*-api.*.*`) |
| `https://ws.example.com/` | refused by a deny rule (`ws.*.*`) |
| `https://rpc.example.com/` | refused by a deny rule (`rpc.*.*`) |
| `https://code.claude.com/docs/en/permissions.md` | allowed (positive control) |

A refusal must name the deny rule. A DNS or connection error instead of a rule refusal means the wildcard did not match: stop and report it. Do not test with any real venue, exchange, or data host.

### Later: fail-closed WebFetch from `T0 − m` (E-B4-4)

No allowlist-default mode exists in the deny/allow rules: deny beats allow, so `deny: ["WebFetch"]` plus allow rules blocks everything. The documented options are:
- `defaultMode: "dontAsk"` ("Auto-denies every call that would otherwise prompt"), with `WebFetch(domain:…)` allow rules for the owner-listed hosts. This affects every tool, not just WebFetch;
- `sandbox.network.strictAllowlist`, which covers Bash only and can be set only in user, managed, or CLI settings, not project settings;
- a bare `WebSearch` deny.

The mechanism is chosen and committed before `T0 − m`, as part of cycle preparation.

## 3. B10-D10 and B10-D6: live-host removal and proxy credential rotation (owner, 2026-10-19)

**Status (owner correction, 2026-10-19; `docs/decisions/2026-10-19_b10_source_reconnaissance.md`, "Owner correction: runtime-secret hardening"):**
- **B10-D6 is resolved by control hardening.** The exposed credential was not a PMV Squid credential. It was most likely injected by the Claude sandbox/runtime networking layer; its issuer and lifetime are not proven. `pmv-egress-proxy` has no authentication configuration, and there is no PMV password to rotate. Step 3 is superseded and kept for the record.
- **B10-D10 removal (steps 1, 2, 4, 5) is not required to close B10.** It is required before any cycle's `T0 − m` / protected evaluation. Live and public market hosts may stay available during explicitly authorized development or reconnaissance.
- Diagnostics follow the permanent rule in `docs/conventions.md`, "Diagnostics and Runtime Secrets".

**Why the owner must do this.** Both network layers, and the proxy credential, are outside what an agent session may change:
- **Layer A**, the Claude Code sandbox allowlist, is `sandbox.network.allowedDomains` in `/etc/claude-code/managed-settings.json`. The sandbox makes it read-only.
- **Layer B** is the PMV egress proxy outside the container.
- **The proxy credential** is the one injected into sandboxed processes as `HTTPS_PROXY`/`CLOUDSDK_PROXY_*`, at `localhost:3128`. **Its issuer is unverified** (outer PMV egress proxy, or the Claude Code sandbox runtime; see step 3). Either way, agents cannot rotate it. *(Superseded 2026-10-19: the owner verified that the PMV egress proxy has no authentication, which rules out the first option; see the status above.)*

The repository holds no agent-runnable rotation procedure. Agents must not try to widen, edit, or route around either layer (`docs/backup_and_recovery.md`).

**State found on 2026-10-19 (B10 follow-up):**
- Layer A lists `api.kraken.com`, `ws.kraken.com`, and `api.exchange.coinbase.com`. It also lists `exchange.coinbase.com`, which B10 never used; removing it is recommended, but it is not part of B10-D10.
- All three hosts answer `HTTP/1.1 200 Connection Established` through the sandbox proxy.
- `tests/integration/test_live_host_egress_refusal.py` therefore fails 4 checks: the Layer A static check and three refusal probes. Its other 4 checks pass. Refusal detection was confirmed against a host that is already refused (`api.elections.kalshi.com` → `403 Forbidden`).

**Steps, from a normal terminal outside Claude Code:**
1. **Layer A.** Remove `api.kraken.com`, `ws.kraken.com`, and `api.exchange.coinbase.com` (and, recommended, `exchange.coinbase.com`) from `sandbox.network.allowedDomains` in `/etc/claude-code/managed-settings.json`. Keep the documentation hosts `docs.kraken.com`, `support.kraken.com`, and `docs.cdp.coinbase.com`, and the other documentation and research hosts. **For owner disposition (optional; not B10-D10 scope; review RT2-B10-m4):** Layer A also lists data-class or file hosts that an allowlist entry admits despite wildcard denies: `hist.databento.com`, `datamine.cmegroup.com`, `raw.githubusercontent.com` (the B10 fixture-deviation route), `codeload.github.com`, and `api.github.com`. Consider removing or narrowing them. Validate with `python3 -m json.tool /etc/claude-code/managed-settings.json > /dev/null`. Recommended (defense in depth, review API2-B10-m4): make the file root-owned (`sudo chown root:root …; sudo chmod 644 …`). It is currently owned by the agent user with mode 644, so it is read-only to agents only because of the sandbox deny list.
2. **Layer B.** Remove the same hosts from the PMV egress proxy allowlist. Keep the same documentation hosts. Restart the proxy.
3. **B10-D6 (superseded 2026-10-19: resolved by control hardening; no action).** First confirm which component issues the credential. Its `srt.` username prefix suggests the Claude Code sandbox-runtime proxy, possibly minted per session, rather than the outer PMV egress proxy (review API2-B10-m5). If it is per-session, rotation means ending every session that saw it (the B10 lead session and the API/Execution re-review session) and confirming that the old value is invalid. Otherwise, rotate the credential with the issuing proxy's own tooling, then restart the container or session so that the new value is injected. Never paste the new credential into a Claude session, a file under `/workspace`, or a commit.
4. **Layer B alone,** outside the Claude sandbox, in the container shell. Use a CONNECT-only probe, so that no TLS handshake or application request ever reaches a live host, and read the **proxy's** status line. Do not use `curl %{http_code}`: a refused CONNECT shows `000` there, and if a host were still allowed, an origin's own 403 or 404 could be mistaken for a refusal (review API2-B10-01). The probe targets the unauthenticated PMV route `pmv-egress-proxy:3128` (owner-verified, 2026-10-19) directly. It reads no proxy variable and sends no credential. *(Revised 2026-10-19: the earlier snippet read the proxy URL from the environment and built a `Proxy-Authorization` header from it. Layer B needs no credential, so the revised snippet handles none. Whether in-memory transmission to the issuing proxy is acceptable under the permanent diagnostic rule awaits owner confirmation; see the decision record, "Applied".)*
   ```bash
   python3 - <<'PY'
   import socket
   PROXY = ("pmv-egress-proxy", 3128)  # Layer B, unauthenticated
   for h in ["api.kraken.com", "ws.kraken.com", "api.exchange.coinbase.com", "docs.kraken.com"]:
       try:
           with socket.create_connection(PROXY, timeout=15) as s:
               s.sendall(f"CONNECT {h}:443 HTTP/1.1\r\nHost: {h}:443\r\n\r\n".encode())
               print(h, s.recv(4096).split(b"\r\n", 1)[0].decode("latin-1"))
       except OSError as exc:
           print(h, "connection-error:", type(exc).__name__)
   PY
   ```
   Expected: `200 Connection Established` for the `docs.kraken.com` control, and a `403` policy refusal for each prohibited host. If the control line is not `200`, the run is invalid: the probe did not get through Layer B. With a valid control:
   - any `200` for a prohibited host is a failure;
   - a 5xx (for example a DNS or upstream error) does not prove a policy denial; record it as "refused, unconfirmed";
   - an empty line or a connection error for a prohibited host is also "refused, unconfirmed".

   A `407` means Layer B unexpectedly requires authentication: stop and investigate, and do not add credentials to the probe. **Never print, echo, or inspect proxy variables, proxy URLs, or `GIT_SSH_COMMAND` in a Claude session** (`docs/conventions.md`, "Diagnostics and Runtime Secrets"): a partial redaction leaked the runtime credential twice in B10.
5. **Both layers,** in a new Claude Code session on the current active branch (`docs/BRANCH_TIMELINE.md`), before any cycle's `T0 − m`:
   ```bash
   PMV_EGRESS_PROBE=1 uv run --locked pytest tests/integration/test_live_host_egress_refusal.py -q
   ```
   Expected: 10 passed (8 at B10 `ba1fa9e`; the round 3 hardening added two offline checks).
   - The Layer A static check reads `managed-settings.json`, including wildcard entries.
   - Three CONNECT probes must be refused, each with an in-test proxy-path control.
   - Four offline self-checks pass (host list, matcher, 403-only refusal pattern, malformed-proxy redaction), and two documentation-host positive controls pass.

   Never run it with `-l`/`--showlocals`.

   A refusal here alone does not prove Layer B; step 4 does.
6. Report the step 4 and step 5 results to the session, so that they can be recorded in `docs/decisions/2026-10-19_b10_source_reconnaissance.md`. These steps change no repository file.

**Standing requirement.** The step 5 test must pass before any cycle's `T0 − m` (owner decision B10-D10). Future prospective capture runs in the separately chartered cloud capture environment, not in the Claude development sandbox.
