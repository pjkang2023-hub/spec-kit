#!/usr/bin/env bash
# Two-way traceability gate (Bash entrypoint): delegates to the stdlib-only Python implementation.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/../python/verify_trace.py"
if command -v python3 >/dev/null 2>&1; then
    exec python3 "${PY_SCRIPT}" "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "${PY_SCRIPT}" "$@"
else
    echo "Error: python3 or python is required to run verify-trace." >&2
    exit 2
fi
