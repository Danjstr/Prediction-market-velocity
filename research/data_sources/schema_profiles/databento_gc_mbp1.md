# Databento GLBX.MDP3 — `mbp-1` schema (market by price, top of book; COMEX gold GC, MGC)

**Status:** SCHEMA INSPECTED (official Databento docs, verbatim). Also ACTUAL SAMPLE INSPECTED for schema semantics only: official fixture `test_data.mbp-1.dbn` = GLBX.MDP3 **ESH1, 2020-12-28, 2 records**, not gold. `hist.databento.com` not called. `legal.databento.com` ACCESS BLOCKED. LICENSE GATED (NEEDS_LICENCE_CLARIFICATION, repo-Git).

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
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/tests/data/test_data.mbp-1.dbn (deleted after inspection) | 2026-10-19T04:22:33Z | 200 | 513 | b6ea8469368c6e3c1e857ea6e7efebac7be5079473ca7176c870eb888ba4e9e0 | ACTUAL SAMPLE (ES, not gold) |

## Access and connectivity
As in `databento_gc_trades.md`.

## Transport, format, compression, delivery (historical vs live)
DBN/CSV/JSON and zstd/none, as in the trades profile. The record is `Mbp1Msg`, 80 bytes, rtype 1 (shared with TBBO). Billed size is 80 B × the number of top-of-book events. That is one record per trade plus one per book change at the BBO, so the count is materially higher than for TBBO. The GC/MGC ratio of quote updates to trades is UNKNOWN (not observed; get it from `get_record_count` / `get_cost`). The schema is grouped under L1.

## Fields
| field | native type | official semantics (quote) | PMV classification | notes |
|---|---|---|---|---|
| ts_recv | uint64 ns | "The capture-server-received timestamp" | DIRECT | index timestamp |
| ts_event | uint64 ns | "The matching-engine-received timestamp" | DIRECT | |
| rtype | uint8 | "Always 1 in the MBP-1 schema." | SOURCE_SPECIFIC | |
| publisher_id, instrument_id | | as trades | SOURCE_SPECIFIC | |
| action | char | "Can be Add, Cancel, Modify, cleaR book, or Trade." | DIRECT | no Fill in MBP |
| side | char | "The side that initiates the event. Can be Ask for a sell order (or sell aggressor in a trade), Bid for a buy order (or buy aggressor in a trade), or None" | DIRECT | "two-sided BBO changes in a single update … side code N" |
| depth | uint8 | "The book level where the update event occurred." | DIRECT | |
| price | int64 1e-9 | "The order price" | DIRECT | price of the event, not necessarily the BBO |
| size | uint32 | "The order quantity." | DIRECT | |
| flags | uint8 | bit field | SOURCE_SPECIFIC | |
| ts_in_delta | int32 | "nanoseconds before ts_recv" | DERIVABLE | |
| sequence | uint32 | "The message sequence number assigned at the venue." | SOURCE_SPECIFIC | |
| bid_px_00, ask_px_00 | int64 1e-9 | top-level bid/ask price | DIRECT | the book state after the event (for Trade records, before the trade's effect) |
| bid_sz_00, ask_sz_00 | uint32 | top-level size | DIRECT | aggregate size at the level |
| bid_ct_00, ask_ct_00 | uint32 | "order count at the top level" | DIRECT | not in trades; also in TBBO |

## Timestamps
As in the trades profile. Key points: ts_recv is guaranteed monotonic per symbol, and is unavailable before 2017-05-21 (set equal to ts_event, F_BAD_TS_RECV). Fixture: ts_recv > ts_event on both records, nanosecond digits populated, ts_in_delta positive (5-digit ns), ts_recv − ts_event 5–6-digit ns.

## Sequencing and book semantics
- "MBP-1 (market by price) provides every order book event that updates the top price level, also known as the best bid and offer (BBO). This includes every trade and changes to book depth, alongside total size and order count at the BBO."
- "MBP-1 is the only one [of MBP-1/TBBO/BBO] that provides every top of book update."
- Databento derives MBP-1 from MBO: "Order book feeds are usually normalized into our MBO schema … Databento derives all of the less granular schemas starting from the most granular schema available." F_LAST matters: "it is important to use the F_LAST flag when calculating the best bid and offer, like our MBP-1 schema. Between records without the F_LAST flag, the book is in the process of updating … This is accounted for when we construct our other schemas, such as MBP-1 and Trades."
- Each record carries the full top-of-book state, so it is stateless at L1. No snapshot is needed to read the BBO (unlike MBO).
- Derivable from MBP-1 (doc): "BBO, TBBO, and Trades can be derived from MBP-1", plus OHLCV.
- Fixture: action set {A}, side {A}, depth {0}, flags {128 = F_LAST}. levels[0] fully populated, bid < ask. Sequence strictly increasing (gap of 2 between records).
- Implied book: likely excluded (merged real+implied top-of-book is published as CMBP-1). Inference; see open questions.

## Instrument / contract identity, expiry, reference-end, settlement/reference fields
As in the trades profile (join `definition`; GC vs MGC contract size SECONDARY).

## Licence / access gating
As in the trades profile (NEEDS_LICENCE_CLARIFICATION; repo-Git).

## PMV relevance, unique vs derivable
- Over TBBO, MBP-1 adds every quote change between trades (quote-update intensity, spread dynamics, BBO flicker, cancellations at the touch). It is derivable from MBP-10 and MBO. It is not derivable from TBBO, BBO, or trades.
- For a 15–60 min horizon with decisions in the last minutes, MBP-1 is a step up from TBBO/bbo-1s. It is worth paying for only if quote-dynamics features are hypothesized. Cost scales with quote-update count (UNKNOWN for GC/MGC).

## Open questions / unverified items
- GC/MGC MBP-1 record counts per day vs trades: use the free metadata endpoints (owner).
- Implied-price inclusion in GLBX MBP-1 (confirm with Databento).
