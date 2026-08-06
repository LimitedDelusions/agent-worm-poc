# Start Here

Use **only v0.6.0**. Earlier v0.4.x and v0.5.x packages are obsolete. Review `AUDIT_REPORT.md` and `FINAL_VALIDATION_REPORT.md` before deployment.

## Before renting another GPU

Complete these free steps:

1. Extract the v0.6.0 release on your computer.
2. Create a GitHub repository and upload the extracted project contents.
3. Let the included GitHub Actions workflow validate the code and build the container.
4. Confirm both GitHub jobs are green.
5. Download the `agent-worm-poc-container-reference` artifact.
6. Open `RUNPOD_IMAGE.txt` and copy the exact image reference ending in `@sha256:...`.
7. Make the GitHub Container Registry package public so RunPod can pull it.

Do **not** deploy a Pod if the GitHub workflow failed or if you only have a mutable image tag such as `:0.6.0`.

## RunPod configuration

Create one template with:

- 1 × A100 PCIe 80 GB or A100 SXM 80 GB
- On-Demand rental
- exact GHCR image digest from `RUNPOD_IMAGE.txt`
- 80 GB container disk
- 300 GB volume mounted at `/workspace`
- HTTP port `8888`
- no Docker command or entrypoint override
- Hugging Face token and Jupyter password injected through RunPod Secrets

Required environment variables are listed in [docs/RUNPOD_SETUP.md](docs/RUNPOD_SETUP.md).

## One command starts everything

After the Pod is running and JupyterLab opens, create a terminal and run:

```bash
cd /workspace/agent_worm_poc_v0.6.0
export RUNPOD_HOURLY_RATE="1.49"  # replace 1.49 with RunPod's displayed total hourly rate
bash scripts/runpod/start_gated_run.sh
```

Monitor it with:

```bash
bash scripts/runpod/status.sh
```

Cancel safely with:

```bash
bash scripts/runpod/cancel_run.sh
```

Do not stop or terminate the Pod while the run is active. Cancel first and wait until `status.sh` reports `NOT RUNNING`.

## Completion goal

The run is complete when:

- `status.sh` reports `NOT RUNNING`;
- `session_status.json` reports `completed`;
- a ZIP named `agent-worm-results-...zip` exists in `/workspace`;
- the adjacent `.sha256` file exists.

Download both files, confirm the ZIP exists locally, and then **terminate** the Pod to stop compute and storage billing.
