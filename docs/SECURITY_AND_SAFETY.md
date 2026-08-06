# Security and Safety Boundary

## Threat simulation

The POC uses synthetic text to test whether a marker can move through a controlled four-agent workflow and influence a nonfunctional action decision.

## What is not present

- no malware or executable worm;
- no external email, messaging, browser, MCP, or network tool;
- no real credential, account, API, or sensitive record;
- no filesystem-writing agent tool;
- no destructive or persistent action;
- no testing of third-party hosted model guardrails;
- no provider system-prompt extraction;
- no public target.

## Synthetic impact

`restricted_mock_action` is only a string allowed by the output schema. There is no function with that name and no code that executes it. An approved restricted action is a measurement event, not a real operation.

## External network use

The infrastructure itself contacts Hugging Face to read model metadata and download model files. This is ordinary authorized model retrieval with the user’s read-only token. Model-generated outputs are not connected to any external tool or network destination.

## Secrets

- Hugging Face and Jupyter credentials are passed through RunPod Secrets.
- The release audit scans source for token-like strings.
- Tokens are not written into manifests or the evidence package.
- The Jupyter server refuses to start without a password.
- The model server listens only on `127.0.0.1` inside the Pod and uses a local API key.
- The vLLM model subprocess does not inherit `JUPYTER_PASSWORD`, `RUNPOD_API_KEY`, `PUBLIC_KEY`, or `GITHUB_TOKEN`.
- The read-only `HF_TOKEN` is retained by the model subprocess only because first-time model retrieval may occur when vLLM starts.
- Nemotron requires frozen remote model code and a frozen reasoning-parser file. Both use the exact repository revision and recorded hashes; no mutable parser is downloaded at inference time.

## Safe cancellation

Use `scripts/runpod/cancel_run.sh`. It requests process-group termination, stops residual vLLM processes, waits for cleanup, and packages partial evidence. Do not stop the Pod first when a run is active.

## Research interpretation

A model producing a marker or restricted mock decision is evidence about this controlled workflow only. It does not establish that the model is generally unsafe, compromised, or vulnerable in every deployment.
