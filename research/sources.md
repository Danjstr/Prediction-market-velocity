# External Sources

Record important external sources here, as required by CLAUDE.md.

For each source, record:
- title;
- URL or other locator;
- retrieval date (UTC);
- what it was used for;
- source type: official documentation, primary source, or secondary;
- verification status: documented guarantee, observed behavior, or assumption.

Entries are append-only. Mark superseded entries rather than deleting them.

## Sources

### Claude Code permissions documentation
- URL: https://code.claude.com/docs/en/permissions.md
- Retrieved: 2026-10-07
- Used for: `.claude/settings.json` deny-rule syntax, path-pattern semantics, deny/ask/allow precedence, and the limits of Read/Edit denies for Bash commands and subprocesses
- Source type: official documentation
- Verification status: documented guarantee

### Claude Code settings documentation
- URL: https://code.claude.com/docs/en/settings.md
- Retrieved: 2026-10-07
- Used for: settings-scope precedence and `.claude/settings.local.json` handling
- Source type: official documentation
- Verification status: documented guarantee

### Claude Code sandboxing documentation
- URL: https://code.claude.com/docs/en/sandboxing.md
- Retrieved: 2026-10-07
- Used for: sandbox settings keys and platform support, deferred to Phase 0 compatibility testing
- Source type: official documentation
- Verification status: documented guarantee

### Claude Code subagents documentation
- URL: https://code.claude.com/docs/en/sub-agents.md
- Retrieved: 2026-10-07
- Used for: whether permission rules apply to subagents
- Source type: official documentation
- Verification status: documented guarantee

### Kalshi API documentation set (docs.kalshi.com), Phase 1 batch 2 venue verification
- URL: `https://docs.kalshi.com/` (the pages listed below, fetched as Markdown, plus the published `openapi.yaml` and `asyncapi.yaml`). `https://docs.kalshi.com` answers `308` to `https://docs.kalshi.com/welcome`, on the same approved domain.
- Retrieved: 2026-10-15, 23:58:51Z to 23:59:57Z. Each page's time is in the table.
- Access basis: AR-1 (`docs/decisions/2026-10-16_phase1_batch2_owner_decisions.md` D1). No API host was contacted.
- Used for: the verified and unresolved Kalshi facts in `research/kalshi/venue_verification.md`, covering environments, authentication, REST and WebSocket schemas, sequencing, timestamps, lifecycle, settlement mechanics, fee fields, rate limits, historical data, and the demo environment.
- Source type: official documentation (the venue's own API documentation and machine-readable specifications).
- Verification status: documented statements (what Kalshi documents, not observed behavior). Example payloads in these pages are illustrations, not data, and were not used as data.
- Hashes identify the bytes retrieved on that date. The pages change over time; a later re-verification compares against these hashes.

| Path under `https://docs.kalshi.com/` | Retrieved (UTC) | SHA-256 of retrieved bytes |
|---|---|---|
| `llms.txt` (documentation index) | 2026-10-15T23:58:51Z | `4b97d36e6e5c0b949d0a9bdced42fe0499be277a0a9c2dc8f66342fae14520f0` |
| `welcome/index.md` | 2026-10-15T23:59:21Z | `df7897ce967ea172b1ec1317fe2e1d3cc4497e31684e8bef327598428fdbbba2` |
| `getting_started/api_environments.md` | 2026-10-15T23:59:22Z | `3699198c05638954d62dfb2ed0e6c51c45eea35f12aeb9b2afe17aa675be1023` |
| `getting_started/quick_start_market_data.md` | 2026-10-15T23:59:23Z | `71889f44b353de08f22cbc6910abe3e5aeef95889947d1d35b498eac89b7a957` |
| `getting_started/quick_start_websockets.md` | 2026-10-15T23:59:23Z | `645674c6f694a21d7432b6e7f6bbc7ad9f42b604047baa0cfb71c538527f28a5` |
| `getting_started/quick_start_authenticated_requests.md` | 2026-10-15T23:59:24Z | `c6d2c43ba05c9a196f0385eacc4c843291e669e391a8781c82e7b033f36dcb7b` |
| `getting_started/demo_env.md` | 2026-10-15T23:59:24Z | `c1e144fe01d5f5ea5bab4b0167d1eed1a05bd52f409bfd2bd6886ebd6d6eca87` |
| `getting_started/api_keys.md` | 2026-10-15T23:59:25Z | `70d8b3957dd952c30fc9beff9085f1dbe16f270098cfd465725afe4e85101b9f` |
| `getting_started/rate_limits.md` | 2026-10-15T23:59:26Z | `3baaee8fcffe3fbca14cf1bded8e8141e85f69f60ebc6113ea8e00c563561a76` |
| `getting_started/pagination.md` | 2026-10-15T23:59:26Z | `abe2bcc1f8931ed672b94ae652999e9c5ecb65f545e6387b3f1e6e572a80b96b` |
| `getting_started/orderbook_responses.md` | 2026-10-15T23:59:27Z | `a87d1a2b795b7fc06c9f57222ba95542a450fc987f90f2c10396af2fa2628c85` |
| `getting_started/order_direction.md` | 2026-10-15T23:59:27Z | `596c8beb4eb6ccf67199762ea92cd6d471bb7b593ebcf427810e9b70cc66ba63` |
| `getting_started/fixed_point_migration.md` | 2026-10-15T23:59:28Z | `249bb44d972bfef98061ecffcd7869eba0aef356c610fcab8946ca33072cecb4` |
| `getting_started/fee_rounding.md` | 2026-10-15T23:59:29Z | `0e75e087de5e90897e59a19a13ccb5d554a417177a28fc3a9a05fee18152f669` |
| `getting_started/historical_data.md` | 2026-10-15T23:59:29Z | `547782c580ec46acf8d4b84fe2fa3636d5f74104e57f394772496edba1fc37de` |
| `getting_started/market_lifecycle.md` | 2026-10-15T23:59:30Z | `fc1e534166262db091638dcc5e2629c4456aa3579aa8eb987a381867731a359e` |
| `getting_started/maintenance_and_pauses.md` | 2026-10-15T23:59:30Z | `18bd36f86a9fab4e687976d1aeb8f0ef3bd73a7cdf27d1a502e71a34c71d8d4e` |
| `getting_started/market_settlement.md` | 2026-10-15T23:59:31Z | `ae5b054f4489952276cfdfb4f5144eef861e231118b58c1124a7a1e0a4d773f7` |
| `getting_started/settlement_bounds.md` | 2026-10-15T23:59:31Z | `67611785e6b52c161fb16be8ec8b42daa5ee580f8cf2aca1ffeb469f3c16edd7` |
| `getting_started/exchange_sharding.md` | 2026-10-15T23:59:32Z | `d3988f83a6c5c9e90f9329523d54b6267e64e22fa19313ab3d180cef4fed6589` |
| `getting_started/terms.md` | 2026-10-15T23:59:33Z | `a52d8a7ad71d90c8bbbfbad41187c32369ece5ad6b34ca6dae018816f5e16d35` |
| `cfbenchmarks/rest-passthrough.md` | 2026-10-15T23:59:33Z | `bf0ef09aae3c97542090c17bce999e04441f830e6db390c6d392e67929996b51` |
| `sdks/overview.md` | 2026-10-15T23:59:34Z | `bbe932da3abaa3119857f3cf66c9b882eaedd107cfa87572840ffd0a9155e5f1` |
| `api-reference/exchange/get-exchange-status.md` | 2026-10-15T23:59:34Z | `f802f49f8d3c44edeab893293ce991bbeef04cf5f874da067c4f8f35319a9d2b` |
| `api-reference/exchange/get-series-fee-changes.md` | 2026-10-15T23:59:35Z | `0e89ceee6124b97aad2225e8da3ca5172469d1e90bd8b70dd1c0178e1a77978d` |
| `api-reference/exchange/get-exchange-schedule.md` | 2026-10-15T23:59:35Z | `c132d28acc3e5483cf6e44ff178dbe4c1c15a9e881b7c3732c9ae118ea8a4d85` |
| `api-reference/exchange/get-user-data-timestamp.md` | 2026-10-15T23:59:36Z | `667587901abf5fb7a2500f9916544e60743c0a2780b5b61828caa7795c2ce59e` |
| `api-reference/market/get-market-candlesticks.md` | 2026-10-15T23:59:37Z | `e7456ed336684990ee0b156e0a5f7b9b30b0cc6b37a42ceb14948954401b4a51` |
| `api-reference/market/get-trades.md` | 2026-10-15T23:59:37Z | `56d72b0b6db9d80ac2f219e6c793fa0255c06948703a393ae8fed9981a38e7ab` |
| `api-reference/market/get-market-orderbook.md` | 2026-10-15T23:59:38Z | `ec5115f85471624872a6cbd8213c7e1fe3c994e19a0f7e4d86549cf2fd2c4f2e` |
| `api-reference/market/get-series.md` | 2026-10-15T23:59:38Z | `3112e2e5ae8c4e11b557033e5ec8b72991457ea08a34d0f810e56d91b83fe2f4` |
| `api-reference/market/get-series-list.md` | 2026-10-15T23:59:39Z | `af5ffa15ac90cfd49f0338e8f45b24a3d32a208c5e39024474a4bf3e4d433185` |
| `api-reference/market/get-markets.md` | 2026-10-15T23:59:40Z | `172f9ace7531e1ec2422b7099c5c2e93b7e0428d427f7978374a255a5a959c41` |
| `api-reference/market/get-market.md` | 2026-10-15T23:59:40Z | `ae9d917509f33d278b59657e5793277574846208635e845cc07f5762a6178bea` |
| `api-reference/events/get-events.md` | 2026-10-15T23:59:41Z | `53edc7744038cc3e999a57dcfb8b1d68d83cd25a479795e2fb634d6643788758` |
| `api-reference/events/get-event.md` | 2026-10-15T23:59:41Z | `3d578cfe0a3817fb5da3d1933f9440dccd57b896ca59fc31c0a31dc9515db991` |
| `api-reference/events/get-event-metadata.md` | 2026-10-15T23:59:42Z | `d07078d2251c7ca24f7529421c1d5838beabde99c9e6d229ab60f844e697076a` |
| `api-reference/events/get-event-fee-changes.md` | 2026-10-15T23:59:42Z | `0bfa439901cd21fb38cade43fa0c57df2d9546d95d03a8c53dc9eb1a5fcffcac` |
| `api-reference/live-data/get-event-live-data.md` | 2026-10-15T23:59:43Z | `c6f93b87342cfa23ee9d25f44d0724c6d5add739f114a732300e6aae6d9e6f03` |
| `api-reference/historical/get-historical-cutoff-timestamps.md` | 2026-10-15T23:59:44Z | `a50b953d229f1117ed7fffa48a9e5bfddbce087c2c6cefbaa5b8f03188c2e45a` |
| `api-reference/historical/get-historical-market-candlesticks.md` | 2026-10-15T23:59:44Z | `12b4d68411e91251adc4b7fd8b4fb99af20ae5c5786c0ee485381d2b9fe97842` |
| `api-reference/historical/get-historical-trades.md` | 2026-10-15T23:59:45Z | `eca34229c0f15738872c26615a63a31b7a30e4a4786f6891192a6a73169251c0` |
| `api-reference/historical/get-historical-markets.md` | 2026-10-15T23:59:45Z | `69e131d13e0727aab1d84e55dcc4ac38fa8770c70a9e5341d858a919f7fefbfc` |
| `api-reference/historical/get-historical-market.md` | 2026-10-15T23:59:46Z | `2ef52dae1f13f762bdee9897e87ab07ac968db2367386ac8b3b9fc9446d41993` |
| `api-reference/account/get-account-api-limits.md` | 2026-10-15T23:59:47Z | `f1a2b82b1f4c25c25bfb2913e9c9e52f100ba7fce8de869d08f773796e731d4d` |
| `api-reference/account/list-non-default-endpoint-costs.md` | 2026-10-15T23:59:47Z | `5daf84eedcc614a8ed967165da5f12da2cbf9d0e789921e880eda8c408c81836` |
| `websockets.md` | 2026-10-15T23:59:48Z | `91785dbb111eb0b07c0e9c37f81a2b4084708a9400737846e26782b9e32b71fb` |
| `websockets/websocket-connection.md` | 2026-10-15T23:59:49Z | `d22be650c3cb9be69228e2d999585b767a42217c9c3c4291059aba3173fd923b` |
| `websockets/connection-keep-alive.md` | 2026-10-15T23:59:49Z | `03b3b4e9e1f446cf1782b7021acb6fd5076807f57f4a91fe4d029e098ecf6416` |
| `websockets/orderbook-updates.md` | 2026-10-15T23:59:50Z | `d3c138b713d2463ab91d7625ac281d7cc5e58e3f8667f9e4837ec90e10d9cecc` |
| `websockets/market-ticker.md` | 2026-10-15T23:59:51Z | `1af765091fcdfc0b4ea81fd743cd2cd1bdc15bac00533a636d8fd2a9359ffb21` |
| `websockets/cfbenchmarks-value.md` | 2026-10-15T23:59:51Z | `4c61a8f08fd896e7eeb0c746f666f7951be365032eb054b698018a4c15b36fa2` |
| `websockets/cfbenchmarks-value-5hz.md` | 2026-10-15T23:59:52Z | `d1eefda0dac7fcc07162b92ba78a906ec461f214f9c30142d5f9a987700acfbb` |
| `websockets/pyth-value.md` | 2026-10-15T23:59:52Z | `70c0e8062402b316e6398bf86e079eafb74ca905606c1f8a60858664f11a0a5b` |
| `websockets/public-trades.md` | 2026-10-15T23:59:53Z | `1ec7c692014483c2777ac0780efeb7793b2a2c2a6d231f5b6161ee35497d7198` |
| `websockets/market-and-event-lifecycle.md` | 2026-10-15T23:59:54Z | `be79b2ba6119f2a984f1d998c4ca40e03872f395f4e562004b2be6b620a7c187` |
| `fix/market-data.md` | 2026-10-15T23:59:54Z | `0d10eed9d9acfc6b24c19a74ee939f3f55937737ebae27b0897f74b643e8d613` |
| `changelog/index.md` | 2026-10-15T23:59:55Z | `8fabf2e1ee1e223471bd830f49337b4929a04056e3627e613de49b7c9a9ebe80` |
| `openapi.yaml` | 2026-10-15T23:59:56Z | `a33d05aaa5deab319674407d543b5c0027d41adbf2c4f8a11dab708a0debd35a` |
| `asyncapi.yaml` | 2026-10-15T23:59:57Z | `3c86bae7d89b44baba1119b3a097a54054c1d851e1dcd8ad894c7cb35b9890b6` |

### kalshi.com legal, fee, and developer pages (attempted, NOT retrieved)
- URLs attempted: `https://kalshi.com/terms`, `https://kalshi.com/developer-agreement`, `https://kalshi.com/fee-schedule`, `https://kalshi.com/docs/kalshi-fee-schedule.pdf`. Each one is linked from the docs.kalshi.com pages above.
- Attempted: 2026-10-16, 00:00:57Z to 00:01:04Z.
- Result: HTTP 429 with a "Vercel Security Checkpoint" JavaScript challenge page, so no document content was obtained. The challenge was not circumvented. `https://kalshi.com/` also answered 429 to a HEAD request on 2026-10-15. `www.kalshi.com` is not on the network allowlist.
- Consequence: the terms of service, the Developer Agreement, the fee schedule, and the contract-rule documents are **unverified**. See ACCESS REQUEST AR-3 in `docs/phase1.md`.
- Source type: official (intended). Verification status: not retrieved.

## Phase 1 batch 3: historical-data inventory sources (retrieved 2026-10-16)

Merged from the three batch 3 inventory agents. Hashes identify the bytes retrieved. Inventories: `research/historical_data/inventory_*.md`.

### Batch 3 group: Prediction markets (section A)

These entries use the format of `research/sources.md`, for later merge by the lead. Every item was retrieved 2026-10-16 (UTC), between 02:05Z and 02:29Z. SHA-256 values identify the bytes retrieved. They were fetched with curl through the sandbox egress proxy, except where noted. No market API, RPC, subgraph, or query host was contacted. No dataset files or viewers were opened. Example payloads in documentation are illustrations, not data, and were not used as data.

### Polymarket documentation set (docs.polymarket.com)
- URL: `https://docs.polymarket.com/` (pages listed below, fetched as `.md`)
- Retrieved: 2026-10-16
- Access basis: owner direction 2026-10-16 (Polymarket documentation research approved for this inventory; no adapter, account, or collection)
- Used for: historical endpoints and retention; trade and price-history timestamp semantics; on-chain event model; resolution sources (UMA; Chainlink TWAP); settlement-rule, fee, and taker-delay change dates; geoblock (US close-only); absence of a historical book endpoint
- Source type: official documentation (the venue's own docs and the OpenAPI excerpts embedded in them)
- Verification status: documented statements, not observed behavior

| Path | SHA-256 |
|---|---|
| `llms.txt` | `bc1dd18d474ffad8154e7939c4b8e013d99b91895b67cecef112a53bb99888eb` |
| `_llms/en/api-reference/predictions.txt` | `ee72a2ab5d10d9c4a1b8a6c7532db037dfe090f91b09f2f03e0b2cef9200bd10` |
| `api-reference/markets/get-prices-history.md` (CLOB, legacy) | `e8e811fc15da9cedc750732e85db65ac4049a7d373ed264a2a7bace9d559d98d` |
| `api-reference/markets/get-batch-prices-history.md` | `8e861601f816fa1af3d413dbabe8bc7096df5358130e725842c11a5d846de406` |
| `api-reference/markets/get-a-tokens-price-history.md` (Data API v2) | `dbd5e33956200540998dd8f99a361ff12cafc28de019ccc562170ac7b2582faa` |
| `api-reference/feeds/list-trades.md` (Data API v2 `/v2/trades`) | `507b47690c31d7d47657b667d304868e2d86aa959d368a42644691fa78ec2b5d` |
| `api-reference/core/get-trades-for-a-user-or-markets.md` (v1) | `d8c04e1218d6fdc1e8c164c0182d7e3053b59cbfdf5416f484051e7f279a0886` |
| `api-reference/markets/get-resolution-state.md` | `a703d0ebc6ff2c1bd32fd711cae2a72220aa88559058be4ea7c63ff5ca0f5441` |
| `api-reference/service/get-data-freshness.md` | `371f32ca156ad0537d17049761cb806e8749695233067be668f84d18eb6d9a40` |
| `api-reference/data-api/overview.md` | `ee1c773be5d18dbb3a554e45644ce6242c2d5fa0cb5bc5f90d2fcfcb8037ff2d` |
| `api-reference/markets/list-markets.md` (Gamma) | `783670f60fbdacf179fb869af5b0265d4954402069383b6582147bd092032fa6` |
| `api-reference/markets/get-market-by-id.md` | `1a52ff01572c8a39e176432c0720ed0bc27aca31a9ec1122885a7c4c8b778b52` |
| `api-reference/events/list-events.md` | `ae4d57cf733a9b2cde990fade7227ee4432522ff96f5b8c2304da9a90b2a1e87` |
| `api-reference/series/list-series.md` | `54d5131df88bf567bc34df25359e402320de50e83d569511eca925bf654f5443` |
| `api-reference/market-data/get-order-book.md` | `85a606166da518d9c85523406bfeeeae76f4f069171320ea3b8c6c906974fcc4` |
| `api-reference/wss/market.md` | `0828ba0ecbff80d9e611f6ceb3922ef48a9cd794feab97ede1ab879d7cbd5a79` |
| `api-reference/wss/polybolt.md` | `c3870cb5efb7aca23893f353646ce9d36128bdd3b34dfc4aa311972cf38c264e` |
| `api-reference/live-data/overview.md` | `0d1ead0547430d2b9411f7bc1cb5eb3a32482d205044f6f827f3ed915f35f2b5` |
| `api-reference/rate-limits.md` | `1a238b502342564ff0afb087a725aad2bf16e5fa5978d19bcf414ea81d2a84a5` |
| `api-reference/geoblock.md` | `0497c110220bd31c69acedcffbe478ff3c28c9b4a2c59bca45ab9028567cf0c3` |
| `api-reference/predictions/overview.md` | `abf1388c44092ca4fcac0dd00563d8648ff4551b64278966439c32911cbaa59d` |
| `concepts/resolution.md` | `2264660d3f55b7d3df875d73b68098d7d62c1489cdd252bd846932e3088cd047` |
| `concepts/markets-events.md` | `89a0a338161924c0e65a935dfb0e6ac0bb6e0826b4f1643500712fb1d72f9244` |
| `concepts/prices-orderbook.md` | `f3f23f21862272a505f098b3703c8954a52719f0dc45eb9c71bc7231b5ce0380` |
| `market-data/overview.md` | `9d340c9cb056bfed11b189dcf02279db46e7ce9a4dad93bb9da87aa8b33c7568` |
| `market-data/prices-order-books.md` | `438b620f7ac6c856c03444ac4f0d5893938c30510f533a25e0068907cec704cd` |
| `market-data/market-details.md` | `00be2ab64b017c31524715c4ae43c08571e5bfa444e77ee885d0adc388aafd99` |
| `market-data/discover-markets.md` | `a73c970113abf3a3eecdf2426fc385a81ff834a4baf8d6c0dd1894ce85a856ee` |
| `market-data/public-analytics.md` | `f97802fc740bb129cafe3e393656732d3e3382a1e96e5c88c54a7e99d164a7c7` |
| `market-data/realtime-data.md` | `adcc641bde699fc6e2196e80a84e21b680aa0d36b30183b29b753c910dd5671e` |
| `market-data/chainlink-twap.md` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty body; redirect, content not retrieved) |
| `resources/blockchain-data.md` | `b43e28861d67e2b2a27cb02ec939ce09c99388dc3945107df46e00183acd81b7` |
| `resources/onchain-position-data.md` | `3f6b9e31b5eecd4a7ab0f2d303a17ea2c75ea4364d5d034c69cf57de672ae5de` |
| `resources/contracts.md` | `64ff1d4a6c51afb7cfda55de05ed5b3b417e4846ed13f7dcf4d85dae9d0a7113` |
| `trading/fees.md` | `7409b13c646126ff1c3bacc478c0594a7b3db2a2e735fcdf6ddb59b3fdc44035` |
| `trading/matching-engine.md` | `e064c6d50ac3b7de501346c736d24eef74e22ad0aa2049677eaf4b5a163c1498` |
| `changelog/predictions.md` | `ff37e36331c9b7766e55f9aeda0077e6b3b354a95b635561f124c412ff7b11cd` |
| `migrate/data-api-v1-to-v2.md` | `96955b89c27fe908979a73fbb77d31b30c50f9f5fdebca211b009c4ffb0d05fd` |
| `migrate/rtds-to-polybolt.md` | `6e97f169e3a4562e9c3252a36fbadd4d394d1defe1a0aa18f8d8347bb5586bd8` |
| `migrate/polymarket-v2/overview.md` | `4a680ef8f3d25279f528f8da83d5a27b39e5903de50834cd37b11401c8ee9d89` |

Not fetched: `https://data-api.polymarket.com/v2/openapi.json` and `https://ws-live-v2.polymarket.com/asyncapi.json`, which are listed in `llms.txt`. Both are on API hosts, which the hard rules exclude. Their relevant content is embedded in the docs pages above.

### polymarket.com Terms of Use page (attempted; body not retrievable)
- URL: https://polymarket.com/tos
- Retrieved: 2026-10-16. HTTP 200, SHA-256 `b2199996060a6242e14f70c7e0197a576bd35f87041e514036054f0c7ac2cc8d`
- Used for: only the served banner "Trading is blocked in the United States on polymarket.com. Switch to polymarket.us". The terms text is JS-rendered and was not in the HTML.
- Source type: official venue page
- Verification status: observed page content (banner only). Data-use terms UNRESOLVED.

### KalshiEX CFTC filing: BTC contract amendment (Rule 40.6), 2024-11-12
- URL: https://www.cftc.gov/sites/default/files/filings/orgrules/24/11/rules1112248590.pdf
- Retrieved: 2026-10-16. SHA-256 `ad45dba4b3863d7286842a2b647ef2ac885a6999ffe53d8892b27ad4326fe5b3`
- Used for: BTC rulebook Underlying changed from 300 s to a 60 s BRTI average "excluding the highest and lowest 20% of values", effective 2024-11-27. Source Agency CF Benchmarks.
- Source type: primary source (regulatory filing). Text was extracted with a local stdlib script. The PDF was treated as data, not executed.
- Verification status: documented statement

### KalshiEX CFTC filing: CRYPTO rulebook contract, 2025-07-18
- URL: https://www.cftc.gov/sites/default/files/filings/ptc/25/07/ptc07182526860.pdf
- Retrieved: 2026-10-16. SHA-256 `d6864df0bdcf33e0e55775ccd3e08e4db76c1ecf4515229882678b8d0ea4e765` (a WebFetch copy had identical bytes)
- Used for: CRYPTO rulebook, a 60 s simple average of the CF index; "no data → affected strikes resolve to No"; Source Agency CF Benchmarks
- Source type: primary source (regulatory filing)
- Verification status: documented statement

### KalshiEX CFTC filing: CRYPTOSHORT rulebook contract, 2026-03-11
- URL: https://www.cftc.gov/sites/default/files/filings/ptc/26/03/ptc03112640675.pdf
- Retrieved: 2026-10-16. SHA-256 `880a5516c31a8dbcebeffeb3ee3b265622eaaecf159494aed940fb7fe92ea8e2`
- Used for: CRYPTOSHORT with a configurable `<lookbackduration>`; rounding before comparison; "no data → last piece of data available"; post-expiration CF corrections ignored; times in ET
- Source type: primary source (regulatory filing)
- Verification status: documented statement. Applicability to KXBTC15M is UNRESOLVED.

### GitHub READMEs and schema docs (raw.githubusercontent.com)
- Retrieved: 2026-10-16
- Used for: dataset and tool descriptions, licences, coverage claims, and known pitfalls (V2 migration, double counting)
- Source type: secondary (third-party repositories). Not cloned; no code was run.
- Verification status: claims by the authors, unverified

| Repository / file | SHA-256 |
|---|---|
| `Jon-Becker/prediction-market-analysis` README | `9596ded62210245b634814f9c99bf0560d05635ea0610cc8e78687da5bda9d71` |
| `Jon-Becker/prediction-market-analysis` docs/SCHEMAS.md | `5e2746fe38c0e2e871fe0806bb5ac49af409cb4387fb5f09e2e12fd07ec6547a` |
| `warproxxx/poly_data` README | `c5a4a3cb8ae14dcb9fb6b9d41a2b468f78338bca38124deb4e6a1f2e3c9f41b0` |
| `Polymarket/polymarket-subgraph` README (official) | `a0940caf7ed68f1837c20443dff41446d95360dbefcb01361d0d05728c48c171` |
| `Polymarket/agent-skills` market-data.md (official) | `447dafa4cabe127f8de9f7a38d900d09ca4ae5143e850fabdce3893e48f3c5bf` |
| `PaulieB14/polymarket-v2-subgraphs` README | `96271893caab25b02be44d8cb877d94d762654beee25b04f0b1faeab5b215e49` |
| `jdkatz21/Prediction_Markets_Public` README | `32613a1da34acd401904e2c92ff1e277b691a35c5336a081a0fdd373f0b8482e` |
| `marketlenstrade/polymarket-historical-data` README | `1e6f3446b01970cd3d2aaca7cb02ed657551235c263f79f8c270721cf3028745` |
| `JasonJSant/polymarket-skilled-traders` README | `8d5a096e36096ab320cf049ae5c6dd359b006f6503ce5a73ee78a37ee79e12ac` |
| `manja316/polymarket-historical-data` README | `d692fd73333ce3231537bfd9155ed269e0557203584ec4b554d75626cf6271e5` |
| `Polymarket/agents` README (ToS statement; grep only) | not hashed |

### Hugging Face dataset cards (README.md via `huggingface.co/datasets/<id>/raw/main/README.md`; no viewer, no files)
- Retrieved: 2026-10-16
- Used for: coverage, schema, timestamp, licence, and provenance claims
- Source type: secondary (dataset publishers)
- Verification status: claims by the publishers, unverified

| Dataset | SHA-256 of card |
|---|---|
| `TrevorJS/kalshi-trades` | `b9ec30d19b183b03f017470b2c42b7440de4a11ab4f7abbba161ad9f04e3de63` |
| `DegenHedge/kalshi-btc-15m` (incidental exposure; see inventory) | `a91a55a2406f850f6423e99c730a3da81bf111e5793af503e31fc2d2a1d3f28c` |
| `lerchen3/kalshi-orderbook-alpha` | `c87c603b276b1d7ac08b842fd101319377dcad97561789cdf3ad6280661c1916` |
| `carpetxie/winniethepooh` | `494818940e92370a4a154c77376d83bfd7574348d41f948bd1b7cfd3e95a8b80` |
| `thomaswmitch/kalshi-prediction-markets-betting` | `a3646dc628a16ee6a39cdcd20beccd33460b0edc41748e5ae5f2f64e7b0e1740` |
| `thomaswmitch/kalshi-prediction-markets-markets` | `adea36be2c8b31151d518846dea435a426cb30245ca2154bda923a7bae9f0a33` |
| `SII-WANGZJ/Polymarket_data` | `04addcffb36d97d7facaa5f544a7f5079dc73861e4d78e3c62659744f4c9dffc` |
| `TimeSeventeen/Polymarket-v1` | `617f19d07415bcc4c4e06ad30a86bac703affd03a805c57f87c3432a1b699f36` |
| `benjessel/polymarket_trades` | `db36d7a190075719e8bfde2b28bba10555bc184e9d44bfe672fd89ee845c426d` |
| `BrockMisner/polymarket-btc-updown` | `eab1209e2050d79a3bb5841fca4b9e834a43ccd3cadca4476be38a671e2dd4ae` |
| `sadaftkhan/sayf-episodes` (HTTP 401, gated) | `c18354b67a4658bc603a631038c7442f703b86b4ad54b894e1ebf06e4bc9d415` (error body) |

### arXiv 2606.04217, "Polymarket-v1 Database" (abstract page)
- URL: https://arxiv.org/abs/2606.04217
- Retrieved: 2026-10-16. SHA-256 `6c1a7ae3e4c913538637b84b3eaf25fefa0d88b6877dd3e3b833ae15b5066c06`
- Used for: coverage (2022-11-21 to 2026-04-28, V1 only) and the ground-truth aggressor claim for T9
- Source type: secondary (preprint)
- Verification status: authors' claim

### Kaggle dataset page `hugobde/polymarket-bitcoin-15min-up-or-down` (metadata only)
- URL: https://www.kaggle.com/datasets/hugobde/polymarket-bitcoin-15min-up-or-down
- Retrieved: 2026-10-16. SHA-256 `f7f87efdf29d49b599cdd8328f44da71c4c6fe21c0a7aa84eb2cc734d444b3ec`
- Used for: title, and licence "Unknown" from the page JSON. The coverage description came from a search snippet. The data tab was not opened.
- Source type: secondary
- Verification status: page metadata

### WebSearch discovery results (not fetched pages)
- Retrieved: 2026-10-16
- Used for: SECONDARY claims only:
  - KXBTC15M rules (BRTI 60 s, tie → YES);
  - KXGOLD15M (Pyth GOLD 1-minute close, launched around August 2026);
  - Polymarket gold daily markets on Pyth;
  - the pre-2026-08-07 Polymarket Chainlink Data Streams snapshot;
  - Polymarket US (separate venue, BTC 15m launched around 2026-09-22, conflicting settlement-source claims, no public tape);
  - the locator of `kalshi-public-docs.s3.amazonaws.com/contract_terms/CRYPTO15M.pdf`;
  - vendor coverage claims (Marketlens, PolymarketData.co, PolyHistorical, PMData, PolyOrderbooks).
- Source type: secondary (search-engine summaries of third-party sites)
- Verification status: assumption until verified against the official sources in AR-A1, AR-A3, AR-A5, AR-A6, and AR-3

### Refused or not attempted (no content)
- Proxy-refused: docs.goldsky.com, thegraph.com, docs.dune.com, dune.com, docs.uma.xyz, oracle.uma.xyz, docs.chain.link, data.chain.link, docs.cfbenchmarks.com, learn.polymarket.com, docs.polymarket.us, polymarketexchange.com, integrity.polymarket.com, www.polymarketdata.co, polyhistorical.com, pmdata.dev, polyorderbooks.com, marketlens.trade, www.telonex.io, predictionmarketspicks.com, calipermarkets.com, www.pyth.network, docs.pyth.network, pythdata.app, docs.allium.so, crypto.clickhouse.com, polygonscan.com, docs.envio.dev, degenhedge.com
- Anti-bot: kalshi.com (HTTP 429; AR-3)
- Not attempted (outside D1, needs its own access request): help.kalshi.com, kalshi-public-docs.s3.amazonaws.com
- Reachable but deliberately not used: web.archive.org (archive or mirror routes to blocked content are prohibited); www.cfbenchmarks.com (reference-feed scope, not section A)

### Batch 3 group: BTC and gold underlyings and reference sources (sections B, C)

These entries use the format of `research/sources.md`. They are staged here for review and are not yet appended there. Retrieval date for every entry: **2026-10-16 (UTC)**, between 02:15Z and 02:31Z. Each SHA-256 covers the bytes as retrieved by `curl` through the sandbox egress proxy. HTML pages change often, so a hash only identifies the retrieved copy. Where no hash is given, the content came from a WebSearch summary and is SECONDARY. No market-data API host was contacted. Kalshi documentation was accessed under AR-1 (docs only).

### CF Benchmarks: BRTI index page
- URL: https://www.cfbenchmarks.com/data/indices/BRTI
- Retrieved: 2026-10-16
- Used for: BRTI publication frequency; the provider's statement that BRTI is the settlement input for Kalshi event contracts; licensing statements; the website terms that prohibit automated access (after which no further fetches were made)
- Source type: official documentation (benchmark administrator)
- Verification status: documented statement
- SHA-256: `ade8b08c5fe9c7540462ee57a8d213395829c3f8fe578a2aa23c055bf9c8abab`

### Kalshi docs: CF Benchmarks REST Passthrough
- URL: https://docs.kalshi.com/cfbenchmarks/rest-passthrough.md
- Retrieved: 2026-10-16 (AR-1)
- Used for: availability of historical, tick-level BRTI values through the authenticated, entitlement-gated Kalshi passthrough
- Source type: official documentation
- Verification status: documented statement
- SHA-256: `bf0ef09aae3c97542090c17bce999e04441f830e6db390c6d392e67929996b51`

### Kalshi docs: Pyth Value Feed
- URL: https://docs.kalshi.com/websockets/pyth-value.md
- Retrieved: 2026-10-16 (AR-1)
- Used for: Pyth gold feed symbols and IDs (`Metal.XAU/USD` 346, `Metal.Index.GOLD/USD` 3153, `Metal.Index.1OZGOLD/USD` 3712); price of USD 1,000/month; timestamp handling
- Source type: official documentation
- Verification status: documented statement
- SHA-256: `70c0e8062402b316e6398bf86e079eafb74ca905606c1f8a60858664f11a0a5b`

### Kalshi docs index (llms.txt)
- URL: https://docs.kalshi.com/llms.txt
- Retrieved: 2026-10-16 (AR-1); hash identical to the batch 2 copy
- Used for: locating the reference-feed pages
- Source type: official documentation
- Verification status: documented statement
- SHA-256: `4b97d36e6e5c0b949d0a9bdced42fe0499be277a0a9c2dc8f66342fae14520f0`

### Polymarket docs: Resolution
- URL: https://docs.polymarket.com/concepts/resolution.md
- Retrieved: 2026-10-16
- Used for: Chainlink TWAP as the resolution source for up/down markets; tie rule (Up when final price ≥ price to beat)
- Source type: official documentation
- Verification status: documented statement
- SHA-256: `2264660d3f55b7d3df875d73b68098d7d62c1489cdd252bd846932e3088cd047`

### Polymarket docs: Predictions changelog
- URL: https://docs.polymarket.com/changelog/predictions.md
- Retrieved: 2026-10-16
- Used for: TWAP resolution from 2026-08-07; 5-minute markets moved to a 60-second window on 2026-08-14; PolyBolt `source` field and Chainlink default (2026-09-29 and 2026-10-02)
- Source type: official documentation
- Verification status: documented statement
- SHA-256: `ff37e36331c9b7766e55f9aeda0077e6b3b354a95b635561f124c412ff7b11cd`

### Polymarket docs: Real-Time Data (Chainlink TWAP / reference prices)
- URL: https://docs.polymarket.com/market-data/chainlink-twap
- Retrieved: 2026-10-16
- Used for: TWAP `windowSeconds: 60` lookback semantics; snapshot of two minutes of history; payload timestamp fields; `xauusd` reference symbol; carried-forward handling
- Source type: official documentation
- Verification status: documented statement. Example payloads are illustrations and were not read as data.
- SHA-256: `4cc6b7b91de6207101804b5026a40117f97827ed4995c2cb3d94f1e8698da244`

### Polymarket docs: RTDS to PolyBolt migration; docs index
- URLs: https://docs.polymarket.com/migrate/rtds-to-polybolt.md ; https://docs.polymarket.com/llms.txt
- Retrieved: 2026-10-16
- Used for: navigation only
- Source type: official documentation
- Verification status: documented statement
- SHA-256: `6e97f169e3a4562e9c3252a36fbadd4d394d1defe1a0aa18f8d8347bb5586bd8` ; `bc1dd18d474ffad8154e7939c4b8e013d99b91895b67cecef112a53bb99888eb`

### Coinbase Exchange docs: candles, trades, WebSocket channels, pagination
- URLs: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles.md ; .../get-product-trades.md ; https://docs.cdp.coinbase.com/exchange/websocket-feed/channels.md ; https://docs.cdp.coinbase.com/exchange/rest-api/pagination.md ; index https://docs.cdp.coinbase.com/_llms/api-reference/coinbase-exchange-api.txt
- Retrieved: 2026-10-16
- Used for: candle granularities and limits; candle incompleteness warning; trade_id pagination; level2 now requiring authentication; level2_batch at 50 ms; sequence numbers
- Source type: official documentation
- Verification status: documented statement
- SHA-256: candles `ce66414274ecc32b6c5317d6a595f8e131f7db602596b9cad0bac485e987548f`; trades `4cbf49585ca519b91f8374751059cf16f1a41c27cb8797a544e2f799a4f59464`; channels `21b5c86683e63f322c6edd7735d27e7016a0a52d11fbc654fa3ad932f8b552dc`; pagination `ce96bdac919a320f41ffc0c9d6abba00053d4f0ad6c9a4580018762c23b304f7`; index `e381926dde3f0af97a56b485d69036bfa5a319f24e25bec8a9b097d3c2566050`

### Kraken API docs (landing page and llms.txt)
- URLs: https://docs.kraken.com/api/ ; https://docs.kraken.com/llms.txt
- Retrieved: 2026-10-16
- Used for: WebSocket v2 book/level3 channels and CRC32 checksums
- Source type: official documentation
- Verification status: documented statement
- SHA-256: landing `29c8acc1a04cbf49202806909f9631daca64c8555d88a0cd80512d7c3b3cac92`

### Kraken downloadable historical data (support articles 360047543791 and 360047124832)
- URL: https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales- ; https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data
- Retrieved: not fetched (WebSearch summary 2026-10-16)
- Used for: archive coverage (trades through 2026-09-30, OHLCVT through 2026-06-30), part files, SHA-256 sums
- Source type: official documentation (via secondary summary)
- Verification status: assumption until fetched (AR-U5)

### Binance public data README and Vision Dataset Terms
- URLs: https://github.com/binance/binance-public-data/blob/master/README.md ; https://raw.githubusercontent.com/binance/binance-public-data/master/TERMS_AND_CONDITIONS.md
- Retrieved: 2026-10-16
- Used for: dataset types; microsecond timestamps from 2025-01-01; archive updates and checksums; **licence CC BY-NC-SA 4.0 with a prohibition on live proprietary trading use (terms v1.0, updated 2026-08-26)**
- Source type: official documentation (the provider's GitHub repository)
- Verification status: documented statement
- SHA-256: README page `0f54390aa2573f10e09c7b9f0333b2abf725cefee48b9c20d51ee4320c3652e2`; terms `dcf358e9d18f598a7a635fac80f6e643fa24a0e111a4d39bda47f1e246b31eb1`

### Databento blog: CME history extended to 2010
- URL: https://databento.com/blog/CME-history-extended-to-2010
- Retrieved: 2026-10-16
- Used for: GLBX.MDP3 coverage from 2010-06-06; MBO only from 2017-05-21; tag-52 timestamps and `F_BAD_TS_RECV` before 2017-05-21
- Source type: official documentation (vendor)
- Verification status: documented statement
- SHA-256: `73c0a6af1898798fd0c81cd79f814749f4937b0580cd93825271a1b5beef5b9a`

### Databento blog: Upcoming changes to CME data normalization
- URL: https://databento.com/blog/cme-normalization-changes-2026-07
- Retrieved: 2026-10-16
- Used for: retroactive renormalization of the full history at the 2026-08-08 cutover (F_LAST record, per-leg definitions, price limits, implied matching status)
- Source type: official documentation (vendor)
- Verification status: documented statement
- SHA-256: `bad78d7767252fa3b9631ed3b563b04f1d0942070bddaac9ed7d05b137d0af54`

### Databento blog: new CME pricing plans; exchange licence fees FAQ
- URLs: https://databento.com/blog/introducing-new-cme-pricing-plans ; https://databento.com/blog/understanding-exchange-fees
- Retrieved: 2026-10-16
- Used for: usage-based historical pricing retained; licensing referral process
- Source type: official documentation (vendor)
- Verification status: documented statement (2025 plan prices are superseded; current prices are SECONDARY)
- SHA-256: `80d588f1fefa06b2b3ac59b39f8139e7d05950177722f3ac310908be4cf51c50` ; `1aed25e0e4c791b6202cb81d175c6689c5a10192869280795c81fa47185bacae`

### Databento blog: Core Indices; historical CME event contract data
- URLs: https://databento.com/blog/databento-core-indices ; https://databento.com/blog/historical-cme-event-contract-data
- Retrieved: 2026-10-16
- Used for: DBIX.CORE crypto index providers (no CF Benchmarks listed); CME event contracts on Bitcoin and Gold in GLBX.MDP3 from 2025-09-25
- Source type: official documentation (vendor)
- Verification status: documented statement
- SHA-256: `5c53c6d18ef808f6b2f613eb64abc9d7b13d00447ddaef214947bd10a20ac70f` ; `55576aaf276b8a4cdfea7eb21dce8a7d0a01f412bfa402d5f3e3aea7d9fdadf0`

### Databento GLBX.MDP3 docs and pricing pages
- URLs: https://databento.com/docs/venues-and-datasets/glbx-mdp3 ; https://databento.com/pricing
- Retrieved: 2026-10-16 (JavaScript shells, no usable content)
- Used for: nothing (recorded as a source-access limitation)
- Source type: official documentation
- Verification status: not usable
- SHA-256: `ea3c0d4de144020a714ce7e12f554c96111a6ba692d6c7aff795a0844847a5e5` ; `9470ffac8372982123f75ba7a3b497ef41d49f6da73a1696d59b08462fe8e9e9`

### CME Group datamine_python README (GitHub)
- URL: https://github.com/CMEGroupPublic/datamine_python
- Retrieved: 2026-10-16
- Used for: DataMine dataset tags (TICK, MBO, CRYPTOCURRENCY with second-interval BRTI, STL); CME's own reference for its datasets
- Source type: official documentation (CME's public repository)
- Verification status: documented statement
- SHA-256: `79fbbe7f81b513769eafd590c308a6b2bb6890c717b849596308aa670235b279`

### LBMA: LBMA Gold Price page
- URL: https://www.lbma.org.uk/prices-and-data/lbma-gold-price
- Retrieved: 2026-10-16
- Used for: IBA administration; requirement for a usage licence; list of direct participants
- Source type: official documentation
- Verification status: documented statement
- SHA-256: `daa4b5bae721201a3506dc637a0446427fb01d5cc3da8fd122ff2adeeb9de0f0`

### ICE Benchmark Administration: LBMA Gold Price
- URL: https://www.ice.com/iba/lbma-gold-price
- Retrieved: 2026-10-16
- Used for: auction times (10:30 and 15:00 London), round mechanics, licensing, holiday calendars
- Source type: official documentation (administrator)
- Verification status: documented statement
- SHA-256: `c0d1e6440ed36a4f9e2f51ccf8281c9cdc27fd502f52f700bdd4bc436305e776`

### Kaiko docs: timestamp, tick-level trades, raw order book snapshot
- URLs: https://docs.kaiko.com/rest-api/general/getting-started/api-output/timestamp.md ; https://docs.kaiko.com/rest-api/cefi-spot-market-data/tick-level-trades.md ; https://docs.kaiko.com/cloud-delivery/cefi-spot-market-data/raw-order-book-snapshot.md ; index https://docs.kaiko.com/llms.txt
- Retrieved: 2026-10-16
- Used for: UTC millisecond timestamps; trade timestamp is either the exchange's or Kaiko's collection time; book snapshots at least once per minute, to 10% depth, stamped at request time
- Source type: official documentation (vendor)
- Verification status: documented statement
- SHA-256: `056cd8698ad0f1a3517a39e84546b004c3654323a841e906966bdeb4d85b101b` ; `e220b18826fc6e4424b24be3223834aa39f943bc740ab05c112ae4bcad32f6b6` ; `a9887948dd73ca84203d27be9885cbef705f56d1f22752268dc7fded17e8b44e` ; `efa7b848fe2f3842eca945df64d1bb37c88b9c2a0550e6250e8490717d78f05b`

### Coin Metrics docs landing page
- URL: https://docs.coinmetrics.io/
- Retrieved: 2026-10-16
- Used for: product structure only; detail pages blocked
- Source type: official documentation (vendor)
- Verification status: documented statement (structure only)
- SHA-256: `0ca784cee6102c3b14e99edc49c383a3ca60affdc0ccc7f09eb2340af4cb021b`

### CFTC filing: KalshiEX LLC, 2026-09-08 (GOLDPERP)
- URL: https://www.cftc.gov/filings/ptc/ptc09082624176.pdf
- Retrieved: 2026-10-16
- Used for: nothing substantive. The text could not be extracted, and the WebFetch summary was hallucinated and discarded.
- Source type: primary source (regulatory filing)
- Verification status: unread
- SHA-256: `19fca70eab778293c36c5de96ad2033462690fdeeaa70c1debc755fe1f556df5`

### Secondary sources used only as leads (WebSearch summaries; not fetched; no hashes)
- Tardis.dev docs (coverage, `local_timestamp`, pricing, ToS): https://docs.tardis.dev/historical-data-details/coinbase, .../kraken, .../bitstamp, .../gemini, https://docs.tardis.dev/faq/billing-and-subscriptions, https://docs.tardis.dev/legal/terms-of-service: secondary; assumption.
- CF Benchmarks constituent list and RTI methodology v17: https://docs.cfbenchmarks.com/CME%20CF%20Constituent%20Exchanges.pdf, https://docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf: secondary (official documents not fetched because of the site terms); assumption.
- Chainlink Data Streams docs (REST API, v2 schema, report timestamps, sign-up): https://docs.chain.link/data-streams/...: secondary; assumption.
- Pyth blog and Pyth Indices press release: https://www.pyth.network/blog/24-7-finance-needs-24-7-price-infrastructure-introducing-pyth-indices, https://www.businesswire.com/news/home/20260610193791/en/: secondary; assumption.
- Third-party Kalshi and Polymarket rule explainers (predictionmarketspicks.com, calipermarkets.com, genfinity.io, tradoxvps.com): secondary; assumption. The venue agent must verify against official rules.
- Databento CME licensing and plan prices (roadmap, X post, third-party comparisons); CME fee list mirror at api.databento.com (not fetched: API host): secondary; assumption.
- CME GC settlement procedure, contract specs, 1OZ FAQ, 24/7 press release, DataMine overview, DDLA/ILA: https://www.cmegroup.com/... (site blocks automated clients): secondary; assumption. Owner-supplied copies requested (AR-U6).
- FRED notice on removal of IBA data (2022-01-31): https://fred.stlouisfed.org/series/GOLDAMGBD228NLBM (not fetched; the page displays values): secondary; assumption.
- Gold futures vendors (Tick Data, AlgoSeek, PortaraCQG, Kibot, FirstRate, Barchart, Norgate, Nasdaq Data Link CHRIS GitHub issue); Dukascopy; OANDA licence PDFs: secondary; assumption.
- Coin Metrics community terms, CoinDesk Data (CCData), Amberdata, Gemini Market Data Agreement, Bitstamp and Bullish API behaviour: secondary; assumption.

### Batch 3 group: Open datasets, literature, software, regulatory (sections D, E, F)

Status: research record, not an approved requirement. Entries are in research/sources.md format, staged for append. Retrieval date for all: 2026-10-16 (UTC). Documentation and metadata only; no dataset files opened and no market values used.

### Hugging Face Hub datasets API (metadata only)
- URL: https://huggingface.co/api/datasets
- Retrieved: 2026-10-16
- Used for: discovery and metadata (license, revision SHA, file paths) for all HF records in section D
- Source type: secondary (platform metadata)
- Verification status: observed behavior (metadata as served)

### TrevorJS/kalshi-trades dataset card
- URL: https://huggingface.co/datasets/TrevorJS/kalshi-trades
- Retrieved: 2026-10-16
- Used for: D-K1 schema, coverage, provenance claims
- Source type: secondary (third-party redistribution)
- Verification status: documented claim by redistributor

### jon-becker/prediction-market-analysis README
- URL: https://github.com/jon-becker/prediction-market-analysis
- Retrieved: 2026-10-16
- Used for: D-K2 dataset and indexers; list of papers using it
- Source type: secondary
- Verification status: documented claim

### DegenHedge/kalshi-btc-15m dataset card
- URL: https://huggingface.co/datasets/DegenHedge/kalshi-btc-15m
- Retrieved: 2026-10-16
- Used for: D-K5 settlement-rule description and provenance; incidental exposure G-1
- Source type: secondary
- Verification status: documented claim

### lerchen3/kalshi-orderbook-alpha dataset card
- URL: https://huggingface.co/datasets/lerchen3/kalshi-orderbook-alpha
- Retrieved: 2026-10-16
- Used for: D-K6 recorder design and timestamp semantics
- Source type: secondary
- Verification status: documented claim

### SII-WANGZJ/Polymarket_data dataset card
- URL: https://huggingface.co/datasets/SII-WANGZJ/Polymarket_data
- Retrieved: 2026-10-16
- Used for: D-P1 on-chain OrderFilled schema, coverage, revision history
- Source type: secondary (primary-verifiable on Polygon)
- Verification status: documented claim

### vgregoire/polymarket-users dataset card
- URL: https://huggingface.co/datasets/vgregoire/polymarket-users
- Retrieved: 2026-10-16
- Used for: D-P1 academic replication dataset, sample period, ToS caveat
- Source type: secondary
- Verification status: documented claim

### Joseph3222/polymarket-orderbook dataset card (pmxt-derived)
- URL: https://huggingface.co/datasets/Joseph3222/polymarket-orderbook
- Retrieved: 2026-10-16
- Used for: D-P2 historical Polymarket book coverage, gaps, timestamp resolution
- Source type: secondary
- Verification status: documented claim

### mileswangs/polymarket-btc-updown-5m-orderbook-tick-data dataset card
- URL: https://huggingface.co/datasets/mileswangs/polymarket-btc-updown-5m-orderbook-tick-data
- Retrieved: 2026-10-16
- Used for: D-P2 dual-timestamp WebSocket and Chainlink recording design
- Source type: secondary
- Verification status: documented claim

### aliplayer1/polymarket-crypto-updown dataset card
- URL: https://huggingface.co/datasets/aliplayer1/polymarket-crypto-updown
- Retrieved: 2026-10-16
- Used for: D-P2 crypto up/down markets, ticks, BBO, spot feeds
- Source type: secondary
- Verification status: documented claim

### polyorderbooks/polymarket-crypto-updown-orderbooks-l2 dataset card (Zenodo 10.5281/zenodo.22084114)
- URL: https://huggingface.co/datasets/polyorderbooks/polymarket-crypto-updown-orderbooks-l2
- Retrieved: 2026-10-16
- Used for: D-P2 1-second L2 capture method
- Source type: secondary
- Verification status: documented claim

### delmiron27/cryptolake-binance-futures-btc dataset card
- URL: https://huggingface.co/datasets/delmiron27/cryptolake-binance-futures-btc
- Retrieved: 2026-10-16
- Used for: D-B2 flagged as probable vendor-terms breach
- Source type: secondary
- Verification status: documented claim

### CarlosSilva1/xauusd-ticks dataset card
- URL: https://huggingface.co/datasets/CarlosSilva1/xauusd-ticks
- Retrieved: 2026-10-16
- Used for: D-G1 gold tick provenance (unnamed broker)
- Source type: secondary
- Verification status: documented claim

### Kaggle public datasets list API
- URL: https://www.kaggle.com/api/v1/datasets/list
- Retrieved: 2026-10-16
- Used for: discovery of Kaggle Polymarket/Kalshi/BTC/gold datasets (titles, licenses)
- Source type: secondary (platform metadata)
- Verification status: observed behavior

### Harvard Dataverse doi:10.7910/DVN/KHX5QY (Chernoff 2026)
- URL: https://doi.org/10.7910/DVN/KHX5QY
- Retrieved: 2026-10-16
- Used for: D-P4 matched-pair metadata, CC0
- Source type: secondary
- Verification status: documented claim

### Young (2026) OpenMarket, arXiv:2607.26245
- URL: https://arxiv.org/abs/2607.26245
- Retrieved: 2026-10-16
- Used for: E#3 null-result analogue and paired corpus
- Source type: primary (research paper)
- Verification status: documented claim (abstract)

### Lee et al. (2026) Cryptocurrency prediction markets through the derivatives lens, IRFA
- URL: https://doi.org/10.1016/j.irfa.2026.105433
- Retrieved: 2026-10-16
- Used for: E#2 digital-option view of BTC 15m on both venues
- Source type: primary (research paper)
- Verification status: citation verified via Crossref; content via search summary

### Bürgi, Deng, Whelan, Makers and Takers (SSRN 5502658)
- URL: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5502658
- Retrieved: 2026-10-16
- Used for: E#1 Kalshi FLB and maker/taker returns
- Source type: primary (research paper)
- Verification status: search-result metadata

### Dai, Jia, Yu (2026) Settlement Manipulation in Prediction Markets, arXiv:2606.31675
- URL: https://arxiv.org/abs/2606.31675
- Retrieved: 2026-10-16
- Used for: E#4 settlement-window manipulation risk
- Source type: primary (research paper)
- Verification status: documented claim (abstract)

### Dubach (2026) Anatomy of a Decentralized Prediction Market, arXiv:2604.24366
- URL: https://arxiv.org/abs/2604.24366
- Retrieved: 2026-10-16
- Used for: E#5 feed vs chain timestamp and direction
- Source type: primary (research paper)
- Verification status: documented claim (abstract)

### Qin, Yang (2026) Polymarket-v1 Database, arXiv:2606.04217
- URL: https://arxiv.org/abs/2606.04217
- Retrieved: 2026-10-16
- Used for: E#6 ground-truth aggressor side; OFI/VPIN bias
- Source type: primary (research paper)
- Verification status: documented claim (abstract)

### Cont, Kukanov, Stoikov (2014) The Price Impact of Order Book Events
- URL: https://doi.org/10.1093/jjfinec/nbt003
- Retrieved: 2026-10-16
- Used for: E#17 OFI feature
- Source type: primary (research paper)
- Verification status: citation verified via Crossref

### Kull, Silva Filho, Flach (2017) Beta calibration, PMLR 54
- URL: https://proceedings.mlr.press/v54/kull17a.html
- Retrieved: 2026-10-16
- Used for: E#32 calibration method
- Source type: primary (research paper)
- Verification status: search-result metadata

### Gneiting, Raftery (2007) Strictly Proper Scoring Rules
- URL: https://doi.org/10.1198/016214506000001437
- Retrieved: 2026-10-16
- Used for: E#28 scoring rules
- Source type: primary (research paper)
- Verification status: citation verified via Crossref

### Bailey, Borwein, López de Prado, Zhu (2016) Probability of Backtest Overfitting
- URL: https://doi.org/10.21314/JCF.2016.322
- Retrieved: 2026-10-16
- Used for: E#35 PBO
- Source type: primary (research paper)
- Verification status: citation verified via Crossref

### Bailey, López de Prado (2014) The Deflated Sharpe Ratio
- URL: https://doi.org/10.3905/jpm.2014.40.5.094
- Retrieved: 2026-10-16
- Used for: E#36 DSR
- Source type: primary (research paper)
- Verification status: citation verified via Crossref

### Howard, Ramdas, McAuliffe, Sekhon, Time-uniform confidence sequences, arXiv:1810.08240
- URL: https://arxiv.org/abs/1810.08240
- Retrieved: 2026-10-16
- Used for: E#40 always-valid monitoring
- Source type: primary (research paper)
- Verification status: citation verified via arXiv page

### Baker, McHale (2013) Optimal Betting Under Parameter Uncertainty
- URL: https://doi.org/10.1287/deca.2013.0271
- Retrieved: 2026-10-16
- Used for: E#43 uncertainty-adjusted Kelly
- Source type: primary (research paper)
- Verification status: citation verified via Crossref

### Shin (1993) Measuring the Incidence of Insider Trading in a Market for State-Contingent Claims
- URL: https://doi.org/10.2307/2234240
- Retrieved: 2026-10-16
- Used for: E#45 margin removal
- Source type: primary (research paper)
- Verification status: citation verified via Crossref

### Andersen, Bollerslev, Diebold, Vega (2003) Micro Effects of Macro Announcements
- URL: https://doi.org/10.1257/000282803321455151
- Retrieved: 2026-10-16
- Used for: E#27 basis for macro release-time features
- Source type: primary (research paper)
- Verification status: citation verified via Crossref

### Aït-Sahalia, Mykland, Zhang (2005) How Often to Sample… Microstructure Noise
- URL: https://doi.org/10.1093/rfs/hhi016
- Retrieved: 2026-10-16
- Used for: E#21 RV under noise
- Source type: primary (research paper)
- Verification status: citation verified via Crossref

### GitHub REST API repository metadata (license, pushed_at, archived) for E.6 projects
- URL: https://api.github.com/repos/
- Retrieved: 2026-10-16
- Used for: software license and maintenance status
- Source type: secondary (platform metadata)
- Verification status: observed behavior

### CFTC press release 8302-20, CFTC Designates KalshiEX LLC as a Contract Market
- URL: https://www.cftc.gov/PressRoom/PressReleases/8302-20
- Retrieved: 2026-10-16
- Used for: F-1 venue legal basis
- Source type: official documentation
- Verification status: documented (title verified)

### CFTC press releases 9194-26, 9249-26, 9310-26, 9179-26 (2026 event-contract rulemaking track)
- URL: https://www.cftc.gov/PressRoom/PressReleases/9249-26
- Retrieved: 2026-10-16
- Used for: F-2 regulatory change risk
- Source type: official documentation
- Verification status: titles and dates verified; content via search summary

### CFTC press release 8478-22, Polymarket (Blockratize) $1.4M penalty
- URL: https://www.cftc.gov/PressRoom/PressReleases/8478-22
- Retrieved: 2026-10-16
- Used for: F-4 Polymarket jurisdiction context
- Source type: official documentation
- Verification status: documented (title verified)

### CFTC Commitments of Traders index
- URL: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
- Retrieved: 2026-10-16
- Used for: F-7 COT availability
- Source type: official documentation
- Verification status: page reachable; content not analysed

### BEA release schedule
- URL: https://www.bea.gov/news/schedule
- Retrieved: 2026-10-16
- Used for: F-5 macro release-time calendar
- Source type: official documentation
- Verification status: page reachable
