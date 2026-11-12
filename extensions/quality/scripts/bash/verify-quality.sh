#!/usr/bin/env bash
# Deterministic systems quality verification gate (Bash entrypoint).
# Delegates to the sibling stdlib-only Python implementation when Python 3 is
# available (always present in Specify CLI environments), with identical CLI
# semantics across sh / py / ps1.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/../python/verify_quality.py"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: verify-quality.sh [--json] [--soft-exit | --strict] [--project-root <dir>]

Run deterministic compiler, linter, test/sanitizer, and zero-stub verification
gates for C, C++, Rust, and Go projects.
EOF
    exit 0
fi

if command -v python3 >/dev/null 2>&1; then
    exec python3 "${PY_SCRIPT}" "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "${PY_SCRIPT}" "$@"
else
    echo "Error: python3 or python is required to run verify-quality." >&2
    exit 2
fi
