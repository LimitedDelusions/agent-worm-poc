# Recovery and Failure Handling

## If GitHub validation fails

Do not deploy. Open the failed step, fix the source, rerun all validation, and obtain a new digest.

## If the Pod cannot start the image

Stop the Pod. Confirm the exact lowercase GHCR digest and registry visibility. Do not substitute a mutable tag.

## If preflight fails

Read `outputs/setup/preflight.json` and the gated log. Correct the missing secret, storage, image reference, GPU, or runtime issue. A failed preflight should occur before model download.

## If a model fails compatibility

The run stops. Preserve the packaged partial evidence. Do not skip the model or continue to the POC. Review the model-specific server log and compatibility manifest.

## If positive control fails

The assay cannot demonstrate multi-hop artifact reproduction. Do not interpret neutral zero propagation. Review the carrier, generated artifacts, schemas, and scoring before another paid run.

## If shakedown fails

Do not run all 24 placements. Correct invalid structured output, server stability, or workflow handoff first.

## If the POC hangs or cost grows

```bash
bash /workspace/agent_worm_poc_v0.7.0/scripts/runpod/status.sh
bash /workspace/agent_worm_poc_v0.7.0/scripts/runpod/cancel_run.sh
```

The cancellation path sends a controlled termination signal and packages partial evidence.

## If the result ZIP is missing

Run:

```bash
bash /workspace/agent_worm_poc_v0.7.0/scripts/runpod/package_results.sh \
  "$(cat /workspace/agent_worm_outputs/latest_session.txt)"
```

Do not terminate the Pod until the ZIP and checksum are downloaded and verified.
