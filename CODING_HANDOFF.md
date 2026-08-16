# Coding Handoff — v0.8.2

## Objective

Publish one immutable, tested container before another paid RunPod session. Do not change prompts, carriers, scoring, gates, sample construction, or model configuration without incrementing the version and regenerating the release manifest.

## 1. Verify and extract

PowerShell:

```powershell
Get-FileHash .\agent_worm_poc_v0.8.2.zip -Algorithm SHA256
Get-Content .\agent_worm_poc_v0.8.2.zip.sha256
Expand-Archive .\agent_worm_poc_v0.8.2.zip .\agent-worm-poc-v082
Set-Location .\agent-worm-poc-v082\agent_worm_poc_v0.8.2
```

The two hashes must match.

## 2. Replace the repository cleanly

Do not extract over an older source tree. Preserve only `.git`, then copy v0.8.2 into the repository root.

## 3. Run free validation

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]" PyYAML==6.0.2
python -m compileall -q src scripts tests
pytest -q
python scripts\release\generate_integrity.py --check
python scripts\validate_release.py
Remove-Item outputs\local-fake -Recurse -Force -ErrorAction SilentlyContinue
python scripts\run_gated.py fake-gated --root . --output-root outputs\local-fake
```

Expected results:

- all tests pass;
- release audit returns `"passed": true`;
- fake gated run ends with `"status": "completed"`;
- compatibility, positive-control, and shakedown gates all pass;
- fake main phase contains 672 workflows and 1,344 stage events;
- a valid evidence ZIP and checksum are created.

## 4. Commit and push

```powershell
git add -A
git commit -m "Agent worm POC v0.8.2 RunPod launch and provenance hardening"
git tag v0.8.2
git push origin HEAD
git push origin v0.8.2
```

## 5. Build the container

1. Start exactly one run against the immutable tag:
   ```powershell
   gh workflow run validate-and-build.yml --ref v0.8.2
   ```
2. Open GitHub → **Actions** and select **Validate and Build Agent Worm POC**.
3. Select the run for `v0.8.2`; do not dispatch a duplicate while it is active.
4. Confirm `validate` is green.
5. Confirm `build` is green.
6. Download artifact `agent-worm-poc-container-reference`.
7. Record the exact `ghcr.io/...@sha256:...` value from `RUNPOD_IMAGE.txt`.
8. Make the GHCR package public, or configure RunPod registry credentials.

## 6. Return these handoff artifacts

- commit SHA;
- workflow URL;
- immutable image digest;
- local fake-run evidence ZIP checksum;
- any warnings from Docker build logs.

No GPU should be rented until this handoff is complete.
