# Kraken spot — WebSocket v2 `trade` channel

**Status:** **ACTUAL SAMPLE INSPECTED** (1 snapshot of 50 trades + 13 update messages carrying 17 trades; live, 2026-10-19; same capture as `kraken_l2.md`, manifest there). **LICENCE OPEN** (M2).

## Evidence

| URL | Retrieved (UTC) | HTTP | Bytes | SHA-256 | Grade |
|---|---|---|---|---|---|
| https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/trade.md | 2026-10-19T04:19:54Z | 200 | 9,905 | `5f7412240a2095b144b49c4b23cac4182606d8f049f6206a22f717feb1990edb` | VERIFIED-BY-DOC |

Sample: `wss://ws.kraken.com/v2`, file SHA-256 `46e61b677db074b51b5b6fdf97a9f732c39671714280dd0d9650c5a55f962084` (shared with the book sample; deleted after inspection).

## Fields

| Field | JSON type observed | Official semantics (verbatim) | PMV class |
|---|---|---|---|
| `type` | string | "One of: `snapshot`, `update`"; "The snapshot reflects the most recent 50 trades." | — |
| `symbol` | string | "The symbol of the currency pair." | DIRECT |
| `side` | string {`buy`, `sell`} | "The side of the taker order." | DIRECT (aggressor) |
| `qty` | JSON number | "Size of the trade." | DIRECT; parse as Decimal |
| `price` | JSON number | "**Average price of the trade.**" | DIRECT; see note |
| `ord_type` | string {`limit`, `market`} | "The order type of the taker order." | DIRECT |
| `trade_id` | int | "Trade identifier is a sequence number, unique per book." | DIRECT (sequence) |
| `timestamp` | RFC3339 string, µs | "The book order update timestamp." | DIRECT (event time) |

Note: "Average price of the trade" is unexplained; observed prices sit on the 0.1 tick grid, so each message row appears to be one print. Treat it as the print price until a doc says otherwise (UNKNOWN residual).

## Semantics observed

- `trade_id` steps were +1 across all 66 consecutive trades (snapshot through updates): the trade stream is gap-detectable by `trade_id`, unlike the book channel.
- Batching: 11 update messages carried 1 trade, 2 carried 3 trades. Doc: "Multiple trades may be batched in a single message but that does not mean that these trades resulted from a single taker order."
- Side labels differ by surface: WS `buy`/`sell`; REST and archive `b`/`s`. Same meaning (taker side).
- The REST/archive `trade_id` series and the WS `trade_id` appear to share one per-book counter (REST 2023 ids are lower than WS 2026 ids). Equality for the same trade is UNVERIFIED (needs an overlap window, not observed in B10 because the REST sample was deliberately old).

## Timestamps

Exchange event time (µs). Receipt time only from PMV's own `recv_ns`. For trade updates, local receipt minus exchange timestamp falls in the same range as the book (see `kraken_l2.md`; unsynchronized clock caveat).

## PMV relevance

This is the prospective, receipt-time-true version of the historical trade tape (`kraken_historical_trades.md`): same fields plus PMV receipt time. Historical trades and live WS trades should share one normalized schema keyed by `trade_id`.
