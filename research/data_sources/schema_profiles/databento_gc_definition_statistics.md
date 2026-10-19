# Databento GLBX.MDP3 — `definition` and `statistics` schemas, plus `status` (COMEX gold GC, MGC)

**Status:** SCHEMA INSPECTED (official Databento docs, verbatim). ACTUAL SAMPLE INSPECTED for schema semantics only:
- `test_data.statistics.dbn`: GLBX.MDP3, 2 records, one instrument (product not identified; no definition in the file), 2023-04-23, DBN v2.
- `test_data.definition.dbn`: **XNAS.ITCH (US equity), DBN v2, 2 records**. It is not CME.
- `test_data.definition.v3.dbn.frag`: an uncompressed v3 definition fragment with no metadata header. It is GLBX.MDP3 (publisher 1), 2 records, both **CME options on futures** (Eurodollar and E-mini S&P), 2020-12-27.

None is gold. `hist.databento.com` not called. `legal.databento.com` ACCESS BLOCKED. LICENSE GATED (NEEDS_LICENCE_CLARIFICATION, repo-Git).

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
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/tests/data/test_data.statistics.dbn (deleted) | 2026-10-19T04:22:34Z | 200 | 256 | 9daad763159d844b08d30fe6ede1e4c76c58d59f319f61e04cbc05dd7cd87a63 | ACTUAL SAMPLE (GLBX, not gold) |
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/tests/data/test_data.definition.dbn (deleted) | 2026-10-19T04:22:34Z | 200 | 5972 | 00a0aed85e2eda1699af7327b4d489fbbec6e53252f939ded219e748e7a84393 | ACTUAL SAMPLE (XNAS equity, not CME) |
| https://raw.githubusercontent.com/databento/dbn/82f76c1de6f5c8a1f4b3711fac423f88a3f91d67/tests/data/test_data.definition.v3.dbn.frag (deleted) | 2026-10-19T04:23:17Z | 200 | 1040 | a2e40d287c71051e131cc6339a5902471f902e8fc6fdcd1f4dc1051d7d89db17 | ACTUAL SAMPLE (GLBX options, not gold) |

## Access and connectivity
As in `databento_gc_trades.md`. `symbology.resolve` (free, authenticated) maps continuous and parent symbols to instrument IDs per date. Not called.

## Transport, format, compression, delivery (historical vs live)
- DBN/CSV/JSON and zstd/none. GLBX uses DBN v3: `InstrumentDefMsg` is 520 B (v2: 400 B; v1: 360 B), `StatMsg` is 80 B (v1/v2: 64 B, with `quantity` i32 instead of i64), `StatusMsg` is 40 B. All three are L0 and small (I).
- v3 changes (doc): "Expanded quantity to 64 bits in StatMsg"; definition adds `leg_*` fields and "A definition record will be created for each strategy leg"; "Removal of statistics-schema related fields trading_reference_price, trading_reference_date, and settl_price_type".
- Definition snapshots: "the historical API provides a snapshot of all active definitions at UTC midnight Monday through Friday". This applies "for publishers that do not provide a full list of instrument definitions at least daily". Whether GLBX relies on it or on CME's own definition cycle is not stated (UNKNOWN).

## Fields — definition (selected; the full list has about 70 fields)
| field | native type | official semantics (quote) | PMV classification | notes |
|---|---|---|---|---|
| ts_recv / ts_event | uint64 | capture / matching-engine time | DIRECT | point-in-time: "the instrument definitions are timestamped to the nanosecond and treated as a time series" |
| instrument_id | uint32 | numeric ID | SOURCE_SPECIFIC | "only guaranteed to be unique within a given day" |
| raw_symbol | char[71] (v2/v3) | "The instrument name (symbol) provided by the publisher" | DIRECT | CME tag 55; product + month code + 1- or 2-digit year ("CME has begun using a 2-digit year, e.g. NGN25") |
| security_update_action | char | "Added, Modified, or Deleted" | SOURCE_SPECIFIC | |
| instrument_class | char | F future, S future spread, C/P options, … | DIRECT | filter `F` to drop calendar spreads in `GC.FUT` |
| min_price_increment | int64 1e-9 | "The minimum constant tick for the instrument" | DIRECT | GC/MGC tick: verify here |
| display_factor | int64 1e-9 | "multiplier to convert the venue's display price to the conventional price" | SOURCE_SPECIFIC | |
| expiration | uint64 ns | "The last eligible trade time … May only have date precision depending on the publisher." | DIRECT | roll and expiry modelling |
| activation | uint64 ns | "The time of instrument activation" | DIRECT | |
| high_limit_price / low_limit_price / max_price_variation | int64 1e-9 | daily limits / banding | SOURCE_SPECIFIC | |
| unit_of_measure_qty | int64 1e-9 | "The contract size for each instrument, in combination with unit_of_measure" | DIRECT | GC vs MGC contract size |
| unit_of_measure | char[31] | "e.g. USD or LBS" | DIRECT | expected troy ounces for gold (UNVERIFIED code) |
| min_price_increment_amount | int64 1e-9 | "The minimum price increment amount disseminated by the venue" | DIRECT | $ value per tick |
| asset | char[11] (v3) | "The underlying asset code (product code)" | DIRECT | basis of parent/continuous symbology (CME tag 6937) |
| group, exchange, cfi, security_type | char[] | security group, exchange (e.g. XCME), ISO CFI, FUT/OOF… | SOURCE_SPECIFIC | the COMEX `exchange` code is UNVERIFIED (not seen) |
| match_algorithm | char | "typically FIFO" (F, K, C, T, O, S, Q, Y, P, V, A) | SOURCE_SPECIFIC | |
| market_depth / market_depth_implied | int32 | "(outright) book depth on the price level data feed" / implied | SOURCE_SPECIFIC | |
| maturity_year/month/day/week | u16/u8 | from the symbol | DERIVABLE | |
| inst_attrib_value | int32 | CME tag 872 bitfield (block-trade eligible, implied-matching eligible, …) | SOURCE_SPECIFIC | |
| underlying_id, underlying, raw_instrument_id, currency, settl_currency, leg_* | | | SOURCE_SPECIFIC | `leg_count` 0 for outrights |

## Fields — statistics
| field | type | semantics (quote) | PMV | notes |
|---|---|---|---|---|
| ts_recv | uint64 | capture time | DIRECT | **use as availability time** |
| ts_event | uint64 | matching-engine time | DIRECT | limits use tag 60 |
| ts_ref | uint64 | "The reference timestamp" | DIRECT | CME 5796-TradingReferenceDate: "the source only has date precision, users should avoid localizing ts_ref" |
| price | int64 1e-9 | "The value for price statistics" | DIRECT | |
| quantity | int64 (v3) | "The value for non-price statistics. Will be INT64_MAX when unused." | DIRECT | |
| sequence, ts_in_delta, channel_id | | | SOURCE_SPECIFIC | |
| stat_type | uint16 | type of statistic | DIRECT | table below |
| update_action | uint8 | "newly added (1) or deleted (2)" | SOURCE_SPECIFIC | |
| stat_flags | uint8 | settlement: CME 731-SettlPriceType | DIRECT | bit0 final vs preliminary; bit1 actual vs theoretical; bit2 trading vs clearing tick; bit3 intraday settlement |

**stat_type values published on GLBX.MDP3** (from the doc's per-dataset table): 1 Opening price; 2 Indicative opening price; 3 Settlement price; 4 Trading session low; 5 Trading session high; 6 Cleared volume ("contracts cleared … on the previous trading date"); 7 Lowest offer; 8 Highest bid; 9 Open interest; 10 Fixing price; 17 Upper price limit; 18 Lower price limit. **Not on GLBX:** 19 Block volume, 11 Close price, 13 VWAP.

Publication timing (CME page, verbatim): "Cleared volume and open interest statistics will normally publish on the following UTC date, unless they are for Friday's session, in which case they will be published on the following Sunday. Settlement price statistics will first publish shortly after the settlement window." "CME often publishes multiple messages for the same trading session date … The initial messages indicate preliminary values, and the final message … indicates the final value." "The CME does not publish settlement prices on their MDP feed for instruments without open interest or volume."

## Fields — status (brief)
`ts_recv`, `ts_event`, `action` (u16: pre-open, trading, halt, …), `reason` (u16), `trading_event` (u16), `is_trading`/`is_quoting`/`is_short_sell_restricted` ("best-efforts state … Y, N, or ~"). CME caveat: "the status state fields (is_trading and is_quoting) may be incorrect before activation or after expiration". Pre-2015 status data is sparse.

## Timestamps
- Definitions are point-in-time (ts_recv / ts_event). In the v3 GLBX fragment, definition ts_event had millisecond-only precision (sub-millisecond digits zero) while ts_recv had nanosecond digits.
- Statistics: ts_event and ts_recv in ns; ts_ref is date-only. Fixture (GLBX statistics): stat_types {5, 7}, ts_ref UNDEF on both (matches the doc table: ts_ref is not applicable to these types), quantity = null sentinel, stat_flags 255 (= null/max sentinel; "Null … values are represented by the maximum value of the field's type"), update_action 1, ts_recv > ts_event, sequence strictly increasing.

## Sequencing and book semantics
Not applicable to books. Statistics may be republished (preliminary to final) for the same `ts_ref`. Use the last record whose `stat_flags` bit0 is set, as of a `ts_recv` cut-off.

## Instrument / contract identity, expiry, reference-end, settlement/reference fields
- Symbology (doc): parent `[ROOT].FUT` (e.g. `GC.FUT`, `MGC.FUT`), which includes futures spreads. Continuous `[ROOT].[c|n|v].[RANK]`: c = calendar ("offset from the closest expiration"), n = open interest "at the previous day's close", v = "previous day's trading volume". The doc states "The continuous contract prices returned are the original, unadjusted prices." GLBX.MDP3 supports both parent and continuous.
- Analysis (I): gold futures list nearby serial months that are typically less active than the main delivery months (repo SECONDARY lists Feb/Apr/Jun/Aug/Oct/Dec). `GC.c.0` may therefore map to an illiquid contract. `GC.v.0`/`GC.n.0` rank on prior-day data (no lookahead, but the roll happens at a day boundary). Record the mapping per date via `symbology.resolve` or the DBN metadata mappings.
- Fixture (v3 GLBX fragment): `security_type` OOF, `instrument_class` P, `cfi` set, `exchange` XCME, `asset` and `underlying` populated, `expiration` and `activation` populated with time-of-day, `match_algorithm` values {F, Q}, `security_update_action` A, `leg_count` 0, `currency` USD, and `unit_of_measure` populated (codes seen: USD and IPNT). The DBN metadata in the v2 fixtures shows per-date `raw_symbol → instrument_id` mapping intervals (in the XNAS fixture the instrument_id changes daily for the same symbol, illustrating the daily-remap caveat).
- **GC vs MGC (SECONDARY, repo-Git):** GC 100 oz, tick 0.10, physical; MGC 10 oz, physical (tick UNVERIFIED in repo); 1OZ 1 oz, tick 0.25, cash-settled. The `definition` fields `unit_of_measure_qty`, `min_price_increment`, and `min_price_increment_amount` will establish these deterministically. Liquidity (GC deeper than MGC) is SECONDARY and was not observed.
- Settlement: the GC/MGC daily settlement (`stat_type` 3) is a COMEX settlement. It is **not** the Kalshi gold settlement reference (Pyth, repo-Git DET-1).

## Licence / access gating
As in the trades profile. Repo G-3: "Priority 1, with G-2", NEEDS_LICENCE_CLARIFICATION.

## PMV relevance, unique vs derivable
- `definition`: unique for contract metadata (expiry, tick, contract size, activation) point-in-time. Required to map instrument_id and to roll. Not derivable from market-data schemas.
- `statistics`: unique for official settlement, open interest, and cleared volume (exchange-computed, published late). Session high/low/open are partially derivable from trades, but the doc warns official and Databento-derived values differ. Low frequency, so of limited direct relevance to 15–60 min features. Useful for roll choice and for sanity checks.
- `status`: session state (halts, pre-open, daily pause). It is a machine-readable calendar to validate `pandas_market_calendars` (repo G-24a).

## Open questions / unverified items
- The COMEX `exchange` code and the gold `unit_of_measure` code in GLBX definitions (no gold sample seen).
- Whether GLBX definitions use Databento's UTC-midnight snapshot or CME's own definition replay (UNKNOWN).
- Exact settlement publication latency for GC/MGC (repo SECONDARY says 1 to 30+ minutes after the window).
