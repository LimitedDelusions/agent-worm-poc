# Start Here — Agent Worm POC v0.7.0

Use only this v0.7.0 release. Do not mix files with v0.6.0 or an earlier image.

## What you need

- the complete v0.7.0 ZIP and its SHA-256 file;
- the GitHub repository previously used for the POC;
- a successful GitHub Actions validation/build run;
- the exact `ghcr.io/...@sha256:...` reference from `RUNPOD_IMAGE.txt`;
- the existing RunPod and Hugging Face accounts/secrets;
- one A100 80 GB Pod for the real gated run.

## Stage 1 — send the project to the coding workspace

1. Put the v0.7.0 ZIP and checksum in the coding workspace.
2. Give the coder [`CODING_HANDOFF.md`](CODING_HANDOFF.md).
3. Replace the prior repository contents with the extracted v0.7.0 contents; do not overlay them.
4. Run the pre-deployment validation commands in the handoff.
5. Commit and push only after all gates pass.

**End goal:** a GitHub commit containing exactly v0.7.0.

## Stage 2 — build the prevalidated image before paid GPU use

1. Open the repository’s **Actions** tab.
2. Run **Validate and Build Agent Worm POC Container**, or allow the push to `main` to trigger it.
3. Confirm both `validate` and `build` are green.
4. Download the `agent-worm-poc-container-reference` artifact.
5. Save the exact digest in `RUNPOD_IMAGE.txt`.
6. Make the GHCR package public, or configure RunPod registry credentials for the private package, before deployment. Do not paste a GitHub token into the image or project files.

**Stop if:** any job is red, the validation artifact is absent, only a mutable tag is available, or RunPod cannot authenticate to the GHCR package.

**End goal:** one immutable GHCR image reference.

## Stage 3 — update the RunPod template

Follow [`docs/RUNPOD_SETUP.md`](docs/RUNPOD_SETUP.md). Use the v0.7.0 digest, one A100 80 GB GPU, a password-protected Jupyter service, Hugging Face token secret, and persistent `/workspace` storage.

**End goal:** the container reports v0.7.0 ready and `/workspace/agent_worm_poc_v0.7.0` exists.

## Stage 4 — run the gated POC

In Jupyter Terminal:

```bash
cd /workspace/agent_worm_poc_v0.7.0
bash scripts/runpod/start_gated_run.sh
```

Monitor:

```bash
bash scripts/runpod/status.sh
```

The command automatically runs:

1. preflight;
2. model revision freeze;
3. tests;
4. simulated positive/control validation;
5. four-model compatibility;
6. real positive propagation control;
7. one-placement cross-model shakedown;
8. all 24 placements across four main scenarios;
9. evidence packaging.

**End goal:** a ZIP named `agent-worm-results-...zip` plus its `.sha256` file.

## Stage 5 — preserve evidence and stop billing

1. Download the result ZIP and checksum.
2. Verify the checksum locally.
3. Extract and read `outputs/NEXT_MEETING_SUMMARY.md`.
4. Confirm the artifact index and major manifests are present.
5. Terminate the Pod after the files are verified locally.

Full beginner instructions: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).
