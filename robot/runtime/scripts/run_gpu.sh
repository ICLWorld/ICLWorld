#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
: "${ICLWORLD_ISAACLAB_ROOT:?Set ICLWORLD_ISAACLAB_ROOT to IsaacLab checkout}"
: "${ICLWORLD_ISAAC_PYTHON:?Set ICLWORLD_ISAAC_PYTHON to an existing Isaac Sim Python environment}"
export PYTHONPATH="$project_dir:$ICLWORLD_ISAACLAB_ROOT/source/isaaclab:$ICLWORLD_ISAACLAB_ROOT/source/isaaclab_assets:$project_dir/vendor/python:${PYTHONPATH:-}"
if [ -n "${ICLWORLD_ISAACSIM_ROOT:-}" ]; then export ISAACSIM_PATH="$ICLWORLD_ISAACSIM_ROOT"; fi
export ACCEPT_EULA=Y
export OMNI_KIT_ACCEPT_EULA=YES
exec "$ICLWORLD_ISAAC_PYTHON" "$@"
