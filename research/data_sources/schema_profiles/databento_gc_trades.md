# Databento GLBX.MDP3 — `trades` schema (COMEX gold GC, MGC)

**Status:** SCHEMA INSPECTED (official Databento docs read verbatim). Also ACTUAL SAMPLE INSPECTED, but only for schema semantics: the official `databento/dbn` test fixture `test_data.trades.dbn` is GLBX.MDP3 **ESH1 (E-mini S&P 500), 2020-12-28, 2 records**. It is not a GC/MGC sample. No gold data was requested. `hist.databento.com` (authenticated) was NOT called. `legal.databento.com` is ACCESS BLOCKED (per lead). LICENSE GATED: NEEDS_LICENCE_CLARIFICATION (repo-Git).

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
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/tests/data/test_data.trades.dbn (official fixture; deleted after inspection) | 2026-10-19T04:22:32Z | 200 | 449 | 6ef751abbd186b862afd9c65fd88dd54585587aa8cc3a059bc78305125efce3c | ACTUAL SAMPLE (ES, not gold) |

## Access and connectivity
- Historical data comes from `hist.databento.com` (HTTP API, streaming or batch) and needs an API key on an owner account. No key exists and none was created. Live data comes from the Databento Live gateway (key and subscription needed). Neither was contacted.
- `databento.com/docs/<path>` is a JavaScript application. Each page is a 15008-byte shell (sha256 `ea3c0d4d…`), and `/llms.txt` returns 404. The real content is static HTML fragments `databento.com/docs/NN-00-00-<section>.html`, listed in the docs bundle's navigation index. Those fragments are the evidence used here.
- The metadata endpoints (`metadata.get_cost`, `get_billable_size`, `get_record_count`, `symbology.resolve`) are free but authenticated. They were not called.

## Transport, format, compression, delivery (historical vs live)
- Encodings: "We support DBN, CSV, and JSON encodings for our data." DBN "is also the default encoding for all Databento APIs, including live data streaming, historical data streaming, and batch flat files." CSV has "one header line, followed by one record per line"; JSON "follow[s] the JSON lines specification".
- Compression: "zstd … is available for all encodings, and is recommended"; `none` is the alternative. Optional text-output parameters: `pretty_px` (decimal prices), `pretty_ts` (ISO 8601), `map_symbols` (adds a symbol column).
- DBN version: "version 3 is used for the … GLBX.MDP3 … datasets". The trades record layout is the same in v1, v2, and v3: `TradeMsg` is 48 bytes (`assert!(size_of::<TradeMsg>() == 48)` in record.rs).
- Streaming vs batch: "Both methods yield exactly the same data." With batch you can "Download the same data multiple times over a 30 day period, for no additional charge". Batch is recommended for requests over 5 GB.
- Cost model: "Historical data is billed per byte consumed. Databento meters data by its uncompressed size in binary encoding." CSV and JSON cost nothing extra ("you only pay for the data sized in the smaller encoding"). Docs say schema levels "are also how Databento prices data: L0, L1 … L2 … L3", and `trades` is grouped under L1. The per-level $/GB rates were NOT obtained: the pricing page is a JS shell. Repo-Git (SECONDARY) says pay-as-you-go from about $0.50/GB, a $125 signup credit (also VERIFIED-BY-DOC in the FAQ: "All new users receive $125 in free credits … expire after 6 months"), and Standard at about $199/month.
- Relative size: about 48 bytes per trade (DBN, uncompressed, the billed size). It is the smallest event-level schema; see the size table in `databento_gc_mbo.md` §F.

## Fields
Field order follows the doc table. Types are from the doc and record.rs.

| field | native type | official semantics (quote) | PMV classification | notes |
|---|---|---|---|---|
| ts_recv | uint64 ns | "The capture-server-received timestamp expressed as the number of nanoseconds since the UNIX epoch." | DIRECT (availability time, Databento-side) | Index timestamp for this schema; requests filter on it |
| ts_event | uint64 ns | "The matching-engine-received timestamp" | DIRECT | CME tag 60-TransactTime for MDP3 (2017-05-21 onward); for MDP 2 data (before 2017-05-21, from FIX flat files) the venue mapping gives **52-SendingTime** (review API-B10-09) |
| rtype | uint8 | "Always 0 in the trades schema." | SOURCE_SPECIFIC | MBP-0 record |
| publisher_id | uint16 | "denotes the dataset and venue" | SOURCE_SPECIFIC | GLBX.MDP3 = 1 (publishers.rs `GlbxMdp3Glbx = 1`) |
| instrument_id | uint32 | "The numeric instrument ID." | SOURCE_SPECIFIC | "only guaranteed to be unique within a given day" |
| action | char | "Always Trade in the trades schema." | DIRECT | `T` |
| side | char | "Can be Ask for a sell aggressor in a trade, Bid for a buy aggressor in a trade, or None where no side is specified." | DIRECT (aggressor) | CME: "Implied trades may not have an aggressing side set … normalized with side set to None." |
| depth | uint8 | "The book level where the update event occurred." | SOURCE_SPECIFIC | 0 in the fixture |
| price | int64 fixed 1e-9 | "every 1 unit corresponds to 1e-9"; UNDEF_PRICE = INT64_MAX | DIRECT | Signed; spreads can be negative |
| size | uint32 | "The order quantity." | DIRECT | In contracts. GC and MGC contracts differ in size (see below) |
| flags | uint8 bitfield | "A bit field indicating event end, message characteristics, and data quality." | SOURCE_SPECIFIC | See the flags list below |
| ts_in_delta | int32 ns | "The matching-engine-sending timestamp expressed as the number of nanoseconds before ts_recv." | DERIVABLE (send time = ts_recv − ts_in_delta) | CME tag 52-SendingTime; clamps at INT32 bounds; "may be negative" |
| sequence | uint32 | "The message sequence number assigned at the venue." | SOURCE_SPECIFIC | Which MDP3 sequence (packet or message) is not stated: UNKNOWN |

Flags (VERIFIED-BY-DOC): F_LAST 128 "Marks the last record in a single event for a given instrument_id"; F_TOB 64; F_SNAPSHOT 32 "Message sourced from a replay, such as a snapshot server"; F_MBP 16; F_BAD_TS_RECV 8 "The ts_recv value is inaccurate due to clock issues or packet reordering"; F_MAYBE_BAD_BOOK 4 "An unrecoverable gap was detected in the channel"; F_PUBLISHER_SPECIFIC 2 ("provides no additional meaning in this dataset"); bit 0 "Reserved for internal use can safely be ignored. May be set or unset." Test flags with a bitwise AND, never equality.

## Timestamps
- `ts_event` is CME 60-TransactTime: "the time that the event is received by the matching engine". It is unadjusted ("any non-monotonicity in the original data will remain").
- `ts_recv` is Databento's capture-server receipt (CME MDP 3.0 is received "over UDP multicast in our DC3 datacenter"; DC3's location is not stated in the docs): "synchronized against UTC with sub-microsecond accuracy … always guaranteed to be monotonic for any given symbol", "hardware timestamping … GPS clock source using PTP".
- `ts_in_delta`: send time = `ts_recv − ts_in_delta`.
- **Historical availability of ts_recv:** "All of our historical data … includes receive timestamps." **Exception: before 2017-05-21 (MDP 2)**, "capture timestamps … are not available. The ts_recv field on all MDP 2 data is set to the same value as ts_event", with F_BAD_TS_RECV set. Also, "Timestamps prior to [2015-11-20] are limited to millisecond resolution."
- All timestamps are UTC nanoseconds. Parameters are start-inclusive and end-exclusive.
- PMV note (I): `ts_recv` is the earliest point-in-time availability *at Databento's colocated capture*. A PMV cloud collector will receive later. Historical simulation should key on `ts_recv` plus a latency margin, never on `ts_event`.
- Fixture (ES, 2020-12-28): 2 records, both `ts_recv > ts_event`, no ts_recv equal to ts_event, nanosecond digits populated, ts_in_delta positive (5-digit ns order), ts_recv − ts_event 6-digit ns order.

## Sequencing and book semantics
- Trades "is a subset of MBO", derived by Databento from MBO ("Databento derives all of the less granular schemas starting from the most granular schema available"). CME Trade Summary messages become one `Trade` record per trade summary. `Fill` records (passive side) are excluded: "The MBP-n and trades schemas include Trade records, but do not include Fill detail records."
- There is no book state. `depth` is present but carries no book.
- Fixture: action set {T}, side set {A}, depth set {0}, flags set {129 = F_LAST + reserved bit 0}. Sequence strictly increasing between the two records, with a gap: sequence counts all channel messages, not just trades.
- Gap detection: no checksum. F_MAYBE_BAD_BOOK flags unrecoverable channel gaps.

## Instrument / contract identity, expiry, reference-end, settlement/reference fields
- Only `instrument_id` is present. Join to the `definition` schema for `raw_symbol`, `expiration`, `min_price_increment`, and `unit_of_measure_qty` (see `databento_gc_definition_statistics.md`).
- Symbology: `GC.FUT` and `MGC.FUT` (parent, all outrights **and futures spreads**), and `GC.c.0` / `GC.v.0` / `GC.n.0` (continuous; "original, unadjusted prices"). The fixture header shows stype_in = raw_symbol, stype_out = instrument_id, and a per-date mapping interval list.
- **GC vs MGC (SECONDARY, repo-Git `research/historical_data/inventory_underlying_btc_gold.md` and `docs/phase2.md`; must be verified from CME specs or from `definition` fields):** GC is 100 troy oz with a 0.10 tick, physically delivered. MGC is 10 troy oz, physical; its tick is not recorded in the repo (UNVERIFIED). One GC contract is about 10× the notional of one MGC, so trade `size` is not comparable across the two without `unit_of_measure_qty`. Relative liquidity (GC generally deeper) is SECONDARY and was not observed.
- No settlement fields here (see `statistics`).

## Licence / access gating
Repo-Git: NEEDS_LICENCE_CLARIFICATION (owner credential; payment beyond the credit). Databento exchange-fees page (FS, repo): "a license is not required for historical data". CME DS-45 ML scope and DDLA are open (INV-3, E-U4). The legal page is unreachable. Every gold source is an equivalent observable of the protected gold contracts. It is development-only for exposed dates and embargoed from a cycle's `T0 − m` (repo).

## PMV relevance, unique vs derivable
- Unique within the L1 ladder: none. Trades is derivable from TBBO, MBP-1, MBP-10, and MBO. It is the cheapest event-level source of trade price, size, aggressor side, and timestamps, and OHLCV at any interval is derivable from it.
- Main candidate first pull for gold velocity and trade-intensity features (repo G-2). This is not evidence of predictive value.
- Kalshi gold contracts reportedly settle on a Pyth gold index, not on COMEX (repo-Git, DET-1 unresolved). COMEX trades are a feature source, never a label source.

## Open questions / unverified items
- Per-level $/GB rates for GLBX.MDP3: get from the owner portal or the `get_cost` estimator.
- Whether `sequence` is the MDP3 packet MsgSeqNum or a per-message counter (UNKNOWN).
- GC and MGC tick and contract size: verify from `definition` (`min_price_increment`, `unit_of_measure_qty`, `min_price_increment_amount`).
- Whether CME block trades or other off-book trades appear in `trades` for GC (UNKNOWN; DataMine has a separate BLOCK file, see `cme_datamine.md`).
