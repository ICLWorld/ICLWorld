# Dataset and runtime contract

The dataset has one `metadata.jsonl` across Web, OS and Robot, with videos and environment resources under `asset/cua/` and `asset/rua/`. It contains data annotations rather than execution schedules. See the dataset's `README.md` for every field.

Prepare a native workspace with:

```bash
python3 scripts/prepare_dataset.py /path/to/iclworld-dataset --out work/dataset
```

Preparation verifies data assets, reads public task identities and creates the native Harbor task directories. `experiments/dataset_layout.json` maps public names to native environment identities and required resources. `experiments/native_layout/` contains the execution manifests, seeds, budgets, environment bindings, verifier entrypoints and native layout templates. These are codebase resources. Preparation makes no model requests. Use a fresh output directory; source dataset files are not edited.

All subsequent `--dataset` arguments refer to `work/dataset`, the generated workspace. The workspace has 330 Web/OS Harbor schema 1.3 tasks and 176 Robot Harbor packages covering 255 physical configurations. `public-task-names.json` maps native implementation IDs to the numbered public task names. Native directory names are internal to the execution adapters.

The benchmark uses GUI/robot action protocols and authoritative verification, not Harbor's default terminal agent. QA receives question/options but never its answer. Video/None branches must not read text contexts or evaluator state. User-selected models, endpoints and keys are configured independently of dataset annotations.
