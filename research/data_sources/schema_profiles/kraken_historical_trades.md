# Kraken spot — historical trades (downloadable archive and REST `Trades`)

**Status:** REST `GET /0/public/Trades`: **ACTUAL SAMPLE INSPECTED** (5,000 rows, 2023-03-01, old development interval). Downloadable trade archive (`Kraken_Trades_*.zip`): **SCHEMA INSPECTED**; sample **ACCESS BLOCKED** (`assets.kraken.com`, refused by the PMV egress proxy). Both surfaces: **LICENCE OPEN** (Kraken API notice requires prior permission for non-personal commercial use; outreach M2, `research/data_sources/owner_source_action_sheet.md` B1).

## Evidence

| URL | Retrieved (UTC) | HTTP | Bytes | SHA-256 | Grade |
|---|---|---|---|---|---|
| https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales- | 2026-10-19T04:22:43Z | 200 | 996,496 | `88e3abffe0893e49267e97dbc1066b8155bfd10e155cd90a98188a56f0355089` | VERIFIED-BY-DOC (page "Last updated: October 12, 2026") |
| https://docs.kraken.com/api-reference/market-data/get-recent-trades.md | 2026-10-19T04:19:53Z | 200 | 7,882 | `1b213ed004082e55abb4e3c9a352e4b8432d8550583adef35005a53be5b3432b` | VERIFIED-BY-DOC (OpenAPI `spot-rest.yaml` 1.1.0) |
| https://docs.kraken.com/exchange/guides/general/historical-data.md | 2026-10-19T04:19:56Z | 200 | 6,942 | `d415740c12a57127480b93e37d10cdcaef03d56e90cca9ab72eb5a486adbc5d1` | VERIFIED-BY-DOC |
| https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_Full.zip.part04 (HEAD only) | 2026-10-19 | — | — | — | **BLOCKED** by proxy (`assets.kraken.com`) |

### Sample manifest (raw files deleted after inspection)

Source: `https://api.kraken.com/0/public/Trades?pair=XBTUSD&since=<cursor>&count=1000`; tool `research/data_sources/recon_tools/kraken_rest_trades_sample.py`; JSON, uncompressed; sampled interval 2023-03-01T00:00:00Z to about 03:27Z.

| Page | `since` (ns) | Retrieved (UTC) | Bytes | Rows | SHA-256 |
|---|---|---|---|---|---|
| 0 | 1677628800000000000 | 2026-10-19T04:21:20.025Z | 67,804 | 1,000 | `535b0aad173a740f8541328b9ea118319e65e987d68ab80201e6fc6487fc2d54` |
| 1 | 1677631577068543302 | 2026-10-19T04:21:22.490Z | 67,777 | 1,000 | `282dd7e4a5677d76ecdf4794acbb2e0b55cbd293ba4a54ebef0dcb8e1cca48d7` |
| 2 | 1677633786789226589 | 2026-10-19T04:21:24.783Z | 67,801 | 1,000 | `e40c648c7708034b8ab562d9a6fb077e89539eb1fe0d4c8a69b266d4c4a78887` |
| 3 | 1677636706747934046 | 2026-10-19T04:21:27.033Z | 67,771 | 1,000 | `8b3677e2d35fdc2c000533a366fd07be4e7c7cb47c6228fd9e4ed4624c789bc1` |
| 4 | 1677640022432181603 | 2026-10-19T04:21:29.698Z | 67,824 | 1,000 | `5268bd02ea88e01f4d3d97840ad39c213c06486ef3caecc0e13fd9a06ba37b4c` |

Total 339,000 bytes, 5,000 rows (4,996 unique trades; see pagination). Profiled with `recon_tools/kraken_rest_trades_profile.py`.

## Access and connectivity

- `api.kraken.com`: reachable through the proxy (HEAD `/0/public/SystemStatus` → 404, GET `Trades` → 200). Public, unauthenticated.
- `support.kraken.com` and `docs.kraken.com`: reachable (documentation).
- `assets.kraken.com` (archive file host): **refused by the proxy**. No mirror or alternative path was tried.

## Transport, format, delivery

| Surface | Delivery | Format | Compression | History |
|---|---|---|---|---|
| Trade archive | Static ZIP files; full history in ~2 GB parts `Kraken_Trades_Full.zip.part00`–`part13`, plus quarterly incremental ZIPs `Kraken_Trades_2026Q1/Q2/Q3.zip`; published SHA-256 for parts and for the joined ZIP | One CSV per pair, header row; `MANIFEST.json` per archive | ZIP (deflate assumed; not inspected) | "each pair from its first trade on Kraken through 30 September 2026" |
| REST `Trades` | HTTPS JSON, 1,000 rows per call, cursor `since`→`last` | JSON arrays | none observed | From the first trade (`since` paging); "1–2 seconds" safe delay per call |

Doc conflict, now explained: the developer guide says "Kraken does not provide a bulk historical data dump or websocket replay service", while the support article (updated 2026-10-12) publishes the archive. The archive is a support/marketing download, not an API product. B09 E-B09-BTC-3 should be updated: the archive is documented and current.

## Fields

Archive (verbatim, support article): "each row has seven columns: `timestamp, price, volume, type, order_type, misc, trade_id` where `type` is `b` (buy) or `s` (sell) and `order_type` is `l` (limit) or `m` (market). Rows are ordered by timestamp." **This corrects B09**, which recorded only timestamp, price, and volume (`inventory_btc_detail.md` B-2, from search summaries).

REST (verbatim, OpenAPI `trade` schema): "`[<price>, <volume>, <time>, <buy/sell>, <market/limit>, <miscellaneous>, <trade_id>]`".

| Field (REST position) | Native type observed | Official semantics | PMV class | Sample findings |
|---|---|---|---|---|
| price [0] | JSON string | "price" | DIRECT | 5 decimal places in all 5,000 rows; parse as Decimal |
| volume [1] | JSON string | "volume" | DIRECT | 8 decimal places in all rows |
| time [2] | JSON **number** (float) | "time" (Unix seconds) | DIRECT (event time) | 3–7 fractional digits with trailing zeros dropped (7 digits in 76%): the pattern of a shortest round-trip float64 repr. The server serializes a double, so sub-µs digits are representation artifacts, not 100 ns precision (B10 review API-B10-04). Normalize to integer µs with a documented rounding rule; join REST, WS, and archive trades on `trade_id`, never on time |
| buy/sell [3] | string | REST: "buy/sell"; archive: "`b` (buy) or `s` (sell)"; WS v2 `trade.side`: "The side of the taker order" | DIRECT (aggressor side **inferred** for REST and archive from the WS definition; verify on the first acquired archive file) | value set {`b`, `s`}; no nulls |
| market/limit [4] | string | "market/limit" (taker order type, per WS `ord_type`: "The order type of the taker order") | DIRECT / SOURCE_SPECIFIC | value set {`l`, `m`} |
| miscellaneous [5] | string | "miscellaneous" | UNKNOWN | empty in all 5,000 rows; semantics undocumented |
| trade_id [6] | JSON integer | not described on the REST page; WS v2: "Trade identifier is a sequence number, unique per book" | DIRECT (sequence) | contiguous (+1) within pages |
| `result.last` | string (ns) | "ID to be used as since when polling for new trade data" | — | a nanosecond timestamp matching the last row's time to float precision (it carries true ns digits); not a trade_id. Pass it verbatim as the next cursor |

Archive `timestamp` precision and format (integer seconds vs fractional) are **UNKNOWN**: the article does not state them and the file was not inspectable.

## Timestamps

- **Event time:** exchange trade time only. No receipt or publish time exists in either surface. Receipt-time truth is **ABSENT** historically; it exists only in prospective PMV capture (WS `recv_ns`).
- Time zone: Unix epoch (UTC). Precision: sub-microsecond tokens in REST, carried as float; archive precision UNKNOWN.

## Sequencing and pagination

- `trade_id` is strictly +1 within each page (4,995 of 4,995 within-page steps).
- **Pagination overlap (OBSERVED at 4 of 4 boundaries; not documented):** the first row of every page repeated the last row of the previous page (same `trade_id`, step 0). The `since` cursor behaved as inclusive. The overlap is all trades whose time equals `last`, which can be more than one. Collector rules (B10 review API-B10-02):
  - pass `last` verbatim as a string; never derive the cursor from row times;
  - drop overlap rows only after asserting they are identical to the previous page's rows;
  - assert `trade_id` steps of exactly +1 across page boundaries and fail closed on any gap (dedupe alone would silently accept a gap);
  - detect a non-advancing `last` (a stall if more than 1,000 trades shared one timestamp).
- Timestamps are non-decreasing. Among the 4,995 unique trades, no two consecutive distinct trades share a timestamp. (An earlier draft reported 0.08%: those were the four duplicated boundary rows; review API-B10-03.)

## Sample spacing (old 2023-03-01 interval; descriptive only)

Inter-trade gap: p10 ≈ 0.00004 s, p50 ≈ 0.08 s, p90 ≈ 8.3 s, p99 ≈ 27 s, max ≈ 67 s. Trades per minute: p10 8, p50 18, p90 50 (207 one-minute buckets). These were computed before de-duplication and include the four boundary duplicates (negligible effect); the tool now de-duplicates first. Bursts of sub-millisecond prints with the same side are common: one taker order sweeping several levels appears as several prints (consistent with the WS note that a batch "does not mean that these trades resulted from a single taker order"). These numbers describe one old three-hour window and are not representative.

## Instrument identity

Pair key `XXBTZUSD` (internal name; `assetVersion=1` gives `BTC/USD`). The archive uses one CSV per pair; the file naming was not inspected. No expiry or settlement fields (spot).

## PMV relevance and redundancy

- The archive and REST `Trades` carry the **same seven fields** (archive: "The same data is available programmatically via Kraken's public REST API"). They are two delivery paths for one upstream, not independent sources. The archive is the efficient bulk path; REST is the gap-fill path after the archive cutoff and a reconciliation check (dedupe by `trade_id`).
- Trades give price, size, aggressor side, taker order type, and a per-book sequence. They contain no quotes, spread, or depth.
- OHLCV, VWAP, trade count, signed volume, and trade-flow imbalance at any bar size are **DERIVABLE** from trades (see `kraken_ohlcvt.md`).
- Kraken spot is a **PROXY** for BRTI (Kraken is one BRTI constituent; `cf_benchmarks_brti.md`).

## Open questions

1. Archive `timestamp` format and precision; whether archive `trade_id` equals REST/WS `trade_id` for the same trade (needed for archive/REST reconciliation). Resolve on the first acquired file, inside the acquisition gate.
2. `misc` semantics.
3. Whether the archive includes trades later busted or corrected (no doc).
4. Licence (M2) for archive and REST use in model development.
