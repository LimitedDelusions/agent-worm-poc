# v0.8.9 CUDA-wheel identity postmortem and v0.8.10 correction

## What happened

The one v0.8.9 workflow dispatch ran against immutable tag `v0.8.9` at commit `b87468b1f7f12b08584438d07eaf4d8007a902b4`. Its validation job passed every step, including 126 Linux tests, Ruff, ShellCheck, integrity, release audit, the complete fake gate, and evidence verification. The Docker layer then passed the same source checks and stopped inside the new vLLM validator before constructing the parser.

The pinned `vllm/vllm-openai:v0.25.1-x86_64-cu129` image exposes semantic release `0.25.1`, but its installed Python distribution has the exact PEP 440 version `0.25.1+cu129`. The validator compared distribution metadata literally with `0.25.1`, rejected the legitimate CUDA local-version suffix, and raised `RuntimeError: Expected vLLM 0.25.1, found 0.25.1+cu129`. This was a build-validation defect, not a model, assay, or thesis result.

The failed workflow is preserved at `https://github.com/LimitedDelusions/agent-worm-poc/actions/runs/32132942531`. It was not retried and the v0.8.9 tag was not moved. The immutable-reference and upload steps were skipped. Public GHCR has neither the `0.8.9` tag nor the commit tag, so no v0.8.9 image or paid RunPod session exists.

## v0.8.10 correction

v0.8.10 requires the exact installed distribution version `0.25.1+cu129`, not merely any distribution with base version `0.25.1`. That matches the digest-pinned CUDA image and rejects a different CUDA wheel suffix. The runtime marker records `vllm_release: 0.25.1` and `vllm_distribution_version: 0.25.1+cu129` separately so evidence distinguishes upstream semantic release from the installed build. CI rejects any dispatch not bound to tag `v0.8.10`, and the paid launcher rechecks the live installed distribution against the baked marker before claiming a run.

Focused tests accept only the exact pinned CUDA distribution and reject the suffix-free version, a wrong release, and wrong CUDA suffixes. The existing GPU-independent parser construction and all 17 production serve-flag checks remain unchanged and must pass inside the actual container before export.

These are container-build validation, provenance, release-identity, and fail-closed preflight changes only. Prompts, carriers, scoring, gates, case construction, model repositories and revisions, seeds, generation settings, scientific execution, and paid model-server commands are byte-identical to v0.8.9. RunPod changes are limited to versioned default paths and the live installed-wheel cross-check described above.
