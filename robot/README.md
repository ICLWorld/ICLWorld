# Robot

50 embodied task families use A/B/C local rules. Each task/version has a matched **real video, sim video, public task description and text rule**. Both video types contain no audio streams. The physical benchmark has 255 fixed input/environment configurations and a separate 51-item video-QA panel on 17 task families.

## Data and runtime

Robot data uses the same dataset metadata schema as Web and OS. Task videos are under `asset/rua/iclworld_robot_XX/` and physical assets under `asset/rua/environment/`. First run `python3 scripts/prepare_dataset.py /path/to/iclworld-dataset --out work/dataset` from the repository root. The following commands use this generated native workspace. Experiment selection, seeds and budgets reside in the codebase's `experiments/` directory. Answer keys and grading rules are evaluator-only.

The physical backend requires Linux, an NVIDIA GPU, compatible NVIDIA drivers, IsaacSim/IsaacLab, and a native model CLI. The Web/OS Docker service is independent. The dataset supplies USD, textures, geometry and robot assets; this directory supplies native runtime code, the GUI/MCP controller and model adapters.

```bash
python3 -m venv robot/.venv
robot/.venv/bin/pip install -e 'robot/harness/VideoICLBench[test]'
robot/.venv/bin/python -m playwright install chromium
robot/.venv/bin/python robot/scripts/validate.py --dataset work/dataset --media
robot/.venv/bin/python robot/scripts/prepare.py \
  --dataset work/dataset --out /work/robot --experiment main
```

`prepare.py` verifies every runtime file, assembles a fresh workspace, and binds task packages, muted videos, robot profiles and asset roots. It makes no model requests. Omit `--experiment` for all 255 physical configurations. `main`, `generalization`, `ablation4`, `ablation_abc` and `ablation_none` select the corresponding experiment membership; shared configurations are stored once.

## Physical execution

Configure your model, compatible native CLI, API endpoint and key. `--engine` selects the CLI adapter; `--model` is your API model ID. Supported engines are `codex`, `claude`, `dsh`, `zcode`, `kimi`, `qwen` and `gemini`. API credentials stay in a private local file. Engine-specific native context capacities and compaction settings are configurable via `--context-window` and `--compact-tokens`; ZCode derives its compact threshold from the native context/output budgets. Codex requires a complete local model catalog and its SHA-256.

```bash
source /work/robot/environment.sh
export VIC_UPSTREAM_ORIGIN=https://YOUR_API_ENDPOINT
export VIC_PROVIDER_DIRECT=1
export VIC_POOL_AUTHFILE=/work/private/model.key  # one key, mode 0600
export CUDA_VISIBLE_DEVICES=0

# Run one isolated case with a user-selected native CLI and model.
robot/.venv/bin/python robot/harness/pool_verified.py \
  --native-python /opt/IsaacLab/python.sh \
  --gui-python "$PWD/robot/.venv/bin/python" \
  --runtime-root /work/robot/runtime \
  --cases /work/robot/cases/af26-e01-c-i-real-s4201.json \
  --engine dsh --model YOUR_MODEL_ID --binary /path/to/dsh \
  --effort high --epoch run-001 --out /work/results/run-001 \
  --max-actions 500 --timeout 0 --coalesce-window-seconds 0.05 \
  --allow-unvalidated-environment
```

First use `--probe-only --max-actions 8 --timeout 120` in a separate output directory to check the native world and GUI without a model request. The explicit native-environment flag enables the supplied engineering backend; it is not evidence of completed GPU validation. Run each generated case file as an independent simulation instance by default. Pooling requires checking the case's `runtime_requirement` and memory capacity; configurations requiring independent paired instances must not share a physical world. Use `--experience`, `--browser-path` and `--native-kit-args` when required by the installed simulator.

Physical execution is limited to 500 actions with no global wall-clock deadline. Native terminal success and process score are separate outputs. Infrastructure failures are unscored. Native task rules and final evaluation are outside the model's workspace.

## Independent video QA

The QA branch exposes only `demo_info`, `demo_frames`, `qa_question` and `qa_answer`. It uses no simulator, robot action, text rule or answer key. The first valid answer is immutable; grading is offline. The launcher supports Codex, DSH and ZCode adapters with configurable model IDs and API endpoints.

```bash
export MODEL_API_KEY=YOUR_KEY
# Validation only unless --execute is supplied.
robot/.venv/bin/python robot/qa/evaluate.py \
  --dataset work/dataset --qa-id af26-qa-e01-c-real-s4201 \
  --engine dsh --model YOUR_MODEL_ID --binary /path/to/dsh \
  --api-base https://YOUR_API_ENDPOINT --out /work/qa/e01-c

# Add --execute to the same command to request the model.
robot/.venv/bin/python robot/qa/grade.py \
  --dataset work/dataset --out /work/qa/e01-c
```

CLI installation must match the adapter's supported version. The robot and Web/OS adapters have separate Python environments. `harness/VideoICLBench/packages/sdk/vic_sdk/direct_tools.py` lists supported Codex versions; other versions are declared in `harness/worker/adapters/`. Use the CLI installation guide for the relevant engine rather than sharing an incompatible installed binary.

## Checks and provenance

```bash
PYTHONPATH=robot/harness/VideoICLBench/packages/sdk:robot/harness/VideoICLBench/tests \
  robot/.venv/bin/python -m pytest -o addopts='' robot/harness/tests robot/qa/test_video_qa.py
```

Source revisions and data origins are recorded in the dataset's `robot/metadata/sources.json`. Dataset and codebase `SHA256SUMS` cover all published files. The [source repository](https://github.com/Aoraku/VideoICLBench) supplies the simulator harness under its included MIT license; IsaacSim/IsaacLab and third-party assets retain their own terms. The [public trajectory repository](https://huggingface.co/datasets/JJimmyL/VideoICL-Embodied-Evaluation-Trajectories-Public) provides optional result analysis independently of the benchmark inputs.
