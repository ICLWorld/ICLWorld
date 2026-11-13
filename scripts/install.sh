#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python - <<'PY'
import site
from pathlib import Path
Path(site.getsitepackages()[0],'iclworld-sdk.pth').write_text(str(Path('runner/sdk').resolve())+'\n')
PY
mkdir -p .runtime
printf '%s\n' 'Python runtime installed. Install pinned native CLIs as described in docs/runtime.md.'
