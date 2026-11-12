#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
"$PYTHON" -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip kaggle
"$ROOT/.venv/bin/kaggle" --version
printf '\nActivate the CLI with:\nsource "%s/.venv/bin/activate"\n' "$ROOT"
