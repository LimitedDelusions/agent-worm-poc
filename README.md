# Agent Worm Model-Placement POC v0.6.0

This project is a controlled proof of concept for the research question:

> **How does the placement of Qwen3-30B-A3B-Instruct-2507, Gemma-3-27B-IT, GPT-OSS-20B, and NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 within a fixed four-agent workflow affect the propagation of synthetic self-replicating prompt injections?**

It runs four open-weight model deployments through a fixed four-role workflow and evaluates all 24 possible placements. The synthetic injection can only reproduce a marker and request a **nonfunctional mock action**. It does not contain a real exploit, real tool, credential, external communication path, or destructive capability.

## Supported deployment path

The only supported paid-compute path is:

1. Build and validate the preconfigured container through GitHub Actions.
2. Deploy that exact image digest on one RunPod A100 80 GB Pod.
3. Start the complete gated run with one command.
4. Monitor or cancel it with the included scripts.
5. Download the generated evidence ZIP and checksum.
6. Terminate the Pod.

There is **no package installation on paid GPU time**, no source ZIP upload to RunPod, no manual model-server setup, and no need for four GPUs.

## Start here

Read [START_HERE.md](START_HERE.md). The full beginner runbook is [docs/RUNBOOK.md](docs/RUNBOOK.md). The completed static/simulated audit is recorded in [FINAL_VALIDATION_REPORT.md](FINAL_VALIDATION_REPORT.md).

## What the gated run does

The run stops automatically at the first failed gate:

1. Environment and integrity preflight
2. Hugging Face access and immutable revision freeze
3. Unit/integration tests
4. Simulated 24-placement validation
5. Four-model compatibility gate
6. One cross-model shakedown
7. Full 24-placement POC
8. Evidence packaging

## Expected POC workload

- 4 exact model deployments
- 4 fixed agent roles
- 4 conditions: 1 benign and 3 synthetic injections
- 24 model placements
- 1 repetition by default
- 96 complete workflows
- 384 logical stage events

Exact model revisions are frozen at runtime and recorded in the evidence package.

## Interpretation boundary

This POC is intended to validate feasibility, workflow competence, measurement integrity, approximate cost, and whether placement produces enough signal for a formal study. One-repetition POC results are **not** final white-paper findings.
