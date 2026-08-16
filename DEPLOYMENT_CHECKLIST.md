# Live Deployment Checklist — v0.8.2

## Free gates

- [ ] Release ZIP and SHA-256 downloaded
- [ ] ZIP checksum verified
- [ ] Source extracted into a clean repository
- [ ] Python compilation passes
- [ ] All tests pass
- [ ] Source integrity manifest passes
- [ ] Release audit passes
- [ ] Complete fake gated run finishes successfully
- [ ] GitHub validation job is green
- [ ] GitHub container-build job is green
- [ ] Immutable GHCR digest recorded

## RunPod configuration

- [ ] One on-demand A100 80 GB, PCIe or SXM
- [ ] Exact GHCR digest used, not a mutable tag
- [ ] Persistent `/workspace` volume is at least 350 GB
- [ ] HTTP port 8888 exposed
- [ ] `HF_TOKEN={{ RUNPOD_SECRET_huggingface_token }}`
- [ ] `JUPYTER_PASSWORD={{ RUNPOD_SECRET_jupyter_password }}`
- [ ] `HF_HOME=/workspace/hf-cache`
- [ ] `AGENT_WORM_IMAGE_REF=<exact GHCR digest>`
- [ ] Displayed total hourly price recorded
- [ ] Maximum planned spend confirmed

## Before launch

- [ ] Jupyter requires the configured password
- [ ] `nvidia-smi` shows one 80 GB A100
- [ ] `/workspace/agent_worm_poc_v0.8.2` exists
- [ ] At least 300 GB is free under `/workspace`
- [ ] No unrelated process is using significant GPU memory
- [ ] `RUNPOD_HOURLY_RATE_USD` is exported with the exact displayed rate
- [ ] `MAX_TOTAL_COST_USD=25` is exported
- [ ] `MAX_GPU_HOURS=8` is exported

## During the gated run

- [ ] Compatibility passes for all four models
- [ ] Nemotron parser plugin is frozen, hashed, and recorded in model revisions
- [ ] Positive control passes for every ordered model pair
- [ ] Sham false-positive rate is zero
- [ ] Hardened calibration stays under its propagation ceiling
- [ ] Neutral calibration shows success and failure within at least one matched block
- [ ] Main phase starts only after calibration passes
- [ ] No package installation occurs on the paid Pod
- [ ] Status and estimated cost are checked periodically
- [ ] Operator remembers that script completion does not stop RunPod billing

## Before termination

- [ ] Gated process reports NOT RUNNING
- [ ] Evidence ZIP downloaded
- [ ] Evidence checksum downloaded
- [ ] Local SHA-256 matches
- [ ] ZIP opens with no errors
- [ ] `PACKAGE_MANIFEST.json` exists inside the ZIP
- [ ] `RUN_STATUS.json` stored locally
- [ ] Actual RunPod balance decrease recorded
- [ ] Semantic review key stored separately from the blinded packet
- [ ] Pod terminated after evidence verification
