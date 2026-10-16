# Reliability / Red-Team review: Phase 1 batch 2 (Kalshi venue verification)

- **Author:** Reliability / Red-Team (development agent). **Date:** 2026-10-16.
- **Independence:** fresh context. I did not write, edit, or advise on `venue_verification.md`, `api_documentation_findings.md`, `statistician_review.md`, the decision record, or the new `research/sources.md` entries. I previously reviewed the batch 1 `books` module (`docs/market_data.md`, red-team M1–M5). Several findings below concern how that module interacts with Kalshi. I reviewed it with that prior involvement in mind.
- **Type:** a documentation-level review only. No tests were run, no code changed, and no network request was made. No real market observation was used. Example payload values in the documentation are illustrations, not data.
- **Evidence base:** the retrieved files in `/tmp/claude-1000/kdocs/pages/` (session scratch). I recomputed the SHA-256 of all 59 files plus `llms.txt`. **All match `research/sources.md`.** Citations use the form `file:line` in that directory. URL = `https://docs.kalshi.com/` + the file name with `_` mapped back to `/`.
- **Severity in this review:** severity refers to the downstream action in the "Owner / next" column.
  - **BLOCKING:** must be resolved before that action.
  - **MAJOR:** an unsafe or misleading element that must be corrected or controlled.
  - **MINOR:** accuracy or hygiene.
  - These labels are not the Phase 5 vocabulary (acceptable / concern / major concern / blocking), and they do not map to it.
- **Failure IDs:**
  - F-xx and RT-4 come from `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md` and `docs/gate0_readiness.md:98`.
  - M2, M3, and M4 are the batch 1 red-team items in `docs/market_data.md:193-197`: M2 = gaps on snapshots and cross-book invalidation; M3 = hard stop and rate limit reset book state; M4 = per-stream silence.
  - "Stat-M4" is the exclusion ledger (`docs/market_data.md:232`).

## Findings

| ID | Sev | Finding | Evidence | Required fail-closed control | Owner / next |
|---|---|---|---|---|---|
| RT-B2-01 | BLOCKING (parser and collector) | **The proposed recovery, "unsubscribe and resubscribe", is unsafe as written.** `subscribe` is idempotent. With the same tickers, "no action will be taken", so no new snapshot arrives. New tickers are "added to your existing subscription". If the `unsubscribe` was lost, failed, or not yet acknowledged, a resubscribe silently leaves the book with no fresh snapshot. That a fresh `sid` is issued is only an inference. | `changelog_index.md:5592-5594` (Sep 25, 2025) | Recovery = an `unsubscribed` acknowledgement for that `sid` (it requires `sid` and `seq`, `asyncapi.yaml:2630-2632`), **then** subscribe. Before any book is valid again, require a new `sid` different from the old one **and** an `orderbook_snapshot` for every market. If anything is ambiguous (timeout, error, a missing acknowledgement within a fixed bound), close the connection and reconnect. Prove this with a deterministic mock-server test. | API / Execution; raw-format v2 and collector batch (F-11, M2, M3) |
| RT-B2-02 | BLOCKING (parser) | **Control messages carry `seq`.** `unsubscribed` requires `seq`. `ok` has an optional `seq`. Subscription-scoped `error` messages carry `sid` and `seq`. A gap check run only over normalized data observations will either (a) raise false gaps every time PMV sends a command, causing self-inflicted book resets clustered around PMV actions, or (b) treat a real gap as explained if control frames are counted inconsistently. | `asyncapi.yaml:2630-2632`, `:2696-2708`; `changelog_index.md:957` | Keep a per-(connection, `sid`) sequence ledger in the collector or raw layer, over **every** frame that carries a `sid`, before normalization. The ledger emits PMV gap events that the book engine consumes. Unit-test with interleaved `ok`, `error`, and `unsubscribed` frames. This also covers the known limit at `docs/market_data.md:155`. | API / Execution (F-12, M2) |
| RT-B2-03 | BLOCKING (parser) | **The existing engine would accept a `get_snapshot` reply as recovery.** The book engine recovers from any fault on "the book's own next snapshot". A `get_snapshot` reply is an `orderbook_snapshot` carrying `sid`, `seq`, and a command `id`. If that reply is not sequence-consistent with deltas still in flight, the rebased book is silently wrong: relative deltas are applied twice or missed, and no fault fires. This contradicts `venue_verification.md` §3 item 2. | `docs/market_data.md:131-132`; `asyncapi.yaml:3023-3031` (`id` "present when replying to a get_snapshot") | The normalizer tags snapshots that carry a command `id`. The engine does not count tagged snapshots as recovery until a recorded test proves they are consistent. Collector v1 does not issue `get_snapshot`. | API / Execution; book-engine change |
| RT-B2-04 | MAJOR | **The delta-semantics verification plan is circular.** "snapshot (S0, seq n) + Σ deltas → compare with get_snapshot (seq m)" assumes `get_snapshot` is sequence-consistent, which is itself unresolved (U4). A test run only in demo cannot settle production semantics either (see RT-B2-09). Converting relative deltas to absolute levels **in the normalizer** would also create a second, stateful book engine with no fault model of its own. | `api_documentation_findings.md:314`; `venue_verification.md:151` | Use a differential test instead: two independent connections, each rebuilt from its own subscription snapshot, must agree level by level at quiescent points. Invariants must hold over long runs: no negative level, no crossed book, every price on the grid. Production confirmation comes only from collector metadata under F-08/S-6. Prefer a relative-delta variant inside `books`, using the same fault model, over conversion in the normalizer. | API / Execution; Statistician informed |
| RT-B2-05 | MAJOR | **The acknowledgement/data race.** The changelog says a race "could skip events arriving immediately after a `subscribed` response" and that it is now fixed. That is a vendor claim, and its date is only a changelog label. On channels without a snapshot (`trade`, `market_lifecycle_v2`), a skipped first message cannot be detected unless the starting `seq` value is known (U3). On books, `delta_without_snapshot` already blocks. | `changelog_index.md:793-804` | Assert that the first `seq` on every new `sid` equals the tested start value. Until that value is verified, mark the first interval "continuity unverifiable" and exclude it. Add a mock-server regression test that drops the first message after the acknowledgement. | API / Execution (F-11, M2) |
| RT-B2-06 | BLOCKING (spec builder, labels, live status) | **Lifecycle status can go stale silently.** `status_as_of` returns the last status, and "a later stream reset does not invalidate it". On Kalshi, open and close have no WS event, and dispute and amendment have no WS event. A `close_date_updated` missed during a lifecycle gap leaves PMV believing a market is open, or holding the wrong close time. That corrupts `time_remaining`, eligibility, and label alignment, and execution would hit `MARKET_INACTIVE`. | `docs/market_data.md:114`; `getting_started_market_lifecycle.md` "Implicit (no WebSocket event)"; `asyncapi.yaml` lifecycle enum | A lifecycle `seq` gap or a reconnect sets every tracked market's spec and status to UNKNOWN until a REST re-poll **received after the gap** reconciles it. Status is a function of the event log, the clock against the known close time, and the market's own shard status. UNKNOWN means no feature row, no tradable flag, and no new exposure. | API / Execution + E-2 design (Stat-M2, F-11) |
| RT-B2-07 | MAJOR | **Hard-coding "shard 2" is unsafe.** The shard table applies to **new** events. Commodities moved to shard 2 only from Sept 10, 2026, 12:00 ET. A series can have several categories (the gas-price example is Economics and Commodities), so mapping category to shard is ambiguous. The docs call the `exchange_index` field "the authoritative source of truth". `exchange_index_statuses` is "Absent when the per-index breakdown is unavailable". | `getting_started_exchange_sharding.md:84-88`; `getting_started_terms.md` (categories); `openapi.yaml:5455`; `changelog_index.md:921-923` | Gate each market on the status entry for **its own** `exchange_index`. If that entry is absent or the index is unknown, the status is UNKNOWN (fail closed). Never fall back to the top-level fields, which describe shard 0. | API / Execution; Risk later |
| RT-B2-08 | MAJOR | **Overclaim: "delivers the full book to any authenticated session".** The source covers only subaccount-restricted keys, so the claim contradicts UR-9. Own-order annotations (`client_order_id`, `subaccount`) appear on the book stream. If the capture key belongs to an account that trades, private account data enters raw market data. | `changelog_index.md:2019-2025` | Correct the text (C1). If a capture credential is ever approved, it belongs to a dedicated non-trading account or subaccount. The parser quarantines the own-order fields. | Lead (text); owner (E-3, F-03) |
| RT-B2-09 | MAJOR (governance) | **The drafts drift toward demo use without naming its preconditions.** "Test in demo" (U12, UR-9, UR-12, the §4.4 plan, and `docs/phase1.md:95`) needs a demo **account** and a **credential**. AR-1 excludes account creation, D3 excludes credentials "of any kind", and `docs/backup_and_recovery.md` does not say whether a demo key counts as "real". Demo "price and behavior ... may not be reflective", so demo can falsify a semantic but cannot close UR-6 or UR-7 for production. Hostnames are easy to confuse: demo `*.kalshi.co` vs production `*.kalshi.com`, plus a second production host, `api.elections.kalshi.com`. | `getting_started_demo_env.md:9-13`; `getting_started_api_environments.md` | An owner decision explicitly classifies demo accounts and keys under F-03 and F-16. Every raw frame header carries an environment identity. Exact-host allowlists per environment; an unknown host is refused. Research loaders refuse demo-tagged captures, proven by a test. | Owner; API / Execution (F-37, RT-4, F-09) |
| RT-B2-10 | MAJOR (protected information) | **Raw lifecycle frames carry outcomes for every market.** `market_lifecycle_v2` "Receives all market and event lifecycle notifications (`market_ticker` filters are not supported)". `determined` carries `result` and `settlement_value`. A raw lifecycle capture therefore holds outcomes for every Kalshi market, including any future protected contract. The drafts quarantine REST outcome fields (Option B) but do not classify the WS frames themselves. | `websockets_market-and-event-lifecycle.md:11`; `asyncapi.yaml:3338+` | Under F-08, classify raw lifecycle frames as outcome-bearing (label channel, released only after reveal). Add them to the guard catalog. Test that `determined` and `settled` reach only `ResolutionRecord`. | Owner (F-08); API / Execution |
| RT-B2-11 | MAJOR | **Slow consumers lose the stream, and the losses cluster.** Error 25 is terminal and happens "during a message burst". Bursts cluster in volatile periods near close, so book losses are not missing at random. If the socket reader is coupled to the raw layer's per-frame durable write, bursts trigger the overflow. | `asyncapi.yaml:45-52`; `getting_started_quick_start_websockets.md`; `docs/raw_data.md:74-75` | Decouple the reader from durable writes with a bounded queue. Queue overflow produces a PMV gap event, never a silent drop. Record error-25 counts in the Stat-M4 ledger by regime. Run a burst-replay load test. | API / Execution (F-33, F-11, M4) |
| RT-B2-12 | MAJOR | **Command outcomes can be ambiguous**, much like an order timeout after possible acceptance. Error 18 ("Command timeout"), 26, or 27 on `add_markets` leaves unknown whether the market was added. | `asyncapi.yaml:20-44` (error table) | After any command error or timeout, reconcile with `list_subscriptions` (`ok.msg.market_tickers` gives the full list), or reconnect. Affected books are invalid until a fresh snapshot. No `add_markets` or `delete_markets` on `orderbook_delta` in v1. | API / Execution |
| RT-B2-13 | MAJOR | **Thursday maintenance and DST.** The window is 03:00–05:00 **ET**, and DST ends on 2026-11-01, which moves the window from 07:00–09:00 to 08:00–10:00 UTC. Disconnects are "should be prepared for", not guaranteed. `exchange_estimated_resume_time` "can be extended". Risks: a hard-coded UTC window; maintenance data labeled tradable; a reconnect storm against the connection limit during the 2 h window. | `getting_started_maintenance_and_pauses.md:9-11`; `openapi.yaml:5451` | A maintenance state taken from `GET /exchange/schedule` `maintenance_windows`, with a timezone-aware ET fallback. The state invalidates books and decisions whether or not a disconnect occurs. Capped reconnect backoff. A pause outside the window = outage → collector unhealthy. | API / Execution; Statistician (pre-registered exclusion) |
| RT-B2-14 | MAJOR | **Schema pinning is not ground truth.** Until Sept 10/17, 2026, Kalshi itself said the AsyncAPI "described some messages inaccurately". A breaking change shipped with no versioning (`available_on_brokers`). Changelog labels are not effective dates: a Sep 25, 2025 entry says "Expected release: October 1, 2025", an Aug 22 entry describes an Aug 20 change, and an Oct 22, 2026 label predates retrieval. Announced changes have been cancelled. | `changelog_index.md:945-965`, `:691-703`, `:837-849`, `:5598`, `:1341`, `:38` | Strict validation fails closed **and** emits counts as collector metadata, so drift is visible. Record the schema hash per capture. Never use `info.version` as a change signal. Add a deterministic production drift alarm. Re-verify on a schedule under a new access request. Label every changelog-derived date "label date, effective date unverified". | API / Execution; Lead (C10) |
| RT-B2-15 | MAJOR | **Without a credential there is no valid Kalshi book.** The REST order book needs no authentication, which makes it tempting, but it has no `seq` and no timestamp. The engine treats unsequenced books as never usable, which is correct. Without E-3, then, no Kalshi book data can be valid. Gate 1 feasibility for book features depends on E-3 and F-16. | `openapi.yaml:9320-9338`; `docs/market_data.md:133,144` | State this in E-3. Polled REST books stay `unsequenced` and are never research book truth. | Lead (E-3 text); owner |
| RT-B2-16 | MAJOR | **Status and timing depend on PMV's clock.** Open and close are implicit. Kalshi's clock synchronization and the signature timestamp tolerance are undocumented. Lifecycle `*_ts` fields are in seconds. OpenAPI `date-time` means RFC 3339, where an offset is mandatory, but conformance is unverified. | `getting_started_market_lifecycle.md`; `api_documentation_findings.md:117` | A clock-health gate (offset bound) before any status derivation. `within_clock_error_of_close` ≥ max(1 s, measured offset). Reject any date-time string without an offset. | API / Execution (F-12, Stat-M3) |
| RT-B2-17 | MAJOR (governance) | **AR-1's egress scope and revocation are unrecorded, and the documentation links into API hosts.** The F-09 denies are absent from project settings (no `kalshi` entry in `.claude/settings.json`), and the allowlist is owner-managed, so I could not verify it. The documentation contains live API links, for example `api.elections.kalshi.com/trade-api/v2/series?category=Crypto`. A wildcard `*.kalshi.com` allowlist would expose the production API hosts. | `getting_started_exchange_sharding.md:87-88`; `docs/backup_and_recovery.md` "Network" | The owner confirms an exact-host allowlist (`docs.kalshi.com`, `kalshi.com`) and records AR-1's expiry and revocation. Implement the F-09 denies for `external-api.kalshi.com`, `api.elections.kalshi.com`, `external-api-ws.kalshi.com`, `demo-api.kalshi.co`, and `*.demo.kalshi.co`. Fetch tooling never follows links. | Owner (F-09) |
| RT-B2-18 | MINOR | **The 64 MiB WS limit equals the raw format's `MAX_PAYLOAD_BYTES` exactly.** Any wrapping, or a decompressed message at the limit, stops and quarantines the capture: fail-closed, but an outage. The limit's direction and whether it applies before or after compression are not stated. Client libraries often default to far smaller maximum sizes (an INFERENCE, to check against the pinned library), which can cause reconnect loops. | `changelog_index.md:611-615`; `src/pmv/raw_format.py:62` | Store the bare message payload with metadata in the header. Set the client's maximum message size explicitly. Do not negotiate `permessage-deflate` in v1, or record the negotiated extension. Test with a synthetic 64 MiB frame. Detect reconnect loops (M4). | API / Execution |
| RT-B2-19 | MINOR | **Quiet markets.** Per-`sid` liveness cannot be proven on a quiet market. A canary on another channel, which is also possibly entitlement-gated, proves only that the connection is alive. | `api_documentation_findings.md:343` | Per-stream silence threshold → stale (M4). Never infer book freshness from a canary. | API / Execution |
| RT-B2-20 | MINOR | **Partial `metadata_updated` messages.** Its fields are optional, and the docs do not say whether an absent field means "unchanged" or "cleared". Before June 18, 2026, changes to `cap_strike` and `strike_type` emitted no event. The event "may expand to more fields". | `changelog_index.md:2589-2598`, `:3365-3367` | The spec fold treats an ambiguous partial update as UNKNOWN until a REST re-poll. | E-2 design |
| RT-B2-21 | MINOR | **Settlement floors.** The settlement-bounds page says floors are "not live yet". The Oct 1, 2026 changelog says markets "now include" `settlement_bounds_type` and `settlement_floor_dollars`, and that a raised floor cancels resting orders. The drafts do not list this as a conflict. | `getting_started_settlement_bounds.md`; `changelog_index.md:355-385` | The parser fails closed on `floor` for BTC until the contract rules are verified. | Parser batch |
| RT-B2-22 | MINOR (governance) | **Decision record.** It was authored by the lead session on the owner's behalf (procedural, F-42). D2 adds "no ... documentation research" for Polymarket. That is stricter than the HEAD wording, and it also prevents assessing E-1's "gold via Polymarket" option. Timestamps need reconciling: the charter was "given on 2026-10-16 (UTC)", but the docs were retrieved 2026-10-15T23:58–23:59Z. | Decision record lines 3, 24; `research/sources.md` | The owner reviews and confirms D1–D3 wording before merge. State that retrieval ran under AR-1 (approved 2026-10-15), and reconcile the times. | Owner; Lead |
| RT-B2-23 | MINOR | **Evidence retention.** The retrieved bytes exist only in session scratch. Hashes alone cannot support a later re-audit of a doc claim. | `api_documentation_findings.md:4` | The owner decides whether to archive the snapshot in an approved location. The license is unknown: the AsyncAPI says "Proprietary", and the terms were not retrieved. | Owner |

## Corrections required to batch-2 drafts

Required before merge (C1–C11):

- **C1** `venue_verification.md:29`.
  - Current text: "It delivers the full book to any authenticated session."
  - Correction: "The changelog (2026-07-23) states that subaccount-restricted keys still receive the full book. Access with a read-only key is unverified (UR-9). Own-order annotation fields can appear on the stream."
- **C2** `sending_ts_ms` is optional.
  - Affected text: `venue_verification.md:78`, "`sending_ts_ms` (all WS messages)"; `api_documentation_findings.md:351`, "(all WS msgs) ... VERIFIED".
  - Correction: "optional on every WS schema (never `required`). The changelog says messages 'now include' it. CONFLICT: absence is flagged, not fatal."
- **C3** Shard gating.
  - Affected text: `venue_verification.md:154`, "Gate trading status on the shard-2 entry of `exchange_index_statuses` for BTC"; `api_documentation_findings.md:586` (§15.6, `exchange_index==2`) and `:420`.
  - Correction: "Gate on the entry matching each market's own `exchange_index`. An absent breakdown or an unknown index is UNKNOWN (fail closed). Never use the top-level fields."
- **C4** Recovery preconditions.
  - Affected text: `venue_verification.md:148`, "recovery is unsubscribe and resubscribe, not a `get_snapshot` rebase"; `api_documentation_findings.md:581(c)`, "a fresh sid gives a fresh snapshot".
  - Correction: add the RT-B2-01 preconditions: a confirmed `unsubscribed`, a new `sid`, and a snapshot for every market; otherwise reconnect. Cite the idempotent-subscribe changelog. Mark "fresh sid" as INFERENCE.
- **C5** `api_documentation_findings.md:295`.
  - Current text: "`ok` (update)" listed as sequenced, "VERIFIED (by schema `required`/properties)".
  - Correction: "`unsubscribed` requires `seq`. `ok` carries an optional `seq`. Subscription-scoped `error` carries `seq` per the changelog of 2026-09-10." Add that the AsyncAPI was officially inaccurate until 2026-09-10/17.
- **C6** `api_documentation_findings.md:314`.
  - Problem: the verification plan depends on U4.
  - Correction: replace it with the differential two-connection test plus invariants (RT-B2-04), and state that demo results cannot close U1–U5 for production.
- **C7** `statistician_review.md:164`.
  - Problem: "[VERIFIED-BY-DOC] Delta semantics ... This reads as **relative**".
  - Correction: re-tag the relativity as INFERENCE. Only the field name and the description "Fixed-point contract delta" are verified.
- **C8** Gold wording.
  - Affected text: `statistician_review.md:26` (H7), "The docs establish **no gold prediction-market series**", and `:247`.
  - Correction: "The docs do not document any gold event-contract series. Existence is UNRESOLVED. The docs do reference Commodities events (shard 2) and 'commodity price timeseries' live data (changelog 2026-07-30)."
- **C9** `venue_verification.md:212-221` (E-1).
  - Addition: every option other than verification (BTC-only, gold via Polymarket, scope revision) is a material scope change. It needs owner approval and a PROJECT_BRIEF.md and CLAUDE.md change. The Polymarket option cannot be assessed while D2 bars Polymarket documentation research.
- **C10** Dates taken from the changelog.
  - Affected text: `venue_verification.md:78,80` ("Added 2026-10-01", "added 2026-04-15"), and `api_documentation_findings.md:267, 450, 589` ("ack/data race fixed Sept 2026; earlier captures may ...").
  - Correction: label each as "changelog label date; effective date unverified".
- **C11** `venue_verification.md:47`.
  - Current text: "with a trading pause and session disconnects".
  - Correction: "a trading pause; clients 'should be prepared for session disconnections' (possible, not guaranteed)."

Recommended (C12–C16):

- **C12** `venue_verification.md` §2, conflicts list. Add:
  - `sending_ts_ms` optional vs "now include";
  - settlement floors "not live yet" vs the 2026-10-01 fields;
  - category-to-shard ambiguity for multi-category series;
  - the AsyncAPI's past inaccuracy;
  - changelog label vs effective date.
- **C13** `api_documentation_findings.md:433`.
  - Current text: "payout rounded to whole cents for scalar".
  - Correction: the docs say the payout (`CollateralAmountChange`) is rounded to whole cents in general, and that settlement **fees** may apply to sub-cent scalar settlement.
- **C14** `venue_verification.md:45`, "of a live market". The docs do not restrict this to live markets. Also add the partial-update and pre-2026-06-18 caveats (RT-B2-20).
- **C15** `venue_verification.md:42`, "Only REST shows them". Correct to: "No WS event type exists; REST status shows them; FIX was not reviewed for these states."
- **C16** Two smaller fixes:
  - `statistician_review.md:116`, "All options assume the m4 split": present the m4 split as a separate open decision, as `venue_verification.md:182` does.
  - `api_documentation_findings.md:4`, "local copies ... are not kept": they currently exist in scratch. Record the retention decision (RT-B2-23).

## Spot-check log

| # | Claim (draft) | Verdict | Evidence |
|---|---|---|---|
| 1 | `seq` description "Sequential number ... snapshot/delta consistency" | Correct | `asyncapi.yaml:2343` |
| 2 | Errors 10 and 25 are terminal | Correct | `asyncapi.yaml:45-52` |
| 3 | `ticker` has no `seq` | Correct | `asyncapi.yaml:3121-3132` (required `type, sid, msg`) |
| 4 | No WS event for open or close | Correct | `getting_started_market_lifecycle.md`, "Implicit (no WebSocket event)" |
| 5 | Top-level exchange status reflects index 0 | Correct, but the "absent" case is omitted | `openapi.yaml:5455` |
| 6 | Gate BTC on shard 2 | **Unsafe extrapolation** (C3) | `getting_started_exchange_sharding.md:84`, "new events" |
| 7 | API versioning removed | Correct | `changelog_index.md:6002-6006` |
| 8 | `sending_ts_ms` on all WS messages | **Overstated**: optional (C2) | `asyncapi.yaml:2322-2325`; no `required` includes it |
| 9 | Ack/data race fixed Sept 17, 2026 | Text correct; the date is a label (C10) | `changelog_index.md:793-804` |
| 10 | 64 MiB message limit | Correct; direction unstated | `changelog_index.md:614` |
| 11 | `delta_fp` relative = INFERENCE | Correct in the API note; **mis-tagged** in the Statistician note (C7) | `asyncapi.yaml` `orderbookDeltaPayload` (`:3094-3096`) |
| 12 | No market-data-only key scope | Correct | `openapi.yaml:5091-5095` |
| 13 | Full book to any authenticated session | **Overstated** (C1) | `changelog_index.md:2019-2025` (subaccount-restricted keys only) |
| 14 | `ok` is sequenced (VERIFIED) | **Overstated**: `seq` optional (C5) | `asyncapi.yaml:2696-2708` |
| 15 | CF Benchmarks 15-min window `(close−60000, close]`, close tick included; not a contract rule | Correct; INFERENCE correctly tagged | `websockets_cfbenchmarks-value.md:97-100` |
| 16 | KXBTC15M appears only as an example and in a changelog mention | Correct | `asyncapi.yaml:1984`; `changelog_index.md:1853` |
| 17 | REST order book has no timestamp and no `seq` | Correct | `openapi.yaml:9320-9338` |
| 18 | `taker_side` removal-date conflict, May 14 vs May 28 | Correct | `openapi.yaml:6912`; `getting_started_order_direction.md:49` |
| 19 | Read 200 / Write 100 at Basic; 429 has no `Retry-After`; "Every **authenticated** request costs tokens" | Correct | `getting_started_rate_limits.md:11,68,112` |
| 20 | Pyth costs $1,000/month | Correct | `websockets_pyth-value.md:11` |
| 21 | `is_provisional` removal | Correct | `openapi.yaml:10089-10092` |
| 22 | Changelog contains future-dated entries | Correct; under-weighted (RT-B2-14) | `changelog_index.md:38` |
| 23 | All 59 page hashes plus `llms.txt` match `sources.md` | Correct | recomputed with `sha256sum` |

## Governance checks

- **Nothing authorizes credentials, API-host access, or account creation.** AR-1 is described as documentation-only, and D3 restates the limits without relaxing any of them.
- **Two gaps remain:**
  - demo preconditions (RT-B2-09);
  - egress-scope evidence (RT-B2-17).
- **AR-3 is correctly framed.** The owner obtains the documents, and the challenge page is not bypassed.
- **The Polymarket deferral is correctly framed** as sequencing, not a change to PROJECT_BRIEF.md (§1, §6). The narrower D2 wording needs owner confirmation (RT-B2-22).
- **Gold** is escalated and not silently re-scoped, subject to C8 and C9.
- **Point-in-time versioning** (`venue_verification.md` §4) is correctly left as options only. The Statistician preference is labeled a recommendation, and Independent Statistical Auditor review is required. C16 fixes one embedded assumption.

## Verdict

**PASS WITH CORRECTIONS for this documentation batch.**
- Merge after C1–C11 are applied and the owner confirms the decision-record wording.
- This is **not** a readiness verdict for any Kalshi parser, collector, `ContractSpec` builder, or demo test. Those stay blocked by E-2, UR-4, UR-6, UR-7, and F-03/F-09/F-16/F-37/RT-4.
- They are now also blocked by RT-B2-01, RT-B2-02, RT-B2-03, and RT-B2-06.
- RT-B2-04, -05, and -07 to -17 must become tests or controls in the collector and parser batches.
- Information I could not verify independently:
  - the owner-managed egress allowlist;
  - the owner's exact batch-2 charter wording;
  - any production behavior. Everything here is documentation-level.

## Lead disposition (added by the lead session, 2026-10-16)

The lead checked C1 and C2 against the retrieved changelog and schemas before applying them. The disposition of each correction:

- **C1–C11 applied.** C1: venue summary and API note. C2: both, recorded as a conflict. C3: both. C4: both, plus the RT-B2-02 and RT-B2-03 conditions added to the venue summary §3. C5: API note. C6: API note and venue summary §3. C7, C8: Statistician note (in place, with errata). C8 is also applied in venue summary §1.7. C9: venue summary E-1. C10: errata blocks and in-place date labels. C11: venue summary §1.2.
- **C12–C15 applied.** C12: added to the conflict list. C13: API note. C14: venue summary §1.2. C15: venue summary §1.2.
- **C16 applied.** The m4 split is stated as a separate open decision in the Statistician note. Scratch retention is recorded as an owner decision (RT-B2-23).
- **RT-B2-09, -10, -17, -22 raised to the owner.** RT-B2-09 and RT-B2-17 are now escalations E-6 and E-7, and RT-B2-10 is item 9 in venue summary §3. RT-B2-22: the decision record's D2 wording was narrowed to "outside the batch 2 charter", the dates were reconciled, and the record now asks for owner confirmation.

The specialist notes are kept as their authors wrote them, apart from these marked corrections.
