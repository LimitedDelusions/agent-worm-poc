# Complete Beginner Runbook

## End goal

At the end of this runbook you will have one verified ZIP containing:

- the exact source and container-build records;
- exact model revisions;
- compatibility results for all four models;
- a mixed-model shakedown;
- all 24 placements across four conditions;
- raw stage responses and scored results;
- a one-page instructor summary;
- runtime, GPU, server lifecycle, cost, and integrity evidence.

The POC answers a feasibility question, not the final white-paper hypothesis:

> **How does the placement of four specific open-weight LLM deployments within a fixed multi-agent workflow affect the propagation of synthetic self-replicating prompt injections?**

## Scope frozen for this POC

- Four exact model deployments: Qwen, Gemma, GPT-OSS, and NVIDIA Nemotron candidates.
- Four roles: intake, relay, planner, and nonfunctional mock executor.
- Four conditions: one benign document and three synthetic injection variants.
- All 24 possible placements, with each model used exactly once in every workflow.
- One A100 80 GB GPU, with models loaded sequentially.
- Fixed prompts, permissions, topology, schemas, generation settings, and 8K context.
- Exact marker tracking; semantic mutation is not measured.
- No real tool, external action, credential, data exfiltration, or destructive behavior.

## Stage overview

| Stage | Cost | Goal | Proceed only when |
|---|---:|---|---|
| 1. Release review | Free | Use the complete audited v0.6.0 package | ZIP checksum and contents are correct |
| 2. GitHub validation/build | Free GitHub compute | Build the runtime before renting GPU time | `validate` and `build` are green |
| 3. RunPod template | No GPU until deployment | Configure exact image, secrets, storage, and Jupyter | Template passes checklist |
| 4. Pod startup | Paid | Start one prebuilt A100 environment | Logs and password-protected Jupyter are correct |
| 5. Gated run | Paid | Execute all automatic gates | Each gate passes or stops safely |
| 6. Export | Paid until terminated | Download and verify evidence | ZIP/hash are preserved locally |
| 7. Instructor review | No GPU | Decide whether to advance/refine | Meeting summary and artifacts reviewed |

## Stage 1 — Verify the release

### Goal

Ensure you are using the exact final release, not v0.4.x or v0.5.x.

### Steps

1. Download `agent_worm_poc_v0.6.0.zip` and its `.sha256` file.
2. Verify the hash with PowerShell:

```powershell
Get-FileHash .\agent_worm_poc_v0.6.0.zip -Algorithm SHA256
Get-Content .\agent_worm_poc_v0.6.0.zip.sha256
```

3. Confirm the hashes match.
4. Extract the ZIP.
5. Confirm the extracted folder contains `.github`, `Dockerfile`, `scripts`, `src`, `tests`, and the docs.

### Pass criteria

- Hashes match.
- ZIP opens successfully.
- Required source and workflow files are present.

### Stop criteria

- Hash mismatch.
- ZIP corruption.
- Missing `.github`, source, scripts, tests, or Dockerfile.

### Artifacts

- Original release ZIP.
- Release ZIP checksum.
- Extracted source folder.

## Stage 2 — Validate and build on GitHub

Follow [GITHUB_BUILD.md](GITHUB_BUILD.md).

### Goal

Create the immutable prebuilt container without spending RunPod credits.

### Pass criteria

- Green `validate` job.
- Green `build` job.
- Public GHCR package.
- Exact `RUNPOD_IMAGE.txt` digest.

### Stop criteria

Any failed workflow or missing digest.

### Artifacts

- `RUNPOD_IMAGE.txt`.
- `IMAGE_BUILD.json`.
- GitHub validation artifact.

## Stage 3 — Configure RunPod

Follow [RUNPOD_SETUP.md](RUNPOD_SETUP.md).

### Goal

Deploy one A100 80 GB Pod from the exact prebuilt image with no paid-time installation.

### Pass criteria

- Correct secrets and variables.
- 80 GB container disk and 300 GB `/workspace` volume.
- Port 8888.
- One on-demand A100 80 GB.
- Ready log and password-protected JupyterLab.

### Stop criteria

Wrong image, wrong GPU, missing storage, passwordless Jupyter, or any startup integrity error.

### Artifacts

- RunPod template.
- Pod ID and displayed hourly rate.
- Startup log if troubleshooting is needed.

## Stage 4 — Run, monitor, and export

Follow [RUN_AND_MONITOR.md](RUN_AND_MONITOR.md).

### Goal

Run every gate with one background command, preserve full or partial evidence, and stop billing after verified download.

### Start command

```bash
cd /workspace/agent_worm_poc_v0.6.0
export RUNPOD_HOURLY_RATE="1.49"  # replace 1.49 with RunPod's displayed total hourly rate
bash scripts/runpod/start_gated_run.sh
```

### Monitor command

```bash
bash scripts/runpod/status.sh
```

### Controlled cancel command

```bash
bash scripts/runpod/cancel_run.sh
```

### Pass criteria

- Status `completed`.
- All gates pass.
- Evidence ZIP and checksum exist and verify.

### Stop criteria

Any automatic gate failure, cost limit, unresponsive phase, or invalid evidence.

### Artifacts

- Full evidence ZIP and `.sha256`.
- All items listed in [ARTIFACTS.md](ARTIFACTS.md).

## Stage 5 — Extract the instructor package

### Goal

Turn the technical evidence into a clear next-meeting decision.

### Steps

1. Extract the evidence ZIP.
2. Open `outputs/NEXT_MEETING_SUMMARY.md`.
3. Open `outputs/compatibility/compatibility_summary.json`.
4. Open `outputs/poc/placement_summary.csv` in Excel.
5. Confirm `outputs/session/cost_estimate.json`.
6. Preserve the complete ZIP unchanged as the audit copy.

### End artifacts to bring to the instructor

1. One-page meeting summary.
2. Exact research question and fixed workflow.
3. Four exact model deployments and revisions.
4. Compatibility pass/fail table.
5. 24-placement preliminary comparison.
6. Benign utility result.
7. Evidence that propagation reached a downstream agent, if observed.
8. Evidence of placement variation within the same injected condition, if observed.
9. Actual/estimated compute cost.
10. Limitations and recommendation to advance or revise.

### Decision rule

Advance only when the generated recommendation says `recommended_to_advance: true` and the underlying artifacts support it. A failed gate does not invalidate the research topic; it identifies what must be changed before a larger experiment.

## Safety, recovery, and interpretation

- Read [SECURITY_AND_SAFETY.md](SECURITY_AND_SAFETY.md).
- Use [RECOVERY.md](RECOVERY.md) for any failed stage.
- Use [COST_CONTROL.md](COST_CONTROL.md) before deployment.
- Read [EXPERIMENT_DESIGN.md](EXPERIMENT_DESIGN.md) before interpreting results.
- Never describe a one-repetition/reused-response POC as final white-paper evidence.
