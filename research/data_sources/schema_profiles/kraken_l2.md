# Kraken spot — WebSocket v2 `book` (L2), plus REST `Depth` and `level3` (L3) schemas

**Status:** WS v2 `book` depth 10: **ACTUAL SAMPLE INSPECTED** (1 snapshot + 175 updates, live, 2026-10-19, authorized by the B10 charter for schema/semantics verification; registered in `docs/exposure_register.md`). REST `Depth`: **SCHEMA INSPECTED** (current-state only; not sampled). WS v2 `level3`: **SCHEMA INSPECTED**; **LICENSE/CREDENTIAL GATED** (authenticated channel; no key exists or may be created). **LICENCE OPEN** (M2). **No historical L2 exists from Kraken** ("The `Depth` endpoint returns the current order book at the time of the request. It is not a historical endpoint").

## Evidence

| URL | Retrieved (UTC) | HTTP | Bytes | SHA-256 | Grade |
|---|---|---|---|---|---|
| https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/book.md | 2026-10-19T04:19:55Z | 200 | 16,174 | `d67335c5b06c82a4a5e9f908bc5b2e3db93462043afe94a0a8263f2862e58573` | VERIFIED-BY-DOC |
| https://docs.kraken.com/exchange/guides/websockets/book-checksum-v2.md | 2026-10-19T04:19:57Z | 200 | 4,134 | `16b1ae803e56148f0e331e784928fc97473cdb6f1c0b5581e38075a7d0f4f426` | VERIFIED-BY-DOC |
| https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/level3.md | 2026-10-19T04:19:55Z | 200 | 21,098 | `411402851683cad8461e6cef169499b099a3b4a352cf5c36f218dc2d9b7d3df8` | VERIFIED-BY-DOC |
| https://docs.kraken.com/api-reference/market-data/get-order-book.md | 2026-10-19T04:19:54Z | 200 | 8,244 | `7f13d801d1c5789e0dea44e05d5e3f5fc58e59f06ee9c9aca2d87fc5213101c2` | VERIFIED-BY-DOC |

### Sample manifest (raw file deleted after inspection)

| Endpoint | Subscriptions | Started (UTC) | Messages | Bytes | SHA-256 |
|---|---|---|---|---|---|
| `wss://ws.kraken.com/v2` | `book` BTC/USD depth 10 snapshot=true; `trade` BTC/USD snapshot=true | 2026-10-19T04:23:48.887Z | 200 (≈ 30 s cap not reached) | 62,136 | `46e61b677db074b51b5b6fdf97a9f732c39671714280dd0d9650c5a55f962084` |

Tools: `research/data_sources/recon_tools/kraken_ws_sample.py` (stdlib RFC 6455 client through the egress proxy; each frame stored unmodified with local `recv_ns`), `kraken_ws_profile.py`. Message mix: 1 `status`, 2 subscribe acks, 1 `trade` snapshot, 13 `trade` updates, 7 `heartbeat`, 1 `book` snapshot, 175 `book` updates. Uncompressed JSON text frames (no permessage-deflate negotiated).

## Fields (book channel)

| Field | JSON type observed | Official semantics | PMV class |
|---|---|---|---|
| `channel` | string | `book` | — |
| `type` | string | "One of: `snapshot`" / "`update`" | DIRECT |
| `data[].symbol` | string | "The symbol of the currency pair." | DIRECT |
| `data[].bids[]`, `asks[]` | list of `{price, qty}` | "The bid price." / "The bid quantity." | DIRECT |
| `price`, `qty` | **JSON numbers** (not strings) | guide: "Parse `price` and `qty` fields using a decimal or string decoder to preserve full precision" | DIRECT; must be parsed as Decimal |
| `data[].checksum` | int (uint32) | "CRC32 checksum for the top 10 bids and asks." | DIRECT (integrity) |
| `data[].timestamp` | RFC3339 string, 6 fractional digits in all 176 | snapshot: "The timestamp of the order book snapshot."; update: "The book order update timestamp." | DIRECT (exchange event time) |
| subscribe ack `time_in`, `time_out` | RFC3339 µs | "when the subscription was received on the wire" / "when the acknowledgement was sent on the wire" | gateway times, ack only |
| `status.data[]` | `version`, `system`, `api_version`, `connection_id`, `upcoming_maintenance`, `emergency` | connection status | operational |
| `heartbeat` | `{channel}` only | liveness | operational |

Subscription depth: "One of: `10`, `25`, `100`, `500`, `1000`".

## Sequencing, snapshot, and delta semantics

- First message after the ack is a `snapshot` with the full subscribed depth (20 level entries = 10 bids + 10 asks). Updates carry only changed levels: 119 updates had 1 level change, 56 had 2.
- **No sequence number exists on the book channel.** Integrity rests on the CRC32 checksum over the top 10 levels, recomputed client-side.
- Maintenance rules (guide, verbatim): "An update with `"qty": 0` means that price level should be removed." "After each update, truncate your book to the subscribed depth — you will not receive `"qty": 0` for levels that fall out of scope." "it is possible to have multiple updates to the same price level in a single update message. Updates should always be processed in sequence."
- **Top-10 state reconstruction verified:** a local book maintained from the snapshot plus every update, with truncation to depth 10, reproduced the server checksum on **176 of 176** messages in one ~30 s window (no reconnect, no injected loss). The documented part of the algorithm is: remove "." and leading zeros, asks low→high then bids high→low. **Padding price to 1 dp and qty to 8 dp is OBSERVED/INFERRED**, not documented: the wire sends JSON numbers, and fixed-dp formatting is what reproduced the checksum (review API-B10-05). Production must read `price_precision`/`qty_precision` from the `instrument` channel and fail closed if the first snapshot's checksum does not match.
- **What the checksum does and does not verify (review API-B10-01):**
  - it verifies the **top-10 state at each message boundary**;
  - it does **not** verify event-stream completeness: a missed update to a level that a later message overwrites leaves a matching checksum, so missed events can be invisible;
  - intermediate states, add/cancel counts, and queue changes without trades are therefore **completeness-unverifiable**;
  - levels 11 and deeper are never verified ("always calculated over the top 10 price levels regardless of subscription depth");
  - a silent stall is not detected (no message, no checksum).
- Capture requirements if P2 is authorized: heartbeat and staleness timers; a connection/session id per frame; book history segmented at every resubscription; event-flow features labelled completeness-unverifiable; depth 10 preferred for verified state (or levels 11–25 explicitly tagged unverified); replay fault injection of dropped messages to measure undetected loss.

## Timestamps

- Exchange event timestamp per book message (µs). Local receipt time exists only because PMV records it (`recv_ns`).
- Local receipt minus exchange timestamp, across book and trade updates: p10 ≈ 65 ms, p50 ≈ 82 ms, p90 ≈ 188 ms. This mixes network path (sandbox proxy, transatlantic — Kraken matching is reported in London), server batching, and **unsynchronized local clock** (no NTP discipline verified). It is not a latency measurement; it shows that receipt time and event time differ materially at the PMV decision scale of seconds, which is why prospective capture records both.
- Book message spacing (local): p50 ≈ 0.1 ms (bursts), p90 ≈ 70 ms, max ≈ 1.3 s in the 30 s window. Descriptive only.

## REST `Depth` and WS `level3`

- REST `Depth`: entries "`[<price>, <volume>, <timestamp>]`" per level (per-level last-update time), up to 500 levels; current state only; no sequence. It cannot be aligned to the WS stream.
- WS `level3`: "provides visibility of individual orders in the book"; events "`add`", "`modify`" ("The order quantity has been modified, i.e. a fill"), "`delete`" ("full fill or cancel"); fields `order_id`, `limit_price`, `order_qty`, `timestamp`, `checksum`. "The `level3` channel is authenticated (i.e. it requires an API token to subscribe)". Not usable without a Kraken credential; out of scope for B10.

## Comparison B — what L2 contains that trades cannot reconstruct

Not derivable from trades, available only from the book (all **SOURCE_SPECIFIC** to L2 relative to the trade tape):
- best bid and ask, therefore **spread** and **mid** between trades (trades reveal only the side that was hit, at the moment of the trade);
- **quoted depth** at each level and cumulative depth within N ticks;
- **order-book imbalance** (bid vs ask quoted size), **microprice** (size-weighted mid);
- **queue changes without trades**: additions and cancellations (quote fading, spoof-like cancels, replenishment), which never appear in the trade tape;
- book resilience after a sweep.

Partly derivable from trades: an approximate effective spread from alternating buy/sell prints, and aggressor-signed flow (already DIRECT in trades).

**PMV caveats (no predictive claim):** at a 15–60 minute contract horizon with decisions in the final minutes, the target is the reference index level at expiry. Book features at one exchange mainly predict very short horizons (seconds to a few minutes). Whether they add calibrated information beyond trade-flow velocity for the remaining few minutes is an **empirical question**. Two structural facts bound it: (1) **Kraken provides no historical L2**, so any historical evaluation of L2 features needs a paid archive (Tardis) or must wait for prospective PMV capture; (2) PMV's own capture of this channel is free once licensed (M2) and yields receipt-time-true L2 for the protected prospective evaluation.

## Open questions

1. Whether `update` messages can coalesce several engine events (batching), and whether the update timestamp is the last event's time.
2. Behaviour on reconnect and on checksum mismatch (resubscribe semantics); none observed in 30 s.
3. Kraken licence for storing and modelling L2 (M2).
