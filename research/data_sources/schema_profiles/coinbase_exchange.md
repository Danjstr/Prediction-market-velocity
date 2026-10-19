# Coinbase Exchange — public market data (Exchange REST + WebSocket; Advanced Trade WS equivalents)

**Status:** SCHEMA INSPECTED (official docs and OpenAPI/AsyncAPI fragments on docs.cdp.coinbase.com read verbatim; no market data sample requested); `api.exchange.coinbase.com` reachable but deliberately NOT called; legal pages ACCESS BLOCKED (`www.coinbase.com`, `help.coinbase.com` not requested under B10 rules); LICENSE GATED (ordinary Market Data Terms require prior written consent for ML use, per repo evidence). Current disposition: **DROP for now** (owner_source_action_sheet.md B5).

**Evidence:** all retrieved 2026-10-19 by curl through the PMV egress proxy (no redirects occurred).

| URL | retrieved UTC | HTTP | bytes | sha256 | grade |
|---|---|---|---|---|---|
| https://docs.cdp.coinbase.com/llms.txt | 2026-10-19T04:20Z | 200 | 59304 | ca2d2e94e97509690a6e82d67ced076baf9f4f8f1dbc3a15aebc560ca2ba1da7 | index |
| https://docs.cdp.coinbase.com/_llms/api-reference/coinbase-exchange-api.txt | 2026-10-19T04:20Z | 200 | 21647 | e381926dde3f0af97a56b485d69036bfa5a319f24e25bec8a9b097d3c2566050 | index |
| https://docs.cdp.coinbase.com/_llms/docs.txt | 2026-10-19T04:20Z | 200 | 71250 | 1366216ca64d2ee96fc079043aa6de4ba2c405f3437430abc9e81743a04bfb57 | index |
| https://docs.cdp.coinbase.com/_llms/api-reference/coinbase-advanced-trade-api.txt | 2026-10-19T04:20Z | 200 | 53747 | 9b995503e2af76583bc462418c45ca50a5a27fcd2f34db49ce38b6727a5e655c | index |
| https://docs.cdp.coinbase.com/exchange/websocket-feed/overview.md | 2026-10-19T04:20:56Z | 200 | 7767 | e8db9bf7983e498b17209cce2333a7d08b085608b4d4a738e1138dd3abd7b27a | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/exchange/websocket-feed/channels.md | 2026-10-19T04:20:56Z | 200 | 25705 | 21b5c86683e63f322c6edd7735d27e7016a0a52d11fbc654fa3ad932f8b552dc | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/exchange/websocket-feed/best-practices.md | 2026-10-19T04:20:56Z | 200 | 2507 | b2d7eedccfd7ce878faa79d81be5caaa541d1faffc5e9edf729f7a1eabcc49c0 | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades.md | 2026-10-19T04:20:56Z | 200 | 4369 | 4cbf49585ca519b91f8374751059cf16f1a41c27cb8797a544e2f799a4f59464 | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles.md | 2026-10-19T04:20:56Z | 200 | 4994 | ce66414274ecc32b6c5317d6a595f8e131f7db602596b9cad0bac485e987548f | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker.md | 2026-10-19T04:20:56Z | 200 | 3821 | 0371ab9e1aa395b359d61eb80d0c93b028d71cc533f3632bf41657f93c5d2a91 | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book.md | 2026-10-19T04:20:56Z | 200 | 8634 | ed527e9c0e8bca07faf337b78a55448acb614dbed0fae73f1ccaa89831c111a1 | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-endpoints.md | 2026-10-19T04:20:56Z | 200 | 12120 | 747b7f665569c70eac2998da5d1b213977937ef24bfeda9be89d048dbd7404bc | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-overview.md | 2026-10-19T04:20:56Z | 200 | 11800 | c8f7e384762ea598007c08b5e8dc4241c37437ed3c104535f5e0be2124d5b38a | not relied on |
| https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/websocket/market-trades.md | 2026-10-19T04:21:55Z | 200 | 9712 | c041c23184dfe2c3309985a65a0a9515c570c58600b7f9eee75e9ce01f221771 | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/websocket/level2.md | 2026-10-19T04:21:55Z | 200 | 9588 | 922d778d79c1e4a2338678abb2358c15bb8499aa0368b8ac4bbcf8d95a843213 | VERIFIED-BY-DOC |
| https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/websocket/ticker.md | 2026-10-19T04:21:55Z | 200 | 10552 | 380ecdddc723b186f4e3f0253c328bcc8a9dc571279b512c360e2c52feb7ea64 | VERIFIED-BY-DOC |
| https://docs.tardis.dev/historical-data-details/coinbase.md | 2026-10-19T04:18:43Z | 200 | 9185 | d6d6874b4093da7088af1211f1bc065170060e20318511a39e2292eb710457bc | VERIFIED-BY-DOC (Tardis's Coinbase archive) |
| https://docs.tardis.dev/legal/terms-of-service.md (clause 23) | 2026-10-19T04:18:43Z | 200 | 50714 | 4c084c8204b8e3a1e5d64b7f334e9dba9b516918ad6018b066011a5a2532cfe8 | VERIFIED-BY-DOC |
| owner_source_action_sheet.md B5; master_source_inventory.md B-5, B-6, B-7, INV-2 | — | — | — | git | repo-Git |

## Access and connectivity

- Docs host `docs.cdp.coinbase.com`: reachable (all 200).
- `api.exchange.coinbase.com` (REST market data): reachable per brief, **not called** (live market observations).
- WS endpoints (not contacted): Exchange "Coinbase Market Data" `wss://ws-feed.exchange.coinbase.com` ("available without authentication"); "Coinbase Direct Market Data" `wss://ws-direct.exchange.coinbase.com` ("requires Authentication"). Advanced Trade public `wss://advanced-trade-ws.coinbase.com` ("A JWT is not required").
- Authentication-required Exchange channels: `full`, `level2`, `level3`, `user`, `balance`. Unauthenticated: `heartbeat`, `status`, `auction`, `matches`, `ticker`, `ticker_batch`, `level2_batch`, `rfq_matches`.
- Legal hosts `www.coinbase.com` (Market Data Terms) and `help.coinbase.com`: not requested (BLOCKED per brief).

## Transport, format, compression, delivery (historical vs live)

- REST JSON. Trades endpoint "Gets a list the latest trades", paginated by trade-id cursors (`before`/`after`, `limit` default 1000). Historical reach via cursor is not specified (inventory B-5: "depth 'not specified'").
- Candles: "`granularity` field must be one of … `{60, 300, 900, 3600, 21600, 86400}`"; "maximum number of data points for a single request is `300` candles"; bucket = `[time, low, high, open, close, volume]`; "Historical rate data may be incomplete. No data is published for intervals where there are no ticks."
- WS: JSON, every message has `type`; "New message types can be added at any time"; permessage-deflate supported; must subscribe within 5 s.
- **No official historical tick/book archive from Coinbase**: historical WS-level data exists only via third parties (Tardis "Coinbase Exchange historical data for all its currency pairs is available since 2019-03-30", captured from `wss://ws-direct.exchange.coinbase.com`, including L3 `received/open/done/change`, `match`, `l2update`, `snapshot`, `ticker`, generated `full_snapshot`), and that is Coinbase-licence-gated.

## Fields

### REST `GET /products/{product_id}/trades` (apiProductTrade)

| field | native type | official semantics | PMV class | notes |
|---|---|---|---|---|
| trade_id | integer (int32 in spec) | required; cursor key | SOURCE_SPECIFIC | spec says int32; real ids may exceed int32 (UNVERIFIED; treat as int64) |
| side | enum buy/sell | "The `side` of a trade indicates the **maker order side**. … A `buy` side indicates a down-tick because the maker was a buy order … A `sell` side indicates an up-tick." | DERIVABLE (taker side = opposite) | **Opposite convention to Kraken and Tardis normalized (taker/aggressor)** |
| size | decimal string | base size | DIRECT | |
| price | decimal string | trade price | DIRECT | |
| time | string date-time | trade time | DIRECT | precision not stated (doc example has ms) |

### REST candles: `time` "bucket start time", `low`, `high`, `open` "opening price (first trade)", `close` "closing price (last trade)", `volume`. DERIVABLE from trades.

### REST ticker: `trade_id, price, size, time, bid, ask, volume, rfq_volume, conversions_volume` — "snapshot information about the last trade (tick), best bid/ask and 24h volume".

### REST product book: levels — "1 | The best bid, ask and auction info", "2 | Full order book (aggregated)", "3 | Full order book (non aggregated)"; response has `sequence`, `auction_mode`, `auction`, `time`. "Level 3 is only recommended for users wishing to maintain a full real-time order book using the WebSocket stream."

### WS `matches` / `match` (also in `full`)

Fields: `type, trade_id, sequence, maker_order_id, taker_order_id, time, product_id, size, price, side`. "The `side` field indicates the maker order side. If the side is `sell` this indicates the maker was a sell order and the `match` is considered an up-tick." First message after subscribing is `last_match`. "Messages can be dropped from this channel. Use the heartbeat channel to track the last trade ID and fetch trades that you missed from the REST API."

### WS `ticker` (on every match, batched during cascades)

Fields: `type, sequence, product_id, price, open_24h, volume_24h, low_24h, high_24h, volume_30d, best_bid, best_bid_size, best_ask, best_ask_size, side, time, trade_id, last_size`. `ticker_batch`: same schema "every 5000 milliseconds … if there is a change".

### WS `level2` (auth) / `level2_batch` (no auth)

- `snapshot`: "`bids` and `asks` are arrays of `[price, size]` tuples and represent the entire order book."
- `l2update`: "`changes` property … is an array with `[side, price, size]` tuples. The `time` property of `l2update` is the time of the event as recorded by our trading engine." "The `size` property is the updated size at the price level, not a delta. A size of `"0"` indicates the price level can be removed." Side values in examples: `buy`/`sell`.
- `level2` "guarantees delivery of all updates"; `level2_batch` "sends batches of `level2` messages **every 50 milliseconds** … The time field correlates to the most recent message in the batch."
- No sequence field shown in level2 messages; no checksum documented.

### WS `full` (auth) — L3 order lifecycle

- `received`: `type, time, product_id, sequence, order_id, size, price, side, order_type` (+`funds` for market orders; `client_oid` only for own orders). "emitted for every single valid order as soon as the matching engine receives it … does not indicate a resting order".
- `open`: `type, time, product_id, sequence, order_id, price, remaining_size, side`. "only sent for orders that are not fully filled immediately".
- `done`: `type, time, product_id, sequence, price, order_id, reason (filled|canceled), side, remaining_size`. "`done` messages for orders that are not on the book should be ignored".
- `match`: as above.
- `change`: STP (`reason":"STP"`, size/funds decrease) or modify (`reason":"modify_order"`, `old_price`, `new_price`).
- `activate`: stop orders (`timestamp` as epoch-seconds decimal string in example).

### WS `level3` (auth) — compact L3

First message is a schema; subsequent messages are positional arrays. Documented schema: `open: [type, product_id, sequence, order_id, side, price, size, time]`; `change: [type, product_id, sequence, order_id, price, size, time]`; `done: [type, product_id, sequence, order_id, time]`; `match: [type, product_id, sequence, maker_order_id, taker_order_id, price, size, time]`; `noop: [type, product_id, sequence, time]`. "While the schema should not change, it may." Note: the compact `match` has no `trade_id` or `side` (side derivable from the maker order's `open`).

### WS `heartbeat`, `status`, `auction`, `rfq_matches`

- `heartbeat`: `type, sequence, last_trade_id, product_id, time` every second — "can be used to verify that no messages were missed".
- `auction`: `auction_state` (collection/opening/complete), indicative open price/size and BBO; "values are not firm"; during collection "the book may appear crossed".
- `rfq_matches`: `type, maker_order_id, taker_order_id, time, trade_id, product_id, side` (+ size/price) — RFQ fills that are not order-book matches.

### Advanced Trade public WS (equivalents)

- Channels: `heartbeats`, `candles` ("five-minute buckets, updated every second"), `status`, `ticker`, `ticker_batch` ("no best bid or ask"), `level2`, `market_trades` ("batched over the last 250 ms").
- Envelope: `timestamp` "Server time the message was sent (RFC 3339)"; `sequence_num` "Per-connection message sequence number; use it to detect dropped or out-of-order messages."; events `type` snapshot|update.
- `level2` (`l2_data`): updates `side` (enum incl. `bid`), `event_time` "Time of the event as recorded by the trading engine", `price_level`, `new_quantity` "Updated size at this price level (not a delta). A value of "0" means the level can be removed."
- `market_trades`: `trade_id`, product, price, size, `side` "The maker's side of the trade" (enum `BUY`/`SELL`), `time` "Time the trade occurred (RFC 3339)".
- No L3 on Advanced Trade public WS. Note: "`-USDC` product IDs … return the same data as the matching `-USD` product".

## Timestamps

- Exchange event time: WS `time` (RFC 3339 / ISO 8601 UTC strings; doc examples show µs, e.g. `…T08:19:28.464459Z`; REST examples show ms). Precision is not formally stated → treat as "up to µs, variable"; UNKNOWN whether trailing zeros are trimmed.
- `l2update.time` = "time of the event as recorded by our trading engine"; `level2_batch` time = most recent message in batch.
- Advanced Trade separates **publish time** (`timestamp`, "Server time the message was sent") from **engine event time** (`event_time` / trade `time`), which gives a native exchange-side publish-lag measure.
- Receipt time: none from Coinbase; PMV collector must stamp its own (Tardis provides `local_timestamp` for its archive).
- `balance` channel (private, irrelevant) shows the same split (`updated` vs `timestamp`).

## Sequencing and book semantics

- Exchange WS: "Sequence numbers are increasing integer values for each product, with each new message being exactly one sequence number greater than the one before it." Gap = dropped message; lower = out of order/ignore. "the WebSocket servers receive market data in a manner that can result in dropped messages. Your feed consumer should be designed to handle sequence gaps … or should use channels that guarantee delivery" (level2).
- L3 recovery procedure (verbatim steps): subscribe `full`; queue messages; "Make a REST request for the order book snapshot"; "Playback queued messages, discarding sequence numbers before or equal to the snapshot sequence number"; apply; then stream. "All `open` and `match` messages always result in a change to the order book. Not all `done` or `change` messages result in changing the order book."
- L2: full-depth snapshot then absolute-size updates (MBP, full depth). No checksum (contrast Kraken's checksummed book).
- Trades gap recovery: heartbeat `last_trade_id` + REST trades.
- Advanced Trade: `sequence_num` is per connection (not per product).

## Instrument / contract identity, expiry, reference-end, settlement

`product_id` such as `BTC-USD`; `status` channel gives `base_increment`, `quote_increment`, `min_market_funds`, trading-state flags (`post_only`, `limit_only`, `cancel_only`), and auction mode. Spot only; no expiry/settlement. Coinbase is a BRTI constituent exchange (repo: "Largest USD BRTI constituent", B5); BRTI itself is not available here.

## Licence / access gating

- Repo evidence: owner_source_action_sheet.md B5 — "Ordinary terms require prior written consent to use market data to train, validate, benchmark, or improve ML systems (OWNER-VERIFIED)", NEEDS_WRITTEN_PERMISSION; disposition table: "DROP for now … Reconsider only if the BRTI-proxy test shows material mismatches"; Tier 3 "Coinbase licensed data: do not buy now". master_source_inventory.md INV-2: "Prefer Kraken, Bitstamp, and Tardis non-Coinbase data. Request consent only if the BRTI-proxy test shows Coinbase matters." A draft consent email exists (action sheet "Optional — Coinbase", not queued).
- Third-party route does not escape this: Tardis Terms clause 23 (VERIFIED-BY-DOC) — "Customer shall not further disseminate Coinbase Data or Derived Works, or use or permit their use for any Prohibited Use", including "any other use of Coinbase Data or Derived Works not expressly permitted under the Coinbase Market Data Terms of Use"; Coinbase "may inspect Customer's use … upon ten (10) days' advance notice" and may require customer name/address reporting. Tardis clause 9.5: "Supplier's permission does not replace any required licensor consent." Tardis also sells Coinbase only in the "All Exchanges" plan.
- Coinbase Market Data Terms text was not re-read here (host blocked); relies on owner-verified repo evidence.

## PMV relevance — comparison C: Kraken vs Coinbase

What Coinbase would add that Kraken does not (relevance, **no predictive claim**):
1. **BRTI weight**: Coinbase is (per repo) the largest USD BRTI constituent. Kalshi BTC settles on BRTI, so Coinbase prices plausibly track the settlement reference more closely than Kraken alone. This is the main genuinely independent piece of information. The planned BRTI-proxy test (Kraken + others vs BRTI) is the right way to measure whether it matters.
2. **Cross-exchange dispersion / lead-lag**: a second major USD venue allows Kraken–Coinbase basis and lead-lag features. In the last minutes of a contract window, a Kraken-only view can miss a move that BRTI already reflects through Coinbase. Plausible but unproven; other BRTI constituents (Bitstamp, Gemini, Bullish, Crypto.com; O4) give partial substitutes with lighter licence burdens.
3. **Richer native microstructure**: unauthenticated full-depth L2 at 50 ms (`level2_batch`), authenticated L3 with order lifecycle, auction state, explicit engine event time vs publish time (Advanced Trade), and sequence numbers per product. Kraken also offers L2 (checksummed) and L3 with key, so this is a quality difference, not a new information class.
4. **Trade-side semantics differ**: Coinbase `side` = **maker** side (`sell` = up-tick, buyer-initiated); Kraken and Tardis-normalized `side` = **taker** side. Any cross-exchange order-flow feature must invert Coinbase side, or signed flow will be silently reversed. This is a correctness hazard, not information. (Whether Tardis's normalized Coinbase trades are already inverted to taker side is implied by its schema text "liquidity taker side (aggressor)" but not verified against a sample.)

Would it justify another connector and licensing surface? **Not now.** This matches the approved DROP:
- No free historical Coinbase tick/book archive exists. History needs Tardis All Exchanges (higher tier) under Coinbase clause-23 restrictions plus Coinbase ML consent. Even prospective capture needs consent before any model training or validation, because the ordinary terms bar ML use.
- A connector is technically cheap (public WS, documented sequencing). The cost is legal: written consent, audit/inspection rights, and reporting.
- Decision rule (already in repo): run the BRTI-proxy test with Kraken (plus Bitstamp/Gemini/etc. if licensed). If the Kraken-based proxy shows material late-window mismatches against BRTI around settlement, then send the drafted Coinbase consent request. Coinbase is the highest-value candidate to close that gap.
- If adopted later, the connector must normalize `side` (maker→taker), treat `trade_id` as int64, stamp receipt time locally, and use `level2` (guaranteed delivery, auth) or `level2_batch` plus sequence/heartbeat gap checks.

## Open questions / unverified items

- Coinbase Market Data Terms current text (host blocked); owner-verified summary relied on.
- Formal timestamp precision for WS/REST `time` — not stated; examples vary (µs vs ms).
- Exact historical reach of REST trades pagination — not specified in docs.
- `trade_id` int32 in OpenAPI vs real magnitude — UNVERIFIED.
- Whether `level2_batch` messages carry a sequence — not shown in docs.
- Tardis normalized Coinbase trade side inversion — UNVERIFIED.
- Exact BRTI constituent weights and Coinbase share — not established here (repo SECONDARY).
