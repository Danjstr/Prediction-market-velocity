# Kalshi — series, event, and market metadata (contract, rule, and settlement metadata)

**Status:** **SCHEMA INSPECTED** (OpenAPI re-fetched 2026-10-19; field-level verbatim evidence in `research/kalshi/api_documentation_findings.md` §3.1–3.3, §8, §11). Samples **ACCESS BLOCKED**: `api.elections.kalshi.com` is on the sandbox deny list (`CONNECT tunnel failed, response 403`; "host is on the deny list"). **LICENSE GATED**: Kalshi Developer Agreement scope (outreach M1; D-B09-22). Contract-terms PDFs are on `kalshi.com` / `kalshi-public-docs.s3.amazonaws.com`, both refused (owner download, K2/G4).

## Evidence

| URL | Retrieved (UTC) | HTTP | Bytes | SHA-256 | Grade |
|---|---|---|---|---|---|
| https://docs.kalshi.com/openapi.yaml | 2026-10-19T04:18:27Z | 200 | 375,483 | `bd0c218a65b79f5ee2a27689a5b1d902b6df67663864373bf9e9980f0f9ad9ee` | VERIFIED-BY-DOC (`info.version: 3.34.0`, same version as the 2026-10-15 snapshot; bytes differ) |
| https://docs.kalshi.com/changelog.md | 2026-10-19T04:19:00Z | 200 | 232,352 | `318819a3f334bc448eb84f582a5d7695a99953bcabfdd74a82bf061ff4c3dca2` | VERIFIED-BY-DOC |
| https://docs.kalshi.com/llms.txt | 2026-10-19T04:18:26Z | 200 | 65,098 | `4b97d36e6e5c0b949d0a9bdced42fe0499be277a0a9c2dc8f66342fae14520f0` | VERIFIED-BY-DOC |
| 2026-10-15 snapshot and field quotes | — | — | — | hashes in `research/kalshi/api_documentation_findings.md` §0 | repo-Git (VERIFIED-BY-DOC at the time) |
| https://api.elections.kalshi.com/trade-api/v2/exchange/status | 2026-10-19 | — | — | — | **BLOCKED** (deny list) |

**Delta check 2026-10-15 → 2026-10-19.** Changelog entries added since the snapshot (labels "October 15, 2026" and "October 22, 2026") concern the portfolio-balance rate-limit bucket, Margin REST schema corrections, Margin funding bars, and FIX mass cancel. None changes a market-data field used here. The `Trade`, `MarketCandlestickHistorical`, `PriceDistributionHistorical`, `BidAskDistributionHistorical`, and `GetHistoricalCutoffResponse` schemas were re-extracted from the 2026-10-19 file and match the snapshot field lists. (A changelog label dated after today's date, 2026-10-19, is a vendor label; effective dates are unverified, per Red-Team C10.)

**Terms-first note.** `docs.kalshi.com` content was fetched under the owner's B10 charter ("official vendor documentation; public API documentation; public schemas"), which this batch relies on for B10 only. Whether the charter also answers D-B09-17(a) generally is left to the owner. Kalshi's terms remain on refused hosts.

## Access, transport, delivery

REST JSON over HTTPS, cursor-paged. Public market-data endpoints need no authentication; historical tier: `/historical/markets`, `/historical/markets/{ticker}` (markets settled before `market_settled_ts`). Series and events "will always still be available through their original endpoints". Live metadata changes also arrive on WS `market_lifecycle_v2` (`kalshi_orderbook.md`).

## Fields (selected, PMV-relevant)

| Object.field | Type | Official semantics (short) | PMV class |
|---|---|---|---|
| Series `ticker`, `frequency`, `category`, `tags` | string | `frequency` is free text: "will be something human-readable" | DIRECT (do not key logic on `frequency`) |
| Series `settlement_sources[] {name,url}` | array | "the official sources used for the determination of markets within the series. Methodology is defined in the rulebook." | DIRECT; SOURCE_SPECIFIC (only Kalshi states its settlement source) |
| Series `contract_url`, `contract_terms_url` | URL | original filing; "current terms" | DIRECT (pointer to the governing rule text, which lives off-API) |
| Series `fee_type`, `fee_multiplier`; Event `fee_type_override`, `fee_multiplier_override`; `/series/fee_changes`, `/events/fee_changes` | enum, double, history | fee structure; overrides "take precedence" | DIRECT; SOURCE_SPECIFIC (needed for after-fee break-even) |
| Event `product_metadata.cadence` (e.g. `fifteen_min`) | free object | changelog | DIRECT (series discovery) |
| Market `open_time`, `close_time`, `expected_expiration_time`, `latest_expiration_time`, `settlement_ts`, `created_time`, `updated_time` | date-time (offset/precision not stated) | `close_time` "May be moved earlier if `can_close_early` is true" | DIRECT. `close_time` and the expiry fields give **time remaining** and the **contract reference-end time** |
| Market `strike_type`, `floor_strike`, `cap_strike`, `functional_strike`, `custom_strike` | enum, number | "Minimum expiration value that leads to a YES settlement" etc. | DIRECT; can change intra-life (`metadata_updated`) |
| Market `rules_primary`, `rules_secondary` | string | summaries; legal terms are behind `contract_terms_url` | DIRECT (summary only) |
| Market `result` | enum `yes`, `no`, `scalar`, `''` | outcome | DIRECT (the label) |
| Market `expiration_value` | string | "The value that was considered for the settlement" | DIRECT; SOURCE_SPECIFIC — the realized reference value per market (format per series UNRESOLVED) |
| Market `settlement_value_dollars` | nullable | YES/LONG settlement value, after determination | DIRECT |
| Market `status` | enum | lifecycle (`initialized … finalized`) | DIRECT |
| Market `price_ranges[] {start,end,step}` | array | "the source of truth for valid prices" | DIRECT (tick grid) |
| Market `yes_bid_dollars`, `yes_ask_dollars`, `last_price_dollars`, `yes_bid_size_fp`, `yes_ask_size_fp`, `volume_fp`, `open_interest_fp` | strings | current snapshot at request time | DIRECT but **current-state only**: no historical value without a timestamped capture |
| Market `is_provisional` | bool | "the market may be removed after determination if there is no activity on it" | provenance risk (survivorship) |

## Timestamps

All REST times are `format: date-time`; timezone and sub-second precision are not stated (UNRESOLVED; require an explicit offset and fail closed). Metadata objects carry no as-of time other than `updated_time` ("Time of the last non-trading metadata update"), so point-in-time reconstruction of strikes or rules from a later REST read is not guaranteed; the WS lifecycle stream or a timestamped PMV snapshot is the point-in-time source.

## Settlement / reference

Kalshi metadata states **which** reference settles a series (`settlement_sources`), and after the fact the realized `expiration_value`, but not the reference series itself. BTC: CF Benchmarks BRTI per rule text (repo evidence; `cf_benchmarks_brti.md`). Gold: Pyth, feed and candle unresolved (DET-1; `pyth_gold.md`). The governing averaging window and tie rule live in the contract terms, not in the API (B09 §11).

## PMV relevance

Indispensable and non-substitutable (labels, contract definitions, fee schedule, timing). No other source carries Kalshi contract semantics. Polymarket and the underlying-market sources cannot replace any field here.

## Open questions

Exact KXBTC15M / KXGOLD15M rule text (owner download); `expiration_value` format; history depth of `/historical/markets` (UNRESOLVED in docs); licence (M1).
