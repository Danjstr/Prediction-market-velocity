"""Venue-neutral normalized market data (Phase 1).

Layers, kept separable as CLAUDE.md "Data" requires:

- raw: byte-exact captures (``pmv.raw_format``, ``pmv.raw_storage``);
- normalized observations: ``events`` (what was observable, and when PMV received it);
- decision-time views and feature rows: ``point_in_time``;
- order books reconstructed from snapshots and deltas: ``books``;
- labels and official outcomes: ``labels``, which never enter an observation log.

Contract identity is ``contracts``; timestamp semantics are ``timing``; deterministic
anomaly detection is ``validation``; raw-to-normalized replay is ``replay``. Venue adapters
(``synthetic``, ``kalshi``) sit behind the ``replay.Normalizer`` boundary. See
``docs/market_data.md``.

Nothing here performs network access, reads real market data, or is wired to a loader of
real observations. Real data reaches development only through the protected-information
controls (``docs/protected_information.md``).
"""
