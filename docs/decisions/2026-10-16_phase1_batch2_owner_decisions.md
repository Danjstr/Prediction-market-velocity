# Phase 1 batch 2: owner decisions on Kalshi documentation access, Polymarket deferral, and authorization limits (2026-10-16)

**Approver:** the project owner. AR-1 was approved on 2026-10-15 in the session that closed Phase 1 batch 1. The batch 2 charter, which instructed this record, was given on 2026-10-15. Documentation retrieval ran under AR-1 on 2026-10-15, 23:58–23:59 UTC. This record was written by the development session on the owner's instruction just after midnight UTC, hence its 2026-10-16 date. The owner should confirm its wording before merge.

**What this records:** three owner decisions that govern Phase 1 batch 2, "Kalshi venue verification" (branch `phase1/kalshi-venue-verification`). Before this record, `docs/phase1.md` noted that the Phase 1 direction had not been recorded under `docs/decisions/`.

**Limitation:** this record is procedural. The system does not cryptographically prove who approved it (see F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

**This is not a gate record.** It changes no gate, holdout, risk, credential, or data-access rule. Nothing here passes Gate 1 or resolves F-16.

## Decisions

### D1. AR-1 approved: temporary, read-only Kalshi documentation access

- **Scope.** Read-only access to `docs.kalshi.com` and `kalshi.com`, for documentation only, as described in `docs/phase1.md` "AR-1". That covers the API reference and the published OpenAPI and AsyncAPI files; schemas; sequence, snapshot, and authentication semantics; rate limits; historical-data depth; the demo environment; terms and API or developer terms; eligibility; the fee schedule; and BTC and gold contract rules.
- **Excluded.** Kalshi trading and market-data API hosts (production and demo REST and WebSocket hosts), live or historical market values, account creation, and credentials. Example payloads printed in the documentation are illustrations, never data.
- **Duration.** Temporary, for the venue-verification work. Phase 12 re-verification (CLAUDE.md "Real Capital and Venue Access") needs a new request.
- **Recording.** Every source is recorded in `research/sources.md` with its URL and retrieval date.
- **Not covered.** Any other domain, including domains that Kalshi documentation links to or redirects to (for example `help.kalshi.com` or a settlement-source provider). Each needs its own access request (AR-2 and later in `docs/phase1.md`).

### D2. Polymarket remains deferred

- Polymarket work stays deferred until the owner separately approves it **and** its eligibility and API access are verified from current official sources.
- Until then, no Polymarket adapter, collection, account, or credential work is done. Polymarket documentation research is outside the batch 2 charter. Whether to allow it earlier, for example to assess gold availability, is for the owner to decide.
- **Conflict surfaced, not resolved:** PROJECT_BRIEF.md §1 and §6 name both Kalshi and Polymarket. This decision sequences the work; it does not remove Polymarket from the approved scope. Removing it would be a change to PROJECT_BRIEF.md and needs its own approval.

### D3. Authorization limits for this batch

The following are **not authorized** in Phase 1 batch 2:

- real venue credentials of any kind, including data-only or read-only ones (F-03 still applies);
- calls to live market-data or trading API hosts;
- retrieving live or historical market values;
- real-money execution;
- protected-holdout access of any kind;
- irreplaceable live-data capture.

These restate existing controls (CLAUDE.md, `docs/backup_and_recovery.md` "Not authorized in either model", `docs/protected_information.md`) for this batch. They do not relax any of them.

## Related open blocker (not decided here)

The Kalshi `ContractSpec` builder and any real-data label pipeline stay blocked until the owner decides on point-in-time contract metadata and identity versioning (`docs/market_data.md`, review m4 and Statistician M1). Batch 2 may research the facts and propose options. It does not choose or implement the policy. The options are in `research/kalshi/venue_verification.md`.
