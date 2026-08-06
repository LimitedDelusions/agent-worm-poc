# Model Configuration and Compatibility Gate

## Why these four models

The sample intentionally spans four distinct developer/model lineages and includes dense, mixture-of-experts, multimodal, and hybrid Mamba/attention designs. The POC does not claim that one selected checkpoint represents its entire family.

## Candidate repositories

| Slot | Repository | Runtime notes |
|---|---|---|
| `qwen_slot` | `Qwen/Qwen3-30B-A3B-Instruct-2507` | BF16; text instruct model |
| `gemma_slot` | `google/gemma-3-27b-it` | BF16; gated license acceptance required |
| `gpt_oss_slot` | `openai/gpt-oss-20b` | Native low-precision weights; low reasoning effort requested |
| `nvidia_slot` | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` | BF16; exact trusted code and custom reasoning parser are frozen |

## Runtime controls

All models use:

- one A100 80 GB GPU;
- vLLM 0.25.1;
- one model loaded at a time;
- tensor parallel size 1;
- 8,192-token context limit;
- maximum one active sequence;
- 90% GPU-memory utilization target;
- eager execution;
- model generation defaults disabled in favor of the fixed POC parameters.

## Immutable freeze

Before any real model server starts, the POC:

1. authenticates to Hugging Face with a read-only token;
2. obtains the exact 40-character commit SHA for each repository;
3. freezes model and tokenizer revisions;
4. downloads and hashes `config.json` and `tokenizer_config.json`;
5. downloads the Nemotron parser from the same frozen revision;
6. records all hashes and paths;
7. parses the frozen file through the same strict config loader used by the experiment.

## Compatibility pass rule

A model passes only if it:

- loads successfully;
- releases GPU memory after shutdown;
- returns schema- and semantic-valid JSON for all roles;
- completes three benign workflows correctly;
- completes one injected workflow without infrastructure or output-format failure.

A failed model does not enter the placement POC. The gated run stops instead of silently substituting another model.

## Why no automatic fallback model

Automatic substitution would change the research question after testing started. Any replacement must be discussed, documented, and followed by a new frozen model inventory and a new POC session.
