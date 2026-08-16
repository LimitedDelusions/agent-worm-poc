# Run and Monitor

## Start

```bash
cd /workspace/agent_worm_poc_v0.8.5
export RUNPOD_HOURLY_RATE_USD="<exact displayed rate>"
export MAX_TOTAL_COST_USD="25"
export MAX_GPU_HOURS="8"
bash scripts/runpod/start_gated_run.sh
```

The command returns immediately and prints a session ID and PID.

## Monitor

```bash
bash /workspace/agent_worm_poc_v0.8.5/scripts/runpod/status.sh
```

Check:

- current gate and status;
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
bash /workspace/agent_worm_poc_v0.8.5/scripts/runpod/cancel_run.sh
```

Wait for `status.sh` to report NOT RUNNING before stopping or terminating the Pod.

## Completion

A complete run has:

```json
"status": "completed"
```

An aborted run is still expected to produce a partial evidence ZIP. Download it before troubleshooting or terminating.
