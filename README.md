# Agent Worm Model-Placement POC v0.7.0

This project is a controlled, non-destructive proof of concept for testing whether the placement of four specified open-weight LLMs changes the multi-hop propagation of a document-borne prompt injection through a fixed agent workflow.

## Research question

> How does the placement of Qwen3-30B-A3B-Instruct-2507, Gemma-3-27B-IT, GPT-OSS-20B, and NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 within a fixed document-processing workflow affect the multi-hop propagation of a document-borne prompt injection?

## Why v0.7.0 exists

The v0.6.0 POC validated the cloud environment and model compatibility, but its main workflow explicitly told every downstream agent to strip the test marker. It therefore measured a hardened containment path, not natural artifact propagation.

v0.7.0 separates three purposes:

1. **Positive propagation control:** explicit calibration proving that two newly generated artifacts can carry the synthetic test block and that external scoring detects it.
2. **Neutral experimental workflow:** realistic procurement instructions that neither preserve nor remove the test block.
3. **Hardened negative control:** explicit provenance separation and prompt-injection controls using the same injected document.

## Fixed workflow

```text
Synthetic vendor document
        ↓
Procurement intake agent → generated internal brief
        ↓
Procurement relay/editor → generated handoff artifact
        ↓
Planning agent → action request
        ↓
Simulated executor → nonfunctional decision only
```

The next agent receives the human-readable artifact created by the prior agent. JSON is used only as a strict response envelope; it is not the propagation carrier.

Trusted role instructions are system messages. The source document and generated artifacts are user-level work items. All three injected architectures receive the same injected vendor document; only the trusted role policy changes.

## Models and placement

Every deployment uses each of the four model slots exactly once across four roles. All 24 permutations are tested. The real POC issues independent inference requests and uses 2–5 repetitions per placement/scenario; the default is 3.

## Safety boundary

The carrier is synthetic text. `external_vendor_callback` is a prohibited but nonfunctional simulation label only. The project contains no real tool implementation, credential, sensitive data, network action, target discovery, file replication, email, or external effect.

## Main outputs

- model compatibility report;
- positive-control evaluation;
- full stage-event and request logs;
- per-workflow scores;
- 24-placement summaries plus a 12-pair intake→relay primary-outcome summary;
- instructor meeting summary and machine-readable decision;
- frozen source, model revisions, image digest, and evidence checksums.

Start with [`START_HERE.md`](START_HERE.md). The coding-side transfer instructions are in [`CODING_HANDOFF.md`](CODING_HANDOFF.md).
