# RunPod Setup — Step by Step

## Prerequisites

- RunPod account with credits
- Hugging Face read token stored as RunPod secret `huggingface_token`
- random Jupyter password of at least 16 characters stored as RunPod secret `jupyter_password`
- Gemma license accepted on the same Hugging Face account
- immutable image reference from GitHub Actions

## 1. Create the Pod

1. Sign in to RunPod.
2. Select **Pods** → **Deploy**.
3. Choose one on-demand **A100 80 GB**. PCIe or SXM is acceptable.
4. Enter Pod name `agent-worm-v087`.
5. In **Container Image** (called **Custom Image** in older screens), paste the exact digest from `RUNPOD_IMAGE.txt`.
   Record a screenshot or copied template value. RunPod does not guarantee that the actual image digest is introspectable from inside the container, so this console check is part of provenance.
6. Leave **Container start command** blank so the image entrypoint runs.
7. Set **Container disk** to at least **50 GB**.
8. Under persistent storage, prefer a **350 GB Volume Disk** mounted at `/workspace`; it survives Stop but is deleted with the Pod at Terminate. If a **Network Volume** is used instead, it survives Pod termination and must be deleted separately after local evidence verification to stop storage billing.
9. Expose HTTP port **8888**.
10. Do not expose a public vLLM port or internal port 8000.

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
6. Open **File → New → Terminal**. If Jupyter does not initialize, use RunPod's **Web Terminal**; the experiment does not depend on the notebook UI.

The image restores `/workspace/agent_worm_poc_v0.8.7` from its baked source on every container start. Do not store operator notebooks or notes inside that directory; use `/workspace/operator-notes` if needed.

## 4. Verify the container

```bash
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
ls -la /workspace/agent_worm_poc_v0.8.7
cat /opt/agent-worm-runtime.json
cd /workspace/agent_worm_poc_v0.8.7
sha256sum -c SOURCE_HASHES.sha256
```

Expected GPU memory is approximately 80 GB. Do not continue if source verification fails.

## 5. Record the rate and launch

Copy the total hourly price displayed by RunPod, then:

```bash
cd /workspace/agent_worm_poc_v0.8.7
export RUNPOD_HOURLY_RATE_USD="<displayed total hourly rate>"
export MAX_TOTAL_COST_USD="25"
export MAX_GPU_HOURS="8"
bash scripts/runpod/start_gated_run.sh
```

The launcher prints the release, immutable image declaration, rate, ceiling, and hard budget, then requires you to type the displayed hourly rate again. It also claims the release/image permanently before the real process starts. Do not run this command twice, even after an abort.

The launcher checks any digest-form provider image field RunPod exposes, but the required `AGENT_WORM_IMAGE_REF` remains an operator declaration. Before launch, visually confirm it exactly matches the immutable digest in the Pod template and the GitHub `RUNPOD_IMAGE.txt` artifact. The baked runtime marker separately verifies release and Git revision.

Open a second terminal and monitor:

```bash
cd /workspace/agent_worm_poc_v0.8.7
bash scripts/runpod/status.sh
```

Do not manually install packages or edit prompts on the paid Pod. The in-container timeout stops the experiment process, not RunPod billing; keep an independent alarm and terminate the Pod from the RunPod console after evidence is verified locally.

When the monitor reports `Process: NOT RUNNING`, send the complete verified evidence bundle:

```bash
bash /workspace/agent_worm_poc_v0.8.7/scripts/runpod/stage_and_send_evidence.sh
```

Receive and verify it on the local machine before terminating the Pod. A Volume Disk is removed with Pod termination. A separate Network Volume must be deleted afterward by exact volume ID, then confirmed absent so storage billing stops.
