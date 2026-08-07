# Cost Control

## Goal

Run the complete v0.7.0 POC on one A100 80 GB Pod without paying for dependency installation, idle debugging, or four simultaneous GPUs.

## Controls

1. Build and validate the container in GitHub Actions before renting the Pod.
2. Use one GPU and load models sequentially.
3. Run one guarded command rather than manual phases.
4. Record RunPod’s displayed total hourly rate in `RUNPOD_HOURLY_RATE`.
5. Use the default eight-hour hard timeout unless deliberately reduced.
6. Start with the default three repetitions; do not increase during the same run.
7. Monitor with `status.sh`.
8. Cancel with `cancel_run.sh`; it packages partial evidence.
9. Download and verify results immediately after completion.
10. Terminate the Pod after local verification.

## Cost artifacts

- `outputs/session/launch.json`
- `outputs/session/cost_estimate.json`
- RunPod Billing page, which remains authoritative.
