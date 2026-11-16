#!/usr/bin/env bash
set -euo pipefail

RAW_BASE="${AGY_STATUSLINE_RAW_BASE:-https://raw.githubusercontent.com/kkrr6840/agy-statusline/main}"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Error: python3 is required to install agy-statusline." >&2
  exit 1
fi

curl -fsSL "${RAW_BASE}/install.py" | "$PY" - "$@"
