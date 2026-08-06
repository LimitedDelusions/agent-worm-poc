# Cost Control

## Paid resource

Use one On-Demand A100 PCIe 80 GB or A100 SXM 80 GB Pod. An H100 and four simultaneous GPUs are unnecessary for this POC.

## Controls built into the project

- dependencies and vLLM are installed during the free GitHub image build;
- models are loaded sequentially on one GPU;
- the run has a default six-hour hard timeout;
- POC repetitions default to one and are capped at three;
- exact duplicate requests may be memoized during the POC;
- status displays elapsed time and estimated gated-run cost;
- the final package records an estimate using the user-entered hourly rate;
- the run stops at the first failed gate instead of continuing to spend money.

## What the estimate includes

The project estimate begins when `start_gated_run.sh` starts and ends when the gated run exits. It does not include:

- image-pull and Pod startup time;
- time spent opening JupyterLab before the command;
- time left running after evidence packaging;
- persistent volume charges;
- provider taxes or pricing changes.

RunPod Billing is authoritative.

## Recommended behavior

1. Build and validate the image before deploying a Pod.
2. Deploy only when you have time to begin promptly.
3. Record the displayed total hourly rate.
4. Use `POC_REPETITIONS=1` for the first real POC.
5. Monitor with `status.sh`.
6. Cancel through `cancel_run.sh` if a phase is clearly stuck.
7. Download evidence immediately after completion.
8. Terminate the Pod after download; stopping alone can leave storage charges.

## Hard stop rules

Cancel if:

- no status update occurs for an unexpectedly long period and the server log is not growing;
- a model repeatedly fails to load;
- preflight or compatibility fails;
- the predicted cost exceeds your personal limit;
- you need to leave and cannot monitor the remaining hard-cap window.
