# Final Validation Report — Agent Worm POC v0.8.10

## Release status

**Local release-candidate validation passed.** v0.8.10 preserves the v0.8.9 scientific and fail-closed design while correcting its exact CUDA-wheel identity check. The sole v0.8.9 workflow passed validation and every source check inside Docker, but stopped before parser construction or export because installed distribution `0.25.1+cu129` was compared literally with semantic release `0.25.1`. No v0.8.9 image, registry tag, immutable-reference artifact, or paid run was created. The final fake-run identifier and evidence checksum are recorded in the release handoff after this report and the integrity manifest are frozen; embedding them here would alter the source snapshot they identify. Commit, workflow, and image digest remain external publication gates.

Relative to v0.8.9, the release does not alter prompts, carriers, scoring, gates, source documents, case construction, randomization seeds, model pins, generation settings, scientific execution logic, paid model-server commands, or the artifact-only stage boundary. It changes release identity/default paths, documentation/integrity metadata, exact build-time vLLM distribution validation/provenance, CI ref binding, and the paid launcher's live-wheel cross-check, with focused regressions. The inherited fail-closed rationale is preserved in `docs/V0_8_6_FAIL_CLOSED_AUDIT.md`; prior CI/rehearsal corrections are preserved in `docs/V0_8_7_CI_POSTMORTEM.md`; the failed v0.8.8 and v0.8.9 builds are preserved in `docs/V0_8_8_BUILD_POSTMORTEM.md` and `docs/V0_8_9_BUILD_POSTMORTEM.md`.

## Scientific controls to validate

- Four exact release-pinned model, tokenizer, and trusted-code deployments.
- Complete 4 × 4 ordered intake-to-relay assignment matrix.
- Three carrier variants, three documents, and two independent generation seeds.
- Matched neutral/hardened inputs and clean utility controls.
- Exact compatibility, positive-control, shakedown, and main topology checks.
- Unique workflow IDs, consistent pair/model labels, and complete parseable endpoints.
- Absolute 0.90 clean utility overall and for every policy/model/role cell.
- Separate design, technical/measurement, assay, and empirical outcome classifications.
- A complete valid null main outcome finishes as evidence rather than being treated as a failure.
- Full dual-reviewer semantic sensitivity protocol with packet anchoring and input reconciliation.
- No response reuse; transport attempts and sanitized retry failures are recorded.

## Operational controls to validate

- Source, release, model-access, one-A100, GPU-idle, persistent-storage, rate, and budget preflight.
- Permanent atomic one-run claim for the exact release/image pair.
- Exact hourly-rate re-entry before the claim and process launch.
- Strict model-server environment with only required Hugging Face credential access.
- Live heartbeat, phase/model/stage/request progress, and remaining budget.
- Unique atomic status temporaries with bounded sharing-violation retry and concurrent-write tests.
- Cancellation grace longer than worst-case model cleanup, orphan cleanup, and emergency packaging.
- Execution outcome kept separate from evidence outcome.
- Final status published only after ZIP, checksum, metadata, CRC, and package manifest verify.
- One-command Pod staging/transfer and full local transfer/evidence/source/status verifier.

## Final frozen validation results

The complete local sequence was run with Python 3.11 and Git for Windows Bash. The final frozen fake run is regenerated after this report is sealed, so its dynamic run identifier and ZIP checksum belong in the external handoff rather than this manifest-covered file.

| Validation | Result |
|---|---:|
| Automated unit/integration tests | **Passed — 128** |
| Ruff | **Passed** |
| Release/design audit | **Passed — 0 errors, 0 warnings** |
| Integrity manifest | **Passed — 93 files** |
| Python compilation and Git Bash syntax | **Passed** |
| Complete simulated gated sequence | **Passed — 876 workflows, 1,776 stage events** |
| Compatibility / positive / shakedown / main validation | **Passed** |
| Main matrix | **672 workflows, 1,344 stage events** |
| Semantic-review packet | **Passed — 463 anchored items across all required classes/strata** |
| Evidence verifier | **Passed — ZIP, sidecars, package/source manifests, status parity** |

Local ShellCheck was unavailable on Windows; the GitHub validation job is the authoritative ShellCheck gate before publication.

## Required external gates

Before another paid run, exactly one GitHub Actions run must validate and build the immutable v0.8.10 tag; its public `ghcr.io/...@sha256:...` reference, workflow URL, commit SHA, and build warnings must be recorded. Real compatibility, positive-control, and shakedown outcomes remain unknown until the one authorized paid run. A valid main null is an acceptable empirical result and must not be rerun to chase variation.
