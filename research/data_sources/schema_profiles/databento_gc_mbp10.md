# Databento GLBX.MDP3 — `mbp-10` schema (market by price, 10 levels; COMEX gold GC, MGC)

**Status:** SCHEMA INSPECTED (official Databento docs, verbatim). Also ACTUAL SAMPLE INSPECTED for schema semantics only: official fixture `test_data.mbp-10.dbn` = GLBX.MDP3 **ESH1, 2020-12-28, 2 records**, not gold. `hist.databento.com` not called. `legal.databento.com` ACCESS BLOCKED. LICENSE GATED (NEEDS_LICENCE_CLARIFICATION, repo-Git).

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
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/tests/data/test_data.mbp-10.dbn (deleted after inspection) | 2026-10-19T04:22:33Z | 200 | 1089 | c59a27672b5727fc63513a2807ddc115f8b78401c4f834c07ba7859b75758dcb | ACTUAL SAMPLE (ES, not gold) |

## Access and connectivity
As in `databento_gc_trades.md`.

## Transport, format, compression, delivery (historical vs live)
- DBN/CSV/JSON and zstd/none. The record is `Mbp10Msg`, **368 bytes** (record.rs: 48-byte common part + 10 × 32-byte `BidAskPair`). Grouped under L2 (priced differently from L1; rate not obtained).
- Billed size is 368 B × (number of events touching levels 1–10). That is 4.6× MBP-1 per record, and there are more records than MBP-1. The doc notes: "Databento provides MBP-10 merely as a convenience feature. You can reduce bandwidth requirements, latency, and transfer time significantly by deriving MBP-10 yourself from MBO."
- Coverage: MBP-10 is "the highest granularity schema available for MDP 2 data", i.e. before 2017-05-21 (repo: dataset from 2010-06-06).

## Fields
| field | native type | official semantics (quote) | PMV classification | notes |
|---|---|---|---|---|
| ts_recv, ts_event, rtype (=10), publisher_id, instrument_id | | as MBP-1; "Always 10 in the MBP-10 schema." | DIRECT / SOURCE_SPECIFIC | |
| action | char | "Can be Add, Cancel, Modify, cleaR book, or Trade." | DIRECT | |
| side | char | initiating side (as MBP-1) | DIRECT | |
| depth | uint8 | "The book level where the update event occurred." | DIRECT | 0-based level index (fixture values 1 and 9, consistent with 0..9) |
| price, size | int64 1e-9, uint32 | event price and quantity | DIRECT | |
| flags, ts_in_delta, sequence | | as MBP-1 | SOURCE_SPECIFIC / DERIVABLE | |
| bid_px_N / ask_px_N | int64 1e-9 | "The bid [ask] price at level N (top level if N = 00)" | DIRECT | N = 00..09 |
| bid_sz_N / ask_sz_N | uint32 | "The bid [ask] size at level N" | DIRECT | |
| bid_ct_N / ask_ct_N | uint32 | "The bid [ask] order count at level N" | DIRECT | |

## Timestamps
As in the trades profile. Pre-2017-05-21 MDP 2 data: ts_recv = ts_event = 52-SendingTime (the doc table for MDP 2 maps both fields to tag 52), F_BAD_TS_RECV on all records, and millisecond resolution before 2015-11-20. Fixture: ts_recv > ts_event, ts_in_delta positive (5-digit ns).

## Sequencing and book semantics
- "MBP-10 … provides every order book event across the top ten price levels, keyed by price. This includes every trade and changes to aggregate market depth, alongside total size and order count at the top ten price levels."
- Each record carries the full 10-level snapshot after the event, so it is stateless up to depth 10.
- CME MBP feed context: "The MBP feed provides up to 10 levels of real liquidity and 2 levels of implied liquidity." Databento's MBP-10 is derived from MBO (real orders). Implied levels appear only in CMBP-1 (top of book).
- Derivable from MBP-10 (doc): "MBP-1, BBO, and Trades can be derived from MBP-10", plus TBBO and OHLCV (derivation table).
- Fixture: action {C, C}, side {A, B}, depth {9, 1}, flags {128 = F_LAST}. All 10 bid and ask levels populated on both records (price, size, and count set), bid < ask at each level. Sequence strictly increasing. The first record has the same ts_event and ts_recv as the first MBO fixture record (one event, consistent with MBO→MBP-10 derivation). The second MBO cancel in the MBO fixture has no MBP-10 counterpart among the two MBP-10 records. That is consistent with it being outside the top 10, but limit=2 makes this tentative.

## Instrument / contract identity, expiry, reference-end, settlement/reference fields
As in the trades profile. `definition.market_depth` gives "The (outright) book depth on the price level data feed"; `market_depth_implied` gives the implied depth.

## Licence / access gating
As in the trades profile. Repo: O3 "Databento deeper books (MBP-10, MBO)" is TIER 2, "only if research justifies".

## PMV relevance, unique vs derivable
- Over MBP-1, MBP-10 adds levels 2–10 sizes and order counts (depth imbalance, book slope, liquidity beyond the touch). It is derivable from MBO (given the daily snapshot). It is the only depth source before 2017-05-21.
- Expensive per record. For GC/MGC research it is a second-stage purchase after L1 features show a signal (repo G-1 priority).

## Open questions / unverified items
- GC/MGC MBP-10 record counts and cost (owner estimator).
- Depth beyond 10: only via MBO.
