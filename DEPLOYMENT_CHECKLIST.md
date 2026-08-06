# Deployment Checklist

## A. Free pre-deployment gate

- [ ] I am using v0.6.0, not an older archive.
- [ ] The complete project was uploaded to GitHub, including `.github/workflows`.
- [ ] GitHub Actions job **validate** passed.
- [ ] GitHub Actions job **build** passed.
- [ ] I preserved the GitHub workflow run URL or downloaded validation artifact as the build record.
- [ ] I downloaded `agent-worm-poc-container-reference`.
- [ ] `RUNPOD_IMAGE.txt` contains `ghcr.io/...@sha256:<64 hex characters>`.
- [ ] The GHCR package is public and pullable.

**Stop if any box above is unchecked. Do not rent a GPU.**

## B. RunPod account/template gate

- [ ] RunPod secret `huggingface_token` exists.
- [ ] RunPod secret `jupyter_password` exists and is at least 16 characters.
- [ ] The template references both secrets using `{{ RUNPOD_SECRET_... }}` and does not contain the plain token or password.
- [ ] The template uses the exact image digest, not a tag.
- [ ] Container disk is 80 GB.
- [ ] Volume disk is 300 GB and mounted at `/workspace`.
- [ ] HTTP port 8888 is exposed.
- [ ] `HF_HOME=/workspace/hf-cache`.
- [ ] `AGENT_WORM_IMAGE_REF` exactly matches `RUNPOD_IMAGE.txt`.
- [ ] `AGENT_WORM_MAX_RUNTIME=6h`.
- [ ] `POC_REPETITIONS=1`.
- [ ] Docker command and entrypoint overrides are blank.

## C. GPU gate

- [ ] One A100 PCIe 80 GB or A100 SXM 80 GB is selected.
- [ ] Rental type is On-Demand.
- [ ] I recorded the total displayed hourly rate.
- [ ] I did not select four GPUs.
- [ ] I did not select an H100 merely for this POC.

## D. Run gate

- [ ] Container logs say v0.6.0 is ready and report no unresolved-secret or source-integrity error.
- [ ] JupyterLab opened on port 8888 and required my password.
- [ ] `/workspace/agent_worm_poc_v0.6.0` exists.
- [ ] I set `RUNPOD_HOURLY_RATE` to the displayed total hourly price.
- [ ] I started `scripts/runpod/start_gated_run.sh` once.
- [ ] I use `scripts/runpod/status.sh` to monitor.
- [ ] I will use `scripts/runpod/cancel_run.sh` before stopping the Pod if needed.

## E. Evidence and billing gate

- [ ] `status.sh` reports `NOT RUNNING`.
- [ ] I downloaded the result ZIP and `.sha256` file.
- [ ] I confirmed the ZIP opens or its hash verifies.
- [ ] I terminated the Pod after preserving the files.
