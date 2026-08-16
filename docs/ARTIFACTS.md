# Evidence Artifacts

## Minimum files to download

- `agent-worm-results-<run-id>.zip`
- `agent-worm-results-<run-id>.zip.sha256`
- `RUN_STATUS.json`

## Evidence ZIP contents

### Provenance

- source snapshot
- `SOURCE_HASHES.sha256`
- `RELEASE_MANIFEST.json`
- every file listed by the release manifest, including tests and top-level release metadata
- Git/container metadata
- exact model and tokenizer revisions
- frozen runtime-plugin file(s) and SHA-256 hashes
- vLLM launch arguments
- GPU and Python environment records

### Experimental evidence

- case manifests
- raw stage-event JSONL
- generated Artifact 1 and Artifact 2 inside parsed events
- workflow records
- workflow scores
- failures and server logs
- model-load manifest

### Analysis

- `transition_matrix.csv`
- `assignment_summary.csv`
- `carrier_variant_summary.csv`
- `matched_policy_pairs.csv`
- `prespecified_inference.json`
- `decision_gates.json`
- `NEXT_MEETING_SUMMARY.md`

### Semantic review

- blinded review packet
- separate review key
- reviewer instructions

## Verification

After downloading:

```powershell
Get-FileHash .\agent-worm-results-<run-id>.zip -Algorithm SHA256
Get-Content .\agent-worm-results-<run-id>.zip.sha256
```

The hashes must match. Open the ZIP and confirm `PACKAGE_MANIFEST.json` exists before terminating the Pod.
