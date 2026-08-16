# Cost and Runtime Gate

## Goal

Prevent another open-ended paid session.

## Required variables

Before launch:

```bash
export RUNPOD_HOURLY_RATE_USD="<exact displayed total hourly rate>"
export MAX_TOTAL_COST_USD="25"
export MAX_GPU_HOURS="8"
```

The launcher calculates:

```text
minimum(MAX_GPU_HOURS, MAX_TOTAL_COST_USD ÷ hourly rate)
```

The launcher refuses to start if those limits permit less than 30 minutes. It reserves the final 10 minutes for graceful termination and evidence packaging, so the active inference timeout plus forced-stop grace does not exceed the calculated process budget.

**Important:** this is a process-level guard, not a RunPod billing shutdown. The Pod continues billing after the process exits until the operator downloads evidence and terminates the Pod.

## Expected workload

- 12 compatibility workflows / 48 requests
- 48 positive-control workflows / 96 requests
- 144 calibration workflows / 288 requests
- 672 main workflows / 1,344 requests
- 876 total workflows / 1,776 independent requests
- approximately 20 sequential model loads because positive and shakedown calibration are batched together

Actual runtime depends on model download caching, model-load time, generation speed, and output length. RunPod Billing is authoritative.

## Stop behavior

A failed gate, SIGTERM, timeout, or user cancellation causes the Python process to stop the active model server and package partial evidence. If forced cancellation is required, `cancel_run.sh` attempts emergency packaging.
