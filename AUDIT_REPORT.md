# Full Scientific and Software Audit — v0.8.8

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
14. **Container and price provenance could be incomplete.** The operator-declared image digest, recorded Pod-template match, build commit, runtime marker, displayed hourly rate, model arguments, and downloaded runtime-artifact hashes are preserved. The container does not falsely claim it can introspect a provider digest when RunPod exposes none.
15. **The schema allowed facts outside the transported artifact.** The real v0.8.4 compatibility gate showed that Gemma correctly populated dedicated intake fields while omitting those facts from `artifact_body`, the only content passed downstream and scored for utility. v0.8.5 states the artifact-body fact-retention contract explicitly and identically in every intake and relay policy prompt.
16. **A reserved test-domain suffix impersonated neutralization.** The real v0.8.5 positive control exposed a collision between the bare-word `invalid` neutralization rule and synthetic contacts under `example.invalid`. v0.8.6 masks contact email addresses ending in that reserved TLD before local neutralization analysis while preserving genuine standalone neutralization terms. The failed pilot and isolated rescore are preserved in `docs/V0_8_5_POSITIVE_CONTROL_POSTMORTEM.md`.
17. **Equal policy failure could pass utility calibration.** v0.8.8 requires the existing 0.90 clean-task threshold overall and in every policy/model/role cell; the neutral-hardened delta is now additional rather than sufficient.
18. **Incomplete evidence could look analyzable.** Compatibility, positive, shakedown, and main gates now require exact rows, ordered pairs, role labels, conditions, blocks, workflow IDs, and parseable endpoints.
19. **A main measurement failure could look complete.** Execution, evidence, design, measurement, assay, and empirical outcomes are now separate. A valid null completes; invalid design or measurement is non-evaluable.
20. **The semantic sensitivity export diverged from its protocol.** v0.8.8 includes all exact positives, ambiguous candidates, and sham artifacts; stratifies negatives; reconciles source ledgers; anchors packet contents; and requires two independent reviews, exact-reference assessment, agreement/kappa, and blinded adjudication.
21. **A paid rerun or incomplete finalizer could overwrite interpretation.** One real run is atomically claimed per release/image, the displayed rate is re-confirmed, and final status is published only after verified evidence. Recovery and transfer are scripted.
22. **Moving upstream model heads weakened replay.** The four model, tokenizer, and trusted-code commits are release-pinned and access-checked before the one-run claim.
23. **A transport retry could become outcome selection.** Only transient network/availability failures are retried; a malformed successful model response is preserved and scored once, with end-to-end latency explicitly defined.
24. **Phase summaries could contradict the enforced gates.** Compatibility and calibration now emit phase-specific gate artifacts; main decision gates exist only for the main phase.
25. **Forced recovery could package an ambiguous status or block transfer after successful cleanup.** Emergency evidence requires a terminal outcome, canonical evidence is reused when already verified, and the transfer helper continues after force only when full verification passes.
26. **The Linux test entry point omitted repository-root script modules.** The sole v0.8.7 workflow failed during collection before any image was built. v0.8.8 uses `python -m pytest` in CI and Docker, matching the validated local invocation, and a regression test locks both call sites.
27. **Concurrent or transient readers could interrupt an atomic status replacement.** The final v0.8.8 local rehearsal reproduced a Windows sharing violation at the packaging transition. Status writes now use unique temporary files, durable flushes, and bounded replacement retries; fault-injection and concurrent-write tests cover the path.
28. **A dead timeout leader could leave a live runner outside cancellation.** Recovery now authenticates the exact Python `real-gated` command inside the process group, so a leaderless but otherwise intact group is still cancelled and packaged; unrelated or multiple groups remain fail-closed.

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
