# B09: Kalshi official historical data, source qualification (analysis)

**Status:** research record for B09 (`b09/kalshi-source-qualification`). It is not a gate record, an owner decision, an acquisition approval, or a licence determination. The owner decisions it prepares are in `docs/decisions/2026-10-16_b09_kalshi_source_qualification.md` ("Owner-decision packet").

**What B09 did not do:**
- acquire, request, view, or derive any real market observation;
- contact any Kalshi host or any other external host (the only network traffic was `git fetch` and `git push` to `origin`);
- use, create, or request a credential, account, or API key;
- accept any terms on the owner's behalf;
- change production code.

**Evidence base.** Every Kalshi documentation fact below comes from the batch 2 snapshot already in Git:
- `research/kalshi/api_documentation_findings.md` and `research/kalshi/venue_verification.md`;
- the source table in `research/sources.md`: 60 files from `docs.kalshi.com`, retrieved 2026-10-15 between 23:58:51Z and 23:59:57Z, with a SHA-256 hash for each; `openapi.yaml` 3.34.0, hash prefix `a33d05aaa5deab31`; `asyncapi.yaml` 2.0.0, hash prefix `3c86bae7d89b44ba`.

Batch 3 inventory facts come from `research/historical_data/inventory_prediction_markets.md`, and are SECONDARY wherever that file says so.

The local copies of the batch 2 pages were session scratch and were not kept (RT-B2-23). So this record can quote only the text that the batch 2 notes quote. Tags:
- **DOC-1015:** documented in the 2026-10-15 snapshot. It needs re-verification against current documentation before an A-1 approval relies on it (§1, AR-B9-1).
- **SECONDARY:** taken from a search summary or third-party page in batch 3.
- **UNRESOLVED:** not established by any source in Git.

---

## 1. External access in B09

### 1.1 Requests made

| Request | Host | Class | Result |
|---|---|---|---|
| `git fetch origin`, `git push origin b09/kalshi-source-qualification` | `ssh.github.com:443` (the repository remote) | Repository remote (`docs/backup_and_recovery.md`) | OK |

No WebFetch, WebSearch, `curl`, or other HTTP request was made. No Kalshi host, settlement-reference host, data vendor, or search engine was contacted.

### 1.2 Why no documentation request was made

Each candidate host was classified first (`docs/external_access.md` §1, F-09, CLAUDE.md "Host-Class Rule"):

| Host | Class | Can B09 request it? |
|---|---|---|
| `docs.kalshi.com` (`*.md` pages, `llms.txt`, `openapi.yaml`, `asyncapi.yaml`) | `docs` by host and path (§1.1 rule 7): the first label is `docs`; the paths contain no `/api/`, no `/v<n>/`, and no `.json`, `.jsonl`, or `.csv` | **Not without an owner ruling.** Two rules leave it ambiguous, so the request fails closed: <ul><li>AR-1 was approved as "temporary, for the venue-verification work" (batch 2 D1). That work is finished, and the AR-1 expiry and revocation the Red-Team asked for (E-7, RT-B2-17) were never recorded.</li><li>§1.1 rule 3 ("terms first"): before any fetch from a data licensor's domain, its terms are obtained from an owner-supplied copy or from a separate `docs` host. B09 qualifies Kalshi as a data licensor. Its terms are on `kalshi.com`, which is neither owner-supplied nor a `docs` host (row below).</li></ul> Batch 3 P3 and batch 4 O-6 allow `docs` hosts in general, but neither overrides rule 3. |
| `kalshi.com`, `www.kalshi.com` | `live-display`: the front end shows live prices, and the strictest class wins (§1.1 rule 2). Both are also denied by the sandbox (`deniedHosts`), and `kalshi.com` returned a bot challenge in batch 2 (AR-3) | **No.** The terms, Developer Agreement, fee schedule, and market-rule pages must be **owner-supplied** (AR-3 option 1). |
| `help.kalshi.com` | `unknown` (no classification; AR-A2 was never decided) | No |
| `kalshi-public-docs.s3.amazonaws.com` | `hist-data` or `unknown`: a cloud bucket (§1.1 rule 9) that also serves `/reporting/` market files (K4) | No. Contract-terms PDFs must be owner-supplied (AR-A1, AR-4). |
| `external-api.kalshi.com`, `api.elections.kalshi.com`, `external-api-ws.kalshi.com`, `*.kalshi.co` | `live-data` (§1.1 rules 1 and 8; F-09 denies) | Never, in B09 (charter §6) |
| `www.cftc.gov` filings | `docs` | Not needed: the batch 3 filings are already in Git |

**OWNER EXTERNAL-ACCESS APPROVAL REQUIRED (ACCESS REQUEST AR-B9-1):**
- **Host and paths.** `https://docs.kalshi.com/`, these exact paths only: `llms.txt`, `welcome/index.md`, `getting_started/historical_data.md`, `getting_started/pagination.md`, `getting_started/rate_limits.md`, `getting_started/terms.md`, `api-reference/historical/get-historical-cutoff-timestamps.md`, `api-reference/historical/get-historical-markets.md`, `api-reference/historical/get-historical-market.md`, `api-reference/historical/get-historical-market-candlesticks.md`, `api-reference/historical/get-historical-trades.md`, `api-reference/market/get-series.md`, `api-reference/exchange/get-series-fee-changes.md`, `openapi.yaml`, `asyncapi.yaml`, `changelog/index.md`.
- **Class.** `docs`. The host serves nothing else as far as is known. It returns a `308` redirect from `/` to `/welcome` on the same host; any cross-host redirect is refused.
- **Terms status.** Not obtained (AR-3). The owner must rule whether rule 3 lets this host be fetched before the AR-3 documents are supplied. **Recommendation:** fetch only after the AR-3 documents are supplied and reviewed.
- **Purpose.** Re-verify every DOC-1015 fact that A-1 and the pagination design rely on: parameter lists, cursor semantics, the end-of-pagination signal, timestamp units, unauthenticated rate limits, and the `license` and terms links in the specs. Compare against the batch 2 hashes.
- **Market observations returned.** None. Example payloads are illustrations and are never used as data.
- **Protected-interval content.** None. No cycle or `T0` exists.
- **Grant proposed.** One-time, agent fetch with `curl` without following redirects, into a fresh `$TMPDIR` directory. The bytes are hashed and recorded in `research/sources.md`.

---

## 2. Candidate source surfaces

All DOC-1015 (`api_documentation_findings.md` §§1–3, 6, 7; `venue_verification.md` §1).

### 2.1 Hosts

| Host | Role | Notes |
|---|---|---|
| `external-api.kalshi.com` | Production REST, "recommended" | Base path `/trade-api/v2` |
| `api.elections.kalshi.com` | Production REST, "also supported". "Despite the `elections` subdomain, the production Trade API provides access to all Kalshi markets" | Also serves WebSocket. **Recommended for exclusion from A-1:** approve one host only |
| `external-api.demo.kalshi.co`, `demo-api.kalshi.co` | Demo | Excluded. Demo data is never development data (F-37, RT-4, B8-4) |
| `external-api-ws.kalshi.com` | Production WebSocket | Excluded: authenticated, and live |

### 2.2 Data types on the historical tier

| Endpoint (relative to `/trade-api/v2`) | Returns | Authentication | Notes |
|---|---|---|---|
| `GET /historical/cutoff` | `market_settled_ts`, `trades_created_ts`, `orders_updated_ts`, `market_positions_last_updated_ts` | none | "Each data type has its own cutoff". The cutoffs advance over time |
| `GET /historical/markets` | Settled markets before `market_settled_ts`, as Market objects in current state | none | Filters `tickers`, `event_ticker`, `series_ticker`, and `mve_filter` are mutually exclusive. Pagination by cursor. The rest of the parameter list is UNRESOLVED (re-verify) |
| `GET /historical/markets/{ticker}` | One historical market | none | The path parameter is a ticker |
| `GET /historical/markets/{ticker}/candlesticks` | 1, 60, or 1440-minute candles, so 1 minute is the finest; historical candle schema | none | `start_ts`, `end_ts`, `period_interval`. The historical schema differs from the live one: `volume`, `open_interest`, and `open/low/high/close/mean/previous` without the `_dollars` suffix; `mean` = "Volume-weighted average price" |
| `GET /historical/trades` | Trade prints before `trades_created_ts` | none | "Same filters as `/markets/trades`": `limit` 1–1000, `cursor`, `ticker`, `min_ts`, `max_ts`, and possibly `is_block_trade` (re-verify). The units of `min_ts` and `max_ts` and the result ordering are UNRESOLVED |
| `GET /historical/fills`, `/historical/orders`, `/historical/positions` | Private account history | **required** | **Excluded:** `trading-private` class |

### 2.3 Metadata needed alongside (not historical-tier endpoints)

"Old Events and Series will always still be available through their original endpoints" (DOC-1015).

| Endpoint | Why PMV would need it | Risk |
|---|---|---|
| `GET /series/{series_ticker}` | `settlement_sources`, `contract_url` (original filing), `contract_terms_url` (**current** terms), `fee_type`, `fee_multiplier` | These fields are current state, so they are post-hoc for old markets (H-4) |
| `GET /events?series_ticker=…` or `GET /events/{event_ticker}` | Event grouping; `product_metadata.cadence` (`fifteen_min`) | Same endpoint family as the live tier. A query can return open, current events. Restrict by date (re-verify that the filters allow this) |
| `GET /series/fee_changes?series_ticker=…&show_historical=true` | The fee regime over time (`scheduled_ts`) | No announcement time; `/events/fee_changes` history is UNRESOLVED |

**Live-tier endpoints are excluded from the first A-1:** `/markets`, `/markets/trades`, `/markets/{t}/orderbook`, `/series/{s}/markets/{t}/candlesticks`, and `/live_data/…`. They return current or recent observations (`live-data`). Data after the historical cutoff waits for the cutoff to advance, or for PMV's own prospective capture.

### 2.4 Transport shape

- HTTPS `GET` returning JSON, with cursor pagination ("Pass `cursor` from the previous response").
- The end-of-pages signal is a **CONFLICT**: the guide says the cursor becomes `null`; the spec says it is "Empty if there are no more results". Both must be treated as terminal.
- "Data can change between requests": pages are not a snapshot.
- Rate limits are token buckets. "Every **authenticated** request costs tokens." **Unauthenticated limits are undocumented.** A 429 has no `Retry-After` header.
- Prices are dollar strings and counts are fixed-point strings.
- REST `date-time` timezone and precision are UNRESOLVED.
- No API version signal exists ("API versioning was removed", changelog 2025-07-29). Schema drift is detected only by strict validation.
- Redirect behavior of the API hosts is undocumented.

### 2.5 Authentication

None, per the OpenAPI spec: the operations in §2.2 and §2.3 declare no `security`. But "By continuing to use or access Kalshi's API, you are agreeing to be bound to our Developer Agreement" (`welcome/index.md`, DOC-1015).

**Consequence:** even unauthenticated acquisition is, on that page's own wording, acceptance of the Developer Agreement by conduct. Under H-7 a licence acceptance needs its own explicit owner approval, so the first request is itself an owner decision, made after the owner has read the agreement.

---

## 3. CANDIDATE A-1 DEFINITION (not approved)

A-1 stays owner-controlled and unapproved. Fields follow `pmv.acquisition.records` `_APPROVAL_KEYS`.

| Field | Candidate value | Status |
|---|---|---|
| `source_id` | `kalshi_official_historical` | Proposed |
| `dataset` | Kalshi Trade API v2 historical tier: markets, trades, 1-minute candles, and series and fee metadata | Proposed |
| `instruments` | BTC short-horizon series (KXBTC15M; KXBTCD hourly if it qualifies) and any gold short-horizon series (KXGOLD15M is SECONDARY) | **UNRESOLVED:** series existence and rules (UR-4, UR-5) |
| `date_range_start` | Earliest available | **UNRESOLVED:** retention is not documented. SECONDARY: "about 100 days" for the historical tier, trades back to 2021-06 (TrevorJS card) |
| `date_range_end` | A fixed instant ≤ the `/historical/cutoff` values at acquisition time, and before any future `T0 − m` | Proposed rule |
| `formats` | JSON (`application/json`), identity encoding | Proposed. No CSV, Parquet, DBN, zstd, or archives |
| `expected_size_bytes` | UNRESOLVED | It cannot be estimated without data. One option is a byte cap per series, with a stop and owner review when it is reached |
| `cost`, `currency` | 0, USD (the API is free) | Proposed. Excludes the paid CF Benchmarks and Pyth channels |
| `credential_required` | `false` | DOC-1015 (no `security`). B7-5 refuses credentialed acquisition anyway |
| `purchase_or_credential_decision` | Not applicable (no purchase or credential). Terms acceptance by conduct still needs an owner decision (§2.5) | — |
| `url_prefixes` | `https://external-api.kalshi.com/trade-api/v2/historical/`, `…/trade-api/v2/series/` and `…/trade-api/v2/events` (scope to be narrowed after AR-B9-1) | Proposed. **Not acquirable with today's tooling** (§4) |
| `host_class_decisions` | An owner classification of `external-api.kalshi.com` with those exact prefixes, as a historical-acquisition host in `docs/external_access.md` §1.5, for the acquisition tool only and never for agents | Required: the host is restricted (label `external-api` contains `api`; `kalshi.com` is a named venue domain; the path contains `/v2/`) |
| `licence_id` | none yet | Blocked by A-2 |
| `decision_record` | — | Owner |

Two further constraints:
- **Ticker-dependent paths.** `/historical/markets/{ticker}` and its candlesticks need tickers. Those tickers are learned from earlier untrusted responses. §4 governs how.
- **Settlement-reference lineage.** For BTC, `expiration_value` is the settlement reference value, built from CF Benchmarks BRTI under the series rulebook. It is upstream-licensed content inside Kalshi's records (A-2 row T).

---

## 4. Paginated REST gap and design-only specification

### 4.1 The mismatch, confirmed from Git

| Tooling today (B06, B07) | What the Kalshi historical API needs (DOC-1015) |
|---|---|
| `hosts.py` `_split_url` refuses any URL with a query or fragment ("URL queries and fragments are refused") | Every list endpoint needs `cursor`, and filters such as `series_ticker`, `ticker`, `min_ts`, `max_ts`, `limit`, `start_ts`, `end_ts`, `period_interval` |
| Every planned file's URL is declared in advance in the plan (`plan.py`) | Page 2 onward depends on a cursor returned by page 1, and per-market paths depend on tickers returned by earlier pages |
| `hosts.py` restricts `api` labels, `kalshi.com`, and `/v<n>/` paths | `external-api.kalshi.com/trade-api/v2/...` matches all three |
| The fetcher requires a plain `Content-Length`, identity encoding, status 200, and the expected size or provider SHA-256 where published | JSON API responses may be chunked (no `Content-Length`). There is no provider checksum. Sizes are unknown in advance. Whether the API honors `Accept-Encoding: identity` is UNRESOLVED |
| There is no production transport (B7-4) | It needs one |
| Each file is fetched once, with retries; the state machine is per file | It needs per-page state, a page chain, cursor-cycle detection, and termination logic |

So the gap is real: the current machinery cannot acquire this source without code changes, and those code changes widen a deliberate safety rule. **B09 changes no code.** The specification below is for a future, owner-chartered batch, followed by a Red-Team review.

### 4.2 Design-only specification (proposed)

**S1. A new governed request type, separate from static files.** Static-file plans keep their current behavior, and `hosts.py` keeps refusing queries for static URLs. A new `RequestSeries` plan item is added. It is the only path that may carry a query string, and its URLs are built by the tool, never parsed from text.

**S2. Endpoint templates in an owner record.** For each permitted endpoint, the record gives:
- the method (`GET` only);
- the host (exactly one);
- a path template with typed path parameters (for example `/trade-api/v2/historical/markets/{ticker}/candlesticks`);
- an exact allowlist of query parameter names, each with a type, value grammar, and range;
- whether each value is **fixed by the plan** or **variable** (only `cursor`, and the time window if the owner allows).

The record cites the documentation snapshot hash it was derived from. A parameter or template not in the record is refused. Changing the record is a new owner approval.

**S3. Parameter values.**
- Fixed values are bound into the plan hash: `limit` (one value), `series_ticker`, `period_interval = 1`, and the window bounds.
- Integers are decimal ASCII, with no sign, leading zeros, or exponent, inside the declared range.
- A time bound must lie inside `[date_range_start, date_range_end]` and at or before the cutoff snapshot (S12).
- Tickers must match a strict grammar (for example `^[A-Z0-9][A-Z0-9._-]{0,63}$`; final grammar after AR-B9-1).
- No value may contain characters outside the grammar. The tool percent-encodes; inputs are never accepted pre-encoded.
- Repeated or empty parameters are refused.

**S4. Canonical form and request identity.**
- The query is serialized with names sorted bytewise, one `name=value` pair each, percent-encoded under RFC 3986 with only unreserved characters left unencoded.
- `request_identity = SHA-256` over a canonical JSON of: method, scheme, host, port, path, canonical query, and the fixed request headers (`Accept: application/json`, `Accept-Encoding: identity`, a fixed `User-Agent`).
- No authentication header is ever sent (B7-5). The fetcher refuses unless the URL it is about to send re-serializes byte for byte to the authorized canonical URL.

**S5. Cursor handling.**
- The cursor is opaque, untrusted server content. It is extracted only by the confined G-1 worker under a strict schema, and the parent re-validates it: length at most an owner-set cap; the character set from the S3 grammar (final set after AR-B9-1); otherwise the series stops with `cursor_invalid`.
- It is never decoded or interpreted.
- It is stored only in the protected journal. Reports and anything agent-visible carry only its SHA-256.

**S6. Ticker-derived requests.**
- Tickers for per-market endpoints come only from a validated list response for the plan's own filter (for example `/historical/markets?series_ticker=X`).
- Each ticker is accepted only when that response's own `series_ticker` or `event_ticker` relationship fields tie it to the approved series. Kalshi says "do not parse ticker strings to infer relationships" (DOC-1015), so no prefix matching is used.
- The number of derived tickers is capped. Every derived URL is rebuilt from the template and re-checked under S2–S4.

**S7. Termination.** A series is `complete` only when a page returns a terminal cursor (`null`, absent, or `""`). The doc conflict is resolved by treating all three as terminal, and the form seen is recorded. Each of these ends the series as **`incomplete`**, never `complete`:
- `max_pages` reached;
- the byte cap reached;
- a repeated cursor (`cursor_cycle`; a set of cursor hashes is kept);
- a non-terminal page with zero items more than an owner-set number of times;
- a page with more items than `limit`;
- a schema failure.

**S8. Page hashing and chain.**
- Each page's raw bytes are hashed on receipt, before parsing.
- The page record binds: `series_id`, `page_index`, `request_identity`, `cursor_in_sha256`, `response_sha256`, `response_bytes`, `cursor_out_sha256`, the selected response metadata (S10), the receipt times (S9), and `prev_page_record_sha256`. The pages form a hash chain inside the B07 hash-chained journal.

**S9. Receipt-time journaling.**
- Per request: `requested_at`, `first_byte_at`, and `received_at` in UTC from the PMV clock, plus monotonic deltas.
- The clock-sync state at run start and end (cf. RT-B8-05, B8S-03). An unknown sync state is recorded as unknown, never as synchronized.
- These times are acquisition times. They are **not** decision-time availability for features. Historical rows use the H-5 synthetic availability `venue_time + L`.

**S10. HTTP metadata kept.**
- Kept: status, `Content-Type`, `Content-Length` if present, `Date`, `ETag` and `Last-Modified` if present, the final URL, and the TLS peer certificate SHA-256 fingerprint.
- Not kept: `Set-Cookie`, tracking or session headers, and any header not on the list.
- Response headers are never echoed into agent-visible reports.

**S11. Retry and idempotency.**
- `GET` is retried only for a transport error, 5xx, or 429. Each retry uses the identical canonical request (same cursor), with exponential backoff and jitter and a bounded number of attempts.
- An accepted page is never replaced. A retry after a successful receipt compares hashes: equal is recorded as `duplicate_receipt`; different is recorded as `page_conflict`.
- A `page_conflict` in a historical-tier series fails the series's consistency status, and the series is re-run under a new attempt with an owner review. The historical tier should be stable, so a difference is an anomaly, not noise.

**S12. Cutoff snapshot.** `/historical/cutoff` is fetched as a governed single request before the first series and after the last. Its pages are stored like any other. If a cutoff moves backward, or a requested window is not wholly before both snapshots, the acquisition stops.

**S13. Duplicate-page protection.**
- The journal refuses a second accepted page for the same `(series_id, page_index)`.
- A response whose hash equals an earlier page's in the same series under a different cursor is recorded as `duplicate_page`, and the series ends `incomplete`.
- Record-level duplicates (the same `trade_id`) are an A-6 matter. They are never silently dropped.

**S14. Redirects.** For API series, any 3xx is refused. Redirects are not followed at all, which is stricter than the static-file fetcher's same-scope redirect rule.

**S15. Byte limits.**
- Per-page cap and per-series cap, from the plan.
- Total acquisition cap ≤ `expected_size_bytes` × an owner-set margin.
- The free-disk precheck applies, as for static files.
- A missing `Content-Length` is accepted **only if** the owner approves this relaxation and the review covers it: the stream is cut at the per-page cap, and an overflow is a refusal, never a truncation. Otherwise a chunked response fails the page.

**S16. Page-count limits.** `max_pages` per series, a maximum number of series per acquisition, and a total request count per run. All are fixed in the plan.

**S17. Rate.**
- Serial requests on one connection, at a fixed conservative rate set by the owner (for example ≤ 1 request/s), well below the documented Basic Read budget, because unauthenticated limits are undocumented.
- On a 429, back off. After an owner-set number of consecutive 429s the run stops with `stage_failed` (`rate_limited`) and resumes later.

**S18. Crash and restart.**
- Each page is journaled before the next request.
- On restart the series resumes from the last journaled `cursor_out`. If the cursor is refused or has expired, the series restarts from page 0 as a new attempt. Earlier pages are kept as evidence, and overlapping pages must be hash-equal, or a `page_conflict` is recorded.
- Torn-tail recovery follows the B07 owner-attested procedure.

**S19. Provenance per page:** the §6 fields.

**S20. Preventing widening.**
- The tool cannot be pointed at a template, parameter, host, or value range outside the owner record.
- The record and the plan are bound by hash into every journal entry, like the B07 authorizing bundle.
- Tests prove that each of these is refused:
  - an extra parameter, a duplicated parameter, or a pre-encoded value;
  - a cursor outside the grammar, or an injected `&`, `?`, `#`, `/`, or `%`;
  - a ticker not tied to the series;
  - a host or port change, or a redirect;
  - an over-limit page.

**S21. Unchanged invariants.**
- A-7: the pages land only in the protected raw store, written outside agent sessions.
- A-8: nothing is released.
- The G-1 worker parses every page.
- B7-5: no credential.
- B7-8: a real-mode run still needs a reviewed production transport (B7-4) and an A-4 record covering the code that implements this design.

**Review.** Implementing S1–S21 changes `src/pmv/acquisition/` (hosts, plan, fetch, state, pipeline). A fresh Reliability / Red-Team review is required, and the A-4 record must cite the reviewed commit.

---

## 5. A-2: licence and terms issue matrix

**Status: A-2 is not assessable.** No governing Kalshi document has been supplied to the project (AR-3), so nothing below is CLEARLY PERMITTED. What the documentation snapshot does show:
- the Developer Agreement governs API use (§2.5);
- the AsyncAPI spec's `license.url` is `https://kalshi.com/terms` (`api_documentation_findings.md` §14);
- SECONDARY: an academic repository (jdkatz21) reports that Kalshi granted it research permission under a "data licensing agreement". That suggests data-use terms exist and matter. It is not evidence of what they say.

| # | Question | Classification | Basis |
|---|---|---|---|
| A | Automated API access | NOT YET EVIDENCED | The API exists and binds users to the Developer Agreement, whose content is unknown. A general API offering is not permission for bulk historical acquisition |
| B | Local caching | NOT YET EVIDENCED | — |
| C | Long-term storage | NOT YET EVIDENCED | — |
| D | Backup copies, including off-site or third-party cloud (A-3) | NOT YET EVIDENCED | Relevant to the choice of A-3 option (§7) |
| E | Historical analysis | NOT YET EVIDENCED | — |
| F | Backtesting | NOT YET EVIDENCED | — |
| G | Statistical modeling | NOT YET EVIDENCED | — |
| H | Machine-learning training | NOT YET EVIDENCED | A general API permission is not treated as ML permission |
| I | Feature engineering | NOT YET EVIDENCED | — |
| J | Derived datasets | NOT YET EVIDENCED | `derived_data` is a required L-PROD field (`records.py`) |
| K | Model weights and fitted parameters | NOT YET EVIDENCED | Not addressed by any document in Git |
| L | Use solely for the owner's own trading | NOT YET EVIDENCED | Even if granted, it does not by itself settle B, C, F, H, J, or K |
| M | Commercial redistribution | NOT YET EVIDENCED | PMV does not intend it |
| N | Publication | NOT YET EVIDENCED | PMV does not intend it. Note that Git holds no raw observations |
| O | Sharing with contractors, agents, or tools (including Claude sessions after H-2 release, cloud backup providers, and CI) | NOT YET EVIDENCED | Material: agents see released rows (H-2), and Anthropic-hosted sessions process them |
| P | Retention after account closure or termination | NOT YET EVIDENCED | No account is held (§2.5). How termination applies to unauthenticated use is unknown |
| Q | Deletion obligations | NOT YET EVIDENCED | Would conflict with "preserve raw data" and with the A-3 backups if they exist |
| R | Website data versus API data | NOT YET EVIDENCED, structurally **AMBIGUOUS** | Two documents are referenced: the Developer Agreement (API) and `kalshi.com/terms` (the spec's licence) |
| S | Documentation versus data | NOT YET EVIDENCED, structurally **AMBIGUOUS** | The spec files carry a licence pointer to the general terms |
| T | Upstream licensors | **AMBIGUOUS** | <ul><li>BTC `expiration_value` and settlement values derive from CF Benchmarks BRTI.</li><li>The CF Benchmarks REST passthrough needs an entitlement.</li><li>The `cfbenchmarks.com` site terms bar automated access (batch 3 terms event).</li><li>Gold reportedly settles on Pyth (SECONDARY). Kalshi's paid `pyth_value` feed costs $1,000/month.</li></ul>Whether Kalshi's historical records may carry and license these upstream-derived values to members is unknown. Unknown counts as no (A-2: "the redistributor's right to grant the licence is established from the upstream terms") |

The existing `LicenceRecord` schema (`records.py`) has no fields for B (caching), D (backups), F (backtesting), H (ML training), K (model artifacts), O (sharing with tools or agents), P (retention after termination), or Q (deletion). If the owner wants those decided explicitly, the schema needs extending: a later code change, with review.

**Escalation (charter §19).** The governing documents are not even in hand, so A-2 stops at NOT YET EVIDENCED. A neutral clarification request is drafted in the decision record. It is to be sent by the owner, if at all, after the owner has read the supplied documents.

---

## 6. Agreement precedence and conflicts (§11): what is known

| Document | Surface it appears to govern (from pointers in Git) | Incorporation, precedence, termination, modification |
|---|---|---|
| Developer Agreement (`https://kalshi.com/developer-agreement`) | "Kalshi's API" (welcome page) | NOT YET EVIDENCED |
| Terms of Service (`https://kalshi.com/terms`) | The website. It is also the `license.url` of the AsyncAPI spec | NOT YET EVIDENCED |
| Member or customer agreement (title unknown) | Trading accounts | Whether it exists as a separate document is UNRESOLVED |
| Rulebook | "Methodology is defined in the rulebook" (Series schema) | NOT YET EVIDENCED. CFTC filings (batch 3) give some rulebook texts |
| Contract terms (`contract_terms_url`, current; `contract_url`, original filing) | Each series | The current URL may not be the terms in force for a past market: a point-in-time issue (H-3, H-4) |
| Fee schedule PDF (`https://kalshi.com/docs/kalshi-fee-schedule.pdf`) | Fees | NOT YET EVIDENCED |
| Market-data page or data terms (`https://kalshi.com/market-data`) | Possibly bulk reports (K4) | Whether separate data terms exist is UNRESOLVED |
| API documentation (`docs.kalshi.com`) | Technical. Its specs point to the general terms | — |
| CF Benchmarks and Pyth terms | Upstream reference data | AR-9 and AR-8 are owner-supplied or unrequested |

**Unresolved by construction:** whether the Developer Agreement or the Terms of Service governs bulk historical data used for private modeling; their precedence; whether either is incorporated into the other; and whether terms may change without direct notice. None of this is interpreted here.

---

## 7. A-3: backup options (owner choice; none adopted)

**Constraints from Git:**
- The primary raw store must resolve inside `~/pmv-protected/raw` (F-01, `docs/raw_data.md`). That is on the owner's Chromebook Linux container, not in the isolated container.
- The acquisition pipeline's backup step is filesystem-based. `backup_and_verify_restore(files, source_dir, backup_dir, restore_dir)` needs mutually disjoint directories and verifies SHA-256 and size.
- A-3 needs an owner-approved policy, then a restore test on a synthetic file of the same format and size class (B7-7's "size class" reading is unconfirmed). After acquisition, a backup and verified restore of the real files is needed before they are recorded as acquired.
- `reproducible_from_provider` must be `unknown` (treated as `no`): retention is undocumented and the tier "advances".

| | **Option 1: encrypted external drive (local, offline)** | **Option 2: encrypted off-site cloud object storage** | **Option 3: hybrid, 3-2-1 (Option 1 plus an off-site copy)** |
|---|---|---|---|
| Primary | `~/pmv-protected/raw` (internal) | same | same |
| Backup medium | A dedicated USB SSD shared to the Linux container only during backup runs | A provider bucket with versioning and object lock, written only by an owner-run uploader | External drive, plus a cloud bucket or a second drive kept elsewhere |
| Physical and logical independence | A separate device and filesystem; offline otherwise. Same physical location as the primary | Off-site, different failure domain. It depends on an account and credential | Both |
| Encryption | Client-side, with an owner-held key or passphrase. The tool is an owner choice, and any new tool is a reviewed dependency | Client-side before upload. Provider-side encryption is not relied on | Both |
| Access control | Mounted only during the owner's backup run; never mounted in the isolated container | Credential in `~/pmv-credentials` style isolation (F-03), owner-run only; never in agent environments | Both |
| Retention | Keep everything (append-only); never prune raw | Versioned, with an object-lock retention period set by the owner | Both |
| Restore procedure | Mount, copy to an empty restore directory, verify SHA-256 against the acquisition manifest | Download to an empty directory and verify SHA-256 | Either path |
| Hash verification | `backup_and_verify_restore` directly (the medium is a directory) | Needs a staging directory plus a separate sync step. `backup_verified` would then mean "staged and synced and re-downloaded". **A code or policy change** | Local copy verified by the existing code; the cloud copy by a periodic owner-run restore |
| Expected restore test | Synthetic file of the same artifact type (`json`) and size class, then the real files after acquisition | same, through the download path | Both media |
| Chromebook practicality | Good: ChromeOS can share a USB drive with the Linux container. exFAT loses POSIX modes, but hashes still verify | Upload bandwidth, plus a CLI tool installed outside agent environments | Most owner effort |
| Expected cost | One drive (order of tens to a little over a hundred USD; verify current prices) | Per-TB-month storage fees plus egress (verify current pricing) | Both |
| Failure modes | Single site (theft, fire); the drive fails silently between tests; the owner forgets to connect it; a lost key means lost data | Credential compromise; provider lock-in or account closure; **licence risk: a third-party cloud may count as storage or sharing that the Kalshi terms restrict (A-2 rows D and O)**; egress cost on restore | Complexity; drift between copies |

**Recommendation (owner decides):**
- Option 1 is the minimum to unblock a *historical* acquisition. It is the only one compatible with today's code without change, and it avoids the A-2 third-party question.
- Plan Option 3 before *irreplaceable* prospective capture, which needs off-site protection that Option 1 lacks. Only after A-2 shows that off-site third-party storage is allowed.

A-3 is **not** satisfied: no policy, no medium, no restore test.

---

## 8. A-4: global versus source-specific (owner decision; no interpretation adopted)

**Wording that supports GLOBAL:**
- `docs/external_access.md` §2 A-4: "Only allowlisted formats are parsed (CSV, JSON or JSONL, Parquet, DBN, plain text), with pinned, patched readers." It can be read as requiring a pinned reader for each listed format.
- The A-4 evidence column: "passing fault-injection fixtures: … pickle disguised as Parquet …".
- §2 tooling status (B07): "A-4 is not yet satisfied: the Parquet, DBN, and zstd readers are deferred …".
- `docs/acquisition_readiness.md`: "Even with no BLOCKING or MAJOR finding, A-4 is not satisfied while items 1 and 2 remain". Item 1 is the Parquet, DBN, and zstd readers.
- `A4ReviewRecord` has one unscoped `a4_satisfied` flag (`plan.py`).

**Wording that supports SOURCE-SPECIFIC:**
- O-3: "Historical acquisition is allowed only after these conditions are satisfied **for the source**." The §2 gate is introduced per source ("Approval to research a source is not approval to acquire it").
- The A-4 format text is a restriction ("Only allowlisted formats are parsed … Every other format … is refused"), not an obligation to adopt every listed reader.
- The B07 status wording is a statement of the current state, recorded by agents, not an owner rule.
- `acquisition_readiness.md` item 4 and the B08 record list "A-4 global-versus-per-source scope" as **open** owner input.

**Safety analysis:**
- **Fail-closed is preserved under the source-specific reading.** The pipeline refuses any plan with a format that has no adopted reader, before transport. The worker's reader registry refuses Parquet, DBN, and zstd today, and keeps refusing them. A JSON-only source never exercises those code paths.
- **The real risk is certification creep.** A bare `a4_satisfied: true` granted for a JSON source could later be cited by a Parquet source. Mitigation: replace the bare flag with a scoped record:
  - `formats_covered`, `compressions_covered`, and `source_ids` (or `any`);
  - `reviewed_commit` (already present);
  - the pipeline refuses a plan unless its formats and compressions are a subset of those covered.
- The Kalshi source needs only JSON with identity encoding. Unused Parquet, DBN, or zstd support would add attack surface (pyarrow's history includes CVE-2023-47248) and give the Kalshi source no benefit.
- **Both readings leave the production transport (B7-4) and the pagination support (§4) outstanding.** The source-specific reading does not by itself make A-4 satisfiable for Kalshi today.

**What would change:**
- `A4ReviewRecord` schema and pipeline check: a code change in `src/pmv/acquisition/`, so a fresh Red-Team review.
- The A-4 text in `docs/external_access.md`: a governance edit needing owner approval. It should make the A-4 evidence per source, covering the formats that source needs, while keeping all the general fault fixtures.

**Recommendation (not adopted):** SOURCE-SPECIFIC, with the format-scoped record above, so a bare flag is never accepted. The fault-injection fixtures stay global. Red-Team re-review of the scoping change.

---

## 9. A-5: provenance design for Kalshi official historical data (candidate)

Today's acquisition manifest (`records.py` `_MANIFEST_KEYS`) and per-file `acquisition.json` already carry:
- `acquisition_id`, `approval_id`, `licence_id`, `input_licence_ids`;
- `source_url`, `retrieved_at`, `upstream_identity`, `is_primary_source`, `mirror_lineage`, `vendor_version`;
- `tool_git_commit`, `tool_tree_dirty`, `reproducible_from_provider`;
- `files[name, format, size_bytes, sha256]`;
- per file: URL, final URL, sizes, hashes, hash source, and retrieval time.

**Candidate additions for paginated REST (needs code later):**

| Level | Field | Content |
|---|---|---|
| Acquisition | `source_id` | `kalshi_official_historical` |
| | `upstream_identity` | The Kalshi Trade API v2, production; `is_primary_source: true`; `mirror_lineage: []` |
| | `environment` | `production`. A demo host is refused (F-37) |
| | `api_doc_snapshot` | The docs snapshot ID and the hashes of `openapi.yaml` and of the pages the endpoint record cites. No runtime version exists, so this is the only version marker. It goes in `vendor_version` |
| | `endpoint_record_sha256`, `plan_sha256` | Bound into every journal entry (S20) |
| | `licence_id` | The A-2 record. Its `terms_sha256` is the hash of the owner-supplied Developer Agreement and terms |
| | `cutoff_before_sha256`, `cutoff_after_sha256` | The pages from S12 |
| | `tool_git_commit`, `worker_identity`, `transport_identity` | Code identity, including the reviewed production transport |
| | `clock_sync_state_start`, `clock_sync_state_end` | S9 |
| | `reproducible_from_provider` | `unknown`, treated as `no` |
| | `provider_checksum` | `none_published` |
| Series | `series_id`, `endpoint_template`, `fixed_params` (canonical), `derived_from` (parent series and page, for ticker-derived series), `status` (`complete` or `incomplete` with a closed code), `page_count`, `bytes`, `terminal_cursor_form` | S2–S7 |
| Page | `page_index`, `request_identity`, `canonical_url`, `cursor_in_sha256`, `cursor_out_sha256`, `requested_at`, `first_byte_at`, `received_at`, `http_status`, `content_type`, `content_length` or `chunked`, `date_header`, `etag`, `last_modified`, `tls_peer_sha256`, `response_sha256`, `response_bytes`, `prev_page_record_sha256`, `attempt` | S8–S11 |
| Lineage (recorded with the data, flagged) | `settlement_reference_lineage` | For each series: `settlement_sources`, `contract_url`, and `contract_terms_url` as returned at acquisition time, tagged `metadata_pit_class = POST_HOC` (H-4); the upstream reference (CF Benchmarks BRTI; Pyth for gold if confirmed); the rulebook regime per market period (CFTC filings) |
| | `upstream_notices` | Any upstream notice that the terms require to be retained, verbatim (after A-2) |

**Never in agent-visible reports:** cursors, header values other than status codes, URLs with query values (only their hashes), and any payload content (B07 rule: counts, sizes, hashes, closed codes only).

---

## 10. A-6: quality and reconciliation procedure (design; nothing executed)

**Tier proposal:** `Q1_authoritative` for official resolution fields (`result`, `settlement_value`, `expiration_value`), and for trade prints as the exchange of record. With these caveats:
- market objects are current-state, post-hoc metadata (H-4);
- there is no book;
- candles are 1-minute aggregates whose bid and ask sampling is UNRESOLVED.

The owner assigns the tier before any outcome-dependent result (`docs/phase2.md` §14).

**Checks** (deterministic, run by owner-side tooling on protected data; agents see only counts and closed codes until H-2 release):

1. **Pagination completeness.** Every series ends `complete` (S7). Page counts are compared with the item counts. Any `incomplete` series is a recorded gap, never silently retried into "complete".
2. **Cutoff consistency.** Every acquired record lies before both cutoff snapshots. Records after them are refused (the live tier is out of scope).
3. **Duplicates.** `trade_id` must be unique. An exact duplicate is counted and recorded. The same `trade_id` with different content is an anomaly (`docs/phase2.md` duplicate policy). Nothing is deleted.
4. **Ordering.** The API's ordering is not documented, so no order is assumed. Within-page and cross-page ordering of `created_time` is measured and recorded. Canonical order is imposed downstream by `(created_time, trade_id)`, with ties flagged.
5. **Timestamps.** Strict RFC 3339 with an explicit offset. A naive timestamp is refused. The precision distribution is recorded (UR-14). `created_time` stays inside the market's `[open_time, close_time]`; a violation is an anomaly. Note that `close_time` can move (early close or reopen).
6. **Market identity.** Every trade's `ticker` exists in the acquired markets for the series. Orphans are counted (the TrevorJS card reports orphan trades). Series, event, and market relationships come from fields, never from parsing ticker strings.
7. **Settlement reconciliation.**
   - `result` ∈ {`yes`, `no`}. `scalar` or `""` on a binary market is an exclusion, never a coerced label (E-5).
   - The status is `finalized`. `determined`, `disputed`, and `amended` are recorded.
   - `settlement_value_dollars` agrees with `result`.
   - The outcome recomputed from `expiration_value`, `floor_strike`/`cap_strike`, and `strike_type` agrees with `result`. A mismatch is flagged, not repaired (SECONDARY reports exist of mis-scaled strikes or settlement values).
8. **Volume and counts.** The sum of trade `count` per market is compared with the market's volume field and with the sum of candle `volume`. Block trades are handled separately (`is_block_trade`). Tolerances are fixed before inspection, by the owner with the Statistician.
9. **Cross-endpoint consistency within Kalshi.** Candle OHLC against trade prints per minute (price range containment), and candle volume against trades. These are **internal consistency checks of one upstream system, not independent corroboration** (RT-B3-14). The same holds for third-party Kalshi archives (TrevorJS, Jon-Becker, DegenHedge), which are copies of the same upstream.
10. **Independent corroboration (needed, later).**
    - (a) PMV prospective capture of the same trades once they age into the historical tier. This is the only same-venue independent capture, for overlapping periods before any `T0 − m`.
    - (b) Settlement recomputation from the upstream reference (CF Benchmarks BRTI under the governing rulebook; Pyth for gold if confirmed). This needs licensed access (AR-9, AR-8, K3), which is not authorized.
    - (c) CFTC filings for rule text. Until (a) or (b) exists, labels rest on one source.
11. **Missing intervals.** A market with no trades is legitimate. Missing *markets* in a 15-minute grid are measured against the expected cadence, from `product_metadata.cadence` and the event schedule. Gaps are recorded with their cause where known, and never filled.
12. **Survivorship.** `is_provisional` markets "may be removed after determination if there is no activity", so the market universe can be activity-selected. This is recorded as a known selection effect, and eligibility rules must not depend on it.
13. **Point in time.** Strikes, `close_time`, `price_ranges` (the tick grid), fees, and `contract_terms_url` are current-state. They are tagged `POST_HOC` (H-4). Fees are reconstructed from `/series/fee_changes?show_historical=true`. Tick-regime history is not recoverable from current-state `price_ranges`; that is recorded as a gap.
14. **Schema regimes.**
    - The historical candle schema is not the live one.
    - Deprecated `taker_side`; removed cent fields; fixed-point strings.
    - The changelog's label dates are not effective dates.

    Records are partitioned by schema signature, and unknown fields are kept and flagged.
15. **Rulebook regimes.** BTC rulebook amendments (2024-11-27 trimmed mean; CRYPTO 2025-07-18; CRYPTOSHORT 2026-03-11) partition the history. Which rulebook governs KXBTC15M is UNRESOLVED (K5).

**Is another independent source eventually needed?** Yes. For labels: the upstream reference recomputation. For trade data: overlap with PMV capture. Neither is available now.

---

## 11. BTC and gold coverage (documentation only)

| | Evidence | Status |
|---|---|---|
| **Bitcoin** | The historical endpoints are generic over series (DOC-1015). `KXBTC15M` appears only as an example ticker and in a changelog mention. The `fifteen_min` cadence exists. BTC rulebook texts exist (CFTC filings, batch 3). SECONDARY: KXBTC15M history from about 2026-01; KXBTCD hourly; trades reachable back to 2021-06 for some series | **Plausible, unverified.** Series existence, the rules that govern KXBTC15M, retention depth, and the cutoff lag are UNRESOLVED. 1-minute candles and trade prints exist; there is no historical book |
| **Gold** | No gold event-contract series is documented on `docs.kalshi.com`. SECONDARY: KXGOLD15M launched about 2026-08 and settles on a Pyth 1-minute gold candle; history at most about 2 months | **Unknown.** Even if it exists, its depth would be thin. P4 keeps gold in scope; nothing here narrows PMV to Bitcoin |
| **15–60-minute horizon** | 15-minute cadence documented as a metadata value; hourly SECONDARY | Plausible for BTC, unknown for gold |
| **Fit to the late-window strategy** (PROJECT_BRIEF.md §3) | Trades and 1-minute candles give coarse final-minutes information. No book means no executable-price history | Discovery-grade only. Executable EV evidence must come from prospective capture (batch 3 key finding; Statistician) |

---

## 12. Provisional verdict

**NOT CURRENTLY QUALIFIABLE — EVIDENCE MISSING**

This is not a rejection. Technically, Kalshi's own historical tier is the strongest available candidate for official BTC labels and trade prints. It is the primary source, it is free, and it needs no credential. What is missing:
- the governing terms (AR-3), without which A-2 cannot even be assessed;
- current documentation re-verification (AR-B9-1);
- gold existence (UR-5);
- retention depth (UR-11).

| Item | Readiness |
|---|---|
| A-1 | Candidate drafted (§3). Not approvable yet: the A-2 evidence and AR-B9-1 re-verification are missing, the host classification is not decided, the pagination tooling does not exist, and the series and retention are UNRESOLVED |
| A-2 | **Not assessable.** All rows are NOT YET EVIDENCED; rows R, S, and T are structurally AMBIGUOUS. Blocked on owner-supplied documents |
| A-3 | Options prepared (§7). No owner choice, no medium, no restore test |
| A-4 | Not satisfied under either reading. The scope decision is open (§8). Transport (B7-4) and pagination support are still needed |
| A-5 | Design ready for owner review (§9). Code needed later |
| A-6 | Design ready for owner review (§10). Owner tier assignment and tolerances needed. Independent corroboration is not yet available |

Acquisition is **not authorized**, and nothing in this record authorizes it.
