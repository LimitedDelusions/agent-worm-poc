# Failure and Recovery

## General rule

Do not install packages, edit prompts, or improvise on paid GPU time. Download the evidence package, terminate billing, fix the versioned source, rebuild in GitHub, and redeploy.

## Compatibility fails

Download partial evidence. Identify the exact model, role, schema, or server error. Fix outside RunPod and issue a new version if behavior-affecting configuration changes.

## Positive control fails

The assay has not proved that the tested pair can reproduce the carrier even under trusted preservation instructions. Do not interpret neutral zeroes as safety.

## Shakedown fails

- universally zero: natural assay is not measurable;
- universally successful: assay is saturated;
- variation only between carrier forms: evidence does not support the model-assignment question;
- hardened ceiling exceeded: negative control is not functioning;
- sham false positive: scorer is invalid.

The main phase intentionally does not start.

## Timeout or cancellation

Use `cancel_run.sh`. The Python process packages partial evidence in `finally`. If forced termination is necessary, download the full session directory and emergency ZIP before terminating the Pod.

## Storage/I/O failure

Stop issuing writes. Download available evidence. One stop/start may test whether the volume recovers. Persistent I/O error requires a new Pod; do not repeatedly reinstall.

## VRAM does not release

The server manager aborts instead of loading another model into residual memory. Preserve the server log and terminate the Pod.

## Evidence ZIP fails verification

Do not terminate until either the ZIP verifies or the entire results directory has been downloaded.
