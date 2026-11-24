#!/bin/sh
set -eu
exec "${ICLWORLD_PYTHON:-python3}" "$(dirname "$0")/verify.py"
