# RunPod Setup — Step by Step

## Prerequisites

- RunPod account with credits
- Hugging Face read token stored as RunPod secret `huggingface_token`
- Jupyter password stored as RunPod secret `jupyter_password`
- Gemma license accepted on the same Hugging Face account
- immutable image reference from GitHub Actions

## 1. Create the Pod

1. Sign in to RunPod.
2. Select **Pods** → **Deploy**.
3. Choose one on-demand **A100 80 GB**. PCIe or SXM is acceptable.
4. Enter Pod name `agent-worm-v084`.
5. In **Custom Image**, paste the exact digest from `RUNPOD_IMAGE.txt`.
6. Configure a persistent volume of at least **350 GB** mounted at `/workspace`.
7. Expose HTTP port **8888**.
8. Do not expose a public vLLM port.

## 2. Add environment variables

```text
HF_TOKEN={{ RUNPOD_SECRET_huggingface_token }}
JUPYTER_PASSWORD={{ RUNPOD_SECRET_jupyter_password }}
HF_HOME=/workspace/hf-cache
AGENT_WORM_IMAGE_REF=ghcr.io/<owner>/<repo>@sha256:<digest>
MAX_TOTAL_COST_USD=25
MAX_GPU_HOURS=8
```

The hourly rate should be entered after the Pod starts because the exact displayed total price is the value to record.

## 3. Start and connect

1. Deploy on-demand.
2. Wait for status **Running**.
3. Select **Connect**.
4. Open HTTP service port 8888.
5. Log in using the Jupyter password.
6. Open **File → New → Terminal**.

## 4. Verify the container

```bash
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
ls -la /workspace/agent_worm_poc_v0.8.4
cat /opt/agent-worm-runtime.json
cd /workspace/agent_worm_poc_v0.8.4
sha256sum -c SOURCE_HASHES.sha256
```

Expected GPU memory is approximately 80 GB. Do not continue if source verification fails.

## 5. Record the rate and launch

Copy the total hourly price displayed by RunPod, then:

```bash
cd /workspace/agent_worm_poc_v0.8.4
export RUNPOD_HOURLY_RATE_USD="<displayed total hourly rate>"
export MAX_TOTAL_COST_USD="25"
export MAX_GPU_HOURS="8"
bash scripts/runpod/start_gated_run.sh
```

Open a second terminal and monitor:

```bash
cd /workspace/agent_worm_poc_v0.8.4
bash scripts/runpod/status.sh
```

Do not manually install packages or edit prompts on the paid Pod.
