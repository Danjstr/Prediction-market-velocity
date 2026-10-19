# CF Benchmarks — CME CF Bitcoin Real Time Index (BRTI)

**Status:** ACCESS BLOCKED (`cfbenchmarks.com`, `www.cfbenchmarks.com`, `docs.cfbenchmarks.com`, all `*.cfbenchmarks.com` hosts are on the PMV deny list; the CF Benchmarks site terms also bar automated access); LICENSE GATED (licence or entitlement required for real-time and historical values); SCHEMA ONLY (known only from Kalshi documentation already in Git and from prior repo research; no CF Benchmarks document was read in this batch).

Recon by agent `refs` (claude-opus-5-5), B10, 2026-10-19. **No network request was made for this profile**, and no index value appears in it. Evidence is repo-Git only: Kalshi docs read in batch 2 under AR-1, and CFTC filings read in batch 3.

**Evidence** (repo files at commit `8b4e026`; sha256 of the current working-tree file)

| Source | retrieved | HTTP | bytes | sha256 | grade |
| - | - | - | - | - | - |
| `research/kalshi/api_documentation_findings.md` §5, §11 (quotes `docs.kalshi.com/websockets/cfbenchmarks-value.md` sha256-prefix 4c61a8f08fd896e7, `…/cfbenchmarks-value-5hz.md` d1eefda0dac7fcc0, `…/cfbenchmarks/rest-passthrough.md` bf0ef09aae3c9754) | Git | — | 93646 | b20ad9044cab016c4a14fcfc1865e1b3a45eb40f2a31de2d5ef06f89f796589c | repo-Git (VERIFIED-BY-DOC at batch 2) |
| `research/kalshi/venue_verification.md` | Git | — | 26437 | 6cf1f62dfc646ae335f4944ec940217903efbe21a607cfde559bb23832c269c4 | repo-Git |
| `research/historical_data/inventory_prediction_markets.md` (CFTC rulebook quotes) | Git | — | 42170 | ecf63ac8e5964dd024f989535d7803d6fd1e92030f7f2ebc3b194a9539be770c | repo-Git (filings VERIFIED-BY-DOC) |
| `research/sources.md` (CFTC filings: CRYPTO `d6864df0…e765`, CRYPTOSHORT `880a5516…8e2`) | Git | — | 61071 | 84304b18d1c00c42ee143f02f121a1cfe4894f1691984fa190e464784baaeb93 | repo-Git |
| `research/historical_data/inventory_underlying_btc_gold.md` §B.1 | Git | — | 46016 | 7087af9a5646ac39a23be659eaabd146e917844cd42ffef0ce6726d97cda8e57 | repo-Git (mixed G/S) |
| `research/data_sources/inventory_btc_detail.md` | Git | — | 23646 | 3537270703d3e4aa0fe058340bc34fe72f98837631550909d0c459c746020e60 | repo-Git (mixed G/S) |
| `research/data_sources/master_source_inventory.md`, `owner_source_action_sheet.md` | Git | — | 49175 / 31360 | 6e57277c…6957 / fb85d569…bd9bb | repo-Git |
| `research/kalshi/b09_source_qualification.md` | Git | — | 52556 | 0bece5c235338058011e5d998a26ea5bb463b5afc32cd9cd40b6eeb55fda617d | repo-Git |

## Access and connectivity

Four routes are known. None is open to agents.

| Route | Repo ID | Access | Status |
| - | - | - | - |
| CF Benchmarks direct API (`www.cfbenchmarks.com/api/v1/`) | B-12 | Licence and entitlement. The history endpoint needs `STREAM_HISTORICAL_VALUES`. Recent values may be delayed 15 min (S) | Host BLOCKED. Quote requested via owner message M4 |
| Kalshi REST passthrough `GET /trade-api/v2/cfbenchmarks/<path>` → `https://www.cfbenchmarks.com/api/v1/<path>` | B-13 | "requires an authenticated Kalshi Trade API request, and it is available only to accounts with the appropriate entitlement"; 50 read tokens; drops `includeVerification` (G) | Needs a Kalshi key and entitlement. Price UNKNOWN |
| Kalshi WebSocket `cfbenchmarks_value` (~1 Hz, with 60 s averages) and `cfbenchmarks_value_5hz` | B-14 | "Authentication required". Whether an extra entitlement is needed is UNRESOLVED (G) | Prospective only |
| CME DataMine `CRYPTOCURRENCY` (BRTI second values since about 2016-11/12) | B-10 | CME login, quote-only, MDLA/DDLA; DS-45 ML prohibition (S) | Not chosen (Tier 3) |

## Transport, format, compression, delivery (historical vs live)

- **Live (via Kalshi):** JSON over the Kalshi WS session, sequenced like other Kalshi channels (`seq`). Kalshi "drops duplicate and out-of-order upstream ticks on both CFB channels", so the stream is a filtered view, not the full upstream. `indexlist` is needed to confirm availability: "A successful `subscribe` response alone does not confirm that a requested index is available." (G)
- **Historical (via Kalshi passthrough):** `/cfbenchmarks/history/values?id=BRTI&timespan=...&timestamp=...` "returns tick-level values, and some indices publish at intra-second granularity" (G). Depth and retention are **not stated** (U21).
- **Historical (direct):** API; values at 200 ms or 1 s (G per `inventory_btc_detail.md` B-12); "later pulls may reflect later revisions" (S). Restatement policy UNKNOWN.

## Fields (Kalshi channel schemas; CF Benchmarks' native schema is not documented in Git)

| field | native type | official semantics (quoted from Kalshi docs via repo) | PMV class | notes |
| - | - | - | - | - |
| index id `BRTI` | string | BTC index ID | DIRECT | Other ids exist (ETH, SOL, XRP, DOGE on 5 Hz) |
| `value_usd` (5 Hz) | decimal, 8 dp | index value | DIRECT (reference) | — |
| `data` (raw upstream frame) | JSON string | upstream frame; the example has a `time` key | SOURCE_SPECIFIC | On `cfbenchmarks_value`, the source time exists **only** inside `data` (INFERENCE that `data.time` is the averaging timestamp) |
| `source_ts_ms` (5 Hz) | int ms | "Upstream publication timestamp of the tick" | DIRECT (time) | — |
| `received_at` | int ms | "When Kalshi received the upstream frame" | DIRECT (receipt time at Kalshi) | Not PMV receipt time |
| `avg_60s_data` | object | "always present": trailing window `[source_ts_ms − 60000, source_ts_ms)`; `window_size` counts prior ticks only; falls back to the current value if empty | DERIVABLE (from ticks) | Kalshi-computed convenience field |
| `last_60s_windowed_average_15min` | object | "present only in the final minute before a quarter-hour close (:00/:15/:30/:45)". Window `(quarter_close_ts_ms − 60000, quarter_close_ts_ms]`; "start-boundary tick is excluded and the close tick is included" | DERIVABLE (Kalshi's computation) | **Not documented as the settlement value** (INFERENCE only) |
| `window_start_ts_ms`, `window_end_ts_exclusive` | int ms | window bounds | SOURCE_SPECIFIC | CONFLICT: the name says "exclusive" but the prose says the close tick is included. The doc example does not match the prose |
| passthrough history rows | UNKNOWN | defer to CF Benchmarks docs (BLOCKED) | UNKNOWN | — |

## Timestamps

- **Cadence:** the `cfbenchmarks_value` channel is "~1 tick/s" (G). Kalshi's changelog (2026-09-03) says the 5 Hz channel carries "indices the vendor publishes at 200ms granularity" (G). **So BRTI is now published at 200 ms, not only once per second.** The "once per second" figure in the task brief matches the older 1 Hz channel and CME DataMine's "second interval" history (S). Which cadence the *settlement* average uses is not stated in Git. The CRYPTO/CRYPTOSHORT rule texts speak of an average over the 60 seconds before the time; they do not say how many ticks.
- **Time semantics:** `source_ts_ms` is upstream publication time; `received_at` is Kalshi receipt. CF Benchmarks' own definition of its timestamp (calculation instant vs publication) is UNKNOWN (docs blocked). Repo INFERENCE: UTC epoch.
- **Gaps:** CF publication → Kalshi receipt → PMV receipt. Each hop needs its own timestamp in PMV capture (`docs/phase2.md` receipt-time rule). Kalshi's dedup and out-of-order dropping means a gap at Kalshi is not proof of an upstream gap.

## Sequencing and book semantics

- BRTI is an index value, not a book. Kalshi `seq` gives per-subscription ordering of the filtered stream (G). There is no upstream sequence number in the parsed schema.
- **Methodology (all SECONDARY; no CF Benchmarks document was read):**
  - Repo record (`inventory_underlying_btc_gold.md` consequence 2): "BRTI is an order-book-based, cross-exchange, exponentially depth-weighted mid (methodology per search summary of CF Benchmarks' RTI guide v17; SECONDARY)".
  - General knowledge (SECONDARY, from memory, unverified): constituent order books are combined into a consolidated book. A mid-price-volume curve and a "utilised depth" are derived from it. The index is an exponentially weighted average of mid prices over that depth, with rules that exclude stale or erroneous books.
  - **Correction to the task brief:** "median of volume-weighted partitions" describes the **BRR** (the daily, trade-based CME CF Bitcoin Reference Rate: trades split into time partitions, volume-weighted median per partition, then averaged). It does not describe BRTI (repo: "BRR (daily 4 pm London, trade-based VWM)", INFERENCE). Do not encode either formula until the owner supplies the methodology PDF (AR-U2/AR-9).
- **Constituents (SECONDARY, point-in-time):** current list (S): Bitstamp, Coinbase, Gemini, Kraken, LMAX Digital, Bullish (from 2025-07-14), Crypto.com (from 2025-03-31). itBit was suspended 2026-07-27 and removed 2026-08-27 (`inventory_btc_detail.md`). Kraken's owner Payward also owns CF Benchmarks (VERIFIED-BY-DOC, footer, batch 3). That is a conflict of interest, not a data defect. A point-in-time constituent history is required for any reconstruction.

## Instrument / contract identity, expiry, reference-end, settlement/reference fields

- **Provider statement (VERIFIED-BY-DOC, batch 3):** "The BRTI is the price input for settlement of event contracts and prediction markets offered by Kalshi, CME Group and ForecastEX". CF Benchmarks is Source Agency in the Kalshi CFTC filings (VERIFIED-BY-DOC).
- **Kalshi rulebook regimes (CFTC filings, VERIFIED-BY-DOC as rule text):**
  - BTC rulebook, amended 2024-11-12, effective 2024-11-27: "simple average of the CF Bitcoin Real-Time Index ('BRTI') for the minute (60 seconds) prior to <time>, excluding the highest and lowest 20% of values". Before that, a 300 s average.
  - CRYPTO rulebook (2025-07-18): plain 60 s simple average. No data → "affected strikes resolve to No".
  - CRYPTOSHORT rulebook (2026-03-11): configurable `<lookbackduration>`; rounding before comparison; no data → "the last piece of data available"; post-expiration CF corrections ignored; times in ET.
- **KXBTC15M (15-minute up/down):** SECONDARY rule text: "60-second simple average of BRTI before close ≥ the same average before open; ties resolve YES". **Which rulebook governs KXBTC15M is UNRESOLVED (DET-2/K5).** That `last_60s_windowed_average_15min` equals the settlement value is INFERENCE only.
- **Label rule (PMV, `docs/phase2.md`, repo):** labels come from the official venue resolution (`expiration_value`, `result`). "BRTI is a feature and recomputation-audit source, never a label source" (`master_source_inventory.md` priority 4).

## Licence / access gating

- CF Benchmarks site: "Use and distribution of the CF Benchmarks data requires a license", and no use "to create, calculate, issue, settle... any financial instruments... without the express written consent" (VERIFIED-BY-DOC, batch 3). Site terms bar scripts and robots: `cfbenchmarks.com` is never fetched by agents.
- Kalshi passthrough and channel: Kalshi terms plus CF Benchmarks terms. Storage, ML, and derived-model rights UNRESOLVED (`b09_source_qualification.md` A-2 row T: AMBIGUOUS). Restatement policy UNKNOWN.
- Owner actions already drafted: M1 (Kalshi: price, depth, rights of the CFB entitlement) and M4 (CF Benchmarks quote with first-published vintages, restatement policy, and point-in-time constituents). `owner_source_action_sheet.md` status NEEDS_LICENCE_QUOTE.
- Protected-information class: BRTI (every route) is a direct equivalent observable and settlement-reference input for protected BTC windows. It must be in the guard's equivalence catalog before any real-data use (E-U1, RT-B3-05).

## PMV relevance: unique vs derivable

- **Unique:** the exact settlement-reference path. That covers the index value in settlement units; a partially realised 60 s settlement average inside the final minute; rulebook edge cases (trimmed vs plain mean, rounding, no-data rule, ignored corrections); and constituent exclusions or stale-book handling that no single exchange shows.
- **Derivable or approximable:** BRTI's short-horizon *direction and velocity*. It is a depth-weighted mid of the same order books (Coinbase, Kraken, Bitstamp, Gemini, LMAX, Bullish, Crypto.com) that PMV can observe directly. A multi-venue mid from constituent books should track it closely in normal conditions. The size of the gap near the strike is exactly what the planned free "BRTI-proxy disagreement test" (BIZ-B9C-07) must measure. Not yet tested.
- No predictive claim is made.

## Comparison E — Kraken vs BRTI: predictive market information vs exact settlement/reference information

| | Kraken (B-1/B-2/B-3: trades, L2 book) | BRTI (B-10/12/13/14) |
| - | - | - |
| Economic object | One constituent venue's tradable market: trades, aggressor side, book depth, queue changes | An index: a depth-weighted mid across about 7 constituents, ~1 Hz or 200 ms |
| Information type | **Microstructure and flow**: order-flow imbalance, trade intensity, book pressure. These are the raw inputs of "velocity" | **Reference state**: the value the contract settles on, and the realised part of the settlement average |
| Lead/lag | Venue events happen first. An index built from books cannot lead its inputs (INFERENCE) | Lags or smooths its inputs. Gains cross-venue robustness and loses flow detail |
| Coverage of BRTI | Partial (one of about 7 venues; weight UNKNOWN) | Complete by definition |
| Cost / licence | Free archive plus WS; permission request M2 pending | Licence or entitlement; quote pending |

Assessment (evidence-based reasoning; INFERENCE, untested):

1. **BRTI's unique value is settlement fidelity, not a new velocity signal.** Any velocity BRTI shows already exists, earlier and in more detail, in its constituents' books and trades. BRTI adds (a) the exact level relative to the strike or open reference in settlement units, (b) the cross-venue basis (Kraken mid minus BRTI), and (c) the realised fraction of the final-minute average. (c) is a strong, mechanical, late-window input: once k of 60 seconds are averaged, the remaining uncertainty shrinks by a known amount. That is averaging arithmetic (repo E-U5), not velocity, and must be labelled separately so it is not mistaken for predictive edge.
2. **Where the gap matters:** only near the strike in the final minutes, where a basis of a few dollars can flip the label. That is the strategy's operating region (late-window, high-confidence). So the BRTI route is low-value for feature discovery and potentially high-value for label-adjacent features and calibration in the tail. It is never needed as a label source (labels = official `expiration_value`/`result`).
3. **Sequencing recommendation (consistent with the existing plan):** develop velocity features on Kraken (plus other licensed constituents). Run the free BRTI-proxy disagreement test, using official `expiration_value` as truth and a constituent-mid proxy. Buy a BRTI route only if the proxy error near the strike is material. For prospective capture, the Kalshi `cfbenchmarks_value` channel (if the entitlement is affordable) is the cheapest BRTI record aligned to KXBTC15M windows.

## Open questions / unverified items

1. DET-2: the rulebook governing KXBTC15M (BTC trimmed mean, CRYPTO, or CRYPTOSHORT), its lookback, rounding, tie rule, and no-data rule. Source: Kalshi contract terms (owner).
2. Whether the settlement average uses 1 Hz ticks or 200 ms ticks, and whether Kalshi's convenience average equals the official settlement value.
3. BRTI methodology document (RTI guide), parameters, stale-book rules, and constituent weights: owner must supply (AR-U2/AR-9).
4. Restatement and correction policy; whether first-published vintages are available.
5. Passthrough history depth and retention; entitlement price; demo availability (U21).
6. Whether `cfbenchmarks_value` WS needs an entitlement beyond authentication.
7. `window_end_ts_exclusive` naming vs "close tick is included" (Kalshi doc conflict).
8. CF Benchmarks' own timestamp semantics (calculation vs publication time).
