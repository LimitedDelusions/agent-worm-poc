# Model Configuration

## Fixed candidate deployments

1. Qwen/Qwen3-30B-A3B-Instruct-2507
2. google/gemma-3-27b-it
3. openai/gpt-oss-20b
4. nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16

These are four specific deployments, not representatives of every model in their broader families.

## Freeze gate

Before real inference, `freeze-models` records:

- model revision;
- tokenizer revision;
- access probe files;
- remote-code revision where applicable;
- local Nemotron reasoning-parser file and SHA-256.

The server refuses real runs when required revisions or parser hashes are missing.

## Common controls

- one A100 80 GB GPU;
- one model loaded at a time;
- vLLM 0.25.1 pinned in the container;
- common generation settings from `configs/experiment.json`;
- one request at a time;
- official model chat behavior through the OpenAI-compatible endpoint;
- model-specific overrides only where declared in `configs/model_candidates.json`.

## Model-specific serving controls

- **GPT-OSS 20B:** uses vLLM's native Harmony/reasoning handling. Requests set `reasoning_effort=low`; no custom reasoning-parser plugin is configured.
- **Nemotron 3 Nano:** uses the model repository's `nano_v3` reasoning-parser plugin. `freeze-models` downloads that parser from the exact frozen model revision, records its SHA-256, and the server refuses to launch if the file or hash changes. Requests set `enable_thinking=false`.
- **Qwen and Gemma:** use their frozen official tokenizer/chat-template behavior through the common OpenAI-compatible vLLM endpoint.

These differences are recorded as properties of the four exact deployments and are not altered between placements.

## Replacement rule

Do not replace a model during the gated run. If a model fails compatibility, stop, preserve the evidence, revise the candidate set, rebuild the image/config, and rerun all gates from the beginning.
