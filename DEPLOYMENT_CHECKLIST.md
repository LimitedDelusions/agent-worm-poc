# Deployment Checklist — v0.7.0

## Before coding handoff

- [ ] v0.7.0 ZIP SHA-256 matches the supplied sidecar.
- [ ] The archive extracts into a clean `agent_worm_poc_v0.7.0` directory.
- [ ] `CODING_HANDOFF.md` has been provided to the coding workspace.

## Before GitHub push

- [ ] Old v0.6 files were removed rather than overlaid.
- [ ] `.github`, `.dockerignore`, and `.gitignore` were copied.
- [ ] Compilation passes.
- [ ] All tests pass.
- [ ] Shell syntax passes.
- [ ] `release_audit.py` reports `passed: true`.
- [ ] Fake positive control reaches artifact depth 2.
- [ ] Fake main POC completes 24 placements × 4 scenarios with no reuse or invalid output.

## Before RunPod

- [ ] GitHub `validate` job is green.
- [ ] GitHub `build` job is green.
- [ ] Exact GHCR `@sha256:` reference is saved.
- [ ] RunPod template uses that exact digest, not `:latest` or `:0.7.0`.
- [ ] Hugging Face and Jupyter secrets are configured.
- [ ] One A100 80 GB GPU is selected.
- [ ] `/workspace` has adequate persistent storage.
- [ ] Total hourly price is recorded in `RUNPOD_HOURLY_RATE`.
- [ ] `POC_REPETITIONS` is 2–5; default 3.

## Before starting the gated run

- [ ] Container says v0.7.0 is ready.
- [ ] `/workspace/agent_worm_poc_v0.7.0` exists.
- [ ] `AGENT_WORM_IMAGE_REF` contains the exact digest.
- [ ] No older gated run is active.

## Before terminating the Pod

- [ ] Gated process is no longer running.
- [ ] Result ZIP exists.
- [ ] Result `.sha256` exists.
- [ ] Both files were downloaded locally.
- [ ] Local SHA-256 verification succeeds.
- [ ] Extracted package contains `ARTIFACT_INDEX.md` and `PACKAGE_MANIFEST.json`.
- [ ] `outputs/NEXT_MEETING_SUMMARY.md` was reviewed.
- [ ] Pod is terminated after verification.
