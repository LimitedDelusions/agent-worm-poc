# Evidence Artifacts

## Minimum files to download

- `agent-worm-results-<run-id>.zip`
- `agent-worm-results-<run-id>.zip.sha256`
- `agent-worm-results-<run-id>.zip.json`
- `RUN_STATUS.json`
- `SHA256SUMS`
- the complete transferred `run/` directory

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

- `01_compatibility/compatibility_gate.json`
- `02_calibration/calibration_gates.json`
- `transition_matrix.csv`
- `assignment_summary.csv`
- `carrier_variant_summary.csv`
- `matched_policy_pairs.csv`
- `prespecified_inference.json`
- `03_main/decision_gates.json`
- `NEXT_MEETING_SUMMARY.md`

### Semantic review

- blinded review packet
- immutable blinded-packet manifest
- key-free exact-reference second-pass packet
- separate review key
- dual-reviewer agreement, kappa, adjudication queue, and reviewer instructions

## Verification

On the Pod, do not assemble these files manually. After `status.sh` reports `NOT RUNNING`, run:

```bash
bash /workspace/agent_worm_poc_v0.8.7/scripts/runpod/stage_and_send_evidence.sh
```

After receiving the folder locally, run the release verifier from the v0.8.7 repository:

```powershell
$RunPodCtl = (Get-Command runpodctl -ErrorAction SilentlyContinue).Source
if (-not $RunPodCtl) {
  $RunPodCtl = (Get-ChildItem "$env:USERPROFILE\Downloads" -Filter runpodctl.exe -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
}
if (-not $RunPodCtl) { throw 'runpodctl.exe was not found; locate the executable installed for the prior transfer.' }
$ReceiveRoot = Join-Path $env:USERPROFILE ('Downloads\agent-worm-v087-' + (Get-Date -Format 'yyyyMMddTHHmmss'))
New-Item -ItemType Directory -Path $ReceiveRoot -Force | Out-Null
Push-Location $ReceiveRoot
try { & $RunPodCtl receive '<one-time-code>'; if ($LASTEXITCODE) { throw "runpodctl receive failed: $LASTEXITCODE" } }
finally { Pop-Location }
$zip = Get-ChildItem $ReceiveRoot -Recurse -Filter 'agent-worm-results-*.zip' -File | Select-Object -First 1
py -3.11 scripts\release\verify_evidence.py $zip.FullName --expected-version 0.8.7
```

The command verifies the full transfer manifest when present, ZIP/sidecar checksum and metadata, CRC, exact package membership and every packaged hash, source snapshot, release version, and byte equality between standalone and packaged `RUN_STATUS.json`.

For a quick independent checksum display:

```powershell
Get-FileHash .\agent-worm-results-<run-id>.zip -Algorithm SHA256
Get-Content .\agent-worm-results-<run-id>.zip.sha256
```

The hashes must match. Do not terminate the Pod until the full verifier passes.
