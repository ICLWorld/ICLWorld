# Runtime and deployment

The release targets Linux x86_64, Python 3.12+, Docker Compose v2 and FFmpeg. The backend needs Chromium, SDL2, Xvfb/noVNC and CJK fonts; the Dockerfile installs these from public sources. The application UI bundles are required runtime assets and are included with the frozen backend source. No private base image or evaluation-server data volume is required.

`bash scripts/install.sh` creates the Python environment and registers the frozen SDK with its interpreter. `bash scripts/install_clis.sh` installs Node 22.21.1, Codex 0.164.0, Claude Code 2.1.231, DSH 0.2.1-rc.5, Kimi CLI 2.4.1, and the pinned ZCode source. ZCode uses Node 24.14.0, pnpm 10.33.2, and commit `a60ba6a7e5a06742270ca605f5d2cc2766afa7e1`. Its single image-transport patch raises the inline MCP image threshold from 200 KiB to 8 MiB; it does not alter image content or grading. The expected evaluated bundle hashes are recorded in `runner/cli-versions.json`; build paths/toolchain can change generated bundle hashes, so the patch assertion and native image guard are also enforced.

`MATRIX_CLI_ROOT` can select another installation directory. `ICLWORLD_CLAUDE_BINARY` can select the matching Claude executable. Native sessions use isolated profiles, disable unrelated local tools and expose the task-specific MCP interface. The dataset and grader are backend-only; the model workspace is empty except for explicitly supplied public task material.

The Compose host port defaults to 8765 and binds only to loopback. `scripts/init_env.py --port PORT` creates fresh secrets and a dataset mount. It never imports server credentials. Named volumes hold new run state. Keep `.env`, provider credentials and workspaces private.

If Docker Hub is unreachable, the same official Python image is available from [Docker's verified ECR gallery](https://gallery.ecr.aws/docker/library/python):

```bash
docker build --build-arg PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.12-slim-bookworm \
  -t iclworld-web-os:local environment
docker compose up -d --wait --no-build
```

Do not equate `--workers` with observed concurrency. Admission pauses with CPU above 95%, available RAM below 16 GiB or disk free below 20 GiB, and reserves memory for each additional worker. The native desktop backend permits at most 12 instances. Use `docker compose down` after all active trials terminate; do not remove volumes needed for receipt verification or debugging.
