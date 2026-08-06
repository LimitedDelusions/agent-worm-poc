# Final Validation Report

## Release under test

- Project: Agent Worm Model-Placement POC
- Version: 0.6.0
- Validation date: 2026-08-06
- Supported paid path: one prebuilt container on one A100 80 GB RunPod Pod

## Completed validations

| Validation | Result |
|---|---|
| Python compilation (`src`, `scripts`, `tests`) | PASS |
| Unit/integration/regression tests | PASS — 43 tests |
| Bash syntax for all shell scripts | PASS |
| JSON config parsing | PASS |
| GitHub Actions workflow YAML parsing | PASS |
| Release integrity/secret/safety audit | PASS — no errors or warnings |
| Full fake-adapter placement validation | PASS |
| ZIP construction and internal integrity test | Performed during final release packaging |
| Release SHA-256 sidecar verification | Performed during final release packaging |

## Simulated placement-validation counts

- Four model slots
- Four fixed roles
- Four conditions
- 24 placements
- 96 workflows
- 384 logical stage events
- 78 unique simulated inference requests
- 306 explicitly linked reused stage events
- 0 failed workflows
- 0 schema-invalid stages
- 0 semantic-invalid stages
- 0 output-invalid stages

The fake adapter validates orchestration, state transfer, placement enumeration, request reuse bookkeeping, scoring, reporting, and packaging. It is explicitly not research evidence about real models.

## Coverage result

Overall measured line coverage: **64%**.

Strongly covered modules include compatibility (88%), engine/orchestration (83%), reporting/packaging (94%), scoring (96%), types (100%), and utilities (96%). Lower coverage is concentrated in code that requires an actual NVIDIA environment or live vLLM HTTP process: preflight, HTTP error handling, server startup/readiness/shutdown, and CLI dispatch.

## Mandatory external gates

The release must not be treated as deployable until:

1. GitHub Actions `validate` passes, including ShellCheck.
2. GitHub Actions `build` successfully builds and publishes the pinned container.
3. RunPod preflight passes on one A100 80 GB GPU.
4. All four exact model deployments pass compatibility.
5. The cross-model shakedown passes.

## Remaining uncertainty

No static audit can guarantee zero defects. The largest unresolved risks are real image build compatibility, Hugging Face repository changes, A100/vLLM model-loading behavior, model-specific reasoning/output handling, and strict JSON-schema compliance. The release handles these as fail-fast gates and packages evidence instead of continuing into an invalid 24-placement run.
