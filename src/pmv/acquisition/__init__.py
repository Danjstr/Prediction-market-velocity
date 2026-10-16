"""Source-neutral historical-acquisition readiness controls (``docs/external_access.md`` §2).

This package holds deterministic, fail-closed building blocks for the historical
acquisition gate. Nothing in it contacts a network host, and no real observation has
passed through it. It is exercised only with synthetic fixtures. Acquisition stores
bytes; it never makes a row visible to an agent (A-8):

- ``hosts``: per-source host and URL-prefix allowlists, with host-class refusal (A-1, F-09);
- ``records``: approval, licence, acquisition-manifest, and source-quality records
  (A-1, A-2, A-5, A-6);
- ``formats``: the parse-format allowlist and content sniffing (A-4);
- ``strict_parse``: strict JSON, JSONL, CSV, and decimal parsing (A-4);
- ``archive``: bounded, link-free, traversal-free archive extraction (A-4);
- ``quarantine``: hash-on-receipt intake and manifest-gated release from quarantine (A-4, A-5);
- ``receipts``: the durable, hash-chained receipt journal for intake and release (A-5);
- ``backup``: backup copy and restore verification against a manifest (A-3);
- ``confinement``, ``worker_protocol``, ``parse_worker``, ``isolation``: isolated, rlimited,
  seccomp-confined parsing and extraction in a separate process (A-4, G-1);
- ``readers``: the reader registry, expected schemas, strict streaming verifiers, and
  bounded single-file decompression (A-4, G-2, G-3, G-5);
- ``fetch``: the fetcher behind an injectable transport, with per-redirect
  re-authorization (A-1, A-4, G-4). No production transport exists;
- ``plan``, ``state``, ``pipeline``: the acquisition plan and evidence records, the
  explicit state machine, and the orchestrator into the protected raw store (G-6, A-7);
- ``synthetic``: a scripted transport and synthetic records for dry runs and tests.

Passing these controls is necessary but never sufficient: every acquisition still needs
the owner approvals and records listed in ``docs/external_access.md`` §2.
"""
