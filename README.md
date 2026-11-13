# ICLWorld

[Dataset](https://huggingface.co/datasets/Aoraku/ICLWorld) · [Code](https://github.com/ICLWorld/ICLWorld)

ICLWorld evaluates whether interactive agents can learn customized rules from context and apply them in interactive environments. Human video demonstrations and matched textual rules specify task-specific conventions, including counterfactual conventions that differ from common priors. Execution, rule-version ablations, generalization, and independent multiple-choice diagnosis measure complementary aspects of in-context learning.

The benchmark contains **160 tasks: 75 Web, 35 OS and 50 Robot**, each with A/B/C rules. One dataset metadata file describes all domains; data assets are organized under `asset/cua/` and `asset/rua/`. This repository provides the environments, execution protocols, experiment plans and Harbor workspace generation.

## Contents

- `environment/`: self-hosted Web applications, desktop simulations, deterministic generators and authoritative graders.
- `runner/`: native agent CLI adapters, pixel/coordinate tools, context isolation, and pre-action QA branching.
- `experiments/`: full evaluation and fixed 25-Web/12-OS ablation manifests.
- `scripts/`: environment setup, dataset checks, experiment launch and score aggregation.
- `robot/`: IsaacSim/IsaacLab runtime, native GUI harness, physical experiment preparation and independent video QA.

The dataset is distributed separately as unified metadata and data assets. The codebase generates Harbor task directories. Execution uses the ICLWorld native GUI backend; these tasks are **not shell tasks for Harbor's default Docker agent**. See [dataset contract](docs/dataset.md).

## Web and OS quick start

Use a Linux x86_64 machine with Docker Compose, Python 3.12+, FFmpeg, and adequate RAM. Download the dataset from Hugging Face, then generate the Harbor workspace locally. Parallel runs require at least 24 GiB available RAM and 20 GiB free disk after installation.

```bash
bash scripts/install.sh
.venv/bin/pip install huggingface_hub
.venv/bin/hf download Aoraku/ICLWorld --repo-type dataset --local-dir work/iclworld-dataset
bash scripts/install_clis.sh
.venv/bin/python -m unittest discover -s tests
python3 scripts/prepare_dataset.py work/iclworld-dataset --out work/dataset
.venv/bin/python scripts/validate_dataset.py work/dataset --media
python3 scripts/init_env.py --dataset work/dataset
docker compose build
docker compose up -d --wait
.venv/bin/python scripts/smoke_environment.py --dataset work/dataset --output work/smoke --all
```

Copy `providers.example.json` to a private configuration file and set the referenced API-key environment variables. Endpoint and model access must be supplied by the user. Each configuration entry specifies `engine`, `api_model`, `base_url`, and `key_env`. Add any model label and select it with `--models my-model`; the benchmark does not restrict API providers or require the listed model IDs. Native CLI versions and installation requirements are in [runtime setup](docs/runtime.md).

```bash
# Inspect coverage without making model requests.
.venv/bin/python scripts/experiment.py main --dataset work/dataset \
  --work work/main --dry-run

# The default six-model I table and fixed R/E subsets: 1,920 trials.
# Add --models my-model to run any model configured in your provider file.
.venv/bin/python scripts/experiment.py main --dataset work/dataset \
  --work work/main --providers providers.private.json --workers 8

# None-C, Video-A/B/C, QA-A/B/C on the fixed 37-family subset.
# Optionally reuse matching Video-C trials from a completed main workspace.
.venv/bin/python scripts/experiment.py ablation --dataset work/dataset \
  --work work/ablation --providers providers.private.json --reuse-main work/main --workers 8

.venv/bin/python scripts/scores.py --work work/main
.venv/bin/python scripts/scores.py --work work/ablation
```

The default three-model ablation contains **777 trials**. Optional reuse is accepted only when model configuration, inputs and result checksums match. See [experimental protocol](docs/experiments.md) for seeds, budgets, conditions and scoring. Concurrency is bounded by memory and CPU; native desktop applications have a separate hard capacity of 12 instances. Begin with a small run before increasing `--workers` (maximum 96).

## Input and evaluation boundaries

Video agents receive video-frame tools and the public goal; text agents receive the full text rule and the public goal. None-C receives neither demonstration nor private rule. Agents interact through screenshots and coordinate input. Dataset answer keys, grader state and source code remain outside the agent workspace. QA forks the context before the first environment action and never feeds an answer back to execution.

Results include authoritative evaluation, identity checks and SHA-256-bound receipts. API/infrastructure errors remain ungraded for review. A terminal model failure is a valid result, not a reason to rerun. Hosted model outputs and provider behavior are not deterministic; reproducibility refers to the released tasks, protocol, runtimes and scoring.

Project code uses the existing [MIT license](LICENSE); third-party resources retain their own terms. See [license inventory](docs/licenses.md).

## Task documentation

The dataset root contains `TASK_REFERENCE_EN.md`, covering all 160 task families, their A/B/C rules and available conditions, and `README.md`, documenting every metadata field. These are evaluator references; they must not be exposed to video-only or no-context agents.
