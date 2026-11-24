# Web/OS experimental protocol

## Main and generalization

Replay, Resample and Relocate are the three generalization levels of the paper; code, metadata and file names use `replay`, `resample` and `relocate`. Resample is the independent and identically distributed (IID) level: for a fixed task and rule, demonstration and evaluation instances are independently sampled from the same task distribution. Replay restores the demonstrated situation, and Relocate moves the task to the counterpart environment. The dataset README defines these levels and the difficulty criteria for all three domains.

The paper evaluates six models, each in a native agent CLI: Claude Opus 5.5 (Claude Code), GPT-6 Astra (Codex), Qwen3.8-Max (Claude Code), GLM-5.3-Flash (ZCode), Kimi K3 (Kimi Code) and DeepSeek-V4.1-Flash (DeepSeek Harness, DSH). All request high reasoning effort through their native runtimes.

Each model has 320 trials: 110 Resample configurations × video/text (220), 13 Replay configurations × video/text (26), and 37 Relocate configurations × video/text (74). Replay and Relocate are fixed stratified subsets, so their aggregate differences do not isolate a causal generalization effect. The main table is Resample only, split by Web/OS and easy/medium/hard. Completed accuracy is correct / valid completed; coverage must be reported separately against the fixed denominator.

Resample and Relocate use seed 4201. Replay replays the demonstration's frozen initial state: Web seed 0 and OS seed 1001. The dataset binds replay state and source video by SHA-256. Each execution has a 3,600-second wall budget and 800 input actions. A/B/C variants retain their own graders.

## Ablations

The fixed subset contains 25 Web and 12 OS task families. The paper evaluates Astra, DeepSeek and GLM; the launcher accepts additional model configurations. Each model contributes 37 None-C execution trials, 111 Video-A/B/C execution trials, and 111 QA-A/B/C trials: 259 per model, 777 total.

When `--reuse-main` is supplied, matching Video-C trials can be imported from a completed main workspace. The launcher checks the user's model configuration, public prompt, video checksum, authoritative result and receipt identity. Otherwise, all trials are executed. Model labels are configurable; use `--models` to evaluate other models under the same protocol.

QA consumes the complete actual viewing prefix before the first action. It is not a separate video-only prompting experiment and cannot use final execution outcomes. None-C suppresses automatic SDK demonstration downloads and contains no private textual rule.

## Model configuration and results

API access is supplied by the experimenter. Each entry in the provider configuration defines a local model label, native `engine`, API `api_model`, endpoint `base_url`, and API-key environment variable `key_env`. Model labels can be added freely and selected with `--models`; provider endpoints are not hardcoded. The supported native engines are Codex, Claude Code, Kimi Code, DSH and ZCode. Additional engines can be implemented through the runner adapter interface.

The launcher records the selected configuration and refuses to mix changed configurations into an existing workspace. Use a separate workspace for a different model or protocol configuration. API keys are never part of the release.

`tests/verify.py` checks final evaluation identity and reward. Execution process score is the authoritative partial score; QA reports choice accuracy. Report transport failures and missing results separately, never as completed trials or zeros. Existing terminal results are protected from automatic reruns.
