# Gate 1 — Build and Validate the Container on GitHub

## Goal

Produce a **tested, prebuilt container image** before any paid RunPod GPU is started. This gate prevents a repeat of the failed paid-time installation attempt.

The gate is complete only when GitHub reports both jobs as green and provides an exact image reference ending in `@sha256:<64 hexadecimal characters>`.

## What you need

- A GitHub account.
- The extracted `agent_worm_poc_v0.6.0` release folder.
- No Hugging Face token, RunPod token, or password inside the project files.

The supported beginner path uses a **public GitHub repository and public GHCR package** so RunPod can pull the container without another registry credential. The project contains only synthetic test material; it does not contain your Hugging Face token. Do not upload any secret manually.

## Steps

### 1. Extract the release

1. Download the final release ZIP.
2. Right-click it in Windows and select **Extract All**.
3. Open the extracted `agent_worm_poc_v0.6.0` folder.
4. Confirm that these items are visible at its top level:

```text
.github
configs
Dockerfile
scripts
src
tests
START_HERE.md
```

Do not upload the outer ZIP itself as the repository contents.

### 2. Create a GitHub repository

1. Sign in at GitHub.
2. Select the **+** menu in the upper-right.
3. Select **New repository**.
4. Use:

```text
Repository name: agent-worm-poc
Visibility: Public
```

5. Do **not** add a README, `.gitignore`, or license because the release already contains them.
6. Select **Create repository**.

### 3. Upload the project contents

1. In the empty repository, select **uploading an existing file**. If the repository page is not empty, use **Add file → Upload files**.
2. Open the extracted project folder in Windows Explorer.
3. Select **all files and folders inside** `agent_worm_poc_v0.6.0`.
4. Drag them into the GitHub upload area.
5. Wait until the upload list finishes populating.
6. Confirm that the upload includes the `.github` folder.
7. Use commit message:

```text
Add audited Agent Worm POC v0.6.0
```

8. Select **Commit directly to the main branch**.
9. Select **Commit changes**.

GitHub's official project-upload flow supports dragging files and folders into the browser. This release is below the browser upload limits.

### 4. Verify the repository structure

On the repository's main page, confirm that you can open all of these paths:

```text
.github/workflows/validate-and-build.yml
Dockerfile
scripts/release/release_audit.py
scripts/runpod/start_gated_run.sh
src/agent_worm_poc/engine.py
tests/test_release_safety.py
```

**Stop here if `.github/workflows/validate-and-build.yml` is missing.** The container will not be built automatically.

### 5. Watch the GitHub Actions run

1. Select the repository's **Actions** tab.
2. Select **Validate and Build Agent Worm POC Container**.
3. Open the newest run.
4. Wait for both jobs:

```text
validate
build
```

The `validate` job compiles the code, runs tests, checks shell/JSON/YAML, audits the release, and runs all 24 simulated placements. The `build` job creates and publishes the prebuilt container.

The first build can take time because the pinned vLLM base image is large. This uses GitHub compute, not your RunPod GPU credits.

### 6. Apply the pass/fail rule

Proceed only when:

- `validate` is green;
- `build` is green;
- the workflow run has an artifact named `agent-worm-poc-container-reference`.

If either job is red:

1. Open the first failed step.
2. save the visible error text;
3. do not rent a GPU;
4. fix and rebuild the release before proceeding.

Do not work around a failed GitHub build by installing packages on RunPod.

### 7. Download the exact image reference

1. On the completed workflow run page, scroll to **Artifacts**.
2. Download:

```text
agent-worm-poc-container-reference
```

3. Extract the downloaded artifact.
4. Open `RUNPOD_IMAGE.txt`.
5. Confirm it contains exactly one line similar to:

```text
ghcr.io/YOUR-USERNAME/agent-worm-poc@sha256:012345...<64 hex characters>
```

6. Save that entire line. Do not shorten it to a tag such as `:0.6.0`.

### 8. Make the container package public

GitHub Container Registry packages are initially private in many configurations. RunPod needs anonymous pull access for this beginner setup.

1. Open your GitHub profile.
2. Open **Packages**.
3. Select the package associated with `agent-worm-poc`.
4. Select **Package settings**.
5. Scroll to **Danger Zone**.
6. Select **Change visibility**.
7. Select **Public** and confirm the package name.

GitHub warns that making a container package public cannot be reversed. Public GHCR packages can be pulled anonymously. The source repository and package contain no tokens.

## Pass criteria

All must be true:

- Both GitHub jobs are green.
- `RUNPOD_IMAGE.txt` exists.
- The image reference starts with `ghcr.io/` and ends in `@sha256:` plus 64 hex characters.
- The GHCR package is public.
- No token or password was committed.

## Stop criteria

Do not create a RunPod Pod when:

- the workflow is red or cancelled;
- the `.github` workflow is absent;
- only a mutable image tag is available;
- the package is private and no GHCR authentication is configured;
- GitHub reports secret scanning or push protection warnings.

## Artifacts produced

Keep these files:

| Artifact | Purpose |
|---|---|
| `RUNPOD_IMAGE.txt` | Exact immutable container digest used in the RunPod template |
| `IMAGE_BUILD.json` | Source commit, version, and image reference |
| `agent-worm-poc-validation` workflow artifact | Free validation evidence from GitHub |
| Green GitHub workflow run | Hard proof that the container was built from the validated release |

## Official setup references

- GitHub project upload: https://docs.github.com/en/get-started/start-your-journey/uploading-a-project-to-github
- GitHub workflow artifacts: https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts
- GitHub package visibility: https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility
