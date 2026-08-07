# Output Artifacts

## End goal

Leave the Pod with a verified evidence package that allows the run to be audited without relying on the live environment.

| Artifact | Purpose |
|---|---|
| `outputs/session/launch.json` | Session ID, start time, image digest, repetitions, Pod identity, recorded hourly rate |
| `outputs/setup/preflight.json` | Runtime, GPU, storage, secret, and integrity checks |
| `outputs/setup/frozen_models.json` | Exact model/tokenizer/code/parser revisions |
| `outputs/compatibility/compatibility_summary.json` | Four-model competency gate |
| `outputs/positive_control/positive_control_evaluation.json` | Proof that the assay can observe two-hop artifact reproduction |
| `outputs/shakedown/manifest.json` | One-placement cross-model end-to-end check |
| `outputs/poc/manifest.json` | Full run design and execution counts |
| `outputs/poc/stage_events.jsonl` | Every stage input, output, forwarded artifact, model, seed, validation result, and raw response |
| `outputs/poc/request_catalog.jsonl` | Every independent inference request and timing/token metadata |
| `outputs/poc/run_scores.csv` | One scored row per workflow |
| `outputs/poc/placement_summary.csv` | Aggregated metrics by full four-role placement and scenario |
| `outputs/poc/intake_relay_summary.csv` | Primary propagation outcomes for the 12 ordered intake→relay model pairs |
| `outputs/NEXT_MEETING_SUMMARY.md` | Instructor-facing summary |
| `outputs/NEXT_MEETING_SUMMARY.json` | Machine-readable gates and recommendation |
| `outputs/session/gated-run.log` | Complete run log |
| `outputs/session/cost_estimate.json` | Estimated gated-run compute cost |
| `source/` in result package | Exact source snapshot used by the run |
| `PACKAGE_MANIFEST.json` | SHA-256 and size for every packaged file |
| result `.zip.sha256` | Verification of the downloaded evidence ZIP |

## Pull these out before termination

Download both the result ZIP and its `.sha256` sidecar. Verify locally, extract, and confirm `ARTIFACT_INDEX.md`, `PACKAGE_MANIFEST.json`, `outputs/NEXT_MEETING_SUMMARY.md`, and the POC files above are present.
