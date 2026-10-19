# Kraken spot — OHLCVT (downloadable archive and REST `OHLC`)

**Status:** **SCHEMA INSPECTED**. Archive sample **ACCESS BLOCKED** (`assets.kraken.com`, refused by the PMV egress proxy). REST `OHLC` **deliberately not sampled**: it "Returns up to 720 of the most recent entries (older data cannot be retrieved, regardless of the value of `since`)", so any REST OHLC sample would be a recent observation, contrary to the B10 rule to use old intervals. **LICENCE OPEN** (M2).

## Evidence

| URL | Retrieved (UTC) | HTTP | Bytes | SHA-256 | Grade |
|---|---|---|---|---|---|
| https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data | 2026-10-19T04:22:44Z | 200 | 1,006,308 | `4146de641267f1d0e97df89a8faf830e625f3c5963a6c08a63f3acd6d112d943` | VERIFIED-BY-DOC (updated 2026-10-12) |
| https://docs.kraken.com/api-reference/market-data/get-ohlc-data.md | 2026-10-19T04:19:53Z | 200 | 9,101 | `70313f475ff97bb1ac1a65a59e8409b546ffae640fcdda10b80c60d1e636e4b1` | VERIFIED-BY-DOC |
| https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/ohlc.md | 2026-10-19T04:19:55Z | 200 | 12,766 | `72192f17a4f98f2efb5f8be93202bab06c346115fd018f8175f33d93ed6dbe4a` | VERIFIED-BY-DOC |

## Format and delivery

| Surface | Row | Intervals | History | Notes |
|---|---|---|---|---|
| Archive (`Kraken_OHLCVT_Full.zip.part00`–`part04`, quarterly `Kraken_OHLCVT_2026Q1/Q2/Q3.zip`) | "`timestamp, open, high, low, close, volume, trades`. OHLCVT files do not include a header row." | 1, 5, 15, (30,) 60, 240, 720, 1440 min (the article lists 30 in one place and omits it in another: minor doc inconsistency) | "through 30 June 2026" (full); quarterly increments | "Only intervals in which trades occurred are included (gaps are not zero-filled)." `MANIFEST.json` per archive |
| REST `GET /0/public/OHLC` | "`[int <time>, string <open>, string <high>, string <low>, string <close>, string <vwap>, string <volume>, int <count>]`" | 1, 5, 15, 30, 60, 240, 1440, 10080, 21600 | latest 720 entries only | "The last entry in the OHLC array is for the current, not-yet-committed timeframe" — a live, mutable bar |
| WS v2 `ohlc` | per-interval candle updates | as REST | live only | not captured |

Archive rows have **no VWAP** column; REST rows do.

## Fields and classification

| Field | Archive | REST | PMV class | Derivation from trades |
|---|---|---|---|---|
| timestamp / time | yes (bar start presumed; UNKNOWN whether start or end) | int, bar start presumed | DERIVABLE | bar key = floor(trade time / interval) |
| open, high, low, close | yes | strings | DERIVABLE | first, max, min, last trade price in the bar |
| vwap | **absent** | string | DERIVABLE | Σ(price·volume)/Σvolume |
| volume | yes | string | DERIVABLE | Σ volume |
| trades / count | yes | int | DERIVABLE | number of trade rows |

## Comparison A — can OHLCVT be recreated deterministically from trades?

**Yes, in principle, and every OHLCVT field is a deterministic function of the trade tape** (support article definitions: "Open - the first traded price … Trades - the number of individual trades"; both archives contain every public trade). The B10 profiler computed open, high, low, close, VWAP, volume, and count from the REST trade sample and confirmed internal consistency (high ≥ open/close ≥ low, VWAP inside [low, high]).

**Not empirically verified in B10**: a byte-level match between an official OHLCVT bar and bars rebuilt from trades needs both archives for the same old interval, and the archive host is blocked. Conventions that must be confirmed on the first acquired files (inside the acquisition gate) before treating OHLCVT as fully redundant:
1. bar timestamp convention (start vs end) and boundary inclusivity;
2. whether busted or corrected trades are excluded from one product but not the other;
3. rounding of volume and of REST VWAP;
4. whether the archive excludes any trade type (none documented).

**Recommendation:** OHLCVT is **REDUNDANT** with the trade archive. Keep it only as a QA/reference product: rebuild bars from trades and reconcile against a small number of official OHLCVT files (for example one quarter of 1-minute XBTUSD). Do not make it an independent research dependency. Downloading the full OHLCVT archive (5 parts × ~2 GB) is not justified once trades are held; a single quarterly increment is enough for the reconciliation check.

## Timestamps and sequencing

**Availability rule (review API-B10-07):** archive bars are keyed by start time (supported by WS `ohlc` `interval_begin`, "start of the interval"; archive convention still to confirm), so a bar is usable only at start + interval. Bar time only. No receipt time, no sequence. The REST last bar is uncommitted and mutable, so any live use must take only committed bars (point-in-time correctness).

## Open questions

Bar timestamp convention; whether the 30-minute archive interval exists; archive numeric formatting. All resolvable from one acquired file.
