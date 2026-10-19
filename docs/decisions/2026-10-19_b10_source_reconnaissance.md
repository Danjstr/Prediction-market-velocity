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
| Terms-first (`docs/external_access.md` §1.1 rule 3; rule 6 requires it in every agent brief); D-B09-17(a) pending | Kalshi, Kraken, Polymarket, Pyth, and Coinbase terms live on refused hosts | Documentation hosts were read under the charter's "official vendor documentation; public API documentation". **Terms were not read for any of these vendors**, so "no terms bar observed" means only that none was seen, not that terms-first was satisfied (review RT-B10-03). The B10 common agent brief stated the host-class rule but **omitted the terms-first rule** (a rule-6 deviation) | D-B09-17(a) stays the owner's (B10-D2) |
| Kraken data under a known permission posture | Kraken's API notice requires prior permission for non-personal commercial use of public market data (M2 pending; `owner_source_action_sheet.md` B1/B2). B10 fetched Kraken REST and WS data without reading those terms (RT-B10-03) | Two bounded requests for schema verification only, under the charter | No further Kraken data request of any kind until M2 is answered (B10-D11) |
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

1. **The Kraken trade archive carries seven columns:** `timestamp, price, volume, type, order_type, misc, trade_id` (support article updated 2026-10-12). This corrects B09 (`inventory_btc_detail.md` B-2: "price, volume, timestamp only"). Aggressor side is therefore free historically, and Tardis does not add it.
2. **Kraken REST `Trades` pagination repeated the boundary trade on every page** (OBSERVED at 4 of 4 boundaries; not documented). Collectors pass `last` verbatim, drop only identical overlap rows, and fail closed on any `trade_id` gap. The REST `time` field is a serialized float64: sub-µs digits are artifacts; join sources on `trade_id`, never on time.
3. **The Kraken top-10 L2 state is checksum-verifiable at each message boundary:** 176 of 176 CRC32 checksums reproduced from snapshot plus updates (fixed-decimal formatting inferred, not documented). Event-stream completeness, levels beyond 10, and stalls are **not** verifiable: there is no sequence number (review API-B10-01). Kraken offers no historical L2.
4. **Kraken OHLCVT is derivable from trades.** The archive rows have no VWAP. The REST last bar is uncommitted and mutable.
5. **Kalshi:** spec versions are unchanged since the B09 snapshot (OpenAPI 3.34.0, AsyncAPI 2.0.0). The 1-minute candle bid/ask OHLC is the only historical quote evidence. Book, quoted size, and receipt time exist only in PMV capture.
6. **Databento:** `ts_event` is matching-engine time (MDP3; for MDP 2 data before 2017-05-21 it maps to CME SendingTime). `ts_recv` is PTP-synchronized vendor capture time from 2017-05-21 (earlier: equal to `ts_event`, flagged `F_BAD_TS_RECV`; millisecond-only before 2015-11-20). `ts_in_delta` gives CME send time (absent from `definition`, `status`, and `bbo-*`). The schema ladder: trades < TBBO/BBO < MBP-1 < MBP-10 < MBO. From 2017-05-21, MBO derives everything below it given snapshots, but not CMBP-1/CBBO (implied), statistics, definition, or status. **Cheapest sufficient for gold: `trades` + `definition` + `statistics` (+ `status`).** Bar `ts_event` is the bar start (a leakage hazard).
7. **CME DataMine is the same MDP3 data** through a different delivery path. Its only extras are block trades, EOD files, and PCAP.
8. **Gold reference:** Pyth XAU is a publisher-median spot reference "derived from futures". The GOLD index feeds are undocumented by Pyth. Pyth Core moved onto Pyth Pro on 2026-08-26 (a potential regime break). Stale prices are carried forward. COMEX and Pyth are different economic objects (basis; session coverage). DET-1 stays open.
9. **BRTI:** B09 described it as a once-per-second index. It is published at 200 ms (the Kalshi 5 Hz channel). Its unique value is settlement fidelity, not velocity. A free proxy test against Kalshi `expiration_value` is possible inside the CORE data.
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

## Status after B10

- Nothing acquired, purchased, licensed, provisioned, or captured beyond the deleted reconnaissance samples.
- No `T0`, cycle, split, or protected scope exists.
- B10 stops for owner review. No merge. No B11.
