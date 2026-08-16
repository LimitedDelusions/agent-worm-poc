# GitHub Validation and Image Build

## Goal

Prove the source, tests, fake experiment, and container build before paid GPU use.

## Steps

1. Push the clean v0.8.3 source and tag to GitHub.
2. Open **Actions**.
3. Select **Validate and Build Agent Worm POC**.
4. Select **Run workflow**.
5. Wait for `validate` to pass.
6. Inspect the validation artifact if any step fails.
7. Wait for `build` to pass.
8. Download artifact `agent-worm-poc-container-reference`.
9. Open `RUNPOD_IMAGE.txt` and save the exact digest reference.
10. Make the GHCR package public or configure RunPod credentials.

## Do not proceed when

- tests fail;
- release audit fails;
- fake gated run aborts;
- Docker build fails;
- only a mutable tag exists;
- the digest reference is missing.

Fix the free build before renting a GPU.
