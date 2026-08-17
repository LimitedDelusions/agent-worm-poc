# v0.8.8 GPU-less container-build postmortem and v0.8.9 correction

## What happened

The one v0.8.8 workflow dispatch ran against immutable tag `v0.8.8` at commit `f63fd029a34e21eac1b4af9105b7fc67e2a1fa29`. Its validation job passed every step: Linux compilation and 124 tests, Ruff, ShellCheck, integrity, release audit, complete fake gate, and evidence verification. The Docker build then stopped before export when its final validation layer invoked `vllm serve --help` on the GPU-less BuildKit host.

Pinned vLLM 0.25.1 constructs configuration defaults while assembling that help parser. `DeviceConfig(device="auto")` could not infer a CUDA platform without an attached GPU and raised `RuntimeError: Failed to infer device type`. This was a build-pipeline defect, not a model, assay, or thesis result.

The failed workflow is preserved at `https://github.com/LimitedDelusions/agent-worm-poc/actions/runs/32053835354`. It was not retried and the v0.8.8 tag was not moved. No container-reference artifact, `RUNPOD_IMAGE.txt`, GHCR `0.8.8` or commit tag, immutable digest, or paid RunPod session was created.

## v0.8.9 correction

v0.8.9 uses the pinned package's dedicated `create_parser_for_docs()` path after applying vLLM's own process-local `CpuPlatform` fallback. It programmatically requires every serve flag used by the production model-server command, including the generated `--no-enable-prefix-caching` option. The check does not start a server, load a model, access Hugging Face, or probe CUDA, and it fails closed if the pinned package version or any required option changes.

Focused tests require the Docker build to invoke that validator, reject the GPU-dependent help command, reject a wrong vLLM version, and reject every missing production flag.

These are container-build validation and release-identity changes only. Prompts, carriers, scoring, gates, case construction, model repositories and pinned revisions, seeds, generation settings, scientific execution, and the paid runtime command are byte-identical to v0.8.8.
