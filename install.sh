#!/usr/bin/env bash
set -euo pipefail

RAW_BASE="${AGY_STATUSLINE_RAW_BASE:-https://raw.githubusercontent.com/kkrr6840/agy-statusline/main}"

is_py3() {
  "$@" -c 'import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1
}

is_win_native_py3() {
  "$@" -c 'import os, sys; raise SystemExit(0 if sys.version_info[0] == 3 and os.name == "nt" else 1)' >/dev/null 2>&1
}

PY_CMD=()
UNAME_S="$(uname -s 2>/dev/null || echo "")"

case "$UNAME_S" in
  MINGW*|MSYS*|CYGWIN*)
    while IFS= read -r cand; do
      [ -n "$cand" ] || continue
      if is_win_native_py3 "$cand"; then
        PY_CMD=("$cand")
        break
      fi
    done < <(type -ap python python3 2>/dev/null || true)

    if [ ${#PY_CMD[@]} -eq 0 ] && command -v py >/dev/null 2>&1 && is_win_native_py3 py -3; then
      PY_CMD=(py -3)
    fi

    if [ ${#PY_CMD[@]} -eq 0 ]; then
      echo "Error: Native Windows Python 3 is required on Windows (Git Bash/MSYS2 Python is not compatible)." >&2
      echo "Install Python 3 for Windows or run in PowerShell:" >&2
      echo "  irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1 | iex" >&2
      exit 1
    fi
    ;;
  *)
    if command -v python3 >/dev/null 2>&1 && is_py3 python3; then
      PY_CMD=(python3)
    elif command -v python >/dev/null 2>&1 && is_py3 python; then
      PY_CMD=(python)
    else
      echo "Error: python3 is required to install agy-statusline." >&2
      exit 1
    fi
    ;;
esac

curl -fsSL "${RAW_BASE}/install.py" | "${PY_CMD[@]}" - "$@"
