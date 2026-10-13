#!/usr/bin/env bash
# Run every local quality check. CI runs this same script.
set -euo pipefail
cd "$(dirname "$0")/.."

uv lock --check
uv sync --locked
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest
