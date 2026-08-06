# Gate 2 — Create the RunPod Template and One A100 Pod

## Goal

Start one cloud machine that already contains the validated runtime. There must be **no CUDA, Torch, vLLM, or project installation on paid GPU time**.

The supported POC configuration is:

```text
1 × NVIDIA A100 PCIe 80 GB or A100 SXM 80 GB
On-Demand
1 GPU total
```

An H100 and four GPUs are unnecessary for this feasibility POC.

## Prerequisites

Before opening RunPod, have:

- green GitHub `validate` and `build` jobs;
- the exact line from `RUNPOD_IMAGE.txt`;
- your read-only Hugging Face token beginning with `hf_`;
- a new unique Jupyter password of at least 16 characters saved in your password manager;
- accepted access to `google/gemma-3-27b-it` on the same Hugging Face account.

Do not paste either secret into this document, source code, GitHub, or chat.

## Steps

### 1. Create the two RunPod secrets

Do this before creating the template:

1. Sign in to RunPod.
2. Open **Secrets** in the left navigation.
3. Select **Create Secret**.
4. Create the Hugging Face secret:

```text
Name: huggingface_token
Value: your read-only Hugging Face token beginning with hf_
```

5. Select **Create Secret** again.
6. Create the Jupyter password secret:

```text
Name: jupyter_password
Value: a new unique password of at least 16 characters
```

7. Save the Jupyter password in your password manager. RunPod will not display either secret value again.
8. Confirm the **Secrets** page lists both secret names.

Do not paste either value into the template as plain text. The template will reference the stored names.

### 2. Create a custom template

1. Sign in to RunPod.
2. Open **Templates** or **My Templates** in the left navigation.
3. Select **New Template** or **Create Template**.
4. Name it:

```text
agent-worm-poc-v0.6.0
```

5. In **Container Image**, paste the complete digest from `RUNPOD_IMAGE.txt`, for example:

```text
ghcr.io/YOUR-USERNAME/agent-worm-poc@sha256:<64 hex characters>
```

Do not use `:latest`, `:0.6.0`, or another tag.

### 3. Set storage

Use:

```text
Container disk: 80 GB
Volume disk: 300 GB
Volume mount path: /workspace
```

The volume must be mounted at `/workspace`. Model weights, results, and the downloadable evidence package are stored there.

Do not reduce the volume for the first run. The four model caches together are large.

### 4. Expose JupyterLab

Add an HTTP port:

```text
8888
```

No public model API port is required. vLLM listens only on `127.0.0.1` inside the Pod.

### 5. Add environment variables

Open the template's **Environment Variables** section. Add exactly these entries:

| Key | Value |
|---|---|
| `HF_TOKEN` | `{{ RUNPOD_SECRET_huggingface_token }}` |
| `JUPYTER_PASSWORD` | `{{ RUNPOD_SECRET_jupyter_password }}` |
| `HF_HOME` | `/workspace/hf-cache` |
| `AGENT_WORM_IMAGE_REF` | the exact `ghcr.io/...@sha256:...` line from `RUNPOD_IMAGE.txt` |
| `AGENT_WORM_MAX_RUNTIME` | `6h` |
| `POC_REPETITIONS` | `1` |

For the two sensitive values, use RunPod's key/secret selector. RunPod will insert the `{{ RUNPOD_SECRET_... }}` reference. Do not paste secret values directly into the template.

### 6. Leave startup overrides blank

Do not set a custom:

- Docker command;
- entrypoint;
- start command;
- model command.

The image's guarded entrypoint starts password-protected JupyterLab and nothing else.

### 7. Save the template

Save the template and reopen it once. Verify:

- exact digest is intact;
- volume mount is `/workspace`;
- port 8888 exists;
- all six environment variables exist;
- command/entrypoint overrides are blank.

### 8. Deploy one Pod

1. Open **Pods**.
2. Select **Deploy** or **+ New → Pod**.
3. Select your `agent-worm-poc-v0.6.0` template.
4. Select **On-Demand**.
5. Select one of:

```text
NVIDIA A100 PCIe 80 GB
NVIDIA A100 SXM 80 GB
```

6. Set GPU count to:

```text
1
```

7. Record the **total displayed hourly price**, including the GPU and disks.
8. Deploy.

The run's internal estimate uses the rate you record, but RunPod Billing remains authoritative.

`AGENT_WORM_IMAGE_REF` is an operator-supplied provenance record. The preflight validates its immutable GHCR digest format and records it in the evidence, but a process inside the running container cannot independently inspect the registry digest RunPod actually pulled. You must therefore copy the exact same line from `RUNPOD_IMAGE.txt` into both the template image field and `AGENT_WORM_IMAGE_REF`.

### 9. Confirm the container started correctly

1. Wait until the Pod shows **Running**.
2. Open the Pod's **Logs** before connecting.
3. Look for:

```text
Agent Worm POC v0.6.0 container is ready.
Project: /workspace/agent_worm_poc_v0.6.0
No model or experiment starts automatically.
```

If the log reports a missing secret, image pull failure, source-integrity failure, or missing runtime marker, stop and correct the template. Do not install anything manually.

### 10. Open JupyterLab

1. Select **Connect** on the Pod.
2. Under HTTP services, open port **8888 / JupyterLab**.
3. Confirm it asks for a password.
4. Enter the password stored in your `jupyter_password` RunPod secret.

If JupyterLab opens without requiring a password, terminate the Pod and inspect the template; this release is designed to refuse passwordless startup.

## Pass criteria

All must be true:

- Exactly one A100 80 GB GPU is attached.
- The Pod uses the exact digest from `RUNPOD_IMAGE.txt`.
- The container log says v0.6.0 is ready.
- JupyterLab requires the configured password.
- `/workspace/agent_worm_poc_v0.6.0` exists.
- No package installation occurred on the Pod.
- The total hourly rate is recorded.

## Stop criteria

Do not start the experiment if:

- the image cannot be pulled;
- the runtime marker or source check fails;
- the GPU is not an A100 with approximately 80 GB VRAM;
- more than one GPU was selected;
- `/workspace` is absent or the volume is smaller than configured;
- JupyterLab is passwordless;
- any instruction suggests running `pip install`, `apt install`, or replacing CUDA/vLLM.

## Artifacts produced

Record or preserve:

| Artifact | Purpose |
|---|---|
| RunPod template name | Reusable configuration reference |
| Exact image digest | Connects the Pod to the GitHub-validated build |
| Pod ID | Recorded automatically by the run when exposed by RunPod |
| Total displayed hourly rate | Used for the internal cost estimate |
| Initial Pod logs | Troubleshooting evidence if startup fails |

## Official setup references

- RunPod templates: https://docs.runpod.io/pods/templates/overview
- RunPod environment variables: https://docs.runpod.io/pods/templates/environment-variables
- RunPod secrets: https://docs.runpod.io/pods/templates/secrets
