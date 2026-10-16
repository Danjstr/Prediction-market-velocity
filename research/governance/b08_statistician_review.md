# B08 Statistician review: prospective-capture hardening

- **Reviewer:** development Statistician (development-time self-review; **not** independent validation).
- **Scope:** branch `b08/prospective-capture-hardening`, commit `222a7e7`, against parent `1aa6c52`. Read-only review, limited to statistical observation semantics and leakage.
- **Material read:**
  - `docs/decisions/2026-10-16_b08_prospective_capture_hardening.md`;
  - `docs/market_data.md` (clocks, normalization boundary, v2 sessions and artifacts, book faults, validation);
  - `docs/raw_data.md` (frame format v2);
  - `git diff 1aa6c52 222a7e7` for `src/pmv/market_data/{events,books,validation,replay,timing}.py`;
  - `src/pmv/market_data/capture_replay.py`, `src/pmv/capture_format.py`;
  - the relevant parts of `src/pmv/capture_store.py` (`_append`, `_write_event`, `iter_frames` connection discipline) and `src/pmv/market_data/point_in_time.py` (`effective_availability`, `status_as_of`).
- **Data:** synthetic only. No real observation exists or was accessed. No test suite was run.
- **Disclosure:** the Statistician did not author B08 code. Earlier Statistician items (M4 exclusion ledger, B6S findings) are referenced.

## Summary

B08 introduces no look-ahead path. Each new rule moves information later, or makes book state unusable more often. None moves information earlier.

- `available_at` stays the wall-clock receipt time. For payloads this is `observed_at`; for events it is the store's `written_at`.
- Effective availability is still the running maximum in capture order. Since session = capture and `sequence` is session-wide, the capture-order prefix property holds.
- `frame_rejected`, connection-event resets, and the `solicited` rule are all conservative for book state.

The statistical risks are on the **selection** side, not leakage:
- new fault and exclusion mechanisms are correlated with fast markets;
- a rejected frame silently removes non-book information (trades, trading status, reference ticks) with no fault on those channels;
- clock-quality evidence needed for F-12 / `max_clock_error` is not yet captured.

None of these blocks B08. Several must be recorded before real data is normalized or consumed.

**Verdict: PASS WITH CONDITIONS** (no BLOCKING finding; two MAJOR conditions that apply before real data or feature work, not before merging B08).

## Answers to the five questions

### 1. Look-ahead / availability time

No change makes information usable earlier than PMV received it.

- **Payload frames:** `received = observed_at` (`capture_replay._payload`), unchanged from v1 semantics.
- **Driver `frame_rejected` events:** stamped at the rejected frame's own `observed_at` and placed at that frame's sequence position, with item index 0. They carry no payload information: kind, time, and provenance only.
  - Its only effect is to break books, which can only reduce what a view may use.
  - Its existence reveals that "some frame was rejected at t". That is also known live at t.
- **Event frames:** use `written_at`, the store's own clock at write time. This is at or after the condition it records, so it is conservative.
- **Monotonic time** is kept in `FrameEntry` and never feeds `available_at` (question 5).
- **Effective availability:** `point_in_time.effective_availability` still raises every item to the running maximum within its capture in provenance order. A wall-clock step backwards therefore cannot pull later frames earlier, and a step forwards only delays.

Residual (pre-existing, not introduced by B08): `observed_at` is supplied by the caller, and neither store checks it against the store's own clocks. See B8S-03.

### 2. Continuity rules, selection, and exclusion

All new rules are conservative for book usability. None is non-conservative in the leakage sense.

| Rule | Direction |
|---|---|
| `frame_rejected` breaks every book in the session | conservative |
| connection opened/closed resets books and sequence expectations | conservative |
| segment rollover does not reset | correct: rollover is a storage boundary within one ordered stream, guaranteed by the hash chain, `previous_last_sequence`, and session-wide sequence continuity in `iter_frames` |
| a `solicited` snapshot keeps earlier faults and adds `unverified_snapshot` | conservative. Its venue sequence still enters sequence tracking. Any value other than exactly `previous + 1` produces a gap, regression, or duplicate, so this is also conservative |
| validation: solicited snapshot drops the book, so later deltas are `delta_without_snapshot` | conservative, consistent with `books.py` |

The rules are conservative for availability, but they increase **non-random missingness**:
- session-wide breaks on a single rejected frame;
- the permanent-until-unsolicited-snapshot rule.

Both are more likely in bursts, near close, and at high volatility, which is where a velocity edge would live (RT-B2-11; the M4 note in `docs/market_data.md`). That must be recorded (B8S-01).

One rule is a **coverage gap**: a rejected frame removes trades, trading status, and reference ticks without any marker on those channels (B8S-02).

### 3. Effective-availability / capture-order prefix for v2

Preserved.
- **Provenance:** `(session_id, sequence, item_index)`.
- **Sequence:** one counter per session across segments, with continuity re-verified on read (`iter_frames`).
- **Reading:** the readable chain stops at the first non-finalized segment and never bridges a gap. Later segments are only reported as `unreachable_indices`.
- **Prefix property:** the normalized log of a session is therefore always a capture-order prefix of what PMV received in that session.
- **Decoding:** `decode_artifact` checks that each frame accounts for exactly its own items, so a moved, dropped, or added observation is detected.
- **One subtlety:** a truncated or salvaged chain has no terminal marker (B8S-04).

### 4. Protected-data semantics, observation families, T0, split, holdout

No effect found.
- Normalized artifacts are written only under the capture store's protected root. Nothing is released (A-7, A-8).
- `require_data_use` refuses demo sessions for every use, and synthetic sessions outside tests. This is stricter, not looser.
- `gates create` and `holdout_log record` refuse `--environment test`. This is stricter.
- No observation-family, `T0`, margin, split, purge, or holdout code or document changed.

One forward-looking note on research degrees of freedom: artifact keys include the parser version (B8S-05).

### 5. Monotonic time and `available_at`

Keeping `CLOCK_MONOTONIC` out of `available_at` is **correct**:
- It has no UTC anchor.
- It is comparable only within one boot (`clock_domain`).
- `available_at` must be comparable across sessions, with contract open, close, and reference times, and with labels.
- The running-maximum wall-clock rule already handles backward steps conservatively.

Monotonic time is the right instrument for **measuring** wall-clock quality, not for replacing it. B8S-03 lists what to record for F-12.

## Findings

| ID | Severity | Finding | Recommendation |
|---|---|---|---|
| B8S-01 | MAJOR (condition before real data is normalized for research; not a B08 merge blocker) | **New exclusion mechanisms are not missing at random.** `frame_rejected` (session-wide), connection resets, `unverified_snapshot`, and chain truncation or salvage (`SessionStatus` ≠ `complete`, `unreachable_indices`) all create unusable-book intervals or lost data. These are likely concentrated in bursts and volatile late-window periods. Under the rule "until the book's own unsolicited snapshot", a venue that only sends snapshots at subscription leaves books unusable until reconnect. Every `frame_rejected` is BLOCKING, so a parser defect that recurs systematically would silently convert into a large, regime-correlated exclusion. | Extend the M4 exclusion ledger (`docs/phase2.md` §13) before any real v2 artifact is used. Required content: <br>- counts and **durations** of unusable-book time by fault (`frame_rejected` by rejection reason, `stream_reset` by event kind, `unverified_snapshot`), by session status, and by unreachable segment count; <br>- stratified by volatility, time remaining, venue, and period. <br>Report the fraction of late-window decision times lost to each fault. Set an alert threshold on the rejection rate per parser version, so that a parser defect cannot pass as data. When venue semantics are verified (AR-1), revisit whether session-wide breaks can be narrowed to sequence scope. Any narrowing is a reviewed change. |
| B8S-02 | MAJOR (condition before feature or simulation code consumes v2 artifacts) | **A rejected frame breaks books but not other channels.** The rejected frame may have carried a `Trade`, a `TradingStatusUpdate` (for example a halt or close), a `ReferenceTick`, or a resolution. `status_as_of` explicitly ignores later stream resets, and trade or reference windows are not marked. Missed halts could let simulated trades occur in a non-tradable market. Lost trades or ticks bias velocity and order-flow features in exactly the bursty periods. | Define, before Phase 2 feature work: <br>(a) after any `RESETS_BOOK_STATE` event (including `frame_rejected`), trading status is **unknown** until the next status update, or the simulator treats the contract as non-tradable; <br>(b) any feature window containing a `frame_rejected` or reset event is flagged and reason-coded (M4); <br>(c) the sensitivity of results to flagged windows is reported. This adds no leakage. It is a coverage rule. |
| B8S-03 | MINOR (pre-existing; condition before live capture, F-12) | **Clock evidence is not yet captured, and `observed_at` is caller-supplied and unchecked.** <br>- Nothing enforces `observed_at ≤ written_at`, or consistency between the caller-supplied payload `monotonic_ns` and the store's own monotonic clock. A collector that stamps `observed_at` from a batch time or a source time would create look-ahead invisibly. <br>- No wall-clock synchronization state is recorded, so `max_clock_error` cannot yet be bounded from data. | Before live capture: <br>(a) the collector stamps `observed_at` and `monotonic_ns` together at socket read, and this is recorded as a tested collector requirement; <br>(b) the store records or flags `observed_at > written_at`. The internal queue delay `written_at − observed_at` becomes a monitored distribution; <br>(c) record clock-sync state per segment or periodically, for example kernel `adjtimex` maxerror/esterror and sync status, or the NTP/chrony offset, as events or header fields. <br>For the F-12 analysis, per session: <br>- the drift of `observed_at − monotonic_ns` (wall-clock steps and slew); <br>- the distribution of `observed_at − source_timestamp` (lead and lag against the venue, a lower bound on latency); <br>- cross-host offsets if sessions run on different hosts. <br>Set `LabelPolicy.max_clock_error` from the upper quantiles of these, plus a margin, and freeze it before use. |
| B8S-04 | MINOR | **A truncated or salvaged chain has no terminal marker.** A session with status `truncated`, `ends_with_salvage`, or `open` ends without `session_closed`. Book state stays "usable" up to `max_silence` after the last frame, although the collector is known to have failed. A live system would know its own feed died. | In the normalized view or the M4 ledger, treat a non-`complete` chain end as a reset at the last frame's effective availability. Alternatively, cap `AsOfView` decision times for that session at that point. Record session status alongside every derived row. |
| B8S-05 | MINOR | **Parser version is a research degree of freedom.** Content addressing correctly makes each parser version a separate artifact. This also makes several normalizations of one session coexist. Choosing among them after seeing results would be an uncontrolled selection. | Pin the parser version per experiment in the experiment record. Re-run the full comparison on a parser change, never cherry-pick by outcome. Log every artifact version produced (failed and superseded ones included) in the research history. |
| B8S-06 | NOTE | **Skipped frames do not break books.** This depends on parser discipline: a parser that "skips" a message carrying book state would hide a loss. Similarly, `solicited` is set by the parser. | Parsers should skip only from an enumerated, tested reason list, and should mark command replies `solicited` as identified by the outbound-command correlation. Cover both in the parser tests when AR-1 semantics are verified. |
| B8S-07 | NOTE | **Multiple concurrent connections in one session share book keys** (`capture_id = session_id`). Interleaved streams for one market would produce duplicate or regression faults, and every connection event breaks all books. This is conservative. | Record which connections carry which subscriptions. If one session later multiplexes feeds, consider per-connection capture identity. That would be a reviewed change. |

## Verdict

**PASS WITH CONDITIONS** for B08 as an engineering batch on synthetic data.
- No BLOCKING finding.
- No look-ahead introduced.
- No effect on protected-data semantics, observation families, `T0`, split, or holdout.
- B8S-01 and B8S-02 are MAJOR conditions. They must be recorded as requirements, and implemented before real v2 data is normalized for research (B8S-01) or consumed by feature or simulation code (B8S-02).
- B8S-03 must be resolved before live capture is authorized.

This is a development self-review and does not substitute for independent statistical review.
