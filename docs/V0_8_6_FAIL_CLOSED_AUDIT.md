# v0.8.6 fail-closed audit and v0.8.7 correction

## Why v0.8.6 was not sent back to paid compute

After the v0.8.6 image was built, a complete high-level rehearsal found release-design and operator-recovery paths that the deterministic fake run did not invalidate. No v0.8.6 paid run was started.

The main defect was an absolute-utility gap. The shakedown compared neutral and hardened clean-task utility, but equal failure under both policies could satisfy the difference threshold. Main analysis also lacked an absolute clean-task utility stop. In addition, shakedown and main analysis did not independently reject every incomplete matrix/block shape, and a main measurement failure could still be recorded as execution-complete.

The prespecified semantic sensitivity review also diverged from its written protocol. It sampled exact positives, omitted sham outputs, did not stratify negative sampling, and lacked fail-closed two-reviewer agreement/adjudication accounting.

Operational rehearsal found separate evidence-preservation risks: a second launch was possible after the first process exited, cancellation could outpace model cleanup, a packaging failure could leave an execution-complete status without verified evidence, status lacked useful progress, and the evidence-transfer procedure required error-prone manual commands.

## v0.8.7 corrections

v0.8.7 makes these release-level changes:

- requires exact compatibility, positive-control, shakedown, and main matrix topology before interpreting outcomes;
- applies the existing 0.90 benign-utility threshold globally and to every policy/model/role clean-task cell;
- separates design validity, technical/measurement validity, assay sensitivity, and empirical outcome in gate and run status;
- treats a complete valid null placement result as a completed empirical result rather than a software failure;
- includes every exact positive, every ambiguous candidate, every sham artifact, and deterministic policy-by-carrier negative samples in the blinded semantic review;
- requires complete review inputs, two independent four-class reviews, exact-reference assessment, agreement/kappa, and adjudication records;
- release-pins model, tokenizer, and trusted-code commits instead of resolving moving repository heads at paid-run time;
- records successful and terminal transport attempts without reusing responses;
- retries only transient transport/availability failures; malformed HTTP-200 model output is preserved and scored once, and latency is explicitly end-to-end across any retry/backoff;
- atomically claims one real run per release/image, verifies Hugging Face access, GPU, storage, source, image declaration, rate, and budget before launch, and requires the operator to retype the displayed hourly rate;
- publishes a final run status only after the evidence ZIP and sidecars verify, and provides guarded cancellation, orphan cleanup, emergency packaging, live progress, and one-command evidence staging/transfer;
- adds a standalone local verifier for ZIP checksum, metadata, CRC, package-manifest membership and hashes, source-snapshot integrity, version, and standalone/packaged status parity.
- emits phase-appropriate compatibility/calibration gate files instead of contradictory main-analysis gates, and requires every recovered bundle to carry a terminal outcome classification;
- treats the registry digest as an operator-declared value unless RunPod exposes a digest-form provider field, while independently binding the baked runtime to release and Git revision and requiring a recorded console/template match.

## Preserved scientific surfaces

The v0.8.7 changes do not alter prompt text, carrier text or construction, deterministic carrier scoring, source documents, ordered-pair case construction, randomization seeds, generation temperature, top-p, output-token limits, vLLM serving controls, or the artifact-only intake-to-relay boundary. Gate enforcement and semantic-review sampling are intentionally changed and versioned. The four model repositories are unchanged; their exact commits are now release-pinned to the commits observed and preserved in the prior paid pilot evidence.

## Interpretation rule

A v0.8.7 stop must be reported by its recorded class. `design_invalid` or `technical_invalid` is not evidence about the research question. A valid positive-control or shakedown empirical failure is an assay result, not an infrastructure failure. A complete main run with a valid null remains a usable finding and must not be rerun to chase variation. Only a new documented defect may justify another versioned run.
