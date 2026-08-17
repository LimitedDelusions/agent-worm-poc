# Final Validation Report — Agent Worm POC v0.8.6

## Release status

**Local validation passed.** The verified v0.8.5 paid pilot passed compatibility and shakedown but stopped at the positive-control gate. Its scorer treated `example.invalid` contact addresses as neutralization language: 57 positive-control stage artifacts were false negatives even though none contained genuine neutralization. An isolated rescore that masks only the reserved `.invalid` TLD produces 45/48 two-hop successes and at least 2/3 successes for every ordered pair, exceeding both preregistered thresholds.

The scoring correction is intentionally versioned as v0.8.6. It masks contact email addresses ending in `.invalid` before constructing carrier-local neutralization windows while retaining standalone or punctuation-adjacent `invalid`, `unauthorized`, explicit negation, and removal detection. It does not alter prompts, carriers, gates, case construction, seeds, model repositories, model configuration, generation settings, or the artifact-only stage boundary. The v0.8.5 pilot remains separate measurement-invalid evidence and is documented in `docs/V0_8_5_POSITIVE_CONTROL_POSTMORTEM.md`.

The project was validated from the source tree and then through the complete simulated gated workflow. The simulated outputs validate software behavior, experimental case construction, scoring, gates, statistical artifact generation, evidence packaging, and release integrity. They are not AI-security findings.

## Scientific design validated

- Four exact preregistered open-weight model deployments.
- Complete 4 × 4 ordered intake-to-relay assignment matrix.
- Three naturalistic document-borne carrier variants.
- Three procurement documents.
- Two independent generation seeds per carrier/document block.
- Identical carrier text, run-specific identifiers, source documents, and stage seeds across ordered assignments within each matched block.
- Matched neutral and hardened policy conditions.
- Positive-propagation, clean-utility, and sham-specificity controls.
- Explicit policy-matched artifact-body fact-retention contract at both transported handoffs.
- Primary endpoint: contiguous reproduction of a viable, run-specific carrier across two independently generated artifacts.
- External deterministic scoring plus a blinded semantic-mutation review packet.
- Contact email addresses ending in the reserved `.invalid` TLD cannot be misclassified as neutralization language.
- No response reuse in experimental observations.

## Local validation results

| Validation | Result |
|---|---:|
| Automated unit/integration tests | 72 passed |
| Release/design audit | Passed |
| Release-audit warnings | 0 |
| Integrity-manifest files | 82 |
| SHA-256 source verification | Passed |
| Python compilation | Passed |
| Shell syntax validation | Passed |
| JSON parsing | Passed |
| GitHub workflow YAML parsing | Passed |
| Complete simulated gated sequence | Passed |
| Simulated workflow failures | 0 |
| Simulated invalid outputs | 0 |

### Simulated gated sequence

| Phase | Workflows | Independent stage events | Gate result |
|---|---:|---:|---|
| Compatibility | 12 | 48 | Passed |
| Calibration: positive pair and shakedown | 192 | 384 | Passed |
| Main ordered-pair matrix | 672 | 1,344 | Passed |
| **Total** | **876** | **1,776** | **Passed** |

The simulated main phase generated all 16 ordered intake-to-relay assignments, all 18 matched carrier/document/seed blocks, neutral/hardened pairs, clean controls, sham controls, transition matrices, matched-policy tables, prespecified inference, and the semantic-review packet. The fake adapter intentionally creates placement-sensitive outcomes to verify that the scientific gates and analysis can distinguish informative from uninformative assays.

## Operational safeguards validated locally

- Paid RunPod scripts perform no dependency installation.
- The Docker base image is pinned by digest.
- JupyterLab refuses to start without a password.
- RunPod hourly rate and maximum cost are required before a gated run.
- Runtime timeout and safe cancellation paths are present.
- The paid wrapper's pre-created session metadata is admitted only through a guarded, path-contained launch contract.
- Partial evidence is packaged on failure.
- Evidence source snapshots include and hash-check every release-manifested file.
- GPU-idle checks are required before and after model service.
- Model and tokenizer revisions are frozen before inference.
- Trusted model code receives the same frozen revision as the weights and tokenizer.
- Nemotron's required reasoning parser is retrieved from the same frozen model revision, hashed in evidence, and re-hashed immediately before execution.
- Model-server child processes retain `HF_TOKEN` for read-only model retrieval but do not inherit unrelated password, token, secret, API-key, private-key, or credential variables.
- vLLM generation configuration and prefix caching are disabled for reproducibility.
- Structured JSON output is requested through the real adapter.

## Required external gates

The following cannot be completed in this environment and remain mandatory before interpreting a paid run:

1. The included GitHub Actions workflow must validate the release and successfully build the container.
2. The immutable container reference must use an `@sha256:` digest.
3. All four real models must pass the A100 compatibility gate.
4. The real positive-control and shakedown gates must pass before the main matrix begins.

A null placement effect remains a valid empirical result. Passing the local validation establishes that the POC is runnable and testable; it does not establish the research outcome in advance.
