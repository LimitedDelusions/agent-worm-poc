# Live Deployment Checklist — v0.8.7

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
- [ ] Pod template image value copied/screenshot and exactly matches `RUNPOD_IMAGE.txt` and `AGENT_WORM_IMAGE_REF`
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
- [ ] Launcher CUDA/PyTorch/BF16 allocation probe passes before the one-run claim
- [ ] `/workspace/agent_worm_poc_v0.8.7` exists
- [ ] At least 300 GB is free under `/workspace`
- [ ] No unrelated process is using significant GPU memory
- [ ] `RUNPOD_HOURLY_RATE_USD` is exported with the exact displayed rate
- [ ] `MAX_TOTAL_COST_USD=25` is exported
- [ ] `MAX_GPU_HOURS=8` is exported
- [ ] Launcher confirms all four pinned Hugging Face revisions are accessible
- [ ] Typed hourly-rate confirmation matches the displayed total rate
- [ ] One-run release/image claim path is printed and preserved

## During the gated run

- [ ] Compatibility passes for all four models
- [ ] Nemotron parser plugin is frozen, hashed, and recorded in model revisions
- [ ] Positive control passes for every ordered model pair
- [ ] Gate output reports `design_valid=true` and `measurement_valid=true`
- [ ] Sham false-positive rate is zero
- [ ] Hardened calibration stays under its propagation ceiling
- [ ] Neutral calibration shows success and failure within at least one matched block
- [ ] Main phase starts only after calibration passes
- [ ] No package installation occurs on the paid Pod
- [ ] Status and estimated cost are checked periodically
- [ ] The launcher is never executed a second time; monitoring uses only `status.sh`
- [ ] Operator remembers that script completion does not stop RunPod billing

## Before termination

- [ ] Gated process reports NOT RUNNING
- [ ] `stage_and_send_evidence.sh` completes and prints a one-time transfer code
- [ ] Evidence ZIP, `.zip.sha256`, `.zip.json`, standalone status, and full run directory downloaded
- [ ] Local SHA-256 matches
- [ ] `verify_evidence.py` passes CRC, exact package membership/hashes, source snapshot, version, and status parity
- [ ] `RUN_STATUS.json` stored locally
- [ ] Actual RunPod balance decrease recorded
- [ ] Semantic review key stored separately from the blinded packet
- [ ] Pod terminated after evidence verification
- [ ] If Network Volume was used, its exact ID was deleted after Pod termination
- [ ] RunPod console/Billing shows no remaining compute or unintended storage resource
