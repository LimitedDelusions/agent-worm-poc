# Recovery and Failure Handling

## First rule

Do not improvise package installation or edit the scientific parameters on a paid Pod. Preserve the generated evidence, terminate the Pod, fix the source, rebuild the container through GitHub, and start a new session.

## If GitHub validation or build fails

**Do not deploy RunPod.**

1. Open the failed GitHub Actions job.
2. Expand the first red step.
3. Save or copy the error text.
4. Correct the source and push again.
5. Proceed only after both jobs pass and a new digest artifact is produced.

## If the Pod never exposes JupyterLab

1. Open the RunPod Pod logs.
2. Look for a missing secret, image-pull failure, source-integrity failure, or insufficient disk.
3. Do not run a shell installation workaround.
4. If the image cannot start, terminate the Pod and correct the template/image.

## If preflight fails

Read:

```text
/workspace/agent_worm_outputs/<session>/setup/preflight.json
```

The failed check identifies the exact issue. Common fixes:

- image reference does not exactly match the digest;
- volume is too small or not mounted at `/workspace`;
- Hugging Face/Jupyter secret not injected;
- hourly rate not set;
- wrong GPU count or insufficient VRAM;
- stale compute process exists.

Preflight runs before model download, so a failure should be inexpensive.

## If model freeze fails

- Confirm the same Hugging Face account owns the token and accepted Gemma terms.
- Confirm the token is read-only but can read gated public models.
- Do not paste the token into logs or chat.
- Retry only after correcting account access.

## If compatibility fails

The gated run stops automatically and packages partial evidence. Review:

- `compatibility/compatibility_summary.json`;
- the failing model’s `manifest.json` and `failures.json`;
- `compatibility/server_logs/`;
- `compatibility/server_lifecycle.jsonl`.

Do not interpret a model-load or formatting failure as prompt-injection behavior.

## If the run appears stuck

Run:

```bash
bash scripts/runpod/status.sh
```

If the phase and logs are not progressing, cancel safely:

```bash
bash scripts/runpod/cancel_run.sh
```

Wait until status reports `NOT RUNNING`. Download the partial evidence ZIP before terminating the Pod.

## If you must leave

- If the gated run is active and still within your budget, the six-hour timeout protects the upper bound.
- To stop sooner, use the cancel script and wait for packaging.
- Do not use RunPod Stop before the controlled cancellation completes.

## If evidence packaging fails

The raw session remains under:

```text
/workspace/agent_worm_outputs/<session-id>
```

Download that directory or run:

```bash
bash scripts/runpod/package_results.sh /workspace/agent_worm_outputs/<session-id>
```

## If the Pod is terminated before download

An attached volume can be permanently deleted. The project cannot recover files that no longer exist. Always download and verify the ZIP first.
