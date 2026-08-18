# Run and Monitor

## Start

```bash
cd /workspace/agent_worm_poc_v0.8.10
export RUNPOD_HOURLY_RATE_USD="<exact displayed rate>"
export MAX_TOTAL_COST_USD="25"
export MAX_GPU_HOURS="8"
bash scripts/runpod/start_gated_run.sh
```

The command first performs free-in-container release, source, pinned-model-access, GPU, storage, rate, and budget checks. It requires an exact rate confirmation, atomically claims the one permitted real run for this release/image, then returns a session ID and PID. Never execute it again.

## Monitor

```bash
bash /workspace/agent_worm_poc_v0.8.10/scripts/runpod/status.sh
```

Check:

- execution/evidence status and outcome classification;
- current phase, model, stage, request counts, heartbeat, and remaining budget;
- recent log lines;
- GPU memory and utilization;
- evidence archive presence.

## Normal gate order

1. release audit and source integrity;
2. model revision freeze;
3. compatibility;
4. combined positive-control and shakedown calibration;
5. main 16-pair matrix;
6. statistical summaries;
7. blinded semantic-review packet;
8. evidence packaging.

## Safe cancellation

```bash
bash /workspace/agent_worm_poc_v0.8.10/scripts/runpod/cancel_run.sh
```

Wait for `status.sh` to report NOT RUNNING before stopping or terminating the Pod.

## Completion

A complete, evaluable run has:

```json
"status": "completed"
```

Read `gates.main.empirical_outcome` separately. `valid_null_no_ordered_pair_rate_variation` is a completed result, not a reason to rerun. `design_invalid`, `technical_invalid`, and `measurement_invalid` are non-evaluable failures. `assay_sensitivity_failure` or an uninformative shakedown outcome is a valid calibration result but intentionally prevents main.

An aborted run is still expected to produce verified partial evidence. After `Process: NOT RUNNING`, run:

```bash
bash /workspace/agent_worm_poc_v0.8.10/scripts/runpod/stage_and_send_evidence.sh
```

Receive and verify that bundle locally before troubleshooting or terminating.
