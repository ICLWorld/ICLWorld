#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${CONDA_BIN:-}" && -z "${OS_ICL_PYTHON:-}" ]]; then
  exec "$CONDA_BIN" run --no-capture-output -n "${OS_ICL_CONDA_ENV:-data_mining}" \
    python "$ROOT_DIR/server.py" "$@"
fi
TASK_PYTHON="${OS_ICL_PYTHON:-python3}"
if ! command -v "$TASK_PYTHON" >/dev/null 2>&1; then
  echo "Python interpreter not found: $TASK_PYTHON. Activate your environment or set OS_ICL_PYTHON." >&2
  exit 1
fi
exec "$TASK_PYTHON" "$ROOT_DIR/server.py" "$@"
