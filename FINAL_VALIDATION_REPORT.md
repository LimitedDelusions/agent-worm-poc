# Agent Worm POC v0.7.0 Final Validation Report

## Release under test

- Project: Agent Worm Model-Placement POC
- Version: 0.7.0
- Validation date: 2026-08-06
- Supported paid path: one prebuilt container on one on-demand A100 80 GB RunPod Pod
- Main POC default: 24 placements × 4 scenarios × 3 repetitions = 288 workflows and 1,152 independent stage requests

## Completed local validations

| Validation | Result |
|---|---|
| Python compilation (`src`, `scripts`, `tests`) | PASS |
| Unit/integration/regression tests | PASS — 48 tests |
| Bash syntax for all shell scripts | PASS |
| JSON configuration parsing | PASS |
| Release integrity/secret/safety audit | PASS after final manifest regeneration |
| Positive-control simulation | PASS — 2 workflows at artifact depth 2 |
| Full fake-adapter placement validation | PASS |
| Pair-level primary-outcome aggregation | PASS — 48 rows |
| Response reuse accounting | PASS — 0 reused stages |
| Evidence package creation and ZIP integrity | PASS in unit/integration testing; repeated against the extracted final release during packaging |
| Partial-evidence packaging before model freeze | PASS |

## Simulated main-POC counts

- Model slots: 4
- Roles: 4
- Main scenarios: 4
- Complete placements: 24
- Repetitions in simulated plumbing check: 1
- Workflows: 96 planned / 96 completed
- Logical stage events: 384
- Unique simulated inference requests: 384
- Reused stage events: 0
- Failed workflows: 0
- Schema-invalid stages: 0
- Semantic-invalid stages: 0
- Output-invalid stages: 0
- Intake-to-relay summary rows: 48 = 12 ordered pairs × 4 scenarios

The simulated check validates code and measurement plumbing only. It is explicitly marked `research_evidence: false` and cannot be used as a model-security result.

## Experimental design checks

| Design control | Result |
|---|---|
| Injected document equals benign document plus one appended carrier block | PASS |
| Neutral roles contain no attack-specific guidance | PASS |
| Positive and hardened controls are separate | PASS |
| Trusted role instructions use system messages; documents/artifacts use user messages | PASS |
| Positive, neutral, and hardened injected conditions use the same source document | PASS |
| Generated artifacts become downstream inputs | PASS |
| Schemas do not ask the model about the carrier | PASS |
| Contiguous two-artifact scoring is enforced | PASS |
| Independent downstream violations are separated | PASS |
| Main real POC forbids response reuse | PASS |
| Real POC requires 2–5 repetitions | PASS |
| Positive control requires at least 2 repetitions | PASS |
| Real tools and external effects are absent | PASS |

## Mandatory external gates

The release must not be treated as ready for research interpretation until:

1. GitHub Actions `validate` passes, including ShellCheck and simulated validation.
2. GitHub Actions `build` successfully publishes the pinned amd64 container.
3. The exact GHCR digest can be pulled by RunPod using public visibility or separate read-only registry credentials.
4. RunPod preflight passes on one A100 80 GB GPU.
5. All four exact model deployments pass compatibility.
6. The two-repetition positive control reaches both generated artifacts.
7. The one-placement neutral/hardened shakedown passes before the full POC begins.

## Required real-run outputs

The evidence ZIP must contain the frozen model manifest, compatibility summary, positive-control evaluation, shakedown manifest, POC manifest, stage events, independent request catalog, workflow scores, 24-placement summary, 12-pair intake-to-relay summary, instructor summary, cost estimate, exact source snapshot, package manifest, and ZIP checksum.

## Remaining uncertainty

No static audit guarantees real-model success. The largest unresolved risks are container-build disk limits, Hugging Face repository changes, model/vLLM compatibility, model-specific structured-output behavior, actual download/load time, and whether the neutral carrier produces sufficient multi-hop variation. The gated run is designed to stop and package evidence instead of continuing after any invalid prerequisite.
