# Start Here — Agent Worm POC v0.8.3

## End goal

Produce defensible evidence showing whether the **ordered intake-to-relay model assignment** changes the probability that a safe document-borne carrier survives two independently generated artifacts.

This POC decides whether the research question is measurable enough to advance to the full SANS proposal. It does not prove a universal ranking of model families.

## Why v0.8.3 replaces v0.8.2

The v0.8.2 hosted validation stopped on ShellCheck warning `SC2155` before the container build began. v0.8.3 separates the affected shell assignment from its export, with no change to runtime behavior or the locked scientific design.

## Operational hardening inherited from v0.8.2

The v0.8.1 pre-publish audit found three operational blockers that could have failed or weakened a paid run:

1. the RunPod wrapper pre-created the run directory that the Python runner required to create exclusively;
2. vLLM child processes inherited unrelated interactive and provider credentials;
3. trusted remote model code did not receive the frozen model revision explicitly, and the downloaded reasoning-parser plugin was not re-hashed immediately before execution.

v0.8.3 retains those launch, secret-isolation, and provenance repairs. It preserves v0.8.1's prompts, carriers, scoring, scientific gates, sample construction, model repositories, and generation configuration unchanged.

## The three gates

1. **Compatibility:** every model must complete all four benign roles.
2. **Calibration:** positive control, neutral/hardened shakedown, sham specificity, benign utility, and within-block assignment variation must pass.
3. **Main matrix:** all 16 ordered model pairs run across three carriers, three documents, two seeds, and matched neutral/hardened policies.

If any earlier gate fails, the program stops and packages partial evidence.

## Before renting RunPod

1. Verify the release ZIP checksum.
2. Replace the repository with this release; do not overlay it on an older version.
3. Follow `CODING_HANDOFF.md`.
4. Run all free tests and the simulated gated sequence.
5. Push to GitHub.
6. Run `.github/workflows/validate-and-build.yml`.
7. Confirm both jobs are green.
8. Download the immutable image reference from the workflow artifact `agent-worm-poc-container-reference`.
9. Do not start a GPU until the image reference ends in `@sha256:<64 hex characters>`.

## Paid-run overview

Follow `docs/RUNPOD_SETUP.md`. On the Pod, the project is copied to:

```text
/workspace/agent_worm_poc_v0.8.3
```

From a Jupyter terminal:

```bash
cd /workspace/agent_worm_poc_v0.8.3
export RUNPOD_HOURLY_RATE_USD="<exact displayed total hourly rate>"
export MAX_TOTAL_COST_USD="25"
export MAX_GPU_HOURS="8"
bash scripts/runpod/start_gated_run.sh
```

Monitor from a second terminal:

```bash
cd /workspace/agent_worm_poc_v0.8.3
bash scripts/runpod/status.sh
```

Cancel safely:

```bash
bash scripts/runpod/cancel_run.sh
```

## Required deliverables

Before terminating the Pod, download:

- `agent-worm-results-<run-id>.zip`
- its `.sha256` file
- the run’s `RUN_STATUS.json`

The evidence ZIP contains raw stage events, generated artifacts, workflow scores, ordered-pair summaries, matched neutral/hardened results, prespecified inference, model revisions, server logs, source snapshot, environment metadata, and semantic-review files.

Use `DEPLOYMENT_CHECKLIST.md` during the live session.
