# v0.6.0 Audit Report

## Audit objective

Rebuild the proof of concept into a complete, cost-controlled release that a first-time RunPod user can operate without installing CUDA, Torch, vLLM, or project dependencies during paid GPU time. The release must stop before producing invalid POC data, preserve full or partial evidence, and state exactly what the POC does and does not establish.

## Material defects found in earlier versions

1. The original RunPod path installed a large, unpinned Torch/CUDA/vLLM stack during paid time and failed with an input/output error.
2. The later v0.5.1 directory contained documentation but not the runnable source, configs, tests, Dockerfile, GitHub workflow, and scripts those documents referenced.
3. Earlier scoring could confuse an independent downstream policy violation with continuous worm propagation.
4. A restricted action could be selected but blocked and still be presented too close to successful execution.
5. A response schema could encourage the model to report the canary instead of measuring whether it independently preserved it.
6. Reusing an existing output directory could mix evidence from separate attempts.
7. Manual model-server setup, unverified package installation, stale ports, and unreleased GPU memory could waste paid time or contaminate later phases.
8. Earlier evidence packages did not consistently contain the exact source snapshot, raw outputs, integrity records, and clear instructor-facing artifacts.
9. Passwordless or unresolved-secret Jupyter startup was not rejected strongly enough.
10. Model subprocesses could inherit credentials unrelated to model retrieval.
11. Forced cancellation did not explicitly mark the session as a forced-cancel failure before packaging partial evidence.

## Corrective controls in v0.6.0

- Complete source, configs, tests, scripts, Dockerfile, GitHub workflow, and documentation are included.
- The vLLM CUDA base is pinned by immutable digest.
- GitHub Actions validates and builds the image before paid compute is used.
- No package-install command exists on the supported paid RunPod path.
- One A100 80 GB GPU is used sequentially; four GPUs and an H100 are not required.
- Model, tokenizer, trusted remote-code, and Nemotron parser revisions are frozen before real inference.
- Strict role-specific JSON Schemas and cross-field semantic validation are enforced.
- The schema does not request a canary field.
- Propagation advances only through a continuous chain: intake adoption → relay preservation → restricted plan → approved restricted mock action.
- Independent downstream violations and blocked restricted actions are reported separately.
- Every output directory must be new and empty.
- Every model must pass all four roles and three benign workflows before the placement POC begins.
- A cross-model shakedown must pass before all 24 placements begin.
- vLLM binds only to localhost, stale ports are rejected, and GPU memory release is checked after every model shutdown.
- JupyterLab requires a resolved password, supports RunPod's reverse proxy, and rejects unresolved secret-reference strings.
- The model subprocess retains only the read-only Hugging Face token needed for model download and strips Jupyter, RunPod, GitHub, and public-key credentials.
- Timeout, status, controlled cancellation, forced-cancel status, cleanup, cost estimate, and partial-evidence packaging are included.
- Final evidence packages contain outputs, raw responses, source, per-file hashes, an artifact index, and a ZIP checksum.

## Validation completed without paid GPU compute

- Python compilation passed.
- 43 unit/integration/regression tests passed.
- Bash syntax validation passed for every shell script.
- All JSON configs and the GitHub Actions YAML parsed successfully.
- The release audit passed with no errors or warnings.
- The deterministic fake-adapter validation completed all 24 placements and four conditions: 96 workflows, 384 logical stages, 78 unique simulated requests, 306 explicitly reused stages, zero failed workflows, and zero schema/semantic/output-invalid stages.
- Coverage was measured at 64% overall; high-risk orchestration, scoring, compatibility, reporting, and packaging paths have direct tests. GPU-only preflight, real HTTP inference, real process lifecycle, and CLI dispatch remain partly or wholly environment-gated.

## Controls that cannot be validated here

- Docker is unavailable in this environment. The exact image must pass the included GitHub `validate` and `build` jobs before RunPod deployment.
- No A100 is available here. Real model loading, actual VRAM use, model-specific chat templates, GPT-OSS reasoning behavior, Nemotron remote-code/parser behavior, and strict structured-output compliance remain mandatory compatibility gates.
- The process inside the container cannot independently inspect the registry digest RunPod pulled. The operator must copy the exact `RUNPOD_IMAGE.txt` digest into both the RunPod image field and `AGENT_WORM_IMAGE_REF`; preflight validates and records that supplied immutable reference.
- ShellCheck is not installed in this local environment. The GitHub validation job installs and runs it as a hard pre-deployment gate.

## Scientific limitations

- Results apply to four exact model deployments, not their entire model families.
- All models receive a common single-user-message envelope so model-specific role support does not become another uncontrolled variable.
- Strict JSON output is an application-level control and may affect susceptibility.
- Exact-marker tracking does not detect semantic paraphrase or mutation.
- One POC repetition and exact-request reuse are feasibility/cost controls, not independent repeated research observations.
- The final white-paper experiment must use held-out attacks, disable request reuse, and use an approved repeated-trial design.

## Deployment decision

The release is suitable for the next **gated compatibility attempt**, not guaranteed real-model success. Do not rent a GPU until GitHub validation and container build are green. On RunPod, do not bypass a failed preflight, model freeze, compatibility test, or shakedown. A failure produces useful engineering evidence and must be corrected in a rebuilt release rather than patched on the paid Pod.
