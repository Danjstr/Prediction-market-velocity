# B10: data source reconnaissance (2026-10-19)

**Approver:** the project owner, in the "PMV B10 — DATA SOURCE RECONNAISSANCE" batch charter issued on 2026-10-19 in the isolated environment, after B09 was merged by PR #8. The development session wrote this record. It is procedural: the system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

**This is not a gate record, an acquisition approval, a licence determination, or a capture approval.** It records the charter, what the reconnaissance did, its results, and the issues it surfaces. It changes no production code, control, holdout rule, or governance document.

Results:
- `research/data_sources/source_feature_value_matrix.md`;
- `research/data_sources/source_redundancy_decisions.md`;
- `research/data_sources/schema_profiles/` (19 profiles);
- `research/data_sources/recon_tools/` (four standard-library recon scripts; development only);
- `research/governance/b10_reviews.md` (Statistician, API/Execution Engineer, and Reliability/Red-Team reviews, with dispositions). All three found no BLOCKER; every MAJOR finding is fixed in the documents or assigned to an owner decision above.

## Charter

### Goal (verbatim)

> Determine the smallest non-redundant set of market-data sources needed for PMV before we perform bulk acquisition or build source-specific cloud connectors.
>
> More sources are NOT automatically better.
>
> We want maximum non-redundant information per dollar and engineering hour.

### Owner authorization (verbatim, charter §1)

> The owner authorizes bounded READ-ONLY source reconnaissance using the existing PMV sandbox network allowlist.
>
> The allowlist has already been updated and the PMV egress proxy restarted.
>
> Permitted:
>
> - official vendor documentation;
> - public API documentation;
> - public schemas;
> - official sample files;
> - tiny bounded OLD historical samples;
> - public market-data endpoints;
> - metadata/contract definitions;
> - estimator/schema inspection.
>
> Not permitted:
>
> - bulk historical acquisition;
> - purchases;
> - payment actions;
> - account changes;
> - order placement;
> - real-money trading;
> - authenticated trading APIs;
> - trading-capable credentials;
> - prospective protected observations;
> - protected holdout observations.
>
> Do NOT modify the sandbox network configuration.
>
> Do NOT attempt to bypass the PMV egress proxy.

### Sample limits (verbatim, charter §4–§5, extract)

> Default limits:
>
>     <= 10 MB per source/schema
>     <= 5,000 rows for row-oriented datasets
>
> Use deliberately OLD development intervals.
>
> For event/order-book streams, retrieve only enough consecutive messages to determine message semantics.
>
> Every actual observation inspected during B10 is permanently DEVELOPMENT-EXPOSED and can never become protected holdout data.

> Do NOT push raw vendor samples to GitHub unless the governing terms clearly authorize that form of repository storage/redistribution.

Other charter points:
- **Branch:** create `b10/source-reconnaissance` directly from final B09 `8b4e026`, not from the `main` merge commit.
- **Stop:** do not merge, do not create B11, no bulk acquisition, no cloud provisioning.
- **Connectivity:** if a required host is blocked, stop that source and report the hostname.

## Designation

The charter calls B10 "the next numbered cumulative development batch" and directs its creation from final B09. B10 is therefore recorded as the current active ground-truth branch (`docs/BRANCH_TIMELINE.md`), following the B08 and B09 precedents. B09 is a historical checkpoint, preserved, merged by PR #8 (`bbcdd6b`).

## Continuity verified (2026-10-19, before the first B10 commit)

After `git fetch origin` (`origin/main` advanced `a6b5411..bbcdd6b`):
- `git cat-file -t 8b4e026` returned `commit`;
- `git merge-base --is-ancestor 8b4e026 origin/main` returned 0;
- `origin/b09/kalshi-source-qualification` exists at `8b4e0261fad30f978fac19c6d81d11b7334d0c97`;
- `git switch --detach 8b4e026; git switch -c b10/source-reconnaissance`; `git rev-parse HEAD` = `8b4e0261fad30f978fac19c6d81d11b7334d0c97`; `git merge-base --is-ancestor 8b4e026 HEAD` returned 0;
- no `b10/*` branch existed on `origin`.

## How the charter was applied alongside existing rules (surfaced, not silently resolved)

| Existing rule | Tension with the charter | How B10 applied it | Owner action |
|---|---|---|---|
| CLAUDE.md Host-Class Rule: "historical data files are fetched only by deterministic project tooling into the protected raw store … never into agent context"; class 1: real historical observations are agent-visible only after per-row release; `docs/external_access.md` §1.1 rule 9 | The charter expressly permits "tiny bounded OLD historical samples" and "official sample files" for agent inspection | Treated as a **narrow, explicit owner exception for B10 reconnaissance only**. Samples were bounded (≤ 5,000 rows, ≤ 10 MB), old where the endpoint allowed, kept only in git-ignored `.recon_tmp/`, then deleted. Every inspected period is registered as development-exposed (exposure rows X-7 to X-11). Nothing acquired enters the raw store or any development dataset | Confirm that the charter was intended as this exception (B10-D1) |
| CLAUDE.md class 4 and `docs/external_access.md` §1 `live-data` row: live observations need a charter that authorizes them "for that host, purpose, and observable family"; `api.kraken.com/0/public/` is `live-data` class under §1.1 rules 1 and 8 | The charter says "public market-data endpoints" and allows stream messages "to determine message semantics", but names **no host and no observable family** (review RT-B10-02) | One live Kraken WS capture (200 messages, about 30 s) and one old REST `Trades` pull (5 pages), both BTC, for schema verification. No cycle or `T0` exists, so class 3 is not engaged. Registered as X-7 and X-8. The values are not development data. Beyond schema verification, the profiles record derived activity statistics (spacing, lag, counts) of these samples, which arguably exceeds the authorized purpose (review RT-B10-06) | Confirm that the charter covered `api.kraken.com` and `ws.kraken.com` for BTC, for schema verification (B10-D1). Future charters name hosts and families |
| Terms-first (`docs/external_access.md` §1.1 rule 3; rule 6 requires it in every agent brief); D-B09-17(a) pending | Kalshi, Kraken, Polymarket, Pyth, and Coinbase terms live on refused hosts | Documentation hosts were read under the charter's "official vendor documentation; public API documentation". **Terms were not read for any of these vendors**, so "no terms bar observed" means only that none was seen, not that terms-first was satisfied (review RT-B10-03). The B10 common agent brief stated the host-class rule but **omitted the terms-first rule** (a rule-6 deviation) | D-B09-17(a) stays the owner's (B10-D2). *As at `05df35a`; superseded by the owner ruling on B10-D2 below* |
| Kraken data under a known permission posture | Kraken's API notice requires prior permission for non-personal commercial use of public market data (M2 pending; `owner_source_action_sheet.md` B1/B2). B10 fetched Kraken REST and WS data without reading those terms (RT-B10-03) | Two bounded requests for schema verification only, under the charter | No further Kraken data request of any kind until M2 is answered (B10-D11). *As proposed at `05df35a`; rejected and replaced by the owner (see B10-D11 below): Kraken bulk acquisition waits for a published-terms snapshot and classification, not for correspondence* |
| `docs/external_access.md` §1.1 rules 9 and 11: every `raw.githubusercontent.com` URL is `hist-data` or `unknown`, and agents do not fetch it | The Databento research agent fetched eight `.dbn` test fixtures from the `databento/dbn` repository (real market data: E-mini S&P 2020-12-28, a US equity, CME options, one unidentified CME instrument from 2023-04-23). It also fetched Rust and Python **source files** from `databento/dbn` and `CMEGroupPublic/datamine_python` via `raw.githubusercontent.com` (review RT-B10-04) | The fixtures were treated as the charter's "official sample files"; repository test fixtures are not designated vendor sample files, so this is an interpretation. The source-file fetches are an undisclosed-in-draft rule-9 deviation, now disclosed. Fixtures deleted; registered as X-11 | Confirm that repository test fixtures count as "official sample files" (folded into B10-D1) |
| Network control: F-09 wildcard host-class denies (`api.*`, `ws.*`, …) mirrored in the sandbox deny list | `api.kraken.com`, `ws.kraken.com`, and `api.exchange.coinbase.com` were **reachable** although they match `api.*.*`, `ws.*.*`, and `api.*.*.*` (review RT-B10-01). Only exact-named hosts were refused as "on the deny list"; other refusals came from the allowlist. No sandbox bypass occurred (no `allowed_domains`, no sandbox-disable flag). So the wildcard class denies are **not an effective network backstop** once the owner allowlists a host: the embargo on live BTC hosts rests on the allowlist and agent discipline | Recorded here. Kraken WS is a direct equivalent observable for BTC, so this becomes BLOCKING before any cycle's `T0 − m` | Revert the allowlist entries for `api.kraken.com`, `ws.kraken.com`, and `api.exchange.coinbase.com` when B10 closes, and add a deterministic egress check (pre-`T0` checklist) asserting that live-data hosts are refused (B10-D10) |
| Cloud-native decision (2026-10-18): the Chromebook must not hold bulk data | Temporary samples sat in `/workspace/.recon_tmp/` | About 411 KB in total (339,000 + 62,136 bytes, plus about 10 KB of fixtures), deleted after inspection; small metadata only | None |

## What B10 did

### Connectivity (first pass, HEAD requests, before any sample)

| Source | Host | Result |
|---|---|---|
| Kalshi | `docs.kalshi.com` | 308 → `docs.kalshi.com/welcome` (same host), then 200 |
| Kalshi | `api.elections.kalshi.com` | **BLOCKED** (sandbox deny list) |
| Kalshi | `kalshi.com` | **BLOCKED** (deny list) |
| Kraken | `api.kraken.com` | reachable (HEAD 404; GET `Trades` 200) |
| Kraken | `ws.kraken.com` | reachable (WS upgrade 101) |
| Kraken | `docs.kraken.com`, `support.kraken.com` | 200 (support article 308 → same host) |
| Kraken | `drive.google.com` | **BLOCKED** (proxy, user-denied) |
| Kraken | `assets.kraken.com` (archive file host) | **BLOCKED** (proxy, user-denied) |
| CF Benchmarks | `www.cfbenchmarks.com`, `docs.cfbenchmarks.com` | **BLOCKED** (deny list) |
| Databento | `databento.com` | 200 |
| Databento | `hist.databento.com` | reachable (HEAD 405). Not used: authenticated, no key |
| Databento | `legal.databento.com` | **BLOCKED** (proxy) |
| Databento fixtures | `github.com`, `raw.githubusercontent.com` | 200 |
| Pyth | `docs.pyth.network` | 200 (refused in B09; reachable now) |
| Pyth | `hermes.pyth.network` | **BLOCKED** (deny list) |
| Pyth | `benchmarks.pyth.network`, `www.pyth.network` | **BLOCKED** (proxy) |
| Polymarket | `docs.polymarket.com` | 200 |
| Polymarket | `gamma-api.polymarket.com`, `clob.polymarket.com` | **BLOCKED** (deny list) |
| Tardis | `docs.tardis.dev` | 200 |
| Tardis | `api.tardis.dev`, `datasets.tardis.dev` | **BLOCKED** (proxy) |
| Coinbase | `docs.cdp.coinbase.com` | 200 |
| Coinbase | `api.exchange.coinbase.com` | reachable (200). Deliberately not used: DROP candidate with adverse ML terms |
| CME | `www.cmegroup.com` | **BLOCKED** (HTTP/2 stream reset through the proxy) |
| CME | `datamine.cmegroup.com` | **BLOCKED** (TLS handshake failure through the proxy) |

No blocked host was routed around: no mirror, cache, or archive was used. **Correction (review RT-B10-08):** the Databento research agent retried `www.cmegroup.com` and `datamine.cmegroup.com` (04:24:47Z and 04:24:48Z) after the lead's probe had already found them blocked. These were the same hosts, not another route, but the brief should have passed the lead's blocked-host list to subagents. Two attempts each in total.

### Samples (all raw files deleted; manifests in the profiles)

| Source / schema | Endpoint | Interval | Size | Profile |
|---|---|---|---|---|
| Kraken REST `Trades` XBTUSD | `api.kraken.com/0/public/Trades` | 2023-03-01 00:00–03:27 UTC | 5 pages, 5,000 rows, 339,000 bytes | `kraken_historical_trades.md` |
| Kraken WS v2 `book` (depth 10) + `trade`, BTC/USD | `wss://ws.kraken.com/v2` | 2026-10-19 04:22:47–about 04:24:20 UTC (live; the trade snapshot reaches back about 1 minute) | 200 messages, 62,136 bytes | `kraken_l2.md`, `kraken_ws_trades.md` |
| Databento official DBN test fixtures (trades, tbbo, mbp-1, mbp-10, mbo, definition, statistics) | `raw.githubusercontent.com/databento/dbn/82f76c1…/tests/data/` | E-mini S&P 2020-12-28; one CME instrument 2023-04-23; one US equity; two CME options (**no gold, no BTC**) | 8 files, about 10 KB | `databento_gc_*.md` |

The decision not to sample:
- REST OHLC returns only the latest 720 bars, so it could not be old;
- REST Depth is current state only;
- Coinbase is a DROP candidate;
- the Kalshi, Pyth, Polymarket, Tardis, and CF Benchmarks data hosts are blocked.

### Main findings

1. **The Kraken trade archive carries seven columns:** `timestamp, price, volume, type, order_type, misc, trade_id` (support article updated 2026-10-12). B09 had left the columns, sequence field, and timestamp precision unverified (`inventory_btc_detail.md` B-2: "Seq UNKNOWN; TS precision UNKNOWN"). **Attribution correction (follow-up):** an earlier version of this item quoted B09 as saying "price, volume, timestamp only". That phrase came from the B10 lead's own subagent brief, not from B09. Aggressor side (inferred taker side) is therefore free historically, and Tardis does not add it. The B09 rows are corrected in this batch (B10-D7).
2. **Kraken REST `Trades` pagination repeated the boundary trade on every page** (OBSERVED at 4 of 4 boundaries; not documented). Collectors pass `last` verbatim, drop only identical overlap rows, and fail closed on any `trade_id` gap. The REST `time` field is a serialized float64: sub-µs digits are artifacts; join sources on `trade_id`, never on time.
3. **The Kraken top-10 L2 state is checksum-verifiable at each message boundary:** 176 of 176 CRC32 checksums reproduced from snapshot plus updates (fixed-decimal formatting inferred, not documented). Event-stream completeness, levels beyond 10, and stalls are **not** verifiable: there is no sequence number (review API-B10-01). Kraken offers no historical L2.
4. **Kraken OHLCVT is derivable from trades.** The archive rows have no VWAP. The REST last bar is uncommitted and mutable.
5. **Kalshi:** spec versions are unchanged since the B09 snapshot (OpenAPI 3.34.0, AsyncAPI 2.0.0). The 1-minute candle bid/ask OHLC is the only historical quote evidence. Book, quoted size, and receipt time exist only in PMV capture.
6. **Databento:** `ts_event` is matching-engine time (MDP3; for MDP 2 data before 2017-05-21 it maps to CME SendingTime). `ts_recv` is PTP-synchronized vendor capture time from 2017-05-21 (earlier: equal to `ts_event`, flagged `F_BAD_TS_RECV`; millisecond-only before 2015-11-20). `ts_in_delta` gives CME send time (absent from `definition`, `status`, and `bbo-*`). The schema ladder: trades < TBBO/BBO < MBP-1 < MBP-10 < MBO. From 2017-05-21, MBO derives everything below it given snapshots, but not CMBP-1/CBBO (implied), statistics, definition, or status. **Cheapest sufficient for gold: `trades` + `definition` + `statistics` (+ `status`).** Bar `ts_event` is the bar start (a leakage hazard).
7. **CME DataMine is the same MDP3 data** through a different delivery path. Its only extras are block trades, EOD files, and PCAP.
8. **Gold reference:** Pyth XAU is a publisher-median spot reference "derived from futures". The GOLD index feeds are undocumented by Pyth. Pyth Core moved onto Pyth Pro on 2026-08-26 (a potential regime break). Stale prices are carried forward. COMEX and Pyth are different economic objects (basis; session coverage). DET-1 stays open.
9. **BRTI:** it is published at 200 ms (the Kalshi 5 Hz channel carries it; the ~1 Hz channel adds 60-second averages). **Attribution correction (follow-up):** an earlier version of this item said B09 described BRTI as once-per-second. B09 in fact recorded "200 ms / 1 s" (`master_source_inventory.md` B-12); the once-per-second phrasing came from the B10 lead's subagent brief. B09 rows without a cadence are annotated in this batch (B10-D7). Its expected unique value is settlement fidelity, not velocity (untested). A free proxy test against Kalshi `expiration_value` is possible inside the CORE data.
10. **Polymarket:** BTC up/down resolves on a Chainlink TWAP. It is another crowd's estimate of a nearly identical event. US persons are close-only. Deferred.
11. **Tardis licence clause 9.5** excludes LLMs and requires written, Tardis-enforceable terms before disclosure to an "external service provider", including for free samples. This may conflict with PMV's agent-assisted development (new owner question B10-D4).
12. **Coinbase `side` is the maker side,** the opposite of Kraken and Tardis.

### Exposures

Registered in `docs/exposure_register.md` Part A as rows X-7 to X-11. No price, size, or index value appears in any repository file. Derived activity statistics of X-7 and X-8 (spacing, lag, counts) are in the Kraken profiles. Raw values from the samples were printed into the local session transcripts, which persist outside Git (review RT-B10-06). As of row X-11, the latest exposure end is BTC 2026-10-19 (X-8) and gold 2026-10-18 (unchanged: no identified gold observation in B10; one Databento statistics fixture's instrument is unidentified, dated 2023-04-23, which cannot move the gold date). No cycle or `T0` exists, so none is a contamination event.

### Process events (disclosed)

- **Proxy session credential printed to the session transcript.** While checking proxy configuration, `env | grep -i proxy` printed the sandbox egress-proxy username and password (`CLOUDSDK_PROXY_*`) into the lead session's output. The `sed` mask covered only some variables. This is the isolated environment's local proxy credential, not a venue, cloud, or GitHub credential. It is in no repository file and not in Git (verified by the Red-Team by byte search of `/workspace` and `$TMPDIR`), but it **persists in the local session transcript** under `~/.claude/projects/` (review RT-B10-07). Recommendation: rotate it before any transcript is shared or backed up (B10-D6).
- **Harness artifacts:** shell `cd` into a subdirectory made the Claude Code harness create empty `.claude/.cc-writes` directories under `research/data_sources/schema_profiles/`. They were removed (empty; never staged).
- **WebFetch and WebSearch:** not used by the lead session. Research agents used `curl` to documentation hosts, plus the `raw.githubusercontent.com` fetches disclosed above.
- **Recon tools edited after use (review RT-B10-11).** After producing the evidence, the four tools were edited:
  - for lint, with no logic change;
  - the REST profiler: one diagnostic print reworded, and spacing statistics now de-duplicate by `trade_id` first (the published spacing numbers predate this and are labelled);
  - both samplers: they now refuse any `--out` outside `/workspace/.recon_tmp/`;
  - the WS sampler: a cumulative 10 MB cap, a 1 MB per-frame cap, RFC 6455 frame checks, and try/finally socket closure (review API-B10-12).

  The committed tools are therefore not byte-identical to those that produced the samples, which are deleted.
- **Temporary vendor documentation** (about 10 MB of fetched doc pages under `$TMPDIR/b10_*`) was deleted at batch close (review RT-B10-12).
- **Models:** the lead session and all subagents ran as `claude-opus-5-5` (exposure register Part B, M-1).

## Owner-decision packet (B10)

*As proposed at `05df35a`. The owner ruled on every item on 2026-10-19; see "Owner decisions on the B10 packet" below. Where a ruling differs from a recommendation (B10-D2 clarified, B10-D4 not approved, B10-D7 done now, B10-D8 thresholds frozen at cycle registration, B10-D9 deferred, B10-D11 replaced), the ruling governs.*

| # | Decision | Recommendation | Urgency |
|---|---|---|---|
| B10-D1 | Confirm that the B10 charter (a) was intended as a narrow exception to the CLAUDE.md agent-context rule for historical files, limited to reconnaissance; (b) covered `api.kraken.com` and `ws.kraken.com` for BTC, for schema verification; (c) counts repository test fixtures (`databento/dbn`) as "official sample files" | Confirm. Future charters name hosts, observable families, and sample sources explicitly | Before any similar batch |
| B10-D2 | D-B09-17(a): does an owner charter's permission for vendor documentation override terms-first for documentation hosts whose terms live on refused hosts? | Rule once, generally | Before CLOUD-1 |
| B10-D3 | Adopt the source verdicts and the Stage 1 / Stage 2 minimum viable source set (`source_redundancy_decisions.md`) as the acquisition-planning basis | Approve as planning basis; each acquisition still needs A-1 to A-8 | Before the first acquisition charter |
| B10-D4 | **New licence question (Tardis clause 9.5, and generally):** may licensed vendor rows be released into LLM-agent development sessions? The same question applies to Kalshi, Kraken, and Databento data under H-2 release | Add it to the M1–M3 outreach; do not acquire Tardis data, even free samples, until answered | Before the first development release |
| B10-D5 | Kraken prospective capture: capture the `book` channel alongside `trade` even though L2 use is CONDITIONAL | Approve capture-but-not-use when P2 capture is authorized | When capture is chartered |
| B10-D6 | Rotate the sandbox egress-proxy credential printed in the transcript | Optional | Not urgent |
| B10-D7 | Update the B09 inventory rows for the Kraken archive columns (B-2) and BRTI cadence. B10 recorded the corrections in profiles without editing B09 documents | Approve a documentation correction in a later batch | Not urgent |
| B10-D8 | Adopt the promotion-test protocol (`source_redundancy_decisions.md`) and set its numbers (δ, error budget). Amend D-B09-18 K2 so that an M-0 failure under a measured, excessive BRTI-proxy error is UNINFORMATIVE, not FAILED, with the bound fixed before the proxy measurement runs | Approve | Before M-0 or any promotion test |
| B10-D9 | Kalshi CFB (and `pyth_value`) channel capture: these are live-only, and under S-9 deferral excludes reference features from cycle 1 | Decide explicitly, with the cycle-1 consequence recorded | Before cycle registration |
| B10-D10 | Revert the allowlist entries for `api.kraken.com`, `ws.kraken.com`, and `api.exchange.coinbase.com` at B10 close; add a deterministic egress check asserting that live-data hosts are refused | Approve | At B10 close; the check is BLOCKING before any `T0 − m` |
| B10-D11 | No further Kraken data request of any kind until M2 (Kraken permission) is answered | Approve | Now |

## Owner decisions on the B10 packet (2026-10-19, second direction)

Issued by the owner in "B10 OWNER DECISIONS + FINAL RE-REVIEW" on 2026-10-19, after `05df35a`. The rulings below are verbatim; the "Applied" lines say what this follow-up commit did.

**B10-D1: APPROVED.** "The B10 charter intentionally authorized bounded read-only public-market samples for the named source families for schema/semantics reconnaissance. Future charters must explicitly name hosts/data families."
- Applied: the B10 samples (X-7, X-8, X-11) stand as authorized reconnaissance. The process deviations listed above stay recorded as they happened.

**B10-D2: APPROVED WITH CLARIFICATION.** "Official public documentation may be read under an explicit research charter. Governing terms must be checked and recorded before actual market-data acquisition/sample use. Reading documentation itself does not require a separate prior terms fetch unless a source-specific restriction says otherwise."
- Applied: recorded as an owner clarification of terms-first in `docs/external_access.md` §1.1 rule 3. The B10 Kraken sample fetches came **before** any terms review. Under this clarification that is a deviation, and it stays recorded (tension table, Kraken row).

**B10-D3: APPROVED.** "Adopt the B10 minimum-source-set verdicts as the acquisition-planning baseline. This is not evidence of predictive value."
- Applied: `research/data_sources/source_redundancy_decisions.md` status line.

**B10-D4: NOT APPROVED AS WRITTEN.** "Do not initiate new Kalshi/Kraken/Databento outreach merely to ask whether raw licensed rows may be shown to LLM agents." Default policy (verbatim):
> - raw/licensed market rows stay outside LLM/agent context unless terms clearly permit that use;
> - deterministic code may acquire/profile/process authorized data;
> - agents may work from schemas, provenance, aggregates, diagnostics and appropriately permitted development evidence.
- Applied: recorded in `docs/external_access.md` §2 (after A-8) and in `source_redundancy_decisions.md`. The Tardis clause 9.5 concern is now handled by this default: Tardis rows would stay outside agent context unless the terms clearly permit it. No outreach is added.

**B10-D5: APPROVED CONDITIONALLY.** "When prospective capture is separately chartered, capture Kraken L2 alongside trades because it is live-only and cannot be recreated later. Do not promote L2 to a model feature without its preregistered promotion test."

**B10-D6: APPROVED.** "Proxy credential must be rotated before B10 closure because it was printed in the session transcript."
- Status: **owner action pending; not performable from the agent sandbox.** The credential's issuer is unverified: it may be the outer PMV egress proxy, or the Claude Code sandbox runtime, minted per session (`docs/owner_actions/README.md` §3 step 3). Either way, agents cannot rotate it, and no agent-runnable rotation procedure exists in the repository. Agents must not alter the egress layers. The exact owner steps are in `docs/owner_actions/README.md` §3. **B10 is not closed until the owner confirms rotation.**
- **Superseded (owner correction, 2026-10-19):** RESOLVED BY CONTROL HARDENING. There is no PMV Squid password to rotate. See "Owner correction: runtime-secret hardening" below.

**B10-D7: APPROVED,** correct the stale B09-derived documentation in this follow-up commit.
- Applied:
  - `research/data_sources/inventory_btc_detail.md` B-2 and note 4 / E-B09-BTC-3: seven archive columns, `trade_id` sequence, doc conflict resolved;
  - `research/data_sources/master_source_inventory.md` B-2, B-12, B-14: columns; BRTI 200 ms publication and the 5 Hz channel;
  - `research/data_sources/owner_source_action_sheet.md` B1 and K4: same;
  - the B10 misattributions in items 1 and 9 above, and in `schema_profiles/kraken_historical_trades.md`.

**B10-D8: APPROVED IN PRINCIPLE.** "Adopt the promotion-test framework and the informative/underpowered distinction. Exact numerical thresholds/power requirements must be frozen during cycle registration BEFORE the corresponding test results are observed."
- Applied: `source_redundancy_decisions.md` protocol wording.

**B10-D9: DEFERRED.** "Do not authorize Kalshi CF Benchmarks/Pyth reference-channel capture yet. First resolve the exact BTC/gold settlement/reference mechanics and obtain the CF Benchmarks licensing quote."
- Consequence (S-9): until it is decided, cycle 1 cannot use reference-channel features.

**B10-D10: APPROVED.** At B10 close:
- remove `api.kraken.com`, `ws.kraken.com`, and `api.exchange.coinbase.com` from both established sandbox allowlist layers;
- preserve documentation hosts;
- add an automated test proving that prohibited live-data hosts are refused before any protected `T0 − m`/`T0`;
- run future prospective capture in the separately chartered cloud capture environment, not the Claude development sandbox.

Applied:
- **Test added:** `tests/integration/test_live_host_egress_refusal.py`. It runs with `PMV_EGRESS_PROBE=1`, otherwise it skips, so `check.sh` and CI make no network attempts. It has:
  - a Layer A static check of `/etc/claude-code/managed-settings.json`;
  - three proxy-CONNECT refusal probes (CONNECT only; no TLS, no application request);
  - three positive controls (the list check and two preserved documentation hosts).
- **Result on 2026-10-19, before the owner's change (final test version):** 4 failed, 4 passed. Layer A still admits all three hosts, and each returns `HTTP/1.1 200 Connection Established`. The list and matcher self-checks and the two documentation-host controls pass.
- Refusal detection was also confirmed against an already-refused host: `api.elections.kalshi.com` returned `HTTP/1.1 403 Forbidden`, which the test's refusal pattern accepts. The pattern counts any 4xx/5xx as a refusal except 407.
- After review API2-B10-01, each refusal probe runs an in-test proxy-path control, and the Layer A check also catches wildcard entries.
- The test therefore detects the current exposure as intended.
- **Layer removal: owner action pending; not performable from the agent sandbox.** `managed-settings.json` is read-only to agent sessions, and the egress proxy is outside the container. Procedure: `docs/owner_actions/README.md` §3. Layer A also lists `exchange.coinbase.com`, which B10 never used; its removal is recommended there. **B10 is not closed until the test passes (8 passed) after the owner's change and the Layer B CONNECT-only check in §3 step 4 shows refusals.**
- **Timing superseded (owner correction, 2026-10-19):** removal is not required to close B10. It is required before any cycle's `T0 − m`. See "Owner correction: runtime-secret hardening" below.

**B10-D11: REJECTED AS WRITTEN AND REPLACED WITH** (verbatim):
> "No further Kraken bulk acquisition begins until the current governing published terms are snapshotted and classified for private own-account PMV use. Vendor correspondence is required only if that review leaves a material ambiguity. Vendor non-response is not itself an acquisition blocker where the published terms clearly authorize the intended private use."

and "Do not represent silence as permission."
- Applied: `source_redundancy_decisions.md` Kraken rows and Stage 1; the `owner_source_action_sheet.md` status note (its Kraken rows reading NEEDS_WRITTEN_PERMISSION / M2 are to be read in that light); `master_source_inventory.md` B-2; `docs/phase1.md`. Kraken outreach (M2) becomes conditional on the terms review leaving a material ambiguity.

### Process deviations: final disposition (not erased)

| Deviation | Disposition |
|---|---|
| Kraken REST and WS data fetched before any Kraken terms review | Stands as a recorded deviation from terms-first (as clarified by B10-D2). Covered for B10 by the owner's B10-D1 approval of the samples. Future sample use needs terms checked and recorded first |
| Databento fixtures (and source files) fetched from `raw.githubusercontent.com` | Stands as a recorded deviation from `docs/external_access.md` §1.1 rules 9 and 11. Covered for B10 by B10-D1 (named source families, schema reconnaissance). Fixtures deleted; registered as X-11 |
| CME hosts retried by a subagent after the lead found them blocked | Stands as recorded; no route-around occurred. Future briefs pass the lead's blocked-host list |
| Proxy credential printed to the session transcript | Stands as recorded. Not in any repository file. Rotation is required before B10 closure (B10-D6; owner action pending) |
| **Proxy credential printed again** during the round-2 API/Execution re-review (follow-up): its `env \| grep -i proxy` redaction did not cover `GIT_SSH_COMMAND` or `CLOUDSDK_PROXY_*` | Stands as recorded. Not in any file. The B10-D6 rotation must take place **after** this session, covering both exposures. Owner and agent procedures now warn never to print `env`, proxy URLs, or `GIT_SSH_COMMAND` (`docs/owner_actions/README.md` §3) |

Both credential-print rows stand as written. Their rotation requirement is superseded by the owner correction below. The exposures themselves remain disclosed.

## Owner correction: runtime-secret hardening (2026-10-19, third direction)

Issued by the owner in "B10 FINAL SECURITY RECORD CORRECTION" on 2026-10-19, after `ba1fa9e`. It follows the owner-side investigation of the runtime secret and the owner's terminal hardening. The owner's findings and rulings are recorded below as given. The earlier B10-D6 and B10-D10 text above is kept, annotated as superseded.

### Owner-verified findings

1. The host shell has no `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` values.
2. The PMV launcher contains only the unauthenticated route `pmv-egress-proxy:3128`. It has no username or password userinfo, no `srt.` token, and no command substitution that generates credentials.
3. `pmv-egress-proxy` has no Squid `auth_param` / `proxy_auth` configuration and no Squid password or auth files. It holds no PMV-owned proxy credential to rotate.
4. No persistent `srt.`-style runtime token exists in the PMV control directory.
5. The exposed credential was therefore not a PMV Squid secret. The evidence strongly indicates that it was introduced by the Claude managed sandbox/runtime networking layer. **Its exact issuer and lifetime are not proven.**
6. The owner added managed-policy secret guards outside Claude.
7. A fresh Claude sandbox verified the guards (2026-10-19):
   - **Live-denied:** `env`; `printenv`; `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` inspection; `Proxy-Authorization` inspection; `curl --verbose`, `--trace`, and `--trace-ascii`; `pytest --showlocals`; `cat`/`head`/`sed`/`xxd`/Python reads of `/proc/self/environ`; `set`; `declare -p`; `compgen -v`.
   - **Configured denies / additional write boundary:** the Read tool on `/proc/self/environ`, and Edit and Write of `managed-settings.json`. These were not live-denied by policy in that run: other tool checks stopped them first (a device-file guard; read-before-write). The deny rules are present in managed policy, and the managed-settings path is also on the sandbox's write-deny list.
8. Sandbox controls remain: `sandbox.enabled = true`, `failIfUnavailable = true`, `allowUnsandboxedCommands = false`, `allowManagedDomainsOnly = true`, `disableBypassPermissionsMode = "disable"`.
9. Permitted documentation access still works.
10. **Residual defense-in-depth item (non-blocking; future hardening, not a B10 blocker):** the sandbox file-read deny paths for `/proc` appear normalized under `/workspace` (for example `/workspace/proc/self/environ`). The managed permission deny is therefore currently the effective protection for the real `/proc` paths. Recommended owner fix: express those sandbox read-deny entries as absolute paths that resolve to the real `/proc`.

### B10-D6: RESOLVED BY CONTROL HARDENING (replaces the rotation requirement)

Owner disposition, verbatim. Its first bullet is qualified by finding 5 and by the precision notes below.

- The exposed credential was a sandbox/runtime credential, not a PMV Squid credential.
- There is no PMV Squid password to rotate.
- The two historical transcript exposures remain disclosed (process deviations above).
- Persistent managed controls now prevent the known credential-disclosure routes.
- Future network diagnostics must never print, serialize, or reconstruct runtime proxy credentials.

Precision notes (agent, from the round 3 reviews RT3-B10-01, -02, -12 and API3-B10-03; they qualify the evidence, not the ruling):
- What is proven is that the credential was **not** a PMV Squid credential. Its sandbox/runtime origin is the most likely explanation (finding 5). Its issuer and lifetime are not proven.
- The managed denies match command text. They block the known command-text routes (finding 7). They cannot exclude every indirect route, such as a script file that dumps the environment. The Read-tool and managed-settings Edit/Write denies are configured but not live-proven, and the sandbox `/proc` read-deny paths are mis-normalized (finding 10). Review and the static backstop below remain necessary.
- **Residual risk:** the plaintext of both exposures remains in local Claude session transcripts under `~/.claude/projects/`. They are outside Git, but may be included in any backup of that directory. Because the lifetime is unproven, the credential cannot be assumed expired. Optionally, the owner can confirm that it has expired, or purge or exclude those transcripts from backups and sharing. Agents must not open or search them for it.

### B10-D10: timing corrected

Immediate removal of the Kraken/Coinbase live-data hosts is **not** required to close B10.
- Live/public market hosts may remain available during explicitly authorized development or reconnaissance.
- Before `T0 − m` / protected evaluation, both PMV network-control layers must be tightened so that development agents cannot reach prohibited live or future data.
- The pre-`T0 − m` checklist must include an automated refusal test: `PMV_EGRESS_PROBE=1 uv run --locked pytest tests/integration/test_live_host_egress_refusal.py` with all 10 checks passed, plus the owner's Layer B check (`docs/owner_actions/README.md` §3).
- No `T0` or `T0 − m` exists now.
- The hosts were not removed in this task. The test is expected to keep failing its 4 Layer A and refusal checks (of 10) until the owner tightens the layers.
- The pre-T0 owner checklist in START_HERE.md lists P-1 to P-4. This requirement is binding through this record and `docs/external_access.md` §1.4. It is also listed wherever cycle registration prerequisites are listed (`docs/phase1.md`, `docs/release_tool_design.md` step 6a), and as a pending owner action in `docs/owner_actions/README.md`. Adding it to START_HERE.md as a checklist item (proposed P-5) is a governance edit that awaits owner approval.
- **The refusal test passing is necessary, not sufficient** (review RT3-B10-06). The test covers three named hosts. The requirement covers every host through which development agents could reach prohibited live or future data. Before `T0 − m`, the owner also classifies every Layer A and Layer B allowlist entry by host class (`docs/external_access.md` §1), including the data or file hosts listed for owner disposition in `docs/owner_actions/README.md` §3 step 1, and any host serving a protected observable family. Live-data, live-display, and protected-observable hosts are removed or explicitly justified.

### Permanent diagnostic rule

Recorded in `docs/conventions.md`, "Diagnostics and Runtime Secrets", as given by the owner. A static backstop, `tests/unit/test_diagnostic_secret_rule.py`, scans the code and automation trees for the forbidden forms.

### Applied (this corrective commit)

- `docs/conventions.md`: the permanent rule.
- `tests/unit/test_diagnostic_secret_rule.py`: the static backstop (no network). It scans Git-tracked Python, shell, workflow, and configuration files, plus fenced shell and Python blocks in Markdown runbooks. It has rule self-tests (hits and allowed forms), exact-line exemptions, and a repository scan. Findings report only file, line, and rule name.
- `tests/integration/test_live_host_egress_refusal.py`:
  - no `assert` touches the proxy URL, which pytest assertion introspection could otherwise render on failure;
  - a missing or malformed proxy fails with a fixed message. The failure is raised outside the `ValueError` handler, so `urlsplit`'s message, which can quote the userinfo, is not chained into the report (review API3-B10-01, MAJOR, fixed). A regression test uses a dummy sentinel;
  - only `403` counts as a proxy refusal. 407 and 5xx fail (review API3-B10-04). A unit test pins this;
  - an autouse fixture refuses probes when local-variable tracebacks are enabled;
  - the docstring states the credential-handling rule.
  - Probe logic is otherwise unchanged. The live probe was not run in this session, because the owner directed that proxy variables not be inspected.
  - **Pending owner confirmation (RT3-B10-11, API3-B10-02):** the probe builds a `Proxy-Authorization` header in memory, from the injected proxy URL, to authenticate to that same proxy. Read literally, the rule's word "reconstruct" covers this. Reviewers judged the handling sound: the header is sent only to the issuing proxy and is never output. The owner should confirm a narrow carve-out ("in-process transmission to the issuing proxy by a network client is not disclosure") before the probe is next run, which is before `T0 − m`. If the owner declines, the in-sandbox probe would send no credential, and an authenticating sandbox proxy would answer 407, which fails closed.
- `docs/owner_actions/README.md` §3: D6 marked resolved. The step 4 snippet targets the unauthenticated `pmv-egress-proxy:3128` route that the owner verified. Layer B needs no credential, so the snippet reads no proxy variable and sends no auth header. The expected results now require 403, and a failed control line invalidates the run. The D10 timing is corrected. A pending row proposes START_HERE P-5.
- `docs/external_access.md` §1.4, `docs/phase1.md`, `docs/BRANCH_TIMELINE.md`, `docs/release_tool_design.md` step 6a: closure status, the D10 timing, and the pre-`T0 − m` refusal requirement.
- `research/governance/b10_reviews.md`: round 3, the focused post-fix review.

## Status after B10

- Nothing acquired, purchased, licensed, provisioned, or captured beyond the deleted reconnaissance samples.
- No `T0`, cycle, split, or protected scope exists.
- B10 stops for owner review. No merge. No B11.
- ~~**B10 closure is pending two owner actions:** proxy credential rotation (B10-D6) and live-host removal from both egress layers, verified by `tests/integration/test_live_host_egress_refusal.py` passing (B10-D10). See `docs/owner_actions/README.md` §3.~~ Superseded by the owner correction above.
- **B10-D6 resolved by control hardening; B10-D10 removal deferred to before any `T0 − m`.** No owner action is outstanding for B10 closure from D6 or D10. The `/proc` sandbox read-deny path normalization is recorded as future defense-in-depth hardening.
