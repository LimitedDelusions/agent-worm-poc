# Full Scientific and Software Audit — v0.8.6

## Audit objective

Prevent a second paid run from being mechanically successful but scientifically inconclusive. The release was evaluated against software integrity, experimental validity, prompt realism, assay sensitivity, repeatability, scoring validity, confounding, statistical independence, operational cost control, and evidence provenance.

## Critical gaps found in v0.7.0 and corrected

1. **One payload family could overfit one wording.** Three structurally different document-borne carrier forms are now required.
2. **A static identifier could make repeated rows look independent.** Every carrier and authorization reference is unique to its carrier/document/repetition block and is held identical across ordered model assignments and paired policies.
3. **The positive control did not validate all model transitions.** All 16 ordered intake→relay pairs are now gated.
4. **Exact marker scoring missed semantic mutation.** Primary traceable scoring now requires identity plus propagation/action semantics; semantic-only candidates are exported for blinded review.
5. **Document diversity was being mislabeled as repetition.** Carrier, document, and stochastic repetition are separate dimensions in a full 3×3×2 design.
6. **No homogeneous context existed.** Four all-same-model baselines are reported separately.
7. **Relay results could be distorted by failed intake infection.** Conditional relay survival is now prespecified.
8. **Downstream action behavior could be confused with the primary transmission question.** Planner and executor remain compatibility-only in this POC; the primary matrix terminates at relay.
9. **A neutral zero could still be an assay failure.** Positive and shakedown gates automatically prevent the full run when interpretation is impossible.
10. **Utility/format failures could masquerade as security.** Document-specific fact retention, schema validation, and benign end-to-end utility are mandatory.
11. **Post-hoc payload tuning could invalidate inference.** Prompts, payloads, seeds, endpoints, and statistics are frozen in the release.
12. **Model/provider comparisons could be overgeneralized.** The study explicitly concerns four exact deployments, not all members of four families.
13. **Nemotron runtime code could drift or fail silently.** Its official reasoning-parser plugin is downloaded from the same frozen model revision, hashed, preserved in evidence, and passed to vLLM explicitly.
14. **Container and price provenance could be incomplete.** The image digest, build commit, runtime marker, displayed hourly rate, model arguments, and downloaded runtime-artifact hashes are recorded.
15. **The schema allowed facts outside the transported artifact.** The real v0.8.4 compatibility gate showed that Gemma correctly populated dedicated intake fields while omitting those facts from `artifact_body`, the only content passed downstream and scored for utility. v0.8.5 states the artifact-body fact-retention contract explicitly and identically in every intake and relay policy prompt.
16. **A reserved test-domain suffix impersonated neutralization.** The real v0.8.5 positive control exposed a collision between the bare-word `invalid` neutralization rule and synthetic contacts under `example.invalid`. v0.8.6 masks contact email addresses ending in that reserved TLD before local neutralization analysis while preserving genuine standalone neutralization terms. The failed pilot and isolated rescore are preserved in `docs/V0_8_5_POSITIVE_CONTROL_POSTMORTEM.md`.

## Residual limitations that cannot be removed from a POC

- Only one workflow topology and one business domain are tested.
- The carrier is a safe text analog, not autonomous malware.
- Two stochastic repetitions per carrier/document cell provide POC-level—not final-paper—precision.
- GPT-OSS native precision differs from the BF16 deployments; deployment is therefore part of the treatment.
- Semantic review may require human effort and inter-rater agreement.
- A GitHub container build and real A100 compatibility run remain external gates.
- A null placement result is possible and scientifically valid.

## Audit conclusion

The design is capable of answering whether the selected model placement affects traceable two-artifact propagation in the specified workflow, provided the compatibility, positive-control, and shakedown gates pass and the evidence package verifies. The POC can validate feasibility and estimate variance; it cannot establish universal model-family safety.
