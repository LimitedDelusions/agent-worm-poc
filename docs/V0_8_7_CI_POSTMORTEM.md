# v0.8.7 CI portability postmortem and v0.8.8 correction

## What happened

The one v0.8.7 workflow dispatch ran against immutable tag `v0.8.7` at commit `579f28b6fcf2305a74fa2df34446af2478de56ea`. Validation stopped during pytest collection before the Docker build job. The Linux runner invoked the `pytest` console entry point with `PYTHONPATH=src`, so the repository root was absent from the import path. Two focused tests that intentionally exercise release-script entry points could not import `scripts.check_scientific_shakedown` and `scripts.release.summarize_semantic_review`.

No v0.8.7 container image or paid RunPod session was created. The failed workflow is preserved at `https://github.com/LimitedDelusions/agent-worm-poc/actions/runs/32051519906`; it was not retried and the v0.8.7 tag was not moved.

## v0.8.8 correction

v0.8.8 invokes pytest with `python -m pytest` in both GitHub validation and the Docker build. This preserves the repository root on Python's module path and matches the documented/local validation command. A static regression test requires both production build surfaces to keep that invocation.

During the subsequent v0.8.8 local fake rehearsal, a transient Windows sharing violation interrupted the atomic replacement of `RUN_STATUS.json` at the packaging transition. The writer previously reused a process-scoped temporary filename. It now uses a unique temporary file for every write, flushes it before publication, and retries only bounded `PermissionError` sharing failures. Fault-injection and concurrent-write tests reproduce and lock the corrected behavior.

The final operator rehearsal also covered abnormal supervisor death. Cancellation now validates the exact Python `real-gated` command within a discovered process group, so it can safely terminate a surviving runner even if the `timeout` group leader has already exited. Multiple or unrelated groups are still rejected rather than signalled.

These are release/build and operational evidence-status corrections only. Prompts, carriers, scoring, gates, case construction, model repositories and pinned revisions, seeds, generation settings, scientific execution logic, and the artifact-only stage boundary are byte-identical to v0.8.7.
