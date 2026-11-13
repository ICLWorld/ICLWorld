#!/usr/bin/env bash
# Linux x86_64 native runtimes; no model requests or credentials.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
RUNTIME="${MATRIX_CLI_ROOT:-$ROOT/.runtime}"
mkdir -p "$RUNTIME"
case "$(uname -s)-$(uname -m)" in Linux-x86_64) ;; *) echo 'This pinned runtime is Linux x86_64.' >&2; exit 1;; esac
NODE=node-v22.21.1-linux-x64
if [ ! -x "$RUNTIME/$NODE/bin/node" ]; then
  curl --fail --location "https://nodejs.org/dist/v22.21.1/$NODE.tar.xz" -o "$RUNTIME/$NODE.tar.xz"
  curl --fail --location https://nodejs.org/dist/v22.21.1/SHASUMS256.txt -o "$RUNTIME/SHASUMS256.txt"
  (cd "$RUNTIME"; grep " $NODE.tar.xz$" SHASUMS256.txt | sha256sum -c -; tar -xf "$NODE.tar.xz")
fi
export PATH="$RUNTIME/$NODE/bin:$PATH"
npm install --prefix "$RUNTIME/cli" @openai/codex@0.164.0
npm install --prefix "$RUNTIME/claude" @anthropic-ai/claude-code@2.1.231
npm install --prefix "$RUNTIME/dsh" @deepseek-ai/dsh@0.2.1-rc.5
npm install --prefix "$RUNTIME/zcode-tools" node@24.14.0 pnpm@10.33.2 esbuild
export PATH="$RUNTIME/zcode-tools/node_modules/.bin:$PATH"
if [ ! -d "$RUNTIME/zcode-source/.git" ]; then git clone https://github.com/zai-org/ZCode.git "$RUNTIME/zcode-source"; fi
(cd "$RUNTIME/zcode-source"; git checkout --detach a60ba6a7e5a06742270ca605f5d2cc2766afa7e1; pnpm install --frozen-lockfile; pnpm --filter '@zcode/cli...' build)
DIST="$RUNTIME/zcode-source/apps/zcode-cli/packages/cli/dist"
cp "$DIST/zcode.cjs" "$DIST/zcode.iclworld.cjs"
python3 - "$DIST/zcode.iclworld.cjs" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();needle='MCP_IMAGE_INLINE_BASE64_BYTES = 200 * 1024;';assert s.count(needle)==1;s=s.replace(needle,'MCP_IMAGE_INLINE_BASE64_BYTES = 8 * 1024 * 1024;');p.write_text(s)
PY
cat > "$RUNTIME/zcode-source/trust-iclworld.ts" <<'TS'
import { createWorkspaceMcpTrust } from './apps/zcode-cli/packages/bootstrap/src/workspace-mcp-trust/index.ts';
const trust=createWorkspaceMcpTrust({workingDirectory:process.argv[2]});
const reviews=await trust.inspect();
if(!reviews.vic)throw new Error('No vic declaration');
await trust.decide('vic',reviews.vic.declarationDigest,true);
TS
(cd "$RUNTIME/zcode-source"; pnpm exec esbuild trust-iclworld.ts --bundle --platform=node --format=esm --banner:js='import {fileURLToPath as mf} from "node:url";import {dirname as md} from "node:path";import {createRequire as mc} from "node:module";const __filename=mf(import.meta.url);const __dirname=md(__filename);const require=mc(import.meta.url);' --outfile="$RUNTIME/trust-zcode-bundle.mjs")
curl --fail --location https://code.kimi.com/kimi-code/install.sh -o "$RUNTIME/kimi-install.sh"
KIMI_VERSION=2.4.1 KIMI_INSTALL_DIR="$RUNTIME/kimi" KIMI_CODE_HOME="$RUNTIME/kimi-home" KIMI_NO_MODIFY_PATH=1 bash "$RUNTIME/kimi-install.sh"
"$RUNTIME/kimi/bin/kimi" --version
printf '%s\n' 'Native CLI installation complete; verify versions before requesting models.' 
