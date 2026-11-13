# Execution plans

Execution plans belong to the codebase. `native_layout/metadata/main.json` defines the Web/OS I/R/E configurations; `native_layout/metadata/ablation.json` defines the A/B/C ablation subset. Robot plans and exact input bindings are under `native_layout/robot/metadata/` and `native_layout/robot/evaluation/`.

`dataset_layout.json` binds the numbered public task names and dataset asset paths to native environment identifiers. `scripts/prepare_dataset.py` builds a runnable Harbor workspace using these definitions and the unified dataset. Dataset metadata itself contains no experiment membership, model choice, seed or budget.

Run plans with any configured model label. The fixed paper subsets are defaults, not restrictions on additional evaluations.
