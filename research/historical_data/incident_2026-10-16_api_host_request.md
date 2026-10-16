# Incident record: research agent requested an exchange API host (2026-10-16)

**Status:** incident record for Phase 1 batch 3 (Red-Team RT-B3-11). Classified as a **serious near miss**. No data was returned. Not a gate record.

**What happened.**
- During the BTC and gold underlying inventory, the research agent requested a documentation-looking path on `api.exchange.bullish.com`, an exchange API host.
- The batch charter forbids contacting any market-data or trading API host.
- The sandbox egress proxy refused the connection, so no content was returned and nothing was recorded.

**Cause.** Host-class confusion. A documentation path was assumed to be safe on an `api.*` host. The agent rules named hosts to avoid, but gave no general host-class rule.

**Detection.** Only the network layer stopped it: a proxy refusal that depends on the owner's per-host decision. The agent-level control failed.

**Related events in the same batch** (detail in `feasibility_summary.md` §7):
- live-value display hosts were attempted and refused by the proxy;
- `www.cfbenchmarks.com` pages were fetched before its terms, which bar automated access, were read. The output contained a live index value.

**Corrective actions (proposed, for owner decision):**
1. Implement F-09 as committed, deterministic host-class denies before the next research batch (decision record O-6). The pattern classes are:
   - `api.*`, `*-api.*`;
   - `clob.*`, `data-api.*`, `gamma-api.*`;
   - RPC hosts;
   - `assets.*` and `data.*` download hosts;
   - S3 `/reporting/` paths;
   - live-value display sites.
2. Every ACCESS REQUEST names the host class (`docs`, `data`, `api`, `live-display`). By default, only `docs` hosts are prompted.
3. Agent briefs state the host-class rule and a "terms first" rule for data-licensor domains.
4. Every batch record counts incidental exposures, refused host attempts by class, and terms events.
