# Databento GLBX.MDP3 — `mbo` schema (market by order, full book; COMEX gold GC, MGC) and the schema-ladder comparison (F)

**Status:** SCHEMA INSPECTED (official Databento docs, verbatim). Also ACTUAL SAMPLE INSPECTED for schema semantics only: official fixture `test_data.mbo.dbn` = GLBX.MDP3 **ESH1, 2020-12-28, 2 records**, not gold. `hist.databento.com` not called. `legal.databento.com` ACCESS BLOCKED. LICENSE GATED (NEEDS_LICENCE_CLARIFICATION, repo-Git).

**Evidence:**

| URL | retrieved UTC | HTTP | bytes | sha256 | grade |
|---|---|---|---|---|---|
| https://databento.com/docs/08-00-00-schemas-and-data-formats.html (content fragment behind the JS docs app; path found in the docs navigation index) | 2026-10-19T04:20:13Z | 200 | 197032 | ca9c2fa7606370eaca55d06bed5a392b45aca261174ef716f34e4d278e28a6da | VERIFIED-BY-DOC |
| https://databento.com/docs/09-00-00-standards-and-conventions.html | 2026-10-19T04:20:13Z | 200 | 365701 | 269c06d436c901e8245d351b71d86387f9bf5b0961d5ebae4ef2afd23d93120e | VERIFIED-BY-DOC |
| https://databento.com/docs/12-00-00-venues-and-datasets.html (section "CME Globex MDP 3.0") | 2026-10-19T04:20:20Z | 200 | 316057 | 1b6851e6c5c12c2670a220ffff11e960c3215ed89e67d675dd053a221b13113e | VERIFIED-BY-DOC |
| https://databento.com/docs/11-00-00-faqs.html | 2026-10-19T04:21:55Z | 200 | 29611 | f744b4336b7e076466d206b0e3570826214449d60f07f3d52045c545047a83c2 | VERIFIED-BY-DOC |
| https://databento.com/docs/03-00-00-reference-historical-http.html | 2026-10-19T04:21:55Z | 200 | 149712 | f7db4a6fedb723a3166efa7c632fe14986ab7a140dd6d7264809b46c142e9753 | VERIFIED-BY-DOC |
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/rust/dbn/src/record.rs | 2026-10-19T04:22:51Z | 200 | 55940 | 2617f6db93abb318a0a9e0ecabdd08876ca8c969e82d5341f102cbc58106f660 | VERIFIED-BY-DOC (reference implementation, Apache-2.0) |
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/rust/dbn/src/compat.rs | 2026-10-19T04:22:52Z | 200 | 32363 | 640e2624e7d88a451830c975db29b444629969fbc9e238909a6518ae41877ca5 | VERIFIED-BY-DOC |
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/rust/dbn/src/publishers.rs | 2026-10-19T04:23:42Z | 200 | 82125 | b8fa6cdce0cf564ec9ff4448d9438b1259bf0d15e825f6bcff5b6da9b1fdb92a | VERIFIED-BY-DOC |
| https://github.com/databento/dbn/tree/main/tests/data (directory listing; HEAD 82f76c1de6f5c8a1f4b3711fac423f88a3f91d67) | 2026-10-19T04:22:23Z | 200 | 420018 | 9243656e22721768f36abfb8c1bb438d9b5ece64c06de91b86fb3281d810992a | VERIFIED-BY-DOC |
| research/data_sources/inventory_pm_gold_detail.md (G-1..G-5, G-26), master_source_inventory.md, owner_source_action_sheet.md (G1, G2, O3) | (Git, branch b10/source-reconnaissance) | — | — | — | repo-Git / SECONDARY |
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/tests/data/test_data.mbo.dbn (deleted after inspection) | 2026-10-19T04:22:33Z | 200 | 465 | 31403d17bf9801842acf59bca668e6b8f19ff4b5d70dce05f0fe70d995fc70d6 | ACTUAL SAMPLE (ES, not gold) |

## Access and connectivity
As in `databento_gc_trades.md`. Live MBO additionally supports a snapshot subscription.

## Transport, format, compression, delivery (historical vs live)
- DBN/CSV/JSON and zstd/none. The record is `MboMsg`, **56 bytes**, rtype 160. Grouped under L3.
- Coverage: "In May 2017, CME introduced MDP 3.0, which provides full granularity for every order event (MBOFD)". Before 2017-05-21, "the MBO schema is not available."
- Billed size is 56 B × every order event at every price level, plus Trade and Fill records. The per-record size is small, but the record count is the largest of all schemas (I; GC/MGC counts UNKNOWN).

## Fields
| field | native type | official semantics (quote) | PMV classification | notes |
|---|---|---|---|---|
| ts_recv | uint64 ns | "The capture-server-received timestamp" | DIRECT | |
| ts_event | uint64 ns | "The matching-engine-received timestamp" | DIRECT | tag 60 |
| rtype | uint8 | "Always 160 in the MBO schema." | SOURCE_SPECIFIC | |
| publisher_id, instrument_id | | as trades | SOURCE_SPECIFIC | |
| action | char | "Can be Add, Cancel, Modify, cleaR book, Trade, Fill, or None." | DIRECT | Trade/Fill "Does not affect the book" |
| side | char | "The side that initiates the event. Can be Ask for a sell order (or sell aggressor in a trade), Bid for a buy order (or buy aggressor in a trade), or None" | DIRECT | For Fill: "A resting sell [buy] order was filled" |
| price | int64 1e-9 | "The order price" | DIRECT | UNDEF_PRICE on cleaR |
| size | uint32 | "The order quantity." | DIRECT | |
| channel_id | uint8 | "The channel ID assigned by Databento as an incrementing integer starting at zero." | SOURCE_SPECIFIC | |
| order_id | uint64 | "The order ID assigned by the venue." | DIRECT | queue tracking; aggressor ID on Trade records when defined |
| flags | uint8 | bit field | SOURCE_SPECIFIC | F_LAST semantics are essential here |
| ts_in_delta | int32 | "nanoseconds before ts_recv" | DERIVABLE | tag 52 |
| sequence | uint32 | "The message sequence number assigned at the venue." | SOURCE_SPECIFIC | |

Action values (doc): A "Insert a new order into the book."; M "Change an order's price and/or size."; C "Fully or partially cancel an order from the book."; R "Remove all resting orders for the instrument."; T "An aggressing order traded. Does not affect the book."; F "A resting order was filled. Does not affect the book."; N "No action: does not affect the book, but may carry flags".

## Timestamps
As in the trades profile. Snapshot records: "ts_event: unchanged … ts_in_delta: always 0; ts_recv: set to the snapshot generation timestamp (indicated with the F_BAD_TS_RECV flag)". CME weekly-open snapshot orders: "ts_event … corresponds to the time the snapshot is generated by CME. It does not reflect the original time the order was entered". Fixture: ts_recv > ts_event, ts_in_delta positive (5-digit ns).

## Sequencing and book semantics
- CME normalization (verbatim, venue page): "Records in the MBO schema with Add, Modify, and Cancel actions are normalized from Market Data Incremental Refresh - MBOFD, and records with Trade and Fill actions are normalized from … Trade Summary messages, and records with the cleaR action are normalized from … Channel Reset messages."
- Trades: "Each trade summary in the message is normalized into one Trade record. If there is a defined aggressor for the trade, its corresponding order ID entry … is used to populate the order_id field … Following each Trade record, the remaining (passive) order ID entries are normalized into Fill records … If the aggressing order did not already exist on the book then its Fill record is suppressed".
- F_LAST: Databento sets F_LAST "on the last record for each instrument", based on CME 5799-MatchEventIndicator. "Between records without the F_LAST flag, the book is in the process of updating, and the apparent best bid and offer may have already been traded."
- Priority: "first in, first out priority (FIFO) can be determined from message order. Messages for a single instrument_id are never reordered". Tag 37707-MDOrderPriority is not exposed.
- **Snapshots (historical):** "Databento includes an order book snapshot at 00:00:00 UTC each weekday (Monday-Friday)." A snapshot is a cleaR record followed by Add records, flagged F_SNAPSHOT|F_BAD_TS_RECV. "Snapshot records are streamed through the Historical API when the requested interval includes midnight UTC for a given weekday." A historical MBO pull must therefore start at or before a 00:00 UTC weekday boundary to have a complete book (I).
- CME weekly-open snapshot: "Databento buffers the orders from the first CME event of the trading session, per instrument … sorts the records in priority order". F_BAD_TS_RECV and F_SNAPSHOT are set.
- Live snapshot caution: "The order book … is not guaranteed to be in a complete and valid state after the last snapshot record … If the last snapshot record does not have the F_LAST flag set, the order book will not be valid until the next MBO record with the F_LAST flag set."
- Crossed or locked books are normal pre-open and during the daily pause ("CME will accept orders but won't execute any trades until the opening uncrossing").
- Implied orders are not in MBO (CME publishes implied only on its MBP feed; Databento merges it into CMBP-1).
- Fixture: action set {C}, side {A}, flags {128 = F_LAST}, channel_id {0}, order_id non-zero, price defined, size non-zero. Sequence strictly increasing by 1. The two records are consecutive cancels on the ask side, 2 µs apart in ts_event.

## Instrument / contract identity, expiry, reference-end, settlement/reference fields
As in the trades profile (join `definition`). GC vs MGC: separate order books; contract sizes differ (SECONDARY).

## Licence / access gating
As in the trades profile. Repo: TIER 2 "deeper Databento books", "Only after L1 features show signal".

## PMV relevance, unique vs derivable
MBO is the root schema. Uniquely it gives order identity and queue position, per-order add/modify/cancel, passive fills, depth beyond 10 levels, and order-count dynamics at every level. Nothing else in Databento's GLBX ladder can reconstruct it.

## F. Comparison: trades vs TBBO vs MBP-1 vs MBP-10 vs MBO

### Incremental information per layer
| schema | record (DBN bytes) | one record per | adds over the layer below |
|---|---|---|---|
| ohlcv-1m (reference only) | 56 | active minute | — (bar ts_event = interval start "based on the ts_recv from trade messages") |
| trades | 48 | trade | trade price, size, aggressor `side`, ts_event/ts_recv/ts_in_delta, sequence |
| tbbo | 80 | trade | top-of-book px/sz/order-count *immediately before* each trade |
| bbo-1s / bbo-1m | 80 | active second / minute | top of book + forward-filled last trade on a time grid (not derivable from TBBO, nor vice versa) |
| mbp-1 | 80 | top-of-book event | every BBO change between trades (quote-only updates, cancels, and adds at the touch) |
| mbp-10 | 368 | top-10 event | levels 2–10 price, size, and order count |
| mbo | 56 | order event (all levels) + Fill records | order IDs, queue priority, per-order lifecycle, passive fills, full depth |

### Deterministic derivability (VERIFIED-BY-DOC unless marked)
- "Databento derives all of the less granular schemas starting from the most granular schema available … MBP, BBO, TBBO, trades, and OHLCV—are simply derived from MBO data." "You can also derive one schema from another losslessly on the client side, and you should expect your self-derived data to be consistent with ours."
- **MBO →** MBP-10, MBP-1, TBBO, BBO-1s/1m, trades, OHLCV (derivation table). This needs a complete starting book: the historical 00:00 UTC weekday snapshot, or the CME weekly-open snapshot, plus F_LAST-aware event batching (I, from the cited semantics).
- **MBP-10 →** MBP-1, TBBO, BBO, trades, OHLCV ("MBP-1, BBO, and Trades can be derived from MBP-10").
- **MBP-1 →** TBBO (keep action = T), BBO (subsample), trades, OHLCV ("BBO, TBBO, and Trades can be derived from MBP-1").
- **TBBO →** trades, OHLCV ("Trades and OHLCV can be derived from TBBO"). **Trades →** OHLCV.
- **Not derivable:** BBO ↔ TBBO ("it is not possible to derive BBO from TBBO or vice versa"); anything upward. CMBP-1 (merged implied top-of-book) is not derivable from MBO, because implied liquidity comes from CME's MBP feed.
- Caveat (doc): Databento OHLCV may differ from official statistics and from self-built bars ("how trade conditions and retroactive trade breaks are handled, which timestamp is used"). Build bars from trades for transparency.
- Leakage caution (I): OHLCV `ts_event` is the bar *start*. A bar is only available after its end (+ latency). bbo-1s `ts_recv` is the interval *end*, which is the correct availability key.

### Cheapest sufficient schema for initial PMV gold research (15–60 min horizon, late-window decisions)
- **Context (repo-Git/SECONDARY):** Kalshi KXGOLD15M reportedly settles on a "Pyth GOLD" 1-minute close (DET-1 and the exact feed are unresolved), not on COMEX. GC/MGC therefore serve **only as predictive market-dynamics features**, never as labels or settlement reconstruction. COMEX also pauses 17:00–18:00 ET daily and at weekends, while the Pyth index is 24/7. That gap needs another source regardless of schema.
- **Recommendation (evidence-based, optional):** start with **`trades` for GC and MGC** (front contract via `GC.v.0`/`MGC.v.0` or explicit `raw_symbol`s; avoid `c.0` alone, see the definition profile), plus **`definition`, `statistics`, `status`** (small, L0). Trades supports velocity, realized volatility, trade intensity, signed (aggressor) volume, and any bar interval at the lowest event-level cost (48 B/trade).
- Add **`bbo-1s`** (time-grid top of book, robust in quiet periods) **or `tbbo`** (pre-trade BBO at 1.67× trades bytes per trade) only if spread or touch-imbalance features are hypothesized. `bbo-1s` aligns naturally with fixed decision times in the last minutes of a window.
- **MBP-1** only if quote-update dynamics between trades are hypothesized. **MBP-10/MBO** only after L1 features show a signal (consistent with repo priorities G-2 then G-1). If depth is wanted, buy MBO and derive MBP-10 locally (the doc recommends this), budgeting for its record count.
- This is a data-sufficiency judgment, not evidence of predictive value. Costs must come from the owner-run `get_cost` estimator.

## Open questions / unverified items
- GC/MGC record counts per schema (free metadata endpoints; owner).
- Whether GC/MGC outright top-of-book is materially affected by implied (spread-derived) prices excluded from MBO-derived MBP-1 (confirm with Databento; compare MBP-1 vs CMBP-1 on a bounded sample later).
- `sequence` semantic (packet vs message sequence number): UNKNOWN.

## B10 review qualifiers (API-B10-09)

- The derivability ladder holds from **2017-05-21** (MDP3). Before it, MBO does not exist and MBP-10 is the root schema; CMBP-1/CBBO are unavailable for MDP 2; timestamps before 2015-11-20 are millisecond-only.
- MBO (with a starting snapshot and `F_LAST` batching) derives MBP-10, MBP-1, TBBO, BBO, trades, and OHLCV. It does **not** derive CMBP-1/CBBO (merged real + implied top of book), `statistics`, `definition`, or `status`.
- Books derived from MBO are the **outright real book**; implied prices are excluded.
- `ts_in_delta` exists in MBO, MBP, trade, and statistics records, but not in `definition`, `status`, or `bbo-*` records.
- Databento's own OHLCV bars bucket on `ts_recv` ("based on the ts_recv from trade messages"). Bars rebuilt from trades keyed on `ts_event` will differ at boundaries.
