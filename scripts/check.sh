#!/usr/bin/env bash
# Run every local quality check. CI runs this same script.
set -euo pipefail
cd "$(dirname "$0")/.."

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
uv run --locked pytest
