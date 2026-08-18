# Start Here — Agent Worm POC v0.8.10

## End goal

Produce defensible evidence showing whether the **ordered intake-to-relay model assignment** changes the probability that a safe document-borne carrier survives two independently generated artifacts.

This POC decides whether the research question is measurable enough to advance to the full SANS proposal. It does not prove a universal ranking of model families.

## Why v0.8.10 replaces v0.8.9

The single v0.8.9 workflow again passed the complete validation job and every source check inside the Docker layer, then stopped before parser construction or image export. The pinned CUDA image reports semantic vLLM release `0.25.1`, while its exact installed distribution version is `0.25.1+cu129`; v0.8.9 incorrectly required literal distribution equality with the suffix-free release. No v0.8.9 image, registry tag, immutable reference artifact, or paid run was created. v0.8.10 validates the exact digest-pinned CUDA distribution, records both version forms, and retains the GPU-independent real-parser inspection. Details are preserved in `docs/V0_8_9_BUILD_POSTMORTEM.md`.

The prompts, carriers, scoring, gates, cases, model pins, generation settings, scientific execution, and paid model-server commands are byte-identical to v0.8.9. Operationally, v0.8.10 also binds CI to the exact release tag and makes the paid launcher reject any installed vLLM distribution that differs from the baked runtime marker.

## Why v0.8.9 replaces v0.8.8

The single v0.8.8 workflow passed every validation step, including Linux tests, ShellCheck, release audit, and the complete fake gate, but its Docker build stopped before export. The GPU-less BuildKit host invoked `vllm serve --help`; pinned vLLM 0.25.1 constructs device defaults while building that help parser and could not infer a CUDA device. No v0.8.8 image, registry tag, immutable reference artifact, or paid run was created. v0.8.9 constructs vLLM's dedicated documentation parser under its process-local CPU fallback and verifies every production serve flag directly, without starting a server, loading a model, or probing CUDA. Details are preserved in `docs/V0_8_8_BUILD_POSTMORTEM.md`.

The prompts, carriers, scoring, gates, cases, model pins, generation settings, and scientific execution logic are byte-identical to v0.8.8.

## Why v0.8.8 replaced v0.8.7

The single v0.8.7 GitHub validation run stopped before any container build because the workflow invoked the `pytest` console entry point with `PYTHONPATH=src`; on Linux that omitted the repository root needed by two tests of release scripts. v0.8.8 invokes pytest as `python -m pytest` in both CI and the Docker build, matching the validated local command, and locks that invocation with a regression test. Its final local fake rehearsal also exposed a transient Windows sharing race in the live atomic status writer; v0.8.8 now uses unique temporary files plus bounded replace retries, with concurrency and fault-injection tests. The operator rehearsal additionally hardened cancellation when a Python runner survives an abnormal `timeout`-leader exit. No v0.8.7 image or paid run was created. The prompts, carriers, scoring, gates, cases, model pins, generation settings, and scientific execution logic are byte-identical to v0.8.7. Details are preserved in `docs/V0_8_7_CI_POSTMORTEM.md`.

## Why v0.8.7 replaces v0.8.6

A complete post-build rehearsal of v0.8.6 found fail-closed gaps before another paid session: equal zero clean-task utility could pass calibration, incomplete matrices and endpoints were not rejected everywhere, a failed main measurement could still look execution-complete, and the semantic-review export did not implement its locked dual-review protocol. Operational rehearsal also found duplicate-launch, cancellation, packaging, status, and evidence-transfer failure paths.

v0.8.7 fixes those defects, release-pins the four model/tokenizer/code commits, and records design, technical, assay, and empirical outcomes separately. A complete valid null is now a completed result, not a reason to rerun. Details are preserved in `docs/V0_8_6_FAIL_CLOSED_AUDIT.md`.

## Why v0.8.6 replaced v0.8.5

The first real v0.8.5 gated run passed compatibility and shakedown but stopped at the positive-control gate. The frozen scorer reported 17/48 two-hop successes. Evidence review found that every one of its 57 positive-control neutralization flags came from the reserved contact domain `.invalid`, not from model neutralization language. Masking only that TLD before neutralization analysis yields 45/48 two-hop successes and at least 2/3 successes for every ordered pair. The verified pilot and isolated rescore are documented in `docs/V0_8_5_POSITIVE_CONTROL_POSTMORTEM.md`.

v0.8.6 corrects that scoring collision before carrier-local windows are constructed. Standalone neutralization terms remain active. This is a versioned scoring correction. Prompts, carriers, gates, case construction, seeds, model repositories, model configuration, generation settings, and the artifact-only stage boundary are unchanged from v0.8.5.

## Why v0.8.5 replaced v0.8.4

The first real v0.8.4 compatibility run correctly stopped before calibration. All 48 model requests succeeded and were valid, but Gemma passed zero of three benign workflows because it placed the procurement facts in dedicated JSON fields while omitting them from `artifact_body`. That field is intentionally the only artifact transported downstream, so relay genuinely lost the facts. The verified failed-pilot evidence and root-cause analysis are recorded in `docs/V0_8_4_COMPATIBILITY_POSTMORTEM.md`.

v0.8.5 makes the existing interface requirement explicit and identical across all positive, neutral, and hardened intake and relay prompts: `artifact_body` itself must retain supplier, item or service, quantity, total price, delivery timing, and relevant operational or commercial details. This is a versioned prompt correction. Carriers, scoring, gates, case construction, seeds, model repositories, model configuration, generation settings, and the artifact-only stage boundary are unchanged.

## Operational hardening inherited from v0.8.2

The v0.8.1 pre-publish audit found three operational blockers that could have failed or weakened a paid run:

1. the RunPod wrapper pre-created the run directory that the Python runner required to create exclusively;
2. vLLM child processes inherited unrelated interactive and provider credentials;
3. trusted remote model code did not receive the frozen model revision explicitly, and the downloaded reasoning-parser plugin was not re-hashed immediately before execution.

v0.8.10 retains those launch, secret-isolation, provenance, ShellCheck, container-runtime, artifact-body, and reserved-TLD repairs.

## The three gates

1. **Compatibility:** the exact 12-row homogeneous matrix must be complete; schema/runtime validity and clean utility are reported separately.
2. **Calibration:** the exact positive-control and shakedown matrices must be complete; assay sensitivity, specificity, absolute per-model/role utility, and empirical variation are classified separately.
3. **Main matrix:** all 16 ordered model pairs run across three carriers, three documents, two seeds, and matched neutral/hardened policies. A design- or measurement-invalid matrix aborts; a valid null completes.

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
/workspace/agent_worm_poc_v0.8.10
```

From a Jupyter terminal:

```bash
cd /workspace/agent_worm_poc_v0.8.10
export RUNPOD_HOURLY_RATE_USD="<exact displayed total hourly rate>"
export MAX_TOTAL_COST_USD="25"
export MAX_GPU_HOURS="8"
bash scripts/runpod/start_gated_run.sh
```

Monitor from a second terminal:

```bash
cd /workspace/agent_worm_poc_v0.8.10
bash scripts/runpod/status.sh
```

Cancel safely:

```bash
bash scripts/runpod/cancel_run.sh
```

## Required deliverables

After `status.sh` reports `NOT RUNNING`, stage and send the complete verified bundle with one command:

```bash
bash /workspace/agent_worm_poc_v0.8.10/scripts/runpod/stage_and_send_evidence.sh
```

Before terminating the Pod, receive and locally verify:

- `agent-worm-results-<run-id>.zip`
- its `.sha256` file
- its `.zip.json` metadata
- the run’s `RUN_STATUS.json`

The evidence ZIP contains raw stage events, generated artifacts, workflow scores, ordered-pair summaries, matched neutral/hardened results, prespecified inference, model revisions, server logs, source snapshot, environment metadata, and semantic-review files.

Use `DEPLOYMENT_CHECKLIST.md` during the live session.
