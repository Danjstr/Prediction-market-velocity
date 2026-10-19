# Tardis.dev — Kraken spot historical book, trades and quotes (CSV datasets and raw replay)

**Status:** SCHEMA INSPECTED (official CSV column schemas and Kraken coverage page read verbatim on docs.tardis.dev; no sample downloaded); samples and API ACCESS BLOCKED (`datasets.tardis.dev`, `api.tardis.dev`, `tardis.dev` are not requested under B10 rules); LICENSE GATED (paid subscription; Tardis licence clause 9.5 limits AI/ML use; see licence section). OPTIONAL comparison source (owner sheet O2, TIER 2: "only if research justifies").

**Evidence:** all retrieved 2026-10-19 by curl through the PMV egress proxy (no redirects followed; none occurred).

| URL | retrieved UTC | HTTP | bytes | sha256 | grade |
|---|---|---|---|---|---|
| https://docs.tardis.dev/llms.txt | 2026-10-19T04:18Z | 200 | 18374 | 2cb184d9948e482b70527be829245d7cb2cda9809c4f1c8ce5a966b0e06f7739 | VERIFIED-BY-DOC (index) |
| https://docs.tardis.dev/llms-full.txt | 2026-10-19T04:18Z | 200 | 1071935 | c9ae7e79b63c8aa0d832c4440b9d3da4a67b494edb2fccc33617d85ca0744d53 | VERIFIED-BY-DOC (searched only for specific terms) |
| https://docs.tardis.dev/downloadable-csv-files/data-types.md | 2026-10-19T04:18:43Z | 200 | 47528 | 896629e0eadee1dd64dd297ad2ae0fbbf5dd8d0c6c4e92823089e86aa432bf42 | VERIFIED-BY-DOC |
| https://docs.tardis.dev/historical-data-details/kraken.md | 2026-10-19T04:18:43Z | 200 | 9323 | 6f797dac532863f858a5f41d304b614699a41e85be5dc9abcdd191b3f5e9a279 | VERIFIED-BY-DOC |
| https://docs.tardis.dev/historical-data-details.md | 2026-10-19T04:18:43Z | 200 | 12110 | efc6fdd9cd6ff87e8ef78b91c9f2ba570a65ce6bf74bda453d4d153837b49a6c | VERIFIED-BY-DOC |
| https://docs.tardis.dev/faq/data.md | 2026-10-19T04:18:43Z | 200 | 45100 | 190edde644e019135a8d32b7f14589fd25008153aa575ce1145082bd48dca408 | VERIFIED-BY-DOC |
| https://docs.tardis.dev/faq/order-books.md | 2026-10-19T04:18:43Z | 200 | 27014 | ff5473253945207caf37d989dda8721b49cb5c2b81a81486a45bc52642bbb8ee | VERIFIED-BY-DOC |
| https://docs.tardis.dev/faq/billing-and-subscriptions.md | 2026-10-19T04:18:43Z | 200 | 28465 | 655877ad6e0c07bd73b8b34b3b1ff8da35a6cd0f2d06921f4fbd6035fc92ddad | VERIFIED-BY-DOC |
| https://docs.tardis.dev/legal/terms-of-service.md | 2026-10-19T04:18:43Z | 200 | 50714 | 4c084c8204b8e3a1e5d64b7f334e9dba9b516918ad6018b066011a5a2532cfe8 | VERIFIED-BY-DOC (licence text on docs host) |
| https://docs.tardis.dev/api/http-api-reference.md | 2026-10-19T04:18:43Z | 200 | 29367 | cf99ac40ce65411a46f99eab3012e12622937a0045dd92293d371f51c31988cb | VERIFIED-BY-DOC |
| https://docs.tardis.dev/downloadable-csv-files/overview.md | 2026-10-19T04:18:43Z | 200 | 13026 | 2d288160dfa51ce3e5b12ef914ad3675e45c52f5326f96f73122cd834c38fbca | VERIFIED-BY-DOC |
| https://docs.tardis.dev/downloadable-csv-files/api.md | 2026-10-19T04:18:43Z | 200 | 13387 | 9bef7504a3915daaee7024a9c2907199daea05fc72f74c36811e980a2b12745b | VERIFIED-BY-DOC (not relied on beyond overview) |
| https://docs.tardis.dev/tardis-machine/data-types.md | 2026-10-19T04:18:43Z | 200 | 20164 | fd75c2bb139110a014364c8368e4daf503636de2b5ae95dc911e21c14fcc06bf | VERIFIED-BY-DOC (not relied on) |
| https://docs.tardis.dev/faq/general.md | 2026-10-19T04:18:43Z | 200 | 31032 | ba0b76cdd68ec9ea07a09f963562c609688543f55ec8381a4832285110d6ff3c | not relied on |
| research/data_sources/owner_source_action_sheet.md (O2, B1, B2) and master_source_inventory.md (B-1, B-2, B-3, B-8) | — | — | — | git HEAD of b10/source-reconnaissance | repo-Git |

The GitBook "ask" endpoint (`/index.md?ask=`) advertised in llms.txt was not used.

## Access and connectivity

- Documentation host `docs.tardis.dev`: reachable (all requests 200).
- Data hosts **not requested** (BLOCKED by B10 brief): `tardis.dev` (account/order), `api.tardis.dev` (HTTP API `/v1/data-feeds/kraken`, `/v1/exchanges/kraken` coverage and incident reports), `datasets.tardis.dev` (CSV files, including free first-of-month samples).
- Access methods (VERIFIED-BY-DOC, billing FAQ): "Academic and Solo include downloadable CSV files; Professional and Business add the raw data replay API, Tardis Machine and the instruments metadata API." An API key is needed except for free first-of-month data.

## Transport, format, compression, delivery (historical vs live)

- **CSV datasets** (normalized, one file per exchange/data type/day/symbol, gzip; URL pattern `datasets.tardis.dev/v1/<exchange>/<data_type>/<YYYY>/<MM>/<DD>/<SYMBOL>.csv.gz` as shown in doc links). Format: "columns delimiter: **, (comma)**", "date time format: **microseconds since epoch**", "date time timezone: **UTC**". CSV for a day "available on the next day around 06:00 UTC".
- **Raw replay HTTP API** (`/v1/data-feeds/:exchange`): "Our HTTP API provides data only in exchange-native format." Response is NDJSON: "Each line starts with the local timestamp in ISO 8601 format, followed by one exchange-native JSON message"; compression `zstd` or `gzip`. Served in minute slices; "most recent data available is approximately T-6 minutes".
- **Normalized replay**: client libraries (Python/Node) and self-hosted tardis-machine normalize client-side (trade, book_change, book_snapshot, quote...).
- Messages are stored unmodified: "Messages provided by exchanges' WebSocket feeds are being stored without any modifications"; "raw data is not corrected after the fact".
- Live: Tardis also offers real-time streaming via its libraries directly from exchanges (out of scope; would be equivalent to PMV's own Kraken WS capture).

## Fields

### Common to all CSV types

| field | native type | official semantics | PMV class | notes |
|---|---|---|---|---|
| exchange | string | "exchange id" (Kraken = `kraken`) | SOURCE_SPECIFIC | |
| symbol | string | "instrument symbol as provided by exchange (always uppercase)" | SOURCE_SPECIFIC | Kraken symbol break: "Use v1 symbols before **2026-07-10** and v2 symbols from that date onward" (`XBT/USD` → `BTC/USD`); CSV sample links use `XBT-USD` |
| timestamp | int µs epoch | "timestamp provided by exchange in **microseconds since epoch** - if exchange does not provide one `local_timestamp` value is used as a fallback" | DIRECT (event time, conditional) | Fallback silently substitutes receipt time; per-row provenance of which one is used is not flagged in the CSV (UNKNOWN for Kraken book rows) |
| local_timestamp | int µs epoch | "message arrival timestamp in **microseconds since epoch**" | DIRECT (Tardis receipt time) | Rows from one exchange message share a value |

### incremental_book_L2 — `exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount`

| field | official semantics | PMV class |
|---|---|---|
| is_snapshot | "`true` - if update was a part of initial order book snapshot / `false` - if update **was not** a part of initial order book snapshot / If last update was not a snapshot and current one is, then existing order book state must be discarded (all existing levels removed)" | DIRECT |
| side | "`bid` - bid side of the book, buy orders / `ask` - ask side of the book, sell orders" | DIRECT |
| price | "price identifying book level being updated" | DIRECT |
| amount | "updated price level amount as provided by exchange, **not a delta** - an amount of `0` indicates that the price level can be removed" | DIRECT |

Also verbatim: "Files may contain non-snapshot updates before the first snapshot — skip these rows until you encounter the first `is_snapshot=true` row"; multiple levels from one exchange message can be recognized "by grouping rows by the `local_timestamp` field".

### book_snapshot_25 / book_snapshot_5

`exchange,symbol,timestamp,local_timestamp,asks[0].price,asks[0].amount,bids[0].price,bids[0].amount,...` up to index 24 / 4. Reconstructed top-N snapshots "for every update" (doc: "datasets with already reconstructed snapshots for every update"). DERIVABLE from incremental_book_L2.

### trades — `exchange,symbol,timestamp,local_timestamp,id,side,price,amount`

| field | official semantics | PMV class |
|---|---|---|
| id | "trade id as provided by exchange, empty if exchange does not provide one" | SOURCE_SPECIFIC (Kraken v1 trade messages: UNKNOWN whether an id exists; likely empty pre-2026-07-10 — not verified) |
| side | "liquidity taker side (aggressor), possible values: `buy` … `sell` … `unknown` - exchange did not provide that information" | DIRECT |
| price / amount | "trade price as provided by exchange" / "trade amount as provided by exchange" | DIRECT |

CSV trades are deduplicated ("for downloadable CSV files we deduplicate tick-by-tick trades data").

### quotes — `exchange,symbol,timestamp,local_timestamp,ask_amount,ask_price,bid_price,bid_amount`

"Top of the book (best bid/ask) data reconstructed from exchanges' real-time WebSocket order book L2 data feeds, with best bid/ask recorded every time the top of the book changes." Fields "empty if there aren't any asks/bids". DERIVABLE from incremental_book_L2.

### Other CSV types (not applicable to Kraken spot; listed for completeness)

- `book_ticker` (native exchange BBO feed; same columns as quotes) — supported-exchange list not checked for Kraken (UNKNOWN; Kraken `ticker`/`spread` raw channels exist, see below).
- `derivative_ticker`: `...,funding_timestamp,funding_rate,predicted_funding_rate,open_interest,last_price,index_price,mark_price` (derivatives only; relevant to Kraken Futures `cryptofacilities`, not spot).
- `liquidations`: `...,id,side,price,amount`; side "`buy` - short position was liquidated / `sell` - long position was liquidated".
- `options_chain`: `...,type,strike_price,expiration,open_interest,last_price,bid_price,bid_amount,bid_iv,ask_price,ask_amount,ask_iv,mark_price,mark_iv,underlying_index,underlying_price,delta,gamma,vega,theta,rho` (OPTIONS grouped symbol only; Deribit/OKX/Binance options, not Kraken).

Synthetic illustration only (no real values):

```
exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount
kraken,<SYMBOL>,<exch_ts_us:int>,<local_ts_us:int>,true,bid,<price:decimal-string>,<amount:decimal-string>
kraken,<SYMBOL>,<exch_ts_us:int>,<local_ts_us:int>,false,ask,<price:decimal-string>,0
```

## Timestamps

- **Exchange time** (`timestamp`): µs epoch in CSV; falls back to receipt time when the exchange provides none.
- **Receipt time** (`local_timestamp` / raw `localTimestamp`): "Each message received via WebSocket connection is timestamped with 100ns precision using synchronized clock at arrival time (before any message processing) and stored in ISO 8601 format." CSV exposes it at µs; raw replay exposes ISO 8601 (client option `withMicroseconds` otherwise ms).
- Ordering: "Row order in both replay API responses and CSV files reflects the original capture order"; "all messages are sorted by `localTimestamp`"; local timestamps "are always monotonically increasing"; exchange timestamps can be non-monotonic after reconnects. No cross-channel ordering guarantee ("a trade's exchange timestamp does not guarantee that the order book state at that exact timestamp reflects the pre- or post-trade book").
- Timezone: "UTC, always."
- **Collection location matters for receipt time**: Kraken collector "located in GCP europe-west2 region (London, UK)", via "multiple WebSocket connections" to `wss://ws.kraken.com/v2` (v1 `wss://ws.kraken.com` before 2026-07-10). Kraken's own servers per Tardis: "Equinix data center (London, UK) since **2025-11-01**. Before that … AWS eu-west-1 region (Dublin, Ireland) from **2024-01-20**, and initially in AWS us-west-2 region (Oregon, USA)." So `local_timestamp − timestamp` has at least two structural regime breaks (2024-01-20, 2025-11-01) unrelated to market conditions, and none of them reflects PMV's own collector location.

## Sequencing and book semantics

- Kraken Tardis book: "top 1000 levels initial order book snapshot and updates", "real-time" (WS v1 `book` "recorded with depth=1000"; v2 `book` "with `depth=1000`").
- **No Kraken L3 at Tardis**: "Historical L3 data is currently available via API for Bitfinex, Coinbase Exchange and Bitstamp - remaining supported exchanges provide L2 data only." (Corrects the owner sheet O2 shorthand "L2/L3" for the Kraken case.)
- Snapshots: at 00:00 UTC daily (connection re-subscribed) and after every connection drop; a new snapshot batch must reset local book state. "Snapshot rows … may contain price levels outside the nominal top-N depth".
- Sequence/checksum: the CSV schema has no sequence or checksum column. Raw replay preserves exchange-native messages unmodified, so Kraken's native book `checksum` fields should be present in raw replay (SECONDARY inference from "stored without any modifications"; not verified against a sample). Tardis performs "order book sequence number validation for exchanges that provide those".
- Completeness: "collection completeness is around 99.9% and reaches 99.99% on many days … not guaranteed"; gaps "are permanent"; incidents listed in `incidentReports` (on blocked `api.tardis.dev`).
- Kraken captured channels — v2 (since 2026-07-10): `trade`, `book`, `ticker` (`event_trigger=bbo`), `instrument`; v1 (until 2026-07-10): `trade`, `book`, `spread`, `ticker`. Raw format is "the same as provided by real-time Kraken WebSocket v2 API from 2026-07-10 onward, with addition of local timestamps. Data before 2026-07-10 uses Kraken WebSocket v1 format."

## Instrument / contract identity, expiry, reference-end, settlement

Spot only; no expiry/settlement fields. Kraken coverage "for **all its currency pairs** is available since **2019-06-04**". Symbol identity changes at 2026-07-10 (`XBT/USD` available 2019-06-04 to 2026-07-10; `BTC/USD` from 2026-07-10). No BRTI or Kalshi reference fields; Tardis is an exchange-feed archive, not a settlement source.

## Licence / access gating

- Repo evidence: owner_source_action_sheet.md O2 — "Historical order books, only if research shows need", PAID_SELF_SERVICE, cost "Varies by exchange, dataset, history, and billing … → UNKNOWN", licence "reportedly allows internal trading models (OWNER_VERIFY)"; TIER 2. master_source_inventory.md B-8: single class from about $350–700/month, quarterly minimum; All Exchanges about $650–1,200/month (S); §4 step 5 "Tardis smallest slice — only after the trigger in §4.4". No prices appear on the docs pages read (pricing lives on blocked `tardis.dev`).
- Plans (VERIFIED-BY-DOC): Kraken is in the "Spot" plan; Coinbase only in "All Exchanges". History depth: yearly = 4 years (Business: all since 2019-03-30), quarterly = 12 months, monthly = 4 months. "We don't sell single instruments or date ranges."
- Free data (VERIFIED-BY-DOC; **documented only, not downloaded**): "Data for the first day of each month is free for every exchange and data type, as CSV files and through the raw data replay API, without an API key." Free trial: "covers all exchanges for days 1–10 of the previous calendar month (UTC)", 20 GB.
- Licence terms (Terms of Service on docs host, VERIFIED-BY-DOC):
  - 9.1/Permitted Use: "internal business, research, educational or personal use by the Customer and Customer Users only".
  - 9.4: licence for downloaded data "including sample and trial Data … is perpetual and survives termination".
  - 9.5 AI and ML: "the Customer may develop, train and use task-specific quantitative or statistical models for its own market research, trading strategy development, backtesting, trading execution, market simulation or risk management … It does not cover general-purpose AI models, foundation models, large language models". And: "Before disclosing Data, Manipulated Data or Derived Data to an external service provider … the Customer must bind the recipient by written terms … Those terms must give Supplier an express right to enforce". "This Clause applies to all Data … including paid, sample and trial Data."
  - Using first-of-month free files accepts these terms (consistent with inventory note "Tardis first-of-month files, where using them accepts the licence (B-8)").
- **PMV-specific licence concern (new, for owner):** PMV development uses LLM agent sessions (third-party hosted). Releasing Tardis rows into agent context may be "disclosing Data … to an external service provider" and/or use with an LLM outside the "task-specific quantitative" carve-out. This needs an owner/licensor answer before any Tardis data is acquired, including free samples. The deterministic standalone PMV models themselves look within 9.5.

## PMV relevance — comparison D: Kraken free history vs Tardis historical Kraken book

What Kraken's free history contains (lead correction, B10: VERIFIED-BY-DOC in `kraken_historical_trades.md`; the Kraken support article updated 2026-10-12 lists seven archive columns): the downloadable trade archive gives the full public trade tape with `timestamp, price, volume, type` (taker side `b`/`s`), `order_type`, `misc`, `trade_id`, plus OHLCVT 1–1440-minute bars; Kraken REST/WS give **current** book only (B-1, B-3) and recent trades. No free historical book state.

What Tardis Kraken adds that free Kraken history cannot provide:
1. **Historical order-book state** (top-1000 L2, snapshot + updates, 2019-06-04 onward) → historical spread, top-N depth, book imbalance, depth-weighted mid, liquidity withdrawal before moves. Not derivable from trades/OHLCVT.
2. **Historical BBO/quotes** (`quotes`, raw `spread`/`ticker`) → historical bid/ask midpoint and spread at any instant, which the trade tape only approximates (last trade bounces between bid and ask).
3. ~~Trade aggressor side~~ **Not unique (lead correction, B10).** The free Kraken archive and REST `Trades` already carry taker side and `trade_id` (`kraken_historical_trades.md`). Tardis adds only its own µs normalization of the WS trade feed.
4. **A historical receipt-time series** (`local_timestamp`, 100 ns captured, µs in CSV) → the only historical proxy for "when could a live client have known this". It enables point-in-time (as-of-receipt) feature construction and an empirical exchange-to-receipt latency distribution, including feed delays and batching during volatile periods ("WebSocket-sourced historical data reflects what a live trading client would have received"). Caveats: Tardis's London GCP collector is not PMV's collector; Kraken's server moved twice (2024-01-20, 2025-11-01), so latency regimes are not stationary; receipt time is a proxy for, not a measurement of, PMV's own latency.
5. Explicit gap/incident metadata and reconnect snapshots (data-quality provenance that a trade CSV lacks).

Plausible usefulness at the PMV 15–60-minute horizon with late-window decisions (relevance only, **no predictive claim**; schema richness is not predictive evidence):
- The late-window decision depends on the remaining few minutes of underlying movement relative to the strike. Spot-volatility and distance-to-strike features are available from the free trade tape. Book-state features (imbalance, depth, spread widening) are the plausible microstructure additions over a few-minute remaining horizon. Whether they add calibrated information beyond trade-derived volatility is an open empirical question.
- The highest-value item is probably not alpha but **validation infrastructure**: historical mid/spread and receipt-time ordering let PMV test point-in-time correctness, latency sensitivity and staleness rules for the final minutes before prospective PMV capture accumulates enough history. PMV's own Kraken WS capture (B2/B-3) will produce the same fields prospectively for free (and L3 with key), so Tardis only buys the past.
- Relevance to settlement is indirect: Kalshi BTC settles on BRTI (multi-exchange); one exchange's book is a component-level proxy only.
- Recommendation consistent with the approved TIER 2 status: keep Tardis Kraken OPTIONAL. Trigger it only if (a) development on free trades + prospective capture shows book/quote features or latency modelling are decision-relevant, and (b) the licence 9.5 / external-service-provider question is resolved. Smallest slice: Spot plan, quarterly (12 months history).

## Open questions / unverified items

- Kraken coverage endpoint (`api.tardis.dev/v1/exchanges/kraken`: exact channel date ranges, incident reports) — BLOCKED, UNKNOWN.
- Whether Kraken book rows carry an exchange timestamp or fall back to `local_timestamp` (Kraken v1 book messages carry per-level timestamps; how Tardis maps them into `timestamp` is not documented on pages read) — UNKNOWN.
- Kraken trade `id` presence pre/post 2026-07-10 — UNKNOWN.
- Whether `book_ticker` is produced for Kraken — UNKNOWN.
- Checksum presence in raw Kraken replay — SECONDARY inference only.
- Current prices — not on docs host; repo figures are SECONDARY (S).
- Licence: LLM-agent exposure vs clause 9.5 — owner/licensor question (see above).

## B10 review notes (lead)

- **Trigger (S-B10-10):** the promotion trigger is "a prospective test of Kraken book features ends UNDERPOWERED-DEFER with a promising point estimate", not "material improvement and more history needed". See `source_redundancy_decisions.md`.
- **Class (S-9):** Tardis history is archive-class data, so it serves discovery and training only. Selection still runs on receipt-time folds.
- **Depth parity (API-B10-15):** Tardis records Kraken `book` at depth 1000, while PMV would capture depth 10 (preferred). Book features must be truncated to PMV's live depth for training/serving parity. Skip rows before the first `is_snapshot=true`.
