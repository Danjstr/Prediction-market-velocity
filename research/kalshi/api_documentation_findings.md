# PMV Kalshi adapter: verified facts from official documentation

- Scope: Phase 1 batch 2, Kalshi venue verification, documentation research only.
- Source set: official Kalshi documentation retrieved 2026-10-15 between 23:58Z and 23:59Z (URLs, retrieval times, and SHA-256 hashes are recorded in `research/sources.md`; the local copies are session scratch; whether to retain them is an owner decision, Red-Team RT-B2-23). No network request was made in producing this note, and no Kalshi API host was contacted.
- Spec versions in the snapshot: `openapi.yaml` `info.version: 3.34.0` ("Kalshi Trade API Manual Endpoints"); `asyncapi.yaml` `asyncapi: 3.0.0`, `info.version: 2.0.0` ("Kalshi Market Data WebSocket API"). Every rendered `api-reference/*` page embeds the same OpenAPI version, 3.34.0.
- Verification level: everything below is verified by documentation only. Nothing is verified by test. Any item marked VERIFIED still needs confirmation against sandbox or recorded data before production code relies on it, as the role charter requires.
- Example payloads in the docs are illustrations, not data. They are used here only to describe format, such as the sign or type of a field.

> **Errata (Red-Team review, 2026-10-16; see `research/kalshi/red_team_review.md`).** Corrections C2, C3, C4, C5, C6, and C13 are applied in place. C10 applies throughout: every date taken from the changelog is a **label date**; its effective date is unverified. Specifically, "WS ms timestamps added Apr 15, 2026", "`sending_ts_ms` added Oct 1, 2026", and "ack/data race fixed Sept 17, 2026; earlier captures may ..." are vendor-labelled dates, not verified effective dates.

Status legend:
- **VERIFIED**: the doc states it. Quote or close paraphrase given.
- **UNRESOLVED**: the doc is silent, ambiguous, or contradictory. The gap is stated.
- **INFERENCE**: a reasonable reading that the doc does not state. Do not treat it as verified.
- **CONFLICT**: two official sources disagree. Treat as UNRESOLVED until a test settles it.

Source citation form: full `https://docs.kalshi.com/...` URL. For the two spec files, the JSON-pointer-like path inside the file is added, for example `https://docs.kalshi.com/openapi.yaml#/components/schemas/Market`. Changelog entries are cited by their date label.

---

## 0. Source provenance (from manifest; all HTTP 200)

| URL | sha256 prefix | bytes |
| - | - | - |
| https://docs.kalshi.com/welcome/index.md | df7897ce967ea172 | 3561 |
| https://docs.kalshi.com/getting_started/api_environments.md | 3699198c05638954 | 3235 |
| https://docs.kalshi.com/getting_started/quick_start_market_data.md | 71889f44b353de08 | 8567 |
| https://docs.kalshi.com/getting_started/quick_start_websockets.md | 645674c6f694a21d | 15454 |
| https://docs.kalshi.com/getting_started/quick_start_authenticated_requests.md | c6d2c43ba05c9a19 | 7336 |
| https://docs.kalshi.com/getting_started/demo_env.md | c1e144fe01d5f5ea | 1419 |
| https://docs.kalshi.com/getting_started/api_keys.md | 70d8b3957dd952c3 | 8739 |
| https://docs.kalshi.com/getting_started/rate_limits.md | 3baaee8fcffe3fbc | 12883 |
| https://docs.kalshi.com/getting_started/pagination.md | abe2bcc1f8931ed6 | 5407 |
| https://docs.kalshi.com/getting_started/orderbook_responses.md | a87d1a2b795b7fc0 | 8513 |
| https://docs.kalshi.com/getting_started/order_direction.md | 596c8beb4eb6ccf6 | 4463 |
| https://docs.kalshi.com/getting_started/fixed_point_migration.md | 249bb44d972bfef9 | 5220 |
| https://docs.kalshi.com/getting_started/fee_rounding.md | 0e75e087de5e9089 | 3786 |
| https://docs.kalshi.com/getting_started/historical_data.md | 547782c580ec46ac | 6284 |
| https://docs.kalshi.com/getting_started/market_lifecycle.md | fc1e534166262db0 | 5963 |
| https://docs.kalshi.com/getting_started/maintenance_and_pauses.md | 18bd36f86a9fab4e | 1885 |
| https://docs.kalshi.com/getting_started/market_settlement.md | ae5b054f44899522 | 1371 |
| https://docs.kalshi.com/getting_started/settlement_bounds.md | 67611785e6b52c16 | 3855 |
| https://docs.kalshi.com/getting_started/exchange_sharding.md | d3988f83a6c5c9e9 | 6927 |
| https://docs.kalshi.com/getting_started/terms.md | a52d8a7ad71d90c8 | 5005 |
| https://docs.kalshi.com/cfbenchmarks/rest-passthrough.md | bf0ef09aae3c9754 | 5987 |
| https://docs.kalshi.com/sdks/overview.md | bbe932da3abaa311 | 1914 |
| https://docs.kalshi.com/api-reference/exchange/get-exchange-status.md | f802f49f8d3c44ed | 5833 |
| https://docs.kalshi.com/api-reference/exchange/get-series-fee-changes.md | 0e89ceee6124b97a | 5108 |
| https://docs.kalshi.com/api-reference/exchange/get-exchange-schedule.md | c132d28acc3e5483 | 6139 |
| https://docs.kalshi.com/api-reference/exchange/get-user-data-timestamp.md | 667587901abf5fb7 | 3596 |
| https://docs.kalshi.com/api-reference/market/get-market-candlesticks.md | e7456ed336684990 | 11810 |
| https://docs.kalshi.com/api-reference/market/get-trades.md | 56d72b0b6db9d80a | 10598 |
| https://docs.kalshi.com/api-reference/market/get-market-orderbook.md | ec5115f854716248 | 6498 |
| https://docs.kalshi.com/api-reference/market/get-series.md | 3112e2e5ae8c4e11 | 10185 |
| https://docs.kalshi.com/api-reference/market/get-series-list.md | af5ffa15ac90cfd4 | 11128 |
| https://docs.kalshi.com/api-reference/market/get-markets.md | 172f9ace7531e1ec | 22357 |
| https://docs.kalshi.com/api-reference/market/get-market.md | ae9d917509f33d27 | 16009 |
| https://docs.kalshi.com/api-reference/events/get-events.md | 53edc7744038cc3e | 26178 |
| https://docs.kalshi.com/api-reference/events/get-event.md | 3d578cfe0a3817fb | 22246 |
| https://docs.kalshi.com/api-reference/events/get-event-metadata.md | d07078d2251c7ca2 | 5044 |
| https://docs.kalshi.com/api-reference/events/get-event-fee-changes.md | 0bfa439901cd21fb | 6755 |
| https://docs.kalshi.com/api-reference/live-data/get-event-live-data.md | c6f93b87342cfa23 | 4736 |
| https://docs.kalshi.com/api-reference/historical/get-historical-cutoff-timestamps.md | a50b953d229f1117 | 6420 |
| https://docs.kalshi.com/api-reference/historical/get-historical-market-candlesticks.md | 12b4d68411e91251 | 9866 |
| https://docs.kalshi.com/api-reference/historical/get-historical-trades.md | eca34229c0f15738 | 10973 |
| https://docs.kalshi.com/api-reference/historical/get-historical-markets.md | 69e131d13e0727aa | 18349 |
| https://docs.kalshi.com/api-reference/historical/get-historical-market.md | 2ef52dae1f13f762 | 16426 |
| https://docs.kalshi.com/api-reference/account/get-account-api-limits.md | f1a2b82b1f4c25c2 | 6611 |
| https://docs.kalshi.com/api-reference/account/list-non-default-endpoint-costs.md | 5daf84eedcc614a8 | 3952 |
| https://docs.kalshi.com/websockets.md | 91785dbb111eb0b0 | 1448 |
| https://docs.kalshi.com/websockets/websocket-connection.md | d22be650c3cb9be6 | 86301 |
| https://docs.kalshi.com/websockets/connection-keep-alive.md | 03b3b4e9e1f446cf | 5329 |
| https://docs.kalshi.com/websockets/orderbook-updates.md | d3c138b713d2463a | 19024 |
| https://docs.kalshi.com/websockets/market-ticker.md | 1af765091fcdfc0b | 12049 |
| https://docs.kalshi.com/websockets/cfbenchmarks-value.md | 4c61a8f08fd896e7 | 25714 |
| https://docs.kalshi.com/websockets/cfbenchmarks-value-5hz.md | d1eefda0dac7fcc0 | 17427 |
| https://docs.kalshi.com/websockets/pyth-value.md | 70c0e8062402b316 | 26244 |
| https://docs.kalshi.com/websockets/public-trades.md | 1ec7c692014483c2 | 10529 |
| https://docs.kalshi.com/websockets/market-and-event-lifecycle.md | be79b2ba6119f2a9 | 41974 |
| https://docs.kalshi.com/fix/market-data.md | 0d10eed9d9acfc6b | 7546 |
| https://docs.kalshi.com/changelog/index.md | 8fabf2e1ee1e2234 | 230478 |
| https://docs.kalshi.com/openapi.yaml | a33d05aaa5deab31 | 375273 |
| https://docs.kalshi.com/asyncapi.yaml | 3c86bae7d89b44ba | 168120 |

Relevant pages that are listed in `https://docs.kalshi.com/llms.txt` but were **not** downloaded, and so were not reviewed: `getting_started/making_your_first_request`, `getting_started/subaccounts`, `getting_started/targets_and_milestones`, `getting_started/rfqs`, `websockets/user-fills`, `websockets/user-orders`, `websockets/market-positions`, `websockets/multivariate-market-and-event-lifecycle`, `fix/connectivity`, `fix/authentication`, `fix/common-components`, `fix/market-settlement`, `fix/error-handling`, `fix/subpenny-pricing`, `api-reference/market/get-multiple-market-orderbooks`, `api-reference/market/batch-get-market-candlesticks`, and `api-reference/events/get-event-candlesticks`. The specs for those endpoints and channels inside `openapi.yaml`/`asyncapi.yaml` were reviewed.

---

## 1. Environments, hosts, demo

| Fact | Status | Source | Quote / paraphrase |
| - | - | - | - |
| Production REST base, recommended: `https://external-api.kalshi.com/trade-api/v2`. Also supported: `https://api.elections.kalshi.com/trade-api/v2` | VERIFIED | https://docs.kalshi.com/getting_started/api_environments.md | Table "Production \| `https://external-api.kalshi.com/trade-api/v2` \| `https://api.elections.kalshi.com/trade-api/v2`" |
| Demo REST base, recommended: `https://external-api.demo.kalshi.co/trade-api/v2`. Also supported: `https://demo-api.kalshi.co/trade-api/v2` | VERIFIED | same; also https://docs.kalshi.com/getting_started/demo_env.md | Table rows "Demo ..." |
| Production WS: `wss://external-api-ws.kalshi.com/trade-api/ws/v2`. Also supported: `wss://api.elections.kalshi.com/trade-api/ws/v2` | VERIFIED | https://docs.kalshi.com/getting_started/api_environments.md ; https://docs.kalshi.com/websockets.md | WebSocket table |
| Demo WS: `wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2`. Also supported: `wss://demo-api.kalshi.co/trade-api/ws/v2` | VERIFIED | same | same |
| The `elections` host serves all markets | VERIFIED | https://docs.kalshi.com/getting_started/api_environments.md | "Despite the `elections` subdomain, the production Trade API provides access to all Kalshi markets" |
| Credentials are not shared between prod and demo | VERIFIED | https://docs.kalshi.com/getting_started/api_environments.md ; https://docs.kalshi.com/getting_started/demo_env.md | "demo API keys only work against demo endpoints and production API keys only work against production endpoints" |
| Demo uses mock funds | VERIFIED | https://docs.kalshi.com/getting_started/demo_env.md | "a *demo* environment with mock funds" |
| **Demo fidelity warning** | VERIFIED | https://docs.kalshi.com/getting_started/demo_env.md | "The price and behavior of markets in the demo environment may not be reflective of those in real markets." |
| The signature payload does not depend on host. Sign the path from the API root without the query string | VERIFIED | https://docs.kalshi.com/getting_started/api_environments.md | "The host does not change the signature payload. Sign the full request path from the API root, without query parameters." |
| AWS PrivateLink is available for production hosts at Premier tier or above. VPC peering for WS at Prime or above | VERIFIED | https://docs.kalshi.com/getting_started/api_environments.md | "Members on the Premier tier or above can contact institutional@kalshi.com to provision PrivateLink endpoints" |
| Whether demo lists the same series (for example KXBTC15M), the CF Benchmarks channels, or Pyth | UNRESOLVED | (silent) | No doc states which series or channels exist in demo. The `asyncapi.yaml` `servers` block lists only `production`. |
| Whether demo rate limits, tiers, and WS limits match production | UNRESOLVED | (silent) | — |
| Demo account setup is documented on help.kalshi.com, not on docs.kalshi.com | VERIFIED (pointer only) | https://docs.kalshi.com/getting_started/demo_env.md | Links to `https://help.kalshi.com/en/articles/13823775-creating-and-using-a-demo-account` |
| The changelog includes entries dated **after** retrieval, for example "October 22, 2026" (Margin funding) | VERIFIED | https://docs.kalshi.com/changelog/index.md | Entry label "October 22, 2026" appears above Oct 15 entries. The changelog therefore mixes announced and effective dates. |

---

## 2. Authentication, keys, scopes, channel access

| Fact | Status | Source | Quote / paraphrase |
| - | - | - | - |
| Key types: Ed25519 (recommended) and RSA-2048 (RSA-PSS SHA-256, MGF1 SHA-256, salt = digest length) | VERIFIED | https://docs.kalshi.com/getting_started/api_keys.md | Key types table; "RSA keys use RSA-PSS with SHA-256 (MGF1 with SHA-256, salt length equal to the digest length)" |
| Headers are `KALSHI-ACCESS-KEY` (key ID), `KALSHI-ACCESS-TIMESTAMP` (ms), and `KALSHI-ACCESS-SIGNATURE` (base64 of sign(timestamp + METHOD + path-without-query)) | VERIFIED | https://docs.kalshi.com/getting_started/api_keys.md | "The signature is the base64 encoding of the signed concatenation of the timestamp, the HTTP method and the path." |
| The PEM header does not identify the key type. Determine the type from the parsed key | VERIFIED | https://docs.kalshi.com/getting_started/api_keys.md | "The PEM header does not identify the key type" |
| `POST /api_keys/generate` defaults to `rsa` when `key_type` is omitted. The web UI defaults to Ed25519 | VERIFIED | https://docs.kalshi.com/getting_started/api_keys.md ; changelog "October 1, 2026" | "returns a new key pair of the requested `key_type` (`rsa` when omitted)" |
| Kalshi-generated private keys are not stored by Kalshi and cannot be retrieved later. Registering your own public key is supported | VERIFIED | https://docs.kalshi.com/getting_started/api_keys.md | "the private key will not be stored by our service" |
| Allowed clock skew or acceptance window for `KALSHI-ACCESS-TIMESTAMP`; replay protection; nonce | UNRESOLVED | (silent) | No tolerance is documented. This matters for the clock-sync fail-closed threshold. |
| **REST market-data endpoints need no auth.** In `openapi.yaml` there is no global `security`, and these operations declare none: `GET /markets`, `/markets/{ticker}`, `/markets/{ticker}/orderbook`, `/markets/orderbooks`, `/markets/trades`, `/markets/candlesticks`, `/series`, `/series/{t}`, `/series/{s}/markets/{t}/candlesticks`, `/series/{s}/events/{t}/candlesticks`, `/events`, `/events/{t}`, `/events/{t}/metadata`, `/events/multivariate`, `/series/fee_changes`, `/events/fee_changes`, `/exchange/status`, `/exchange/schedule`, `/account/endpoint_costs`, `/live_data/events/{event_ticker}`, `/historical/cutoff`, `/historical/markets`, `/historical/markets/{t}`, `/historical/markets/{t}/candlesticks`, `/historical/trades` | VERIFIED | https://docs.kalshi.com/openapi.yaml (paths; no `security` key on these operations; rendered pages show `security: []`, e.g. https://docs.kalshi.com/api-reference/exchange/get-user-data-timestamp.md) | Also https://docs.kalshi.com/getting_started/orderbook_responses.md: "No authentication is required for this endpoint." Also https://docs.kalshi.com/getting_started/quick_start_market_data.md: "No authentication headers are required for the endpoints in this guide." |
| Authenticated (has `security`): `/historical/fills`, `/historical/orders`, `/historical/positions`, `/account/limits`, the forecast-percentile history endpoint, and all portfolio, order, and api_keys endpoints | VERIFIED | https://docs.kalshi.com/openapi.yaml | `security:` present on those operations |
| Some public endpoints list `401` responses even though they declare no security (`/markets`, `/markets/{ticker}/orderbook`, `/events`) | VERIFIED (oddity) | https://docs.kalshi.com/openapi.yaml#/paths/~1markets~1{ticker}~1orderbook | `'401': $ref UnauthorizedError`. When a 401 can occur on an unauthenticated read is UNRESOLVED. |
| CF Benchmarks REST passthrough `GET /trade-api/v2/cfbenchmarks/*` **requires auth and an entitlement** | VERIFIED | https://docs.kalshi.com/cfbenchmarks/rest-passthrough.md | "The passthrough requires an authenticated Kalshi Trade API request, and it is available only to accounts with the appropriate entitlement." The endpoint is not in `openapi.yaml`. |
| **WebSocket handshake always requires auth**, including for public channels | VERIFIED | https://docs.kalshi.com/websockets/websocket-connection.md ; https://docs.kalshi.com/getting_started/quick_start_websockets.md | "Authentication is required to establish the connection ... Some channels carry only public market data, but the connection itself still requires authentication." WS signing: `timestamp + "GET" + "/trade-api/ws/v2"`. |
| Channels classed as **private** in the quick start: `orderbook_delta`, `fill`, `market_positions`, `communications`, `order_group_updates`. **Public** (no channel-level auth beyond the session): `ticker`, `trade`, `market_lifecycle_v2`, `multivariate_market_lifecycle`, `multivariate` | VERIFIED | https://docs.kalshi.com/getting_started/quick_start_websockets.md | "Private channels (user-specific data): `orderbook_delta`, ..." |
| The `multivariate` channel named in the quick start is not in the AsyncAPI channel enum. Changelog "Aug 6, 2026", "Multivariate lookup endpoint and channel removed", suggests it no longer exists | CONFLICT (stale page) | https://docs.kalshi.com/getting_started/quick_start_websockets.md vs https://docs.kalshi.com/asyncapi.yaml#/components/schemas/subscribeCommandPayload | Enum: `orderbook_delta, ticker, trade, fill, market_positions, market_lifecycle_v2, multivariate_market_lifecycle, communications, order_group_updates, user_orders, cfbenchmarks_value, cfbenchmarks_value_5hz, pyth_value` |
| AsyncAPI marks `orderbook_delta`, `cfbenchmarks_value`, `cfbenchmarks_value_5hz`, and `pyth_value` "Authentication required". `ticker`, `trade`, and `market_lifecycle_v2` need "No additional channel-level authentication" | VERIFIED | https://docs.kalshi.com/asyncapi.yaml#/channels | Channel descriptions |
| Subaccount-restricted keys still receive the **full book** on `orderbook_delta`; only the own-order annotation (`client_order_id`, `subaccount`) is withheld for sibling subaccounts. Access with a read-only key is unverified (U12) (corrected per Red-Team C1) | VERIFIED (restricted keys only) | changelog "July 23, 2026" ("Subaccount-restricted API keys can open WebSocket sessions") | "`orderbook_delta` still delivers the full book; only the own-order annotation (`subaccount`, `client_order_id`) is withheld" |
| Whether `cfbenchmarks_value(_5hz)` WS needs an entitlement beyond auth (the REST passthrough does) | UNRESOLVED | https://docs.kalshi.com/websockets/cfbenchmarks-value.md | Says only "Requires authentication". |
| `pyth_value` is paid: "$1,000/month, with the first seven days free" | VERIFIED | https://docs.kalshi.com/websockets/pyth-value.md | quoted |
| **API key scopes exist.** Enum: `read`, `write`, `read::block_trade_accept`, `read::portfolio_balance`, `write::trade`, `write::transfer`, `write::fcm_risk`, `write::block_trade_accept`. Parent `read` "grants all read endpoints". Default when unspecified is full access (`read`,`write`) | VERIFIED | https://docs.kalshi.com/openapi.yaml#/components/schemas/ApiKeyScope ; `#/components/schemas/CreateApiKeyRequest` ; changelog "Dec 18, 2025" ("Read-Only API Keys") | "Valid scopes are `read` and `write`. Keys default to full access if not specified." |
| **No market-data-only scope exists.** A `read`-scoped key can also read portfolio, orders, fills, and positions | VERIFIED (by enum contents) / design implication | https://docs.kalshi.com/openapi.yaml#/components/schemas/ApiKeyScope | No `read::market_data` or similar in the enum |
| `read::mcp_portfolio` is an OAuth grant for registered MCP clients, not an API-key scope | VERIFIED | changelog "October 15, 2026" | "Registered MCP clients can read portfolio ... using explicitly granted `read::mcp_portfolio` OAuth access." Not in the `ApiKeyScope` enum. |
| A key can be restricted to one subaccount (0-63). Restricted keys may open WS sessions | VERIFIED | changelog "July 2, 2026" ("Sub-account-restricted API keys"); changelog "July 23, 2026" | "Pass `subaccount` (0-63) to `POST /api_keys`" ; "Subaccount-restricted API keys ... can now open WebSocket sessions." |
| Whether a `read`-only key (no `write`) can open the WS session and subscribe to `orderbook_delta`, `cfbenchmarks_value`, and so on | UNRESOLVED | (silent) | Probably yes, but not stated. Test in demo before relying on it. |
| Location attestation: `GET /api_keys` returns `api_key_region_expiration_ts`. After expiry, "API keys are not valid for trading Sports, Elections, and Entertainment markets" | VERIFIED | changelog "August 16, 2026" ; https://docs.kalshi.com/openapi.yaml#/components/schemas/GetApiKeysResponse | quoted. Whether attestation affects Crypto or Commodities, or reads, is UNRESOLVED. |
| Using the API binds the user to Kalshi's Developer Agreement (https://kalshi.com/developer-agreement) | VERIFIED (pointer only) | https://docs.kalshi.com/welcome/index.md | "By continuing to use or access Kalshi's API, you are agreeing to be bound to our Developer Agreement". The agreement's content is not on docs.kalshi.com. |

---

## 3. REST schemas

### 3.1 Series (`#/components/schemas/Series`), https://docs.kalshi.com/openapi.yaml

| Field | Status | Quote / paraphrase |
| - | - | - |
| Required: `ticker, frequency, title, category, categories, tags, settlement_sources, contract_url, contract_terms_url, fee_type, fee_multiplier, additional_prohibitions` | VERIFIED | `required:` list |
| `frequency` is free text | VERIFIED | "There is no fixed value set here, but will be something human-readable like weekly, daily, one-off." Do not key logic on it. |
| `settlement_sources[]` is `{name, url}`, nullable | VERIFIED | "SettlementSources specifies the official sources used for the determination of markets within the series. Methodology is defined in the rulebook." |
| `contract_url` | VERIFIED | "a direct link to the original filing of the contract which underlies the series." |
| `contract_terms_url` | VERIFIED | "the URL to the current terms of the contract underlying the series." |
| `fee_type` enum is `quadratic, quadratic_with_maker_fees, quadratic_with_combo_maker_fees, flat`. Formulas are external | VERIFIED | "Fee structures can be found at https://kalshi.com/docs/kalshi-fee-schedule.pdf. 'quadratic' is described by the General Trading Fees Table ..." |
| `fee_multiplier` is a double | VERIFIED | "a floating point multiplier applied to the fee calculations." |
| `additional_prohibitions[]` (nullable), `product_metadata` (internal, nullable), `volume_fp` (only with `include_volume=true`), `last_updated_ts` (date-time), `exchange_index` (int) | VERIFIED | schema; changelog "Jan 6, 2026", "July 30, 2026" |
| `GET /series` filters: `category` (exact, case-sensitive, matches `categories`), `tags`, `include_product_metadata`, `include_volume`, `min_updated_ts` (seconds) | VERIFIED | https://docs.kalshi.com/openapi.yaml#/paths/~1series |

### 3.2 Event (`#/components/schemas/EventData`)

| Field | Status | Quote / paraphrase |
| - | - | - |
| Required: `event_ticker, series_ticker, sub_title, title, collateral_return_type, mutually_exclusive, settlement_sources` | VERIFIED | schema |
| `collateral_return_type` is `MECNET`, `DIRECNET`, or `""`. `mutually_exclusive` is true only for MECNET | VERIFIED | "True when `collateral_return_type` is `MECNET`: at most one market in this event can resolve to 'yes'." |
| `strike_date` (date-time) and `strike_period` (string) are mutually exclusive | VERIFIED | "Only filled when the event uses a date strike (mutually exclusive with strike_period)." |
| `settlement_sources[]` on events (added June 2026) | VERIFIED | changelog "June 18, 2026" |
| `fee_type_override` and `fee_multiplier_override` (nullable). When present, they take precedence over the series fee | VERIFIED | "When present, takes precedence over the series-level fee for this event's markets." |
| `product_metadata.cadence`, for example `fifteen_min` | VERIFIED (changelog only) | changelog "July 30, 2026": "a `cadence` value inside `product_metadata` ... for example `fifteen_min`." The schema types `product_metadata` as a free object, so the cadence enum is UNRESOLVED. |
| `last_updated_ts` (date-time), `exchange_index` | VERIFIED | schema |
| `GET /events`: limit 1-200, default 200; `status` ∈ {unopened, open, closed, settled}, matched on **child** market status; excludes MVE events; old events are always available | VERIFIED | https://docs.kalshi.com/openapi.yaml#/paths/~1events ; https://docs.kalshi.com/getting_started/market_lifecycle.md FAQ |
| `GET /events/{t}?exclude_markets=true` returns metadata only | VERIFIED | changelog "October 15, 2026" |

### 3.3 Market (`#/components/schemas/Market`)

| Field / fact | Status | Quote / paraphrase |
| - | - | - |
| Required list includes `ticker, event_ticker, market_type, yes_sub_title, no_sub_title, created_time, updated_time, open_time, close_time, latest_expiration_time, settlement_timer_seconds, status, ..._dollars quotes, yes_bid_size_fp, yes_ask_size_fp, volume_fp, volume_24h_fp, open_interest_fp, result, can_close_early, expiration_value, rules_primary, rules_secondary, price_level_structure, price_ranges, settlement_bounds_type` | VERIFIED | schema |
| `market_type` ∈ {binary, scalar} | VERIFIED | enum |
| Time fields (all `format: date-time`): `created_time`, `updated_time` ("Time of the last non-trading metadata update."), `open_time`, `close_time`, `expected_expiration_time` (nullable), `expiration_time` (**deprecated**), `latest_expiration_time`, `settlement_ts` (nullable; "Only filled for settled markets"), `occurrence_datetime` (nullable; "when the underlying event occurred, if available"), `fee_waiver_expiration_time` (nullable) | VERIFIED | schema; https://docs.kalshi.com/getting_started/market_lifecycle.md "Time fields" table |
| `close_time` "May be moved earlier if `can_close_early` is true." `expected_expiration_time` can precede `close_time` | VERIFIED | https://docs.kalshi.com/getting_started/market_lifecycle.md |
| `expiration_time` is deprecated: "Prefer `latest_expiration_time` for the legacy expiry semantics; use `expected_expiration_time` if you want the forecasted time." | VERIFIED | https://docs.kalshi.com/getting_started/market_lifecycle.md |
| `status` enum: `initialized, inactive, active, closed, determined, disputed, amended, finalized` | VERIFIED | schema; changelog "Dec 16, 2025" |
| `result` enum: `'yes', 'no', 'scalar', ''` | VERIFIED | schema. **No `void`/`cancelled` value exists.** See §8. |
| `can_close_early` (bool, required); `early_close_condition` (nullable string, "The condition under which the market can close early") | VERIFIED | schema |
| Strike fields: `strike_type` ∈ {greater, greater_or_equal, less, less_or_equal, between, functional, custom, structured}; `floor_strike` ("Minimum expiration value that leads to a YES settlement"); `cap_strike` ("Maximum expiration value ..."); `functional_strike`; `custom_strike` | VERIFIED | schema |
| Strict vs non-strict inequality at the strike for `greater` vs `greater_or_equal` (tie handling at the boundary) | UNRESOLVED | The enum names imply it, but no definition is given. The contract terms govern. |
| `rules_primary` ("most important market terms") and `rules_secondary` (plain-language) | VERIFIED | schema. These are summaries. The legally governing terms are behind `contract_terms_url` and the rulebook. |
| `expiration_value`: "The value that was considered for the settlement" (string) | VERIFIED | schema. Format and units per series are UNRESOLVED. |
| `settlement_value_dollars` (nullable): "The settlement value of the YES/LONG side ... Only filled after determination" | VERIFIED | schema |
| `settlement_timer_seconds`: "The amount of time after determination that the market settles" | VERIFIED | schema |
| `settlement_bounds_type` ∈ {default, floor}; `settlement_floor_dollars`. Floors are "not live yet" | VERIFIED | schema; https://docs.kalshi.com/getting_started/settlement_bounds.md "Settlement floors are not live yet. The launch timeline is TBA." |
| `price_level_structure` (label) and `price_ranges[] {start,end,step}`. `price_ranges` is the **source of truth** for the price grid | VERIFIED | https://docs.kalshi.com/getting_started/fixed_point_migration.md "This is the source of truth for valid prices ... Do not key pricing logic off this name" |
| `tick_size` removed (May 7, 2026). Cent fields removed (Jan 15 / Mar 12, 2026). `liquidity_dollars` removed (Oct 1, 2026). `response_price_units` and `fractional_trading_enabled` removed (July 9, 2026) | VERIFIED | changelog "Apr 30, 2026", "Jan 6, 2026", "Mar 8, 2026", "October 1, 2026", "July 9, 2026" |
| `is_provisional`: "the market may be removed after determination if there is no activity on it" | VERIFIED | schema; changelog "Jan 9, 2026" ("will be removed from the API if it has no activity by settlement time"). Provenance risk: a market can disappear from the API. |
| `exchange_index`: "The `exchange_index` field is the authoritative source of truth" for the shard | VERIFIED | https://docs.kalshi.com/getting_started/exchange_sharding.md |
| Quote fields `yes_bid_dollars`, `yes_ask_dollars`, `no_bid_dollars`, `no_ask_dollars`, `last_price_dollars`, `previous_*_dollars` (a day ago), `yes_bid_size_fp`, `yes_ask_size_fp` | VERIFIED | schema |
| `GET /markets` status filter values `unopened, open, paused, closed, settled`, one at a time. Timestamp filter groups are mutually exclusive (table). `min_updated_ts`/`max_updated_ts` "Tracks non-trading changes only" | VERIFIED | https://docs.kalshi.com/openapi.yaml#/paths/~1markets ; `#/components/parameters/MinUpdatedTsQuery` |
| `GET /markets/{ticker}` may 404 right after a `created` event; "Retry with backoff" | VERIFIED | https://docs.kalshi.com/getting_started/market_lifecycle.md FAQ |
| Do not parse tickers to infer relationships | VERIFIED | https://docs.kalshi.com/getting_started/terms.md "There are occasional exceptions, so do not parse ticker strings to infer relationships." |

### 3.4 Orderbook (REST)

| Fact | Status | Source | Quote / paraphrase |
| - | - | - | - |
| `GET /markets/{ticker}/orderbook` returns `{orderbook_fp:{yes_dollars:[[price,count]...], no_dollars:[...]}}`. Strings. Bids only | VERIFIED | https://docs.kalshi.com/getting_started/orderbook_responses.md ; https://docs.kalshi.com/openapi.yaml#/components/schemas/OrderbookCountFp | "Each bid is a two-element string array: `[price_dollars, count_fp]`." |
| `no_dollars` levels are priced in **NO-leg** terms. A NO bid at Y equals a YES ask at 1 − Y | VERIFIED | https://docs.kalshi.com/getting_started/orderbook_responses.md | "A **NO BID** at price Y is equivalent to a **YES ASK** at price ($1.00 - Y)" |
| Sort order: ascending; best bid is the **last** element | VERIFIED (guide) / **CONFLICT** | https://docs.kalshi.com/getting_started/orderbook_responses.md vs https://docs.kalshi.com/api-reference/market/get-market-orderbook.md | The guide says "Arrays are sorted by price in **ascending order** ... The **highest** bid (best bid) is the **last** element". The endpoint description says "Each side shows price levels with their corresponding quantities and order counts, organized from best to worst prices." The schema also has **no order counts**. Parse by price; never by position. |
| `depth` query: "0 or negative means all levels, 1-100 for specific depth" (schema min 0, max 100) | VERIFIED | https://docs.kalshi.com/openapi.yaml#/paths/~1markets~1{ticker}~1orderbook | — |
| `GET /markets/orderbooks?tickers=` takes up to 100 tickers | VERIFIED | same, `/markets/orderbooks` ; changelog "Mar 30, 2026" | — |
| **The REST orderbook response has no timestamp and no sequence number** | VERIFIED (by schema) | `#/components/schemas/GetMarketOrderbookResponse`, `MarketOrderbookFp` | Only `orderbook_fp` (and `ticker` in the batch call). A REST snapshot cannot be aligned with the WS delta stream, so it cannot seed a WS book. |

### 3.5 Trade (REST) (`#/components/schemas/Trade`)

| Fact | Status | Quote / paraphrase |
| - | - | - |
| Required: `trade_id, ticker, count_fp, yes_price_dollars, no_price_dollars, taker_outcome_side, taker_book_side, created_time, is_block_trade` | VERIFIED | schema |
| `trade_id` "Unique identifier for this trade". REST does not declare it a UUID. The WS `trade_id` is `format: uuid` | VERIFIED | schema; https://docs.kalshi.com/asyncapi.yaml#/components/schemas/tradePayload |
| `created_time` date-time: "Timestamp when this trade was executed". Sub-second precision is not stated | VERIFIED / precision UNRESOLVED | schema |
| `taker_outcome_side` ∈ {yes,no}. `taker_book_side` ∈ {bid,ask}, where bid ≡ yes and ask ≡ no. Direction does not change price | VERIFIED | https://docs.kalshi.com/getting_started/order_direction.md |
| `taker_side` is deprecated. Removal date **CONFLICT**: "will not be removed before May 14, 2026" (OpenAPI/AsyncAPI) vs "will not be removed before May 28, 2026" (guide and changelog). Both dates have passed, and the WS trade schema still lists it as required | CONFLICT | https://docs.kalshi.com/openapi.yaml#/components/schemas/Trade ; https://docs.kalshi.com/getting_started/order_direction.md |
| `is_block_trade`: off-book block trade. Included by default; filter with `is_block_trade` | VERIFIED | schema; changelog "May 29, 2026" |
| `GET /markets/trades`: `limit` 1-1000 (default 100), `cursor`, `ticker`, `min_ts`, `max_ts`, `is_block_trade` | VERIFIED | https://docs.kalshi.com/openapi.yaml#/paths/~1markets~1trades |
| `min_ts`/`max_ts` units and inclusivity ("Filter items after/before this Unix timestamp"); result ordering (newest-first?) | UNRESOLVED | `#/components/parameters/MinTsQuery`. Units are presumably seconds but not stated. Ordering is not stated. |
| REST trades carry no `market_id` and no sequence number | VERIFIED (by schema) | — |

### 3.6 Candlesticks

| Fact | Status | Source | Quote |
| - | - | - | - |
| `GET /series/{series}/markets/{ticker}/candlesticks`: `period_interval` ∈ {1, 60, 1440} minutes. **Minimum granularity is 1 minute** | VERIFIED | https://docs.kalshi.com/openapi.yaml#/paths/~1series~1{series_ticker}~1markets~1{ticker}~1candlesticks | "Valid values are 1 (1 minute), 60 (1 hour), or 1440 (1 day)." |
| `start_ts`/`end_ts`: "Candlesticks will include those ending on or after/before this time" | VERIFIED | same | — |
| `include_latest_before_start` prepends a synthetic candle with OHLC null and `previous_price` set | VERIFIED | same | — |
| Batch `GET /markets/candlesticks`: up to 100 tickers and 10,000 candles total. `period_interval` here is only `minimum: 1` with no enum | VERIFIED / minor inconsistency | https://docs.kalshi.com/openapi.yaml#/paths/~1markets~1candlesticks | Whether other intervals are accepted is UNRESOLVED. |
| Event candlesticks `GET /series/{s}/events/{t}/candlesticks` take {1,60,1440}. `adjusted_end_ts` handles pagination (5,000-candle cap per changelog) | VERIFIED | openapi path; changelog "Sep 15, 2025" | — |
| Candle schema: `end_period_ts` ("inclusive end"), `yes_bid`/`yes_ask` OHLC (`open_dollars`...), `price` OHLC + `mean_dollars`, `previous_dollars`, `min_dollars`, `max_dollars` (nullable when no trade), `volume_fp`, `open_interest_fp` | VERIFIED | `#/components/schemas/MarketCandlestick` | — |
| **Historical candle schema differs**: `volume`/`open_interest` (not `_fp`); `open/low/high/close/mean/previous` (no `_dollars` suffix); `mean` = "Volume-weighted average price" | VERIFIED | `#/components/schemas/MarketCandlestickHistorical`, `PriceDistributionHistorical` | Separate parsers are needed. The live `mean_dollars` is described only as "Mean traded YES contract price", so whether live and historical means agree is UNRESOLVED. |
| How `yes_bid`/`yes_ask` OHLC are sampled (every BBO change? periodic snapshots?) | UNRESOLVED | — | — |

### 3.7 Pagination

| Fact | Status | Source | Quote |
| - | - | - | - |
| Cursor-based. Pass `cursor` from the previous response | VERIFIED | https://docs.kalshi.com/getting_started/pagination.md | — |
| End-of-pages signal: the guide says "Continue until the cursor is `null`". The spec says "Empty if there are no more results" | CONFLICT (minor) | same vs https://docs.kalshi.com/openapi.yaml#/components/schemas/GetEventsResponse | Treat both null and "" as terminal. |
| Limits: the guide says "typically 1-100, default: 100". The spec says markets/trades max 1000 and events max 200 (default 200) | CONFLICT (minor) | same vs `#/components/parameters/MarketLimitQuery` | — |
| "Data can change between requests". Pages are not a snapshot | VERIFIED | https://docs.kalshi.com/getting_started/pagination.md | — |

### 3.8 Fee-change endpoints

| Fact | Status | Source | Quote |
| - | - | - | - |
| `GET /series/fee_changes?series_ticker=&show_historical=` → `series_fee_change_arr[] {id, series_ticker, fee_type, fee_multiplier, scheduled_ts(date-time)}` | VERIFIED | https://docs.kalshi.com/openapi.yaml#/components/schemas/SeriesFeeChange ; changelog "Sep 21, 2025": "If ... show_historical is set to true, ALL fee changes previous and upcoming will be shown. If set to false, only upcoming" | — |
| `GET /events/fee_changes?event_ticker=&limit=&cursor=` → `event_fee_changes[] {id, event_ticker, series_ticker, fee_type_override, fee_multiplier_override, scheduled_ts}`. A null override means cleared, with fallback to the series | VERIFIED | https://docs.kalshi.com/openapi.yaml#/components/schemas/EventFeeChange | "When null, the event clears any prior override and falls back to the parent series' fee structure." |
| Whether `/events/fee_changes` returns past (historical) changes or only upcoming ones (it has no `show_historical` param) | UNRESOLVED | — | — |
| WS `event_fee_update` on `market_lifecycle_v2` carries `event_ticker, fee_type_override, fee_multiplier_override` and **no effective/scheduled timestamp** | VERIFIED | https://docs.kalshi.com/asyncapi.yaml#/components/schemas/eventFeeUpdatePayload | Whether it is emitted when the override is *scheduled* or when it *takes effect* is UNRESOLVED ("emitted when an event-level fee override is set or cleared"). |
| WS fee enum includes `margin_market_maker_program_fees`. The OpenAPI `FeeType` enum does not | CONFLICT (minor) | asyncapi `eventFeeUpdatePayload` vs openapi `FeeType` | — |
| Fee formulas, rates, and maker/taker schedule | UNRESOLVED on docs.kalshi.com | — | They point to https://kalshi.com/docs/kalshi-fee-schedule.pdf. Rounding mechanics are documented at https://docs.kalshi.com/getting_started/fee_rounding.md (trade fee ceil to $0.000001; rounding fee; per-order accumulator rebate). |

---

## 4. WebSocket

### 4.1 Commands and session

| Fact | Status | Source | Quote / paraphrase |
| - | - | - | - |
| Commands: `subscribe`, `unsubscribe` (`sids`), `update_subscription` (`sid` or one-element `sids`; actions `add_markets`, `delete_markets`, `get_snapshot`; CFB actions `subscribe_indices`/`unsubscribe_indices`/`indexlist`; Pyth actions `subscribe_underlyings`/`unsubscribe_underlyings`/`underlying_list`), `list_subscriptions` | VERIFIED | https://docs.kalshi.com/asyncapi.yaml#/components/schemas | payload schemas |
| Client `id` "should be unique within a WS session". `id: 0` is treated as no id | VERIFIED | `#/components/schemas/commandId` | — |
| `market_ticker` and `market_tickers` are mutually exclusive. `market_id`/`market_ids` (UUID) are supported on some channels; `orderbook_delta` does not support them | VERIFIED | `subscribeCommandPayload`; `#/channels/orderbook_delta` | "`market_id`/`market_ids` are not supported for this channel" |
| Subscribing again is idempotent and **adds** new tickers to the existing subscription | VERIFIED (2025 changelog) | changelog "Sep 25, 2025" | "If passing new market tickers, they will be added to your existing subscription." How this interacts with sid/seq and whether new markets get snapshots is UNRESOLVED. |
| Acknowledgement precedes data | VERIFIED | changelog "September 17, 2026" ("WebSocket subscriptions are ready when acknowledged") | "Fixed a race that could skip events arriving immediately after a `subscribed` response ... The acknowledgement continues to precede subscription data." The fix dates from Sept 2026, so earlier captures may have had skipped events. |
| `market_lifecycle_v2` does not support `market_ticker` filters, yet an AsyncAPI example subscribes `["orderbook_delta","ticker","trade","market_lifecycle_v2"]` with `market_ticker` | CONFLICT | `#/channels/market_lifecycle_v2` vs example `subscribeAllChannelsOneMarket` | Whether the filter is ignored or rejected is UNRESOLVED. |
| Optional RFC 7692 `permessage-deflate`; **64 MiB message limit** | VERIFIED | changelog "September 24, 2026" ("Optional WebSocket compression") | "Message formats and the 64 MiB message limit are unchanged." |

### 4.2 Channel message schemas (market-data relevant)

| Channel / msg type | Fields (required unless noted) | Status | Source |
| - | - | - | - |
| `orderbook_snapshot` | `type, sid, seq, msg{market_ticker, market_id, yes_dollars_fp?, no_dollars_fp?}`; `id` present when replying to `get_snapshot`; `sending_ts_ms` | VERIFIED | https://docs.kalshi.com/asyncapi.yaml#/components/schemas/orderbookSnapshotPayload. "Optional - This key will not exist if there are no Yes offers". **Note:** the WS field names are `yes_dollars_fp`/`no_dollars_fp`, which differ from REST `yes_dollars`/`no_dollars`. The WS level sort order is **not stated** (UNRESOLVED). **The snapshot has no timestamp of its own** apart from `sending_ts_ms`. |
| `orderbook_delta` | `type, sid, seq, msg{market_ticker, market_id, price_dollars, delta_fp, side(yes\|no)}`; optional `client_order_id`, `subaccount`, `ts` (deprecated, RFC3339 string truncated to ms), `ts_ms` (optional, int ms); `sending_ts_ms` | VERIFIED | `#/components/schemas/orderbookDeltaPayload` |
| `ticker` | `type, sid, msg{market_id, market_ticker, price_dollars, yes_bid_dollars, yes_ask_dollars, volume_fp, open_interest_fp, dollar_volume, dollar_open_interest, yes_bid_size_fp, yes_ask_size_fp, last_trade_size_fp, ts(sec, deprecated), ts_ms, time(RFC3339, deprecated)}` and **no `seq`** | VERIFIED | `#/components/schemas/tickerPayload` (`required: ["type","sid","msg"]`). Changelog "September 10, 2026" lists the sequenced channels and omits ticker. Ticker gaps **cannot be detected**. |
| `trade` | `type, sid, seq, msg{trade_id(uuid), market_ticker, yes_price_dollars, no_price_dollars, count_fp, taker_side(deprecated), taker_outcome_side, taker_book_side, is_block_trade, ts(sec, deprecated), ts_ms}` | VERIFIED | `#/components/schemas/tradePayload`. No `market_id`. |
| `market_lifecycle_v2` | `type, sid, seq, msg{market_ticker, event_type, ...optional}`. `event_type` ∈ {created, deactivated, activated, close_date_updated, determined, settled, price_level_structure_updated}. Optional fields: `exchange_index`, `open_ts`, `close_ts`, `determination_ts`, `settled_ts` (all **seconds**), `result`, `settlement_value` (fixed-point $), `is_deactivated`, `additional_metadata{name,title,yes_sub_title,no_sub_title,rules_primary,rules_secondary,can_close_early,event_ticker,expected_expiration_ts, strike_type?, floor_strike?, cap_strike?, custom_strike?}`, `price_level_structure`, `price_ranges` | VERIFIED | `#/components/schemas/marketLifecycleV2Payload`, `lifecycleAdditionalMetadata` |
| `market_lifecycle_v2` `metadata_updated` (a separate message schema with the same `type`) | `msg{event_type:"metadata_updated", market_ticker, strike_type?, floor_strike?, cap_strike?, custom_strike?, yes_sub_title?}` | VERIFIED | `#/components/schemas/marketMetadataUpdatedPayload`; changelog "June 18, 2026": emitted when floor_strike, cap_strike, strike_type, or yes_sub_title change |
| `event_lifecycle` (on `market_lifecycle_v2` and `multivariate_market_lifecycle`) | `msg{event_ticker, exchange_index, title, subtitle, collateral_return_type, series_ticker, strike_date?(int), strike_period?}` | VERIFIED | `#/components/schemas/eventLifecyclePayload`. Emitted "when new events are created". The unit of `strike_date` is "Unix timestamp", seconds presumably (UNRESOLVED). |
| `event_fee_update` | see §3.8 | VERIFIED | — |
| Lifecycle messages carry **no event-time field** apart from the type-specific `*_ts` seconds fields and `sending_ts_ms` | VERIFIED (by schema) | above | Ordering and latency of lifecycle events relative to book/trade data are unknowable from the payload. |
| `price_level_structure` enum (WS) includes `"banded_centi_cent"` and `""` ("An empty string represents an unknown structure"), neither of which appears in the fixed-point guide | VERIFIED / gap | `#/components/schemas/lifecyclePriceLevelStructure` vs https://docs.kalshi.com/getting_started/fixed_point_migration.md | The grid for `banded_centi_cent` is undocumented. Always use `price_ranges`. |
| Lifecycle prose vs schema mismatch: the guide's v2 event list includes `metadata_updated` and omits `price_level_structure_updated`. The schema enum is the reverse, with `metadata_updated` modeled as a separate message | CONFLICT (documentation) | https://docs.kalshi.com/getting_started/market_lifecycle.md vs asyncapi | Accept the union of both lists; reject anything else, fail-closed. |
| `fractional_trading_updated` was removed (Apr 2026) | VERIFIED | changelog "Apr 17, 2026" | — |
| MVE (`KXMVE*`) markets are excluded from `market_lifecycle_v2` | VERIFIED | https://docs.kalshi.com/getting_started/market_lifecycle.md ; changelog "Feb 12, 2026" | — |

### 4.3 `sid` / `seq` semantics (exact quotes)

| Fact | Status | Source | Quote |
| - | - | - | - |
| `sid` | VERIFIED | `#/components/schemas/subscriptionId` | "Server-generated subscription identifier (sid) used to identify the channel" (min 1) |
| `seq` | VERIFIED | `#/components/schemas/sequenceNumber` | "Sequential number that should be checked if you want to guarantee you received all the messages. Used for snapshot/delta consistency" (minimum: 1) |
| Sequenced message types: `orderbook_snapshot`, `orderbook_delta`, `trade`, `market_lifecycle_v2` (incl. metadata/event/fee messages), `multivariate_market_lifecycle`, `cfbenchmarks_value`, `cfbenchmarks_value_5hz`, `pyth_value`, the indexlist/underlying_list replies, `unsubscribed`, `ok` (update; `seq` is **optional** on `ok`, required on `unsubscribed`), and subscription-scoped `error` (carries `sid` and `seq` per changelog 2026-09-10). Note: Kalshi stated the AsyncAPI described some messages inaccurately until the 2026-09-10/17 corrections. **Not sequenced:** `ticker`, `subscribed`, `list_subscriptions` | VERIFIED (by schema `required`/properties) | asyncapi payload schemas; changelog "September 10, 2026": "`seq` is documented on the Predictions trade, market lifecycle ... These channels have always been sequenced." "`sid` and `seq` are documented on error messages scoped to a subscription." |
| **Seq scope: per subscription (sid), per market, or per connection** | **UNRESOLVED** | — | No doc states the scope. INFERENCE: per `sid`, because every sequenced payload carries `sid`, and `unsubscribed` and `ok` carry `sid`+`seq`. Not verified. Specifically unknown: whether a multi-market `orderbook_delta` sid has one shared counter across markets; whether `ok`/`error`/`get_snapshot` replies **consume** sequence numbers in the same counter (their schemas include `seq`, so a gap detector that ignores them may report false gaps); the start value; and whether the counter resets on a new sid. |
| Whether `seq` restarts on resubscribe | UNRESOLVED | — | INFERENCE: a new subscribe gets a new `sid`, and so a new sequence. Not stated. |
| Documented gap / resync / reconnect procedure | UNRESOLVED (not documented) | — | Docs say only "check seq", and give generic "Implement reconnection logic with exponential backoff" plus "Cache initial orderbook state before applying updates" (https://docs.kalshi.com/getting_started/quick_start_websockets.md). No doc tells the client to call `get_snapshot` on a gap, how a get_snapshot reply is ordered relative to deltas in flight, or whether the server resends. |
| `get_snapshot`: "returns an `orderbook_snapshot` for the requested `market_tickers` without modifying the subscription". Only `market_tickers` is accepted | VERIFIED | `#/channels/orderbook_delta`; changelog "Apr 20, 2026": "Only `market_tickers` is supported (not `market_ticker`, `market_id`, or `market_ids`)." "...without adding them to the subscription or affecting the existing delta stream." |
| A get_snapshot reply is carried on the sid's sequence | INFERENCE | `orderbookSnapshotPayload` requires `sid`,`seq` and has optional `id` "Present when replying to a get_snapshot command" | Not stated whether it is sequence-consistent with the deltas, which is needed to rebase. Test it. |
| Cross-channel ordering guarantees (for example trade vs delta vs ticker for the same match) | UNRESOLVED | — | None stated. |
| Duplicate delivery possible? | UNRESOLVED | — | Not stated. |
| Conflation or coalescing of deltas or ticker updates | UNRESOLVED | — | Not stated. Ticker: "Updates sent whenever any ticker field changes". Trade: "Updates sent immediately after trade execution". |

### 4.4 Delta semantics: relative or absolute?

| Fact | Status | Source | Quote / reasoning |
| - | - | - | - |
| `delta_fp` is described as "Fixed-point contract delta (2 decimals)" | VERIFIED | `#/components/schemas/orderbookDeltaPayload` | quoted |
| Message summary: "Update to be applied to the current order book view" | VERIFIED | `#/components/messages/orderbookDelta` | quoted |
| The documented example has a **negative** `delta_fp` (format illustration only) | VERIFIED (format) | https://docs.kalshi.com/websockets/orderbook-updates.md example | A negative value cannot be an absolute level size. |
| **delta_fp is a relative change (new_size = old_size + delta)** | **INFERENCE (strong)** | above | The docs never say "add" or "relative". No doc code applies deltas: `quick_start_websockets.md` only prints them, and `fixed_point_migration.md` has no delta code. Contrast FIX KalshiMD, which uses `MDUpdateAction` New/Change/Delete with `MDEntrySize` (https://docs.kalshi.com/fix/market-data.md), apparently absolute. Do not assume WS and FIX share semantics. |
| Behavior when a level reaches 0 (removed?) and whether a negative resulting size is possible | UNRESOLVED | — | Treat a negative result as an integrity failure. |
| Verification plan (corrected per Red-Team C6) | — | — | Do not use `get_snapshot` as ground truth, because its sequence consistency is itself unresolved (U4). Instead, run a differential test: two independent connections subscribe to the same markets at different times; for each, snapshot + Σ deltas must agree level-for-level at matching `seq`-aligned points. Also check invariants: no negative level, no crossed book, prices on the `price_ranges` grid. Demo results cannot close U1–U5 for production; production behaviour needs a recorded production test under an approved credential and collector. |

### 4.5 `use_yes_price` and side pricing

| Fact | Status | Source | Quote |
| - | - | - | - |
| Default (`use_yes_price` false): no-side deltas and snapshot levels use **no-leg pricing** | VERIFIED | https://docs.kalshi.com/getting_started/order_direction.md | "a no-side delta at `price_dollars=0.30` corresponds to a market offer of 'no at 30c', which would match against 'yes at 70c'." |
| `use_yes_price: true` gives no-side levels in yes-leg pricing; the yes side is unchanged | VERIFIED | same; `subscribeCommandPayload.use_yes_price` | "No-side deltas and snapshot levels are reported in **yes-leg pricing** instead of no-leg" |
| Migration: the default will flip to true and the flag will then be removed. "We will announce concrete dates" | VERIFIED; dates UNRESOLVED | same | No dates are announced in the changelog snapshot. The parser must record the `use_yes_price` value per subscription in raw metadata and set it **explicitly**. |
| Whether `get_snapshot` replies honor the subscription's `use_yes_price` | UNRESOLVED | — | — |

### 4.6 Errors

| Fact | Status | Source | Quote |
| - | - | - | - |
| Error format: `{id?, type:"error", sid?, seq?, msg{code, msg}, sending_ts_ms}` | VERIFIED | `#/components/schemas/errorResponsePayload` | — |
| Code list: 1-5, 7-15, 18-28. 6, 16, and 17 are retired. **25 = Subscription buffer overflow**, 26 = per-subscription market limit exceeded, 27 = command rate limit, 24 = Index IDs required, 28 = Underlying tickers required, 23 = Match IDs required | VERIFIED | `#/components/schemas/errorResponsePayload` code description and enum | — |
| **Terminal errors: 10 (Channel error) and 25 (buffer overflow). "The following channel errors are terminal and the user must resubscribe."** | VERIFIED | https://docs.kalshi.com/asyncapi.yaml `info.description` "Terminal Errors" | quoted |
| 25: "The subscription's event buffer overflowed during a message burst. Subscribe to a smaller subset of data, or ensure that your connection read throughput is optimized." | VERIFIED | https://docs.kalshi.com/getting_started/quick_start_websockets.md ; changelog "May 12, 2026" | quoted. Implication: a slow consumer loses the stream. The ingest reader must never block on processing. |
| The error tables disagree: the quick start lists 25 but not 23/24/26/27/28; the AsyncAPI `info` table omits 23/24/25 from its main table | CONFLICT (documentation completeness) | quick start vs asyncapi info vs errorResponsePayload | Use the `errorResponsePayload` enum as the authoritative list. Any unknown code is fail-closed. |
| Limits: "Max 500k market subscriptions per session. Max 10k/s commands per second enforced." | VERIFIED | changelog "June 18, 2026" | The per-subscription market limit (code 26) is not quantified (UNRESOLVED). |
| WS connections per user: "default limit begins at 200 and increases based on API usage tier" | VERIFIED (2025 changelog; may be stale) | changelog "Sep 18, 2025" | Current per-tier values are UNRESOLVED. |

### 4.7 Keep-alive

| Fact | Status | Source | Quote |
| - | - | - | - |
| Server sends Ping (0x9) every 10 s with body `heartbeat`. Clients should Pong. Clients may Ping | VERIFIED | https://docs.kalshi.com/websockets/connection-keep-alive.md | "Kalshi sends Ping frames (`0x9`) every 10 seconds with body `heartbeat` to maintain the connection." |
| Server disconnect policy on missed Pongs; idle timeout | UNRESOLVED | — | — |
| Data-level heartbeat on quiet markets | UNRESOLVED (none documented) | — | Book staleness on a quiet market cannot be told apart from feed stall using market data alone. Recommendation: use the 10 s ping as liveness, plus a separate active subscription (for example `cfbenchmarks_value` ~1 Hz) as a data-plane canary. |

---

## 5. Timestamps

| Field | Units / format | What it denotes | Status | Source |
| - | - | - | - | - |
| `sending_ts_ms` (WS messages) | int64 Unix ms | "when Kalshi queued this message at the network layer" | VERIFIED meaning; **optional in every schema** (never `required`), while the changelog says messages "now include" it: CONFLICT, so absence is flagged, not fatal | `#/components/schemas/sendingTimestampMs`; changelog label "October 1, 2026" (label date; effective date unverified) |
| `orderbook_delta.ts_ms` | int64 ms, **optional** | "Unix timestamp for when the orderbook change was recorded" | VERIFIED. That this is the matching-engine time is INFERENCE from changelog "May 5, 2026": `order_group_updates` `ts_ms` is the "matching engine's wall-clock timestamp ... matching the pattern already used by `trades`, `fill`, `user_orders`, and `orderbook_delta`". When `ts_ms` is absent is UNRESOLVED. | asyncapi `orderbookDeltaPayload` |
| `orderbook_delta.ts` | RFC3339 string, ms-truncated, deprecated | same | VERIFIED | same |
| `orderbook_snapshot` | — | **no event timestamp** | VERIFIED (absence) | `orderbookSnapshotPayload` |
| `ticker.ts_ms` / `ts` (s, deprecated) / `time` (RFC3339, deprecated) | ms / s / string | "when the update happened" | VERIFIED; whether this is exchange-event time is UNRESOLVED | `tickerPayload` |
| `trade.ts_ms` / `ts` (s, deprecated) | ms / s | "Unix timestamp in milliseconds" (no semantics). The changelog pattern implies matching engine (INFERENCE) | VERIFIED / INFERENCE | `tradePayload` |
| Lifecycle `open_ts, close_ts, determination_ts, settled_ts, expected_expiration_ts` | int64 **seconds** | as named; `close_ts` "Will be updated in case of early determination markets" | VERIFIED | `marketLifecycleV2Payload` |
| `cfbenchmarks_value.received_at` | int ms | "When Kalshi received the upstream frame" | VERIFIED | `cfbenchmarksValuePayload` |
| `cfbenchmarks_value` source time | inside raw `data` JSON string only | upstream frame (the raw example has a `time` key) | INFERENCE that `data.time` is the source timestamp used for averaging (the avg window is defined on `source_ts_ms`, which is not a parsed field on this channel) | same |
| `cfbenchmarks_value_5hz.source_ts_ms` / `received_at` | int ms | "Upstream publication timestamp of the tick" / Kalshi receipt | VERIFIED | `cfbenchmarksValue5HzPayload` |
| `pyth_value.source_ts_ms` / `received_at` | int ms | "Pyth source timestamp" / "When Kalshi received the Pyth update" | VERIFIED | `pythValuePayload` |
| CFB avg windows `window_start_ts_ms`, `window_end_ts_exclusive` | int ms | window bounds | VERIFIED; see §11 for the naming ambiguity | `cfbenchmarksAvgData` |
| REST `date-time` fields (`created_time`, `updated_time`, `open_time`, `close_time`, `settlement_ts`, `Trade.created_time`, cutoffs, `last_updated_ts`, `scheduled_ts`) | OpenAPI `format: date-time` | per field | VERIFIED format. **Timezone and precision UNRESOLVED**: no doc states UTC or sub-second precision. INFERENCE: RFC3339 with explicit offset. The parser must require an explicit offset and fail-closed otherwise. | openapi |
| REST query timestamps (`min_ts`, `max_ts`, `start_ts`, `end_ts`, `min_*_ts`) | "Unix timestamp". Some say "(in seconds)" | filter bounds | Partly VERIFIED: `min_updated_ts`, `min_close_ts` on events, and batch candles state seconds. Others UNRESOLVED. | openapi parameters |
| `end_period_ts` (candles) | int64 Unix | "inclusive end of the candlestick period" | VERIFIED (unit: seconds presumably) | `MarketCandlestick` |
| Exchange schedule `open_time`/`close_time` | "HH:MM" **ET** | trading sessions | VERIFIED: "All times are expressed in ET." DST handling is not stated. | `#/components/schemas/Schedule`, `DailySchedule` |
| FIX KalshiMD `MDEntryDate/MDEntryTime` | UTC `YYYYMMDD` / `HH:MM:SS.sss` | snapshot: "UTC snapshot capture" time; incremental: "UTC source-event time" | VERIFIED | https://docs.kalshi.com/fix/market-data.md |
| User Data Timestamp delay note | — | "There is typically a short delay before exchange events are reflected in the API endpoints. Whenever possible, combine API responses to PUT/POST/DELETE requests with WebSocket data ... This endpoint provides an approximate indication of when the data from the following endpoints was last validated: GetBalance, GetOrder(s), GetFills, GetPositions". Response `{as_of_time: date-time}` | VERIFIED | https://docs.kalshi.com/api-reference/exchange/get-user-data-timestamp.md |
| Read-model eventual consistency | VERIFIED | changelog "June 18, 2026" | "without a follow-up fetch against the eventually-consistent read model" |
| Deprecated WS timestamp fields are removed only after a pre-announcement with an exact date | VERIFIED | changelog "Apr 15, 2026" | "These deprecated fields will be removed in a future API version only after a separate pre-announcement" |
| `ts_ms` fields added Apr 15, 2026 | VERIFIED | same | Captures before that have only seconds or RFC3339. |

---

## 6. Rate limits

| Fact | Status | Source | Quote / paraphrase |
| - | - | - | - |
| Token buckets: separate **Read** and **Write**. The default cost is 10 tokens. `GET /account/endpoint_costs` is the "authoritative list of non-default costs" | VERIFIED | https://docs.kalshi.com/getting_started/rate_limits.md | — |
| "Every **authenticated** request costs tokens" | VERIFIED | same | **Limits for unauthenticated REST reads are UNRESOLVED** (not documented). Changelog "October 15, 2026" says public reads "accept a resource-bound MCP grant for per-user rate accounting", which implies anonymous reads are accounted differently. |
| Basic tier: Read **200** tokens/s; Write **100** tokens/s. Basic Read bucket capacity = 3 s of budget (600). Basic Write = 1 s | VERIFIED (page) | same | "Basic and Advanced Predictions Read buckets, and Write buckets above the Basic tier, hold up to **three seconds of budget**." "Basic-tier Write buckets hold one second of budget." |
| Tier table: Advanced 300/300; Expert 600/600; Premier 1,200/1,200; Paragon 2,400/2,400; Prime 4,800/4,800; Prestige 12,000/9,600 | VERIFIED | same | — |
| Burst capacity CONFLICT: the OpenAPI `BucketLimit` says "write buckets at non-Basic tiers hold two seconds of budget". The rate-limit page says three seconds. A changelog "Apr 30, 2026" example shows advanced write refill 100 / capacity 200, which matches neither the current table (300) | CONFLICT | `#/components/schemas/BucketLimit` vs rate_limits page | Read the live `GET /account/limits` (`refill_rate`, `bucket_capacity`) at runtime rather than hard-coding values. |
| 429 body `{"error": "too many requests"}`. **No `Retry-After` or `X-RateLimit-*` headers**. "There is no penalty or cooldown". Exponential backoff advised | VERIFIED | https://docs.kalshi.com/getting_started/rate_limits.md | quoted |
| Batch requests cost the same as individual calls; the whole batch must fit | VERIFIED | same | — |
| `/portfolio/balance` has its own bucket (1/s at Basic) | VERIFIED | same; changelog "October 15, 2026" | — |
| CF Benchmarks passthrough costs **50 tokens** of Read (Basic ≈ 4 req/s) | VERIFIED | https://docs.kalshi.com/cfbenchmarks/rest-passthrough.md | — |
| Actual per-endpoint costs for market-data reads | UNRESOLVED | — | Changelog "Apr 23, 2026": "single-query read endpoints will be priced below the default cost". Values are only available from the live endpoint, so they need a network check. |
| Read budgets are not shard-scoped | VERIFIED | rate_limits page | — |
| Tier qualification: Basic on signup; Advanced via self-serve `POST /account/api_usage_level/upgrade`; higher tiers by volume | VERIFIED | same; changelog "June 11, 2026" | — |
| WS limits: see §4.6 | — | — | — |

---

## 7. Historical data

| Fact | Status | Source | Quote / paraphrase |
| - | - | - | - |
| Data is split into live and historical tiers; partitioned types are markets, market_candlesticks, trades, orders, and market_positions. Events and Series always stay on their original endpoints | VERIFIED | https://docs.kalshi.com/getting_started/historical_data.md | "Old **Events** and **Series** will always still be available through their original endpoints." |
| `GET /historical/cutoff` → `market_settled_ts`, `trades_created_ts`, `orders_updated_ts`, `market_positions_last_updated_ts` (date-time). "Each data type has its own cutoff and the windows differ"; cutoffs advance over time | VERIFIED | same; `#/components/schemas/GetHistoricalCutoffResponse` | "The cutoff timestamps will be regularly updated, advancing forward over time." |
| `orders_updated_ts` sits two weeks before the present and advances independently | VERIFIED | changelog "September 24, 2026" | — |
| The lag of `market_settled_ts` and `trades_created_ts` behind now | UNRESOLVED | — | Not stated. |
| Public historical endpoints: `/historical/markets`, `/historical/markets/{t}`, `/historical/markets/{t}/candlesticks`, `/historical/trades` (same filters as `/markets/trades`). Fills, orders, and positions history are authenticated | VERIFIED | historical_data page; openapi; changelog "Mar 6, 2026" | — |
| Historical candlesticks: {1, 60, 1440} min, so **1-minute minimum** | VERIFIED | `#/paths/~1historical~1markets~1{ticker}~1candlesticks` | — |
| `/historical/markets` filters are mutually exclusive (`tickers`, `event_ticker`, `series_ticker`, `mve_filter`) | VERIFIED | openapi; changelog "Apr 10, 2026" | — |
| **No historical order-book endpoint exists** in the docs reviewed. REST orderbook endpoints return only the current book. No L2 history, delta replay, or snapshot archive endpoint | VERIFIED (by absence in the historical endpoint list and in openapi paths) | https://docs.kalshi.com/getting_started/historical_data.md "Historical Endpoints" table; openapi paths | The only historical book information is candle `yes_bid`/`yes_ask` OHLC at ≥1 min, plus trade prints. Book depth history must be captured live by PMV. |
| How far back trades, markets, and candles go (retention or earliest date) | UNRESOLVED | — | Not stated. |
| Trade prints are tick-level (one record per trade) | INFERENCE | Trade schema has `trade_id`, `count_fp`, `created_time` | Whether a single aggressor order filling across levels yields one or multiple prints is UNRESOLVED. |
| A record moving between live and historical endpoints during a paged read can cause duplicates or misses; positions guidance warns about this | VERIFIED (positions) / INFERENCE (trades) | historical_data page "The two reads are not one snapshot: deduplicate ..." | For trades: query both live and historical across the cutoff and dedupe by `trade_id`. |
| Changelog wording is inconsistent: "`trades_created_ts` — Fills that occurred before ... `GET /historical/fills`" (cutoff schema) vs "Trades that occurred before ... `GET /historical/trades`" (guide) | Minor inconsistency | `GetHistoricalCutoffResponse` vs historical_data page | The guide says both trades and fills are partitioned by `trades_created_ts`. |

---

## 8. Sharding, maintenance, lifecycle, settlement

| Fact | Status | Source | Quote / paraphrase |
| - | - | - | - |
| Shard assignment for new events: Crypto → shard **2**; Commodities → shard **2** (from Sept 10, 2026, 12:00 PM ET); Exotics/Combos → 1; Sports Tennis/Baseball/Basketball → 3; everything else → 0 | VERIFIED | https://docs.kalshi.com/getting_started/exchange_sharding.md ; changelog "September 10, 2026" | Table "Series Shard Assignments" |
| All child markets of an event live on one shard. No plan to migrate live markets | VERIFIED | same FAQ | — |
| `GET /exchange/status`: `exchange_active`, `trading_active`, `exchange_estimated_resume_time`, `exchange_index_statuses[]` (per shard). "The top-level fields above reflect the default exchange index (0)" | VERIFIED | `#/components/schemas/ExchangeStatus` | So a market's trading status must be read from the `exchange_index_statuses` entry matching **that market's own `exchange_index`**, never from the top-level fields. An absent breakdown or unknown index is UNKNOWN (fail closed). Do not hard-code shard 2 (corrected per Red-Team C3). |
| Scheduled maintenance: **every Thursday 3:00-5:00 AM ET**, with a trading pause (cancels allowed). Rarely, a full exchange pause (no cancels). "Clients should be prepared for session disconnections during this window and reconnect after 5:00 AM ET." An exchange pause outside the window means an outage | VERIFIED | https://docs.kalshi.com/getting_started/maintenance_and_pauses.md | quoted |
| During pauses, resting orders remain unless `cancel_order_on_pause` | VERIFIED | same | — |
| `GET /exchange/schedule` → `standard_hours[]` (weekly, ET HH:MM sessions) and `maintenance_windows[] {start_datetime,end_datetime}` | VERIFIED | `#/components/schemas/Schedule` | — |
| Statuses and filter mapping (`unopened`→initialized, `open`→active, `paused`→inactive, `closed`→past close not finalized, `settled`→finalized) | VERIFIED | https://docs.kalshi.com/getting_started/market_lifecycle.md | — |
| **Implicit transitions have no WS event**: `initialized→active` at `open_time` ("There is no `activated` WebSocket event for this transition") and `active/inactive→closed` at `close_time` | VERIFIED | same | PMV must derive open and closed from its own clock against `open_time`/`close_time`, which makes clock sync safety-relevant. |
| Explicit events: `deactivated` (active→inactive), `activated` (inactive→active; "All resting orders are cancelled on this reactivation"), `close_date_updated` (+`activated` to reopen a closed market), `determined`, `settled` (→finalized) | VERIFIED | same | — |
| `close_date_updated` "can happen when a market is closed ahead of its scheduled close time, including before determination" | VERIFIED | same | Early close. |
| Extension/reopen: "`closed` → reopened `active`: `close_time` is moved into the future. Events: `close_date_updated`, then `activated`." | VERIFIED | same | — |
| **No WS event for `disputed` or `amended`** (not in the v2 `event_type` enum). An amended market restarts the settlement timer | VERIFIED (absence) | asyncapi enum; market_lifecycle page "`amended` | Re-determined after a dispute. Settlement timer restarts." | Disputes are visible only by polling REST `status`. A `determined` event therefore does not mean the result is final until `settled`/`finalized`. |
| Whether `result` or `settlement_value` can change on amendment, and whether a second `determined` event is emitted | UNRESOLVED | — | — |
| Determination: `result` ∈ {yes, no, scalar}; then the settlement timer runs for `settlement_timer_seconds`; settled REST markets are `finalized` with `settlement_ts` | VERIFIED | same | — |
| After `close_time`, all order operations including cancels are rejected with `MARKET_INACTIVE`; resting orders are cancelled shortly after close | VERIFIED | same | — |
| Settlement payout: $1 per contract to the winning side; only net positions settle; the payout (`CollateralAmountChange`) is rounded to whole cents; settlement **fees** may apply to sub-cent scalar settlement (corrected per Red-Team C13) | VERIFIED | https://docs.kalshi.com/getting_started/market_settlement.md | — |
| "Markets typically settle shortly after expiration, but timing can vary based on market type, data source availability, and manual review requirements." | VERIFIED | same | — |
| **Tie, void, cancellation, and "no contest" rules** | UNRESOLVED on docs.kalshi.com | — | No `void` result exists. Rules live in the contract terms and rulebook. |
| WS `settled` event = settlement processed; REST shows `finalized` | VERIFIED | market_lifecycle page | — |
| Lifecycle `event_fee_update` emitted on `market_lifecycle_v2` | VERIFIED | same; asyncapi | — |
| FIX KalshiMD Security Status: 3=Resume, 2=Halt, 100=determined, 101=settled. "Scheduled (time-based) opens and closes are not emitted" | VERIFIED | https://docs.kalshi.com/fix/market-data.md | Consistent with WS. |

---

## 9. Fixed-point, subpenny, and parsing-relevant changes in the 2026 changelog

| Item | Status | Source |
| - | - | - |
| Prices `*_dollars` are strings, "up to 4 decimal places" (guide). OpenAPI `FixedPointDollars`: "responses emit up to 6" | VERIFIED / CONFLICT on max decimals | https://docs.kalshi.com/getting_started/fixed_point_migration.md vs `#/components/schemas/FixedPointDollars`. Parse with Decimal and accept ≤6 dp. Values with more than 4 dp in a price field should be flagged for review. |
| Counts `*_fp`: strings, responses always 2 dp, min 0.01 contract, fractional everywhere ("treat every active market ... as fractional") | VERIFIED | fixed_point_migration page; changelog "Apr 17, 2026" |
| Price grid: per market via `price_ranges`; structures can change mid-life (`price_level_structure_updated`); "When a market moves to a finer tick, resting orders are preserved" | VERIFIED | changelog "July 23, 2026" |
| Removal timeline: legacy integer cents and counts removed **March 12, 2026**; last legacy fields removed **April 2, 2026**; `tick_size` removed **May 7, 2026**; `liquidity_dollars` removed **Oct 1, 2026**; `available_on_brokers` removed **Sept 10, 2026** | VERIFIED | changelog "Mar 8, 2026", "Mar 25, 2026", "Apr 30, 2026", "October 1, 2026", "September 10, 2026" |
| WS ms timestamps added **Apr 15, 2026**; `sending_ts_ms` added **Oct 1, 2026**; `is_block_trade` on WS trades added **Aug 13, 2026**; `taker_outcome_side`/`taker_book_side` added **May 6, 2026** | VERIFIED | changelog entries of those dates |
| WS schema corrections (Sept 10 and 17, 2026) document existing behavior ("No message contents change") | VERIFIED | changelog "September 10, 2026", "September 17, 2026" |
| `center_deci_edge_centi_cent` "previously serialized as an empty string" on lifecycle messages (fixed Sept 10, 2026) | VERIFIED | changelog "September 10, 2026". Historic captures may contain `""`. |
| **API versioning removed**: "The GetApiVersion endpoint has been removed. API versioning will not be available for the time being." | VERIFIED | changelog "July 29, 2025" ("Removed API versioning"). **There is no runtime version signal.** Schema-change detection must be done by strict schema validation (unknown `type`, unknown required-field absence, unknown enum value → fail-closed), not by a version check. |
| Pending dates without announcements: `use_yes_price` default flip; removal of deprecated WS `ts`/`time` fields | VERIFIED (announced as future, no date) | order_direction page; changelog "Apr 15, 2026" |

---

## 10. Latency, replay, data delays, and limits relevant to a 15-minute research system

| Fact | Status | Source | Note |
| - | - | - | - |
| No published latency figures, SLAs, or co-location | UNRESOLVED (none documented) | — | Must be measured. |
| `sending_ts_ms` (Kalshi network-queue time) is now available, so venue-to-receipt transit can be measured as `local_receipt − sending_ts_ms`, subject to clock offset | VERIFIED field / measurement design | `sendingTimestampMs` | Kalshi's clock synchronization is not documented (UNRESOLVED). Treat it as an offset to be estimated. |
| Auto-routing adds latency | VERIFIED | https://docs.kalshi.com/getting_started/exchange_sharding.md "Automatic routing will incur an additional latency cost." | Execution-side only. |
| REST user data lags | VERIFIED | user_data_timestamp page | — |
| Slow consumers get error 25 (terminal) | VERIFIED | §4.6 | — |
| No replay or retransmission of WS messages is documented. FIX KalshiMD "does not support message retransmission" | VERIFIED (FIX) / UNRESOLVED (WS) | https://docs.kalshi.com/fix/market-data.md | Missed WS data must be recovered from a fresh snapshot; it cannot be replayed. |
| No historical L2 book; candles ≥1 min; trade prints are available | VERIFIED | §7 | Book-based features for 15-min windows require PMV's own live capture. |
| A REST snapshot has no seq or timestamp | VERIFIED | §3.4 | Cannot be used as a WS rebase point. |
| `ticker` is unsequenced | VERIFIED | §4.2 | Do not use ticker as the book truth. |
| Thursday 03:00-05:00 ET maintenance with disconnects | VERIFIED | §8 | A 15-min series spanning the window will have gaps or pauses. |
| Event live data `GET /live_data/events/{event_ticker}` (public) serves "crypto price charts (e.g. `KXBTC15M` events)". `details` schema is "flexible"; `range` hint (e.g. `15min`); `is_historical` "True when the event has matured and the payload is a frozen historical snapshot" | VERIFIED | changelog "July 30, 2026"; `#/components/schemas/EventLiveData` | The `details` schema is undocumented (UNRESOLVED). This is a Kalshi display product, not stated to be the settlement source. |

---

## 11. BTC 15-minute, other BTC series, CF Benchmarks, Pyth, and gold

**Important:** channel field definitions are **NOT** contract rules. Nothing on docs.kalshi.com states the settlement source, averaging window, or tie rule for any BTC or gold contract. Those must come from the series `contract_terms_url`, the rulebook, and kalshi.com contract pages (see §13).

| Fact | Status | Source | Quote / note |
| - | - | - | - |
| `KXBTC15M` appears **only** as (a) an example ticker in a `metadata_updated` example (`yes_sub_title` change) and (b) a changelog mention that event live data serves "crypto price charts (e.g. `KXBTC15M` events)" | VERIFIED | https://docs.kalshi.com/asyncapi.yaml#/components/messages/marketMetadataUpdated ; changelog "July 30, 2026" | The docs do not define the series' rules, cadence, strike construction, settlement source, or averaging. That the series currently exists or lists markets is **not** verified. |
| Other BTC tickers appear only as examples: `KXBTCD-...` (subscribe-param examples, fee-update example), `KXBTC-...-B95000` (metadata example with `strike_type: "between"`) | VERIFIED (examples only) | asyncapi `subscribeCommandPayload`, `eventFeeUpdate`, `marketMetadataUpdated` | Examples are not data and do not prove these series exist today. |
| Event `product_metadata.cadence` can be `fifteen_min` | VERIFIED (changelog) | changelog "July 30, 2026" | Use it to discover 15-min series, combined with Crypto/Commodities category queries through the data-access guard. |
| 15-min BTC metadata can change intra-life: `metadata_updated` can change `floor_strike`, `cap_strike`, `strike_type`, `yes_sub_title` | VERIFIED | changelog "May 5, 2026", "June 18, 2026" | When strikes are set relative to the window start is UNRESOLVED. Treat a strike as unknown until `metadata_updated` or REST confirms it. |
| `cfbenchmarks_value`: ~1 tick/s; `BRTI` = BTC index ID; `avg_60s_data` always present: trailing window `[source_ts_ms − 60000, source_ts_ms)`; `window_size` counts prior ticks only; falls back to the current value if empty | VERIFIED | https://docs.kalshi.com/websockets/cfbenchmarks-value.md "Averaging semantics" | — |
| `last_60s_windowed_average_15min`: present only in the final minute before a quarter-hour close (:00/:15/:30/:45). Window `(quarter_close_ts_ms − 60000, quarter_close_ts_ms]` ("start-boundary tick is excluded and the close tick is included"); second-indexed counts up to 60 | VERIFIED | same | — |
| The field name `window_end_ts_exclusive` conflicts with "close tick is included" for the 15-min average | CONFLICT (naming) | `#/components/schemas/cfbenchmarksAvgData` vs the averaging prose | Also, the documented example's window bounds and `window_size` do not match the prose (illustrative values). Do not rely on the example. |
| **That `last_60s_windowed_average_15min` equals the settlement value of KXBTC15M (or any contract)** | **INFERENCE only; NOT VERIFIED** | — | The name and quarter-hour alignment suggest it. No doc says it. It is a Kalshi-computed convenience field built from deduplicated ticks ("duplicate or out-of-order upstream source timestamps are ignored"), and the official contract may use a different methodology (for example CF Benchmarks' own published settlement average, a different tick set, or a different window). |
| `cfbenchmarks_value_5hz`: up to 5 ticks/s for BRTI, ETH, SOL, XRP, DOGE; fields `value_usd` (8 dp), `source_ts_ms`, `received_at`, raw `data`; no averages | VERIFIED | https://docs.kalshi.com/websockets/cfbenchmarks-value-5hz.md ; changelog "September 3, 2026" ("indices the vendor publishes at 200ms granularity") | — |
| Kalshi drops duplicate and out-of-order upstream ticks on both CFB channels | VERIFIED | same | So the stream is a filtered view of the upstream feed, not the full upstream. |
| `indexlist` must be used to confirm availability: "A successful `subscribe` response alone does not confirm that a requested index is available." | VERIFIED | cfbenchmarks-value page | — |
| CF Benchmarks REST passthrough: `GET /trade-api/v2/cfbenchmarks/<path>` forwards to `https://www.cfbenchmarks.com/api/v1/<path>`; **auth + entitlement required**; 50 tokens; drops `includeVerification`; history via `/cfbenchmarks/history/values?id=BRTI&timespan=...&timestamp=...` "returns tick-level values, and some indices publish at intra-second granularity" | VERIFIED | https://docs.kalshi.com/cfbenchmarks/rest-passthrough.md | **Historical depth and retention are not stated.** They defer to CF Benchmarks docs (UNRESOLVED). Error mapping: 404 / 429 / 503 / 400. Demo availability is UNRESOLVED. |
| Pyth `pyth_value` lists gold feeds `Metal.XAU/USD` (346), `Metal.Index.GOLD/USD` (3153, 24/7), `Metal.Index.1OZGOLD/USD` (3712, 24/7); spot metals "follow their market sessions" | VERIFIED | https://docs.kalshi.com/websockets/pyth-value.md | Paid feed ($1,000/month). `underlying_list` shows tickers "observed on the stream within the last two hours". "Duplicate and out-of-order source timestamps are ignored independently per underlying ticker." |
| **Any gold prediction-market (event contract) series** | **UNRESOLVED: not documented** | — | No gold prediction series ticker appears anywhere on the pages reviewed. Gold appears only as Pyth feeds and as Margin/perps (`reference_price` for "Pyth-indexed perps, such as gold and silver", changelog "October 1, 2026"). Perps are out of scope. Commodities events are on shard 2. Existence, cadence, and settlement source of gold event contracts need discovery through the data-access guard and kalshi.com contract terms. |
| Whether Pyth (or CF Benchmarks) is the settlement source for any gold event contract | UNRESOLVED | — | Not stated. |

---

## 12. Mapping to `pmv.market_data.kalshi.REQUIRED_VERIFICATIONS` (`src/pmv/market_data/kalshi.py`)

| Item | Docs status | Notes |
| - | - | - |
| `api_terms_and_permitted_use` | UNRESOLVED (docs give a pointer only) | Developer Agreement at kalshi.com, not reviewed |
| `account_and_jurisdiction_eligibility` | UNRESOLVED | Only the location-attestation note (Sports/Elections/Entertainment) is documented |
| `authentication_for_market_data` | VERIFIED | REST reads are public; WS always needs a signed handshake; no market-data-only scope; `read` scope exists |
| `rest_market_and_event_metadata_schema` | VERIFIED (doc level) | §3 |
| `websocket_channels_and_message_schema` | VERIFIED (doc level) with conflicts noted | §4 |
| `websocket_sequence_and_snapshot_semantics` | **UNRESOLVED** (partial) | Seq exists; scope, resync, and get_snapshot ordering are not documented |
| `orderbook_representation_and_price_units` | VERIFIED with sort-order CONFLICT | §3.4, §4.5 |
| `orderbook_delta_semantics_absolute_or_relative` | **INFERENCE** (relative) | §4.4; needs test |
| `trade_print_schema_and_identifiers` | VERIFIED | §3.5, §4.2 |
| `timestamp_fields_and_resolution` | Mostly VERIFIED; REST TZ and precision UNRESOLVED | §5 |
| `rate_limits` | VERIFIED for authenticated; UNRESOLVED for unauthenticated; burst CONFLICT | §6 |
| `historical_data_depth_and_resolution` | Resolution VERIFIED; depth/retention UNRESOLVED; no historical book | §7 |
| `btc_and_gold_series_availability` | UNRESOLVED | §11 |
| `contract_rules_settlement_source_and_timing` | UNRESOLVED (generic timing only) | §8, §11 |
| `settlement_reference_window_or_averaging` | UNRESOLVED (the channel average is not a contract rule) | §11 |
| `early_close_and_extension_semantics` | VERIFIED (mechanics) | §8; contract-specific conditions UNRESOLVED |
| `lifecycle_status_messages_and_result_fields` | VERIFIED with gaps (no disputed/amended WS events; doc conflicts) | §4.2, §8 |
| `sequence_number_scope_per_subscription_or_market` | **UNRESOLVED** | §4.3 |
| `tie_rounding_and_void_rules` | UNRESOLVED (no void result; fee rounding VERIFIED) | §3.8, §8 |
| `fee_schedule_and_effective_dates` | Endpoints VERIFIED; rates UNRESOLVED (external PDF) | §3.8 |
| `demo_environment_scope_and_fidelity` | Fidelity warning VERIFIED; scope UNRESOLVED | §1 |

---

## 13. Consolidated UNRESOLVED list

Two items are BLOCKING for writing a production-faithful book parser: seq scope and the resync protocol (U1-U4), and delta semantics (U5).

1. **U1 Seq scope**: per sid, per market within a sid, or per connection. Not stated.
2. **U2** Whether `ok`, `error`, `unsubscribed`, and `get_snapshot` replies consume seq numbers in the same counter as data messages.
3. **U3** Seq start value and reset behavior on resubscribe or new sid. Behavior when the idempotent re-subscribe adds markets: new snapshot? seq continuity?
4. **U4** The documented gap or resync procedure (none). Whether a `get_snapshot` reply is sequence-consistent with deltas in flight, so it can be used to rebase. Whether it honors `use_yes_price`.
5. **U5** Whether `delta_fp` is relative (strong inference) or absolute. Level removal at zero. Negative results.
6. **U6** WS snapshot level sort order. REST sort-order conflict (ascending vs "best to worst"), and the "order counts" mentioned in text but absent from the schema.
7. **U7** Cross-channel ordering; duplicate delivery; conflation of deltas or ticker updates.
8. **U8** When `orderbook_delta.ts_ms` is absent. Exact semantics of `ticker.ts_ms` and `trade.ts_ms` (exchange event time vs publish time).
9. **U9** Timezone and precision of REST `date-time` fields. Units and inclusivity of `min_ts`/`max_ts`/`start_ts`/`end_ts` where not stated. Ordering of `/markets/trades` results.
10. **U10** Server keep-alive enforcement (pong timeout, idle disconnect).
11. **U11** Rate limits for unauthenticated REST reads. Actual endpoint costs for market-data reads. Burst-capacity conflict (2 s vs 3 s). Current WS connection limits per tier. The per-subscription market limit (error 26). The command rate limit value behind code 27 (10k/s per the changelog?).
12. **U12** Whether a `read`-only key can open WS and subscribe to `orderbook_delta` and the CFB channels. Whether the CFB WS channels need an entitlement like the REST passthrough does.
13. **U13** Signature timestamp tolerance (clock skew).
14. **U14** Demo scope: which series and channels exist (KXBTC15M? CFB? Pyth?), demo rate limits, demo maintenance.
15. **U15** Lag of historical cutoffs `market_settled_ts`/`trades_created_ts`. Earliest available history (retention). Sampling method of candle bid/ask OHLC. Live `mean_dollars` vs historical `mean` (VWAP) definitions.
16. **U16** Whether `/events/fee_changes` includes past changes. Whether WS `event_fee_update` fires at set time or at effective time. Fee rates and formulas.
17. **U17** Result or settlement changes on dispute or amendment, and whether a new `determined` event is emitted. No WS signal for `disputed`/`amended`.
18. **U18** Tie, void, and cancellation rules; strict vs non-strict strike comparison (`greater` vs `greater_or_equal`) per contract.
19. **U19** KXBTC15M (and any BTC or gold event series): existence, rules, strike construction timing, settlement source, averaging methodology, settlement timer. Whether the `last_60s_windowed_average_15min` field equals the contract settlement value. The `window_end_ts_exclusive` naming conflict.
20. **U20** Gold event-contract series existence and settlement source (Pyth? another source?).
21. **U21** CF Benchmarks history depth and retention through the passthrough; demo availability of the passthrough.
22. **U22** The `market_lifecycle_v2` + `market_ticker` filter conflict (ignored or rejected?). Lifecycle event-type list conflict between the guide and the schema. The undocumented `banded_centi_cent` grid.
23. **U23** Deprecated-field removal dates: `taker_side` (May 14 vs May 28, 2026, both passed but still in schema), `use_yes_price` flip, WS `ts`/`time` removal. There is no API version signal to detect these changes.
24. **U24** Event live data `details` schema for crypto, and whether it relates to settlement.
25. **U25** Whether the 2025 statement of 200 WS connections per user still holds.

---

## 14. Facts needing non-docs.kalshi.com sources

| Need | Likely official source (not retrieved, no network used) |
| - | - |
| API terms of use, permitted automated use, data redistribution and storage rights | https://kalshi.com/developer-agreement ; kalshi.com terms of service (asyncapi `license.url: https://kalshi.com/terms`) |
| Account and jurisdiction eligibility; location attestation scope | kalshi.com terms / member agreement; help.kalshi.com |
| Fee rates, formulas, maker fees, effective dates | https://kalshi.com/docs/kalshi-fee-schedule.pdf (referenced by `Series.fee_type`) |
| Contract terms for KXBTC15M and other BTC series: settlement source (BRTI?), averaging window, strike setting, tie and void rules, early-close conditions, settlement timing | Per-series `contract_terms_url` and `contract_url` (from `GET /series/{ticker}`, which must be fetched via the PMV data-access guard); Kalshi rulebook ("Methodology is defined in the rulebook"); kalshi.com market pages ("Timeline and Payout") |
| Gold event-contract existence and terms | Same as above, via category/series discovery through the data-access guard; kalshi.com |
| CF Benchmarks BRTI methodology, the official settlement-average methodology, history API parameters and retention | https://docs.cfbenchmarks.com/api/category/rest/ (referenced); CF Benchmarks index methodology documents |
| Pyth feed methodology and market sessions for XAU | Pyth Network documentation |
| Demo account creation and demo scope | https://help.kalshi.com/en/articles/13823775-creating-and-using-a-demo-account |
| FIX KalshiMD access eligibility and connectivity | https://docs.kalshi.com/fix/connectivity.md and https://docs.kalshi.com/fix/authentication.md (docs.kalshi.com, but not downloaded) |
| WS user channels (`user-fills`, `user-orders`, `market-positions`) prose | docs.kalshi.com pages not downloaded (specs reviewed in asyncapi only) |

Protected-information note: fetching live series, market, contract, or live-data payloads, or CF Benchmarks or Pyth history, is real market observation. Per CLAUDE.md and docs/protected_information.md it must go through the deterministic data-access guard and must not be done ad hoc by development agents. Contract **terms documents** are not market observations, but retrieving them requires an approved access path (AR-1 covers docs only, not API hosts).

---

## 15. Engineering implications and proposals (recommendations, not approved requirements)

1. **Book integrity design under U1-U5 (blocking):** Until tests resolve them, the parser should: (a) keep one book per (connection, sid, market); (b) treat any seq discontinuity on a sid as stale for **all** markets in that sid (conservative under the per-sid inference); (c) recover by unsubscribing and resubscribing only with preconditions (Red-Team C4/RT-B2-01): a confirmed `unsubscribed`, a new `sid`, and a new snapshot for every market, otherwise reconnect. Subscribe is idempotent per changelog 2025-09-25, so re-subscribing the same tickers may do nothing. "A fresh sid gives a fresh snapshot" is INFERENCE, not by relying on `get_snapshot` rebase semantics, until a test proves `get_snapshot` is seq-consistent; (d) treat a negative level size, a crossed book (YES bid ≥ 1 − best NO bid under no-leg pricing), or an off-grid price per `price_ranges` as an integrity failure. Proposed: a demo or recorded-prod test harness that measures seq behavior across multi-market sids, ok/error messages, add_markets, and get_snapshot.
2. **Set `use_yes_price` explicitly** (recommend `false` until the flip is announced, to match REST no-leg semantics), and record it per subscription in raw capture metadata. The parser must take the pricing convention from capture metadata, never from a default.
3. **Separate ingest reader from processing** to avoid error 25. Treat 10 and 25 as terminal: mark stale, resubscribe, rebuild from snapshot.
4. **Schema strictness replaces version checks:** there is no API version endpoint. The parser should validate every message against a pinned schema derived from asyncapi 2.0.0 and openapi 3.34.0 (with recorded sha256 prefixes `3c86bae7d89b44ba` and `a33d05aaa5deab31`), and fail closed on unknown `type`, missing required fields, or unknown enum values. Unknown optional fields should be preserved in raw capture and flagged, not dropped.
5. **Lifecycle:** derive open and close transitions from `open_time`/`close_time` on a synchronized clock, because no WS event is sent for them. Poll REST status for `disputed`/`amended`, which have no WS event. Do not treat `determined` as final until `settled`/`finalized`.
6. **Shard health:** gate each market on the `exchange_index_statuses` entry matching its own `exchange_index`. An absent breakdown or unknown index is UNKNOWN (fail closed). Never use the top-level flags, which reflect shard 0 (corrected per Red-Team C3).
7. **Credentials for data capture:** WS market data needs a signed key. Recommend a dedicated **`read`-scope-only key**, ideally subaccount-restricted, kept outside agent environments, separate from any trading key. Note that `read` still exposes portfolio data. There is no narrower market-data scope. Escalate to the user, because this affects the secrets policy.
8. **Settlement-reference capture:** capture `cfbenchmarks_value` (with averages) and `cfbenchmarks_value_5hz` raw frames, including `received_at`, `source_ts_ms`/`data.time`, and `sending_ts_ms`. They are reference-market feeds only. Do **not** label `last_60s_windowed_average_15min` as the settlement value until contract terms confirm it.
9. **Historical limitations to surface to the Data Scientist and Statistician:** no historical L2 book; candles ≥1 min; WS ms timestamps only since Apr 15, 2026; `sending_ts_ms` only since Oct 1, 2026; ack/data race fixed Sept 17, 2026 (earlier captures may silently miss first events). Any historical availability time is **estimated**, not observed.
