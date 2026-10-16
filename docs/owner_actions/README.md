# Owner Actions: Patches Agents Cannot Apply

Agent sessions cannot write `.claude/agents/` or `.claude/settings.json`. Both are governance files, and the sandbox makes them read-only. This directory holds patches that the owner applies from a normal terminal, plus the procedure to validate each one. A patch here is a proposal until the owner applies and commits it.

**Owner basis:** batch 4 owner rulings, 2026-10-16 (`docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`, "Owner actions outside the sandbox").

| Patch | Purpose | Blocks |
|---|---|---|
| `2026-10-16_agents_split_wording.patch` | Replaces the literal "oldest ~70% / newest ~30%" split wording in six agent files with the prospective-holdout wording | Not blocking (the CLAUDE.md definition governs), but fresh agents read these files first. The owner directed the fix |
| `2026-10-16_settings_f09_host_class_denies.patch` | Adds deterministic F-09 host-class WebFetch denies | **Priority blocker.** Required before the first historical acquisition (A-1), Phase 1 real collection, and any agent web research after a cycle's `T0 − m` |

Both patches were generated against commit `a1752b4`. On 2026-10-16 both were re-checked on B06 (`b06/governance-continuity-sync`): each passes `git apply --check`; the agents patch leaves no stale split term; and the settings patch yields valid JSON. If either target file changes later, `git apply --check` fails, and the patch must be regenerated, not forced.

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
