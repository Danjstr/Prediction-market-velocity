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
