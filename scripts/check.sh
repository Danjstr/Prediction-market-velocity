#!/usr/bin/env bash
# Run every local quality check. CI runs this same script.
set -euo pipefail
cd "$(dirname "$0")/.."

# uv's default cache (~/.cache/uv) is read-only inside the Claude Code sandbox. Unless the
# caller sets UV_CACHE_DIR, use a fresh private cache under $TMPDIR (or /tmp) for this run
# only and remove it on exit: no repository files, no shared fixed path, no home writes.
if [[ -z "${UV_CACHE_DIR:-}" ]]; then
    uv_cache="$(mktemp -d -p "${TMPDIR:-/tmp}" pmv-uv-cache.XXXXXXXX)"
    trap 'rm -rf -- "$uv_cache"' EXIT
    export UV_CACHE_DIR="$uv_cache"
fi
[[ "$UV_CACHE_DIR" == /* ]] \
    || { echo "check.sh: UV_CACHE_DIR must be an absolute path" >&2; exit 1; }

scripts/scan_secrets.sh
uv_pin_lines="$(grep -E '^version=' scripts/uv.pin)" \
    || { echo "check.sh: scripts/uv.pin has no version entry" >&2; exit 1; }
[[ "$uv_pin_lines" != *$'\n'* ]] \
    || { echo "check.sh: scripts/uv.pin has more than one version entry" >&2; exit 1; }
expected_uv="${uv_pin_lines#version=}"
[[ "$expected_uv" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || { echo "check.sh: scripts/uv.pin has a malformed version entry" >&2; exit 1; }
actual_uv="$(uv --version)"
case "$actual_uv" in
    "uv $expected_uv" | "uv $expected_uv "*) ;;
    *)
        echo "check.sh: uv $expected_uv is required by scripts/uv.pin" >&2
        exit 1
        ;;
esac
uv lock --check
uv sync --locked
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked python -m pmv.gates verify-history
uv run --locked python -m pmv.holdout_log verify-history
uv run --locked python -m pmv.protected_scope verify-history
uv run --locked python -m pmv.data_access_guard check-config
uv run --locked pytest
