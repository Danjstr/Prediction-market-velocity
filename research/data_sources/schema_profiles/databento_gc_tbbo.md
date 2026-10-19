# Databento GLBX.MDP3 — `tbbo` schema (BBO on trade), plus `bbo-1s` / `bbo-1m` (COMEX gold GC, MGC)

**Status:** SCHEMA INSPECTED (official Databento docs, verbatim). Also ACTUAL SAMPLE INSPECTED for schema semantics only: official fixture `test_data.tbbo.dbn` = GLBX.MDP3 **ESH1, 2020-12-28, 2 records**, not gold. The bbo-1s/1m fixtures were not fetched (outside the permitted list); bbo is SCHEMA INSPECTED only. `hist.databento.com` not called. `legal.databento.com` ACCESS BLOCKED. LICENSE GATED (NEEDS_LICENCE_CLARIFICATION, repo-Git).

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
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/tests/data/test_data.tbbo.dbn (deleted after inspection) | 2026-10-19T04:22:33Z | 200 | 513 | c9b7ca671ec6a26664802557fe2d9d76b5d078ebedfbaea2e579a2b6d4b8fc5d | ACTUAL SAMPLE (ES, not gold) |

## Access and connectivity
Same as `databento_gc_trades.md`: historical API key (owner account) or live subscription. Neither was contacted.

## Transport, format, compression, delivery (historical vs live)
- DBN (default), CSV, or JSON; zstd or none. The record is `Mbp1Msg`, 80 bytes (record.rs `size_of::<Mbp1Msg>() == 80`). TBBO and MBP-1 share rtype 1. bbo-1s/1m use `BboMsg`, also 80 bytes (rtype 195/196).
- Billed on uncompressed DBN bytes: about 80 B per trade for TBBO (about 1.67× `trades` per trade). bbo-1s is bounded above by 80 B × active seconds (at most 86,400 per instrument-day; arithmetic from the schema, not observed). TBBO and BBO are both grouped under L1.

## Fields (tbbo)
| field | native type | official semantics (quote) | PMV classification | notes |
|---|---|---|---|---|
| ts_recv | uint64 ns | "The capture-server-received timestamp" | DIRECT | index timestamp |
| ts_event | uint64 ns | "The matching-engine-received timestamp" | DIRECT | tag 60 |
| rtype | uint8 | "Always 1 in the TBBO schema." | SOURCE_SPECIFIC | |
| publisher_id, instrument_id | uint16, uint32 | as trades | SOURCE_SPECIFIC | |
| action | char | "Always Trade in the TBBO schema." | DIRECT | |
| side | char | "Can be Ask for a sell aggressor in a trade, Bid for a buy aggressor in a trade, or None" | DIRECT (aggressor) | |
| depth | uint8 | "The book level where the update event occurred." | SOURCE_SPECIFIC | |
| price | int64 1e-9 | trade price | DIRECT | |
| size | uint32 | "The order quantity." | DIRECT | |
| flags | uint8 | bit field (see trades profile) | SOURCE_SPECIFIC | |
| ts_in_delta | int32 | "nanoseconds before ts_recv" | DERIVABLE | |
| sequence | uint32 | "The message sequence number assigned at the venue." | SOURCE_SPECIFIC | |
| bid_px_00 / ask_px_00 | int64 1e-9 | "The bid [ask] price at the top level" | DIRECT | |
| bid_sz_00 / ask_sz_00 | uint32 | "The bid [ask] size at the top level." | DIRECT | |
| bid_ct_00 / ask_ct_00 | uint32 | "The bid [ask] order count at the top level." | DIRECT | |

In C++, Rust, Python records, and JSON the book fields are an array `levels[0]` (`bid_px`, `ask_px`, …). In the Python DataFrame and CSV they are suffixed `_00`.

## Fields (bbo-1s, bbo-1m) — time-sampled
Conventions (verbatim):
- "If no trade or BBO update occurs within the interval, no record is printed."
- "If a BBO update occurs but no trade takes place within the interval, the last sale information is forward-filled from the previous interval."
- "If no BBO update occurs but a trade takes place within the interval, the BBO information is forward-filled."

| field | type | semantics (quote) | PMV | notes |
|---|---|---|---|---|
| ts_recv | uint64 | "The end timestamp of the interval, clamped to the second/minute boundary" | DIRECT | The record is available only at interval end. Use it as the decision-time key |
| ts_event | uint64 | "The matching-engine-received timestamp of the last trade … Will be UNDEF_TIMESTAMP in cases where there was no last trade in the session." | DIRECT | |
| side | char | "The side that initiated the last trade." | DIRECT | |
| price / size | int64 / uint32 | "The last trade price" / "The last trade quantity" | DIRECT | forward-filled |
| flags, sequence | uint8, uint32 | "sequence number … of the last update" | SOURCE_SPECIFIC | |
| bid/ask px, sz, ct _00 | as TBBO | top level at interval end | DIRECT | |
There is no `action`, `depth`, or `ts_in_delta` in BBO (record.rs `BboMsg` has reserved bytes in those slots).

## Timestamps
As in the trades profile: ts_event = CME 60-TransactTime, ts_recv = Databento capture (monotonic per symbol, PTP/GPS), ts_in_delta from 52-SendingTime. Before 2017-05-21, ts_recv = ts_event with F_BAD_TS_RECV. Fixture: ts_recv > ts_event on both records; same trade events and timestamps as the trades fixture (the two fixtures cover the same 2 trades).

## Sequencing and book semantics
- "BBO on trade (TBBO) provides every trade event alongside the BBO immediately before the effect of each trade. This is a subset of MBP-1."
- "You can derive the TBBO schema by removing any event from the MBP-1 schema that does not have an action of T". "You can derive the BBO schema by subsampling the MBP-1 schema … However, it is not possible to derive BBO from TBBO or vice versa."
- "Trades and OHLCV can be derived from TBBO."
- Staleness: "If an instrument doesn't trade for extended periods of time, the best bid and offer retrieved from the last TBBO message can be stale." Also: "Since most of the price discovery happens around the time of a trade, TBBO can be used to construct many useful signals without the bloat of MBP-1."
- Fixture: action {T}, side {A}, depth {0}, flags {129 = F_LAST + reserved bit}. Both records have levels[0] fully populated (bid and ask price, size, and count all set), with bid < ask. Sequence strictly increasing.
- Implied liquidity (VERIFIED-BY-DOC, with inference): "Databento combines the real and implied books, publishing the merged top-of-book on the CMBP-1 schema." So TBBO/MBP-1/BBO on GLBX are most likely outright (non-implied) books (I). See the open questions.

## Instrument / contract identity, expiry, reference-end, settlement/reference fields
Same as the trades profile. Join `definition` for contract metadata. GC (100 oz) vs MGC (10 oz) sizes and counts are in contracts or orders (SECONDARY, repo-Git; verify via `definition`).

## Licence / access gating
Same as trades: NEEDS_LICENCE_CLARIFICATION (repo-Git: Databento licence classification M3, DS-45 ML scope, DDLA, E-U4).

## PMV relevance, unique vs derivable
- Over `trades`, TBBO adds the pre-trade top-of-book (spread, sizes, order counts) at each trade, enough for trade-time spread, microprice, and book imbalance at the touch. It is derivable from MBP-1, MBP-10, or MBO. It is not derivable from trades.
- bbo-1s gives a regular 1 s grid of last-trade and top-of-book state. It fits fixed decision times late in a 15-min window and handles quiet periods better than TBBO. bbo-1s is derivable from MBP-1, MBP-10, or MBO, not from TBBO.
- Schema richness is not predictive evidence.

## Open questions / unverified items
- Whether GLBX `mbp-1`/`tbbo`/`bbo` exclude implied prices (inferred from the CMBP-1 statement; confirm with Databento). For GC outrights, implied-from-spread liquidity may sometimes set the displayed best price.
- Per-level $/GB rates (L1) for GLBX.MDP3.
