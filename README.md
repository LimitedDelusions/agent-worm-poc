# Agent Worm POC v0.8.10

This is a controlled, defensive proof of concept for a document-borne prompt-propagation question:

> Within a fixed two-stage procurement-document workflow, how does the ordered assignment of Qwen3-30B-A3B-Instruct-2507, Gemma-3-27B-IT, GPT-OSS-20B, and NVIDIA-Nemotron-3-Nano-30B-A3B to intake and relay affect the probability that a document-borne self-replicating prompt injection is reproduced across two agent-generated artifacts?

The experiment tests a complete **4 × 4 intake-to-relay transmission matrix**. It does not claim to implement malware, a live autonomous worm, real tool execution, or external propagation. All documents, identifiers, actions, and authorizations are synthetic. `external_vendor_callback` is a nonfunctional label.

## Scientific controls

- Three natural-looking carrier forms
- Three synthetic procurement documents
- Two prespecified generation seeds per carrier/document cell
- Matched neutral and hardened conditions
- Positive-control testing for all 16 ordered model pairs
- Sham metadata specificity control
- Independent model requests; response reuse is forbidden
- External deterministic scoring plus blinded semantic-mutation review
- Fail-closed exact-matrix, endpoint, absolute-utility, sensitivity, and specificity gates
- Separate design, technical/measurement, assay, and empirical outcome classifications
- Release-pinned model, tokenizer, trusted-code, container, and source revisions
- One real-run claim and verified evidence finalization/transfer

## Operational model

The runtime is built in GitHub Actions before paid GPU use. One A100 80 GB RunPod Pod loads the four models sequentially. No dependency installation occurs during the paid run.

Begin with `START_HERE.md`.
