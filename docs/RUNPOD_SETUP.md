# RunPod Setup for v0.7.0

## Goal

Create one temporary A100 80 GB Pod from the exact prebuilt v0.7.0 image, with persistent evidence storage and no runtime installation.

## Steps

1. Sign in to RunPod and open **Templates**.
2. Duplicate the prior POC template or create a new custom template.
3. Name it `agent-worm-poc-v0.7.0`.
4. In **Container Image**, paste the entire digest from `RUNPOD_IMAGE.txt`.
5. Do not use a tag.
6. If the GHCR package is public, leave registry credentials empty. If it is private, select/add the private registry credential created specifically for this package; use the GitHub username and a read-only `read:packages` token. Never place that token in an environment variable visible to the model process.
7. Set container disk to at least 40 GB so the large prebuilt image has working headroom.
8. Attach at least 350 GB of persistent storage mounted at `/workspace` for the four model caches and evidence. Use 400 GB if the displayed storage price is acceptable.
9. Expose HTTP port 8888 for JupyterLab. No model-server port should be public.
10. Map the existing Hugging Face read-token secret to `HF_TOKEN`.
11. Map the existing Jupyter password secret to `JUPYTER_PASSWORD`.
12. Add `AGENT_WORM_IMAGE_REF` with the exact GHCR digest.
13. Add `AGENT_WORM_MAX_RUNTIME=8h` or a shorter deliberate limit.
14. Add `POC_REPETITIONS=3`.
15. Deploy one on-demand A100 PCIe 80 GB; use A100 SXM 80 GB when PCIe is unavailable. Do not use Spot/Interruptible.
16. Record the total hourly price displayed by RunPod.
17. Add that value as `RUNPOD_HOURLY_RATE` before starting the gated run.
18. Wait for the Pod to report **Running**.
19. Click **Connect** and open JupyterLab.
20. Confirm the startup page/log reports v0.7.0 and no unresolved secret, registry, or integrity error.

## Pass criteria

- the Pod uses the exact digest;
- one A100 80 GB GPU is present;
- `/workspace/agent_worm_poc_v0.7.0` exists;
- Jupyter requires the configured password;
- `HF_TOKEN`, `AGENT_WORM_IMAGE_REF`, and `RUNPOD_HOURLY_RATE` are available without printing secret values;
- no package-install command is needed;
- only Jupyter port 8888 is public; model servers remain on localhost.

## Stop criteria

Stop before the gated run when:

- the image fails to pull or registry authentication fails;
- the container reports another version;
- the GPU is not an A100 80 GB;
- persistent storage is absent;
- Jupyter is unprotected;
- only a mutable image tag is configured;
- the hourly rate is unacceptable.

## Artifacts produced

The setup itself produces no research evidence. The gated run later records the Pod identity, GPU, exact image reference, runtime marker, storage checks, and hourly rate in the session output.
