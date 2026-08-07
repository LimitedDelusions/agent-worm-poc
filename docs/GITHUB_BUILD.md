# GitHub Validation and Image Build

## Goal

Produce a prevalidated, immutable GHCR image without RunPod GPU charges so the paid RunPod session performs no dependency installation.

## Steps

1. Extract v0.7.0 to a clean directory.
2. Replace the old repository contents; keep only `.git` from the old checkout.
3. Copy hidden files and folders, especially `.github`.
4. Follow `CODING_HANDOFF.md` and run all local validation.
5. Commit and push to `main`. GitHub-hosted Actions can consume account minutes, artifact storage, and package storage depending on the repository/account plan; confirm your quota before running the large image build.
6. In GitHub, open **Actions**.
7. Open **Validate and Build Agent Worm POC Container**.
8. Run the workflow manually if the push did not start it.
9. Wait for both `validate` and `build` jobs.
10. Download `agent-worm-poc-validation` and `agent-worm-poc-container-reference`.
11. Open `RUNPOD_IMAGE.txt` and save the entire `ghcr.io/...@sha256:...` line.
12. Open the repository owner’s **Packages** page and select the newly created container package.
13. For the simplest RunPod setup, open **Package settings → Change visibility → Public** and confirm. The source repository may remain private.
14. If the package must remain private, create a separate read-only GitHub classic PAT with `read:packages` and configure it only in RunPod’s private-registry credentials. Do not put that token in this repository, ZIP, Docker image, or Jupyter command history.

## Pass criteria

- `validate` is green;
- all tests pass;
- release audit passes;
- simulated positive control passes;
- simulated main POC completes 24 placements × 4 scenarios with no invalid stages;
- `build` is green;
- `RUNPOD_IMAGE.txt` contains an immutable digest;
- the package is public, or private-registry credentials have been configured and tested.

## Stop criteria

Do not rent a Pod when:

- either GitHub job failed;
- the validation artifacts are absent;
- the image reference is only `:latest`, `:0.7.0`, or another tag;
- the source commit is not the intended v0.7.0 commit;
- the package cannot be pulled by RunPod without exposing a credential.

## Artifacts produced

- `agent-worm-poc-validation` workflow artifact;
- `RELEASE_MANIFEST.json`;
- `SOURCE_HASHES.sha256`;
- simulated validation output;
- `agent-worm-poc-container-reference`;
- `RUNPOD_IMAGE.txt`;
- `IMAGE_BUILD.json`;
- GitHub Actions run URL and source commit SHA;
- GHCR package visibility/authentication decision.
