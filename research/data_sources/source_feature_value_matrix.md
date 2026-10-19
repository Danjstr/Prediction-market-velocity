# PMV source × information value matrix (B10 reconnaissance, 2026-10-19)

**What this is.** For each piece of information PMV may need, this shows which candidate source provides it and how. It records **information availability, uniqueness, reconstructibility, timing fidelity, and settlement fidelity**. It makes **no claim of predictive value**: richer schemas are not evidence of edge. Verdicts are in `source_redundancy_decisions.md`; evidence is in `schema_profiles/` (one profile per source/schema).

**Cell values.**

| Value | Meaning |
|---|---|
| DIRECT | Observed directly in that source |
| DERIVABLE | Deterministically reproducible from another field of the same source or from another retained source |
| PROXY | Related to the required quantity, but not the actual reference or the actual venue |
| ABSENT | Not available from that source |
| UNKNOWN | Semantics not established from official documentation or samples |

**Column codes.** Live-only columns (marked †) have no history: their history exists only from the day PMV starts capturing.

| Code | Source | Evidence status (B10) |
|---|---|---|
| K-H | Kalshi REST, live and historical tiers: series/events/markets, trades, 1-min candles | SCHEMA INSPECTED; samples ACCESS BLOCKED |
| K-WS† | Kalshi WebSocket (`orderbook_delta`, `trade`, `market_lifecycle_v2`; CFB and Pyth channels need paid entitlements), PMV capture | SCHEMA INSPECTED; ACCESS BLOCKED; credential gated |
| KR-T | Kraken trade archive and REST `Trades` (one upstream) | REST: ACTUAL SAMPLE INSPECTED; archive: SCHEMA INSPECTED, ACCESS BLOCKED |
| KR-O | Kraken OHLCVT (archive; REST latest 720 bars) | SCHEMA INSPECTED |
| KR-WS† | Kraken WS v2 `book` (L2) + `trade`, PMV capture | ACTUAL SAMPLE INSPECTED |
| CB | Coinbase Exchange / Advanced Trade (REST trades; WS L2/L3 and PMV receipt time are live only, †) | SCHEMA INSPECTED |
| TD | Tardis.dev historical Kraken (and other exchanges') feeds | SCHEMA INSPECTED; ACCESS BLOCKED; licence gated |
| BRTI | CF Benchmarks BRTI (direct licence, or Kalshi CFB channel) | SCHEMA ONLY; ACCESS BLOCKED; licence gated |
| DB-T | Databento GLBX.MDP3 `trades` (GC, MGC) | SCHEMA INSPECTED; official non-gold fixture parsed |
| DB-TB | Databento `tbbo` (and `bbo-1s`/`bbo-1m`) | as DB-T |
| DB-M1 | Databento `mbp-1` | as DB-T |
| DB-M10 | Databento `mbp-10` | as DB-T |
| DB-MBO | Databento `mbo` | as DB-T |
| DB-DS | Databento `definition` + `statistics` (+ `status`) | as DB-T |
| CME | CME DataMine (direct) | ACCESS BLOCKED (TLS); SECONDARY |
| PY | Pyth gold (`Metal.XAU/USD`; GOLD index feeds known only from Kalshi docs) | SCHEMA INSPECTED; ACCESS BLOCKED; licence gated |
| PM | Polymarket (Gamma, CLOB, Data API, market WS) | SCHEMA INSPECTED; ACCESS BLOCKED |

## Matrix

Notes in brackets refer to the numbered list below the table.

| Information | K-H | K-WS† | KR-T | KR-O | KR-WS† | CB | TD | BRTI | DB-T | DB-TB | DB-M1 | DB-M10 | DB-MBO | DB-DS | CME | PY | PM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Prediction-market last trade | DIRECT | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [1] |
| Prediction bid | DIRECT [2] | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [1] |
| Prediction ask | DIRECT [2] | DERIVABLE [3] | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [1] |
| Prediction spread | DERIVABLE [2] | DERIVABLE | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [1] |
| Prediction L2 depth | ABSENT [4] | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [1] |
| Prediction quoted size | ABSENT [4] | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [1] |
| Prediction contract metadata | DIRECT | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT [5] |
| Time remaining | DERIVABLE [6] | DERIVABLE [6] | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| Contract reference-end time | DIRECT [7] | DIRECT [7] | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| Settlement rule | PROXY [7] | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| BTC spot trade price | ABSENT | PROXY [8] | DIRECT | DERIVABLE | DIRECT | DIRECT | DIRECT | PROXY [8] | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [8] |
| BTC spot trade volume | ABSENT | ABSENT | DIRECT | DERIVABLE | DIRECT | DIRECT | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| BTC aggressor information | ABSENT | ABSENT | DIRECT [33] | ABSENT | DIRECT | DIRECT [9] | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| BTC BBO | ABSENT | ABSENT | ABSENT | ABSENT | DIRECT | DIRECT [10] | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| BTC L2 | ABSENT | ABSENT | ABSENT | ABSENT | DIRECT | DIRECT [10] | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| BTC deeper book (order level) | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT [11] | DIRECT [10] | ABSENT [12] | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT |
| Exact BRTI / reference index | PROXY [13] | DIRECT [14] | PROXY | PROXY | PROXY | PROXY | PROXY | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [8] |
| Gold futures trade price | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | DIRECT | DIRECT | DIRECT | DIRECT | DIRECT | ABSENT | DIRECT | PROXY [15] | ABSENT |
| Gold futures trade volume | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | DIRECT | DIRECT | DIRECT | DIRECT | DIRECT | PROXY [16] | DIRECT | ABSENT | ABSENT |
| Gold BBO | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | DIRECT [17] | DIRECT | DIRECT | DERIVABLE [34] | ABSENT | DIRECT | PROXY [15] | ABSENT |
| Gold MBP-1 (every top-of-book event) | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT [17] | DIRECT | DERIVABLE | DERIVABLE [34] | ABSENT | DIRECT | ABSENT | ABSENT |
| Gold deeper book (levels 2–10) | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | DIRECT | DERIVABLE | ABSENT | DIRECT | ABSENT | ABSENT |
| Gold MBO | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | DIRECT | ABSENT | DIRECT [18] | ABSENT | ABSENT |
| Exact gold reference | PROXY [13] | DIRECT [14] | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [15] | PROXY | PROXY | PROXY | PROXY | PROXY | PROXY | DIRECT [19] | ABSENT |
| Exchange (event) timestamp | DIRECT | DIRECT [20] | DIRECT | DERIVABLE | DIRECT | DIRECT | trades DIRECT; book UNKNOWN | ABSENT | DIRECT | DIRECT | DIRECT | DIRECT | DIRECT | DIRECT | DIRECT | ABSENT | UNKNOWN |
| Receipt timestamp | ABSENT | DIRECT [21] | ABSENT | ABSENT | DIRECT [21] | ABSENT [21] | PROXY [22] | ABSENT | PROXY [22] | PROXY [22] | PROXY [22] | PROXY [22] | PROXY [22] | PROXY [22] | PROXY [22] | ABSENT | ABSENT |
| Publication timestamp | ABSENT | DIRECT [23] | ABSENT | ABSENT | ABSENT | DIRECT [24] | ABSENT | DIRECT | DIRECT [25] | TBBO DIRECT; BBO ABSENT [25] | DIRECT [25] | DIRECT [25] | DIRECT [25] | statistics DIRECT; definition/status ABSENT [25] | DIRECT | DIRECT [26] | UNKNOWN |
| Sequence number | ABSENT | DIRECT [27] | DIRECT [28] | ABSENT | trade DIRECT; book ABSENT [28] | DIRECT | book ABSENT; trades UNKNOWN before 2026-07-10 [29] | ABSENT | DIRECT | DIRECT | DIRECT | DIRECT | DIRECT | DIRECT | DIRECT | UNKNOWN | ABSENT [30] |
| Settlement value (of the prediction contract) | DIRECT | DIRECT | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | DERIVABLE [31] | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | PROXY [32] | PROXY [32] | DERIVABLE [31] | ABSENT [5] |

## Notes

1. Polymarket observes its **own** market on a similar, not identical, event: BTC up/down resolved on a Chainlink TWAP, not BRTI. Its book is a cross-venue estimate of a nearly identical probability, not the Kalshi book (`polymarket_markets_book.md`). Hourly BTC resolution source unresolved.
2. Historically, Kalshi bid and ask exist only as **1-minute OHLC of best bid and best ask** in candlesticks: the only historical quote evidence among documented public endpoints (an authenticated 5-second `forecast_percentile_history` endpoint exists with undocumented semantics: UNKNOWN). Spread is exact only at minute boundaries; within a minute, bounds only. A candle is usable only after its inclusive `end_period_ts` plus publication lag.
3. Kalshi books show bids on both legs. YES ask = 1 − best NO bid (documented). Derived, but exact (hence DERIVABLE).
4. REST market objects and REST order books are current state only (no timestamp, no sequence). No historical L2 endpoint exists.
5. Polymarket metadata describes Polymarket contracts only. It cannot replace Kalshi metadata or settlement values.
6. Time remaining = contract reference-end time − decision time. It needs the exact reference window from the contract terms (for example a 60-second average ending at close), not only `close_time`.
7. The API gives `close_time`, expiration fields, `settlement_sources`, and rule summaries (hence settlement rule = PROXY: summary only). The governing averaging window and tie rule are in the contract terms (`contract_terms_url`, owner download; DET-1 gold, DET-2 BTC). The exact reference window, and so the reference-end time, is DIRECT only once DET-1/DET-2 are resolved.
8. BRTI, the Kalshi CFB channel, and Polymarket's Chainlink stream are index or oracle levels, not trade prints.
9. Coinbase `side` is the **maker** side: it is the opposite of Kraken and Tardis, and must be inverted.
10. Coinbase L2/L3 are live only. Its history exists only through Tardis (All Exchanges plan) and stays bound by Coinbase terms.
11. Kraken `level3` needs an authenticated token.
12. Tardis has no Kraken L3. Its L3 covers Coinbase, Bitstamp, and Bitfinex.
13. Kalshi `expiration_value` ("The value that was considered for the settlement") is the settlement statistic (for example a window average) **at settlement instants only**, not the index series: hence PROXY for the reference series. For the **current** contract, and for any value not yet published at decision time, it must never enter a feature (it is label-defining). Values of **earlier** contracts, and the current contract's strike, are public before the decision and may be used walk-forward, only after their `settlement_ts` (or strike publication) is known to precede the decision (review S-B10-12).
14. Kalshi CFB (`cfbenchmarks_value`, 5 Hz) and `pyth_value` channels give the reference as Kalshi receives it, with upstream `source_ts_ms` and Kalshi `received_at`. Paid entitlements. Live only.
15. COMEX GC/MGC are dated futures. The Pyth XAU spot reference is "derived from futures" and differs from them by carry and roll basis. Distance-to-strike computed from futures needs a basis estimate (`pyth_gold.md` comparison H).
16. `statistics` carries cleared volume and open interest (daily), not intraday volume.
17. TBBO gives the top of book **immediately before each trade** only. `bbo-1s`/`bbo-1m` give a time-sampled top of book. Neither gives every quote event.
18. DataMine PCAP and market-depth products carry full MDP3 messages (SECONDARY).
19. Pending DET-1: which Pyth feed (`Metal.XAU/USD` vs `Metal.Index.GOLD/USD`) and which candle or average rule settles Kalshi gold. The GOLD index methodology is not documented by Pyth.
20. `orderbook_delta.ts_ms` is optional. Snapshots carry no event time.
21. Receipt time exists only where **PMV records it** in prospective capture. Coinbase would gain it only if PMV captured Coinbase.
22. **Vendor** receipt time (hence PROXY for PMV receipt): Databento `ts_recv` (PTP-synchronized capture, from 2017-05-21; earlier records carry `ts_recv = ts_event` with `F_BAD_TS_RECV`); Tardis `local_timestamp` (µs). These are real receipt times at the vendor's collector. They are a PROXY for PMV's own latency and cannot replace PMV capture for the protected evaluation.
23. Kalshi `sending_ts_ms` ("when Kalshi queued this message"), optional; CFB/Pyth `source_ts_ms`.
24. Coinbase Advanced Trade separates server send time (`timestamp`) from engine time (`event_time`).
25. Databento `ts_in_delta` gives CME's sending time (tag 52) as `ts_recv − ts_in_delta`.
26. Pyth Core `publish_time` (integer seconds). Pyth Pro `timestampUs` and `feedUpdateTimestamp` (µs). Stale prices are carried forward when markets are closed. Freshness is detectable only from `feedUpdateTimestamp`.
27. Kalshi `seq` per subscription (inferred scope); no book checksum.
28. Kraken `trade_id` is a contiguous per-book sequence (verified +1 on samples). The Kraken L2 book has **no sequence number**; integrity is a CRC32 checksum over the top 10 levels (verified 176/176 in B10).
29. Tardis raw replay keeps exchange-native sequence fields. Normalized CSVs do not add one.
30. Polymarket book messages carry a `hash` (algorithm undocumented) and no sequence number.
31. The prediction-contract settlement value is a function of the reference series over the contract's window. It is derivable only if the exact rule and tick set are known (BRTI: DET-2, including Kalshi's de-duplication of ticks; Pyth: DET-1).
32. The COMEX daily settlement price is not the Kalshi gold settlement value.
33. Archive `type` and REST "buy/sell" are not documented as the taker side; taker is inferred from the WS v2 definition. Verify on the first acquired archive file.
34. Books derived from MBO are the outright real book; implied prices are excluded (merged real + implied top of book is CMBP-1, not derivable from MBO). MBO exists from 2017-05-21 only.

## Reading the matrix: what is unique

| Information | Only source(s) | Consequence |
|---|---|---|
| Kalshi labels, contract terms, fees, timing | K-H (+ K-WS live) | Non-substitutable. CORE |
| Historical Kalshi quotes | K-H candles (1-min bid/ask OHLC) | Only coarse historical ask evidence. CORE |
| Kalshi L2, quoted size, receipt time | K-WS (PMV capture) | No history anywhere. Prospective capture is the only source |
| BTC trade tape with aggressor side and sequence, free | KR-T | Full tape since first trade. CORE |
| Historical BTC L2/BBO | TD only (paid) | Free path is prospective KR-WS capture only |
| Exact BTC settlement reference | BRTI (direct or Kalshi CFB channel); K-H `expiration_value` gives the settlement statistic at settlement instants only | Expected value: settlement fidelity rather than a new velocity signal (untested; see S-B10-09) |
| Gold intraday dynamics | DB-* (or CME, same upstream) | CORE for gold research |
| Exact gold reference | PY (or Kalshi `pyth_value`); K-H `expiration_value` at settlement instants | Gated on DET-1 |
| Historical receipt timestamps | DB `ts_recv` (gold, from 2017-05-21); TD `local_timestamp` (BTC, paid) | Vendor receipt only (PROXY); PMV receipt only prospectively |
