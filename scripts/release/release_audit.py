from __future__ import annotations

import json
import re
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from agent_worm_poc import __version__  # noqa: E402
from agent_worm_poc.config import load_experiment, load_models, load_roles  # noqa: E402
from agent_worm_poc.constants import CANARY, PROJECT_VERSION, RESTRICTED_ACTION  # noqa: E402
from agent_worm_poc.engine import all_placements  # noqa: E402
from agent_worm_poc.schemas import ROLE_SCHEMAS  # noqa: E402
from agent_worm_poc.util import atomic_write_json, atomic_write_text, sha256_file, utc_now  # noqa: E402

EXPECTED_BASE = (
    "vllm/vllm-openai:v0.25.1-cu129@"
    "sha256:483a446d6b06a3757e4c7f5ca707e32443f49202bd382380dd969f90792e6a8d"
)

REQUIRED = [
    "README.md",
    "START_HERE.md",
    "DEPLOYMENT_CHECKLIST.md",
    "AUDIT_REPORT.md",
    "FINAL_VALIDATION_REPORT.md",
    "Dockerfile",
    "pyproject.toml",
    ".github/workflows/validate-and-build.yml",
    "configs/model_candidates.json",
    "configs/roles.json",
    "configs/experiment.json",
    "data/benign_document.txt",
    "data/injection_direct.txt",
    "data/injection_authority.txt",
    "data/injection_artifact.txt",
    "src/agent_worm_poc/cli.py",
    "src/agent_worm_poc/preflight.py",
    "src/agent_worm_poc/reporting.py",
    "scripts/runpod/container_start.sh",
    "scripts/runpod/start_gated_run.sh",
    "scripts/runpod/gated_run_inner.sh",
    "scripts/runpod/status.sh",
    "scripts/runpod/cancel_run.sh",
    "scripts/runpod/package_results.sh",
    "docs/RUNBOOK.md",
    "docs/END_GOALS.md",
    "docs/GITHUB_BUILD.md",
    "docs/RUNPOD_SETUP.md",
    "docs/RUN_AND_MONITOR.md",
    "docs/ARTIFACTS.md",
    "docs/RECOVERY.md",
    "docs/EXPERIMENT_DESIGN.md",
    "docs/MODEL_CONFIG.md",
    "docs/COST_CONTROL.md",
    "docs/SECURITY_AND_SAFETY.md",
]

SECRET_PATTERNS = [
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(
        r"(?i)(runpod_api_key|github_token|jupyter_password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"
    ),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
]

RUNTIME_INSTALL_PATTERNS = [
    re.compile(r"\bpip(?:3)?\s+install\b"),
    re.compile(r"\buv\s+pip\s+install\b"),
    re.compile(r"\bapt(?:-get)?\s+(?:update|install)\b"),
    re.compile(r"\bconda\s+install\b"),
]

FORBIDDEN_TOOL_PATTERNS = [
    "def restricted_mock_action",
    "smtplib",
    "paramiko",
    "boto3.client",
    "requests.post(\"http",
    "subprocess.run([\"curl\"",
]


def iter_release_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(
            part in {".git", "__pycache__", ".pytest_cache", "outputs", "dist", ".venv"}
            for part in relative.parts
        ):
            continue
        if relative.name in {"RELEASE_MANIFEST.json", "SOURCE_HASHES.sha256", ".coverage"}:
            continue
        if relative.suffix in {".zip", ".pyc"}:
            continue
        yield path


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")

    if __version__ != PROJECT_VERSION:
        errors.append("package version and PROJECT_VERSION constant differ")
    project = _read("pyproject.toml")
    if f'version = "{__version__}"' not in project:
        errors.append("pyproject version does not match package version")

    try:
        roles = load_roles(ROOT / "configs" / "roles.json")
        models = load_models(ROOT / "configs" / "model_candidates.json")
        experiment = load_experiment(ROOT / "configs" / "experiment.json")
        if len(all_placements(models)) != 24:
            errors.append("four models did not produce exactly 24 placements")
        if len(roles) != 4:
            errors.append("role count is not four")
        condition_ids = [item["id"] for item in experiment["conditions"]]
        if condition_ids != [
            "benign",
            "injection_direct",
            "injection_authority",
            "injection_artifact",
        ]:
            errors.append("condition order or inventory differs from the approved POC design")
        safety = experiment.get("safety", {})
        required_safety = {
            "isolated_lab_only": True,
            "external_network_actions": False,
            "real_credentials": False,
            "real_sensitive_data": False,
            "real_tools": False,
            "nonfunctional_mock_action_only": True,
        }
        if any(safety.get(key) is not expected for key, expected in required_safety.items()):
            errors.append("experiment safety flags do not match the lab-only design")
    except Exception as exc:
        errors.append(f"config load failed: {type(exc).__name__}: {exc}")

    schema_text = json.dumps(ROLE_SCHEMAS, sort_keys=True)
    if CANARY in schema_text or "canary" in schema_text.lower():
        errors.append("response schemas must not request a canary field")

    benign = _read("data/benign_document.txt")
    if CANARY in benign or RESTRICTED_ACTION in benign:
        errors.append("benign document contains a worm marker or restricted mock action")
    for relative in (
        "data/injection_direct.txt",
        "data/injection_authority.txt",
        "data/injection_artifact.txt",
    ):
        text = _read(relative)
        if CANARY not in text or RESTRICTED_ACTION not in text:
            errors.append(f"synthetic injected condition is incomplete: {relative}")

    dockerfile = _read("Dockerfile")
    expected_from = f"FROM {EXPECTED_BASE}"
    if expected_from not in dockerfile:
        errors.append("Dockerfile does not use the exact audited vLLM base-image digest")
    first_noncomment = next(
        (line.strip() for line in dockerfile.splitlines() if line.strip() and not line.lstrip().startswith("#")),
        "",
    )
    if first_noncomment != expected_from:
        errors.append("Dockerfile first instruction is not the exact immutable base image")
    if "ENTRYPOINT [\"/opt/agent-worm-poc/scripts/runpod/container_start.sh\"]" not in dockerfile:
        errors.append("Dockerfile does not use the guarded container entrypoint")

    dockerignore = _read(".dockerignore")
    ignored_lines = {line.strip().rstrip("/") for line in dockerignore.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    if ".github" in ignored_lines:
        errors.append(".dockerignore excludes .github, which would break the in-image audit and omit the workflow from evidence")

    workflow = _read(".github/workflows/validate-and-build.yml")
    for required_text in (
        "actions/checkout@v6",
        "actions/setup-python@v6",
        "actions/upload-artifact@v7",
        "docker/build-push-action@v6",
        "RUNPOD_IMAGE.txt",
        "${{ steps.build.outputs.digest }}",
    ):
        if required_text not in workflow:
            errors.append(f"GitHub build workflow is missing: {required_text}")

    for path in iter_release_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT).as_posix()
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible committed secret in {relative}")
        if relative.startswith("scripts/runpod/"):
            for pattern in RUNTIME_INSTALL_PATTERNS:
                if pattern.search(text):
                    errors.append(
                        f"paid RunPod path contains a runtime package-install command in {relative}"
                    )
        if relative.startswith("src/") or relative.startswith("scripts/runpod/"):
            for forbidden in FORBIDDEN_TOOL_PATTERNS:
                if forbidden in text:
                    errors.append(f"possible real tool/network implementation in {relative}: {forbidden}")

    shell_paths = sorted((ROOT / "scripts").rglob("*.sh"))
    for path in shell_paths:
        if not (path.stat().st_mode & stat.S_IXUSR):
            warnings.append(
                f"shell script lacks executable mode in this filesystem: {path.relative_to(ROOT)}; "
                "GitHub Actions and the Docker build normalize it"
            )
        code, detail = _run(["bash", "-n", str(path)])
        if code:
            errors.append(f"shell syntax error in {path.relative_to(ROOT)}: {detail}")

    beginner_docs = {
        "docs/GITHUB_BUILD.md": ("## Goal", "## Steps", "## Pass criteria", "## Stop criteria", "## Artifacts produced"),
        "docs/RUNPOD_SETUP.md": ("## Goal", "## Steps", "## Pass criteria", "## Stop criteria", "## Artifacts produced"),
        "docs/RUN_AND_MONITOR.md": ("## Goal", "## Steps", "## Pass criteria", "## Stop criteria", "## Artifacts produced"),
        "docs/RUNBOOK.md": ("## End goal", "## Stage overview", "## Stage 1", "## Stage 5"),
    }
    for relative, headings in beginner_docs.items():
        if not (ROOT / relative).is_file():
            continue
        doc_text = _read(relative)
        for heading in headings:
            if heading not in doc_text:
                errors.append(f"beginner documentation {relative} is missing section: {heading}")

    start_script = _read("scripts/runpod/start_gated_run.sh")
    inner_script = _read("scripts/runpod/gated_run_inner.sh")
    cancel_script = _read("scripts/runpod/cancel_run.sh")
    container_start = _read("scripts/runpod/container_start.sh")
    for required_text in (
        "AGENT_WORM_IMAGE_REF",
        "AGENT_WORM_MAX_RUNTIME",
        "RUNPOD_HOURLY_RATE",
        "timeout --signal=TERM",
        "if ! python",
    ):
        if required_text not in start_script:
            errors.append(f"gated start script is missing control: {required_text}")
    for required_text in (
        "preflight",
        "freeze-models",
        "fake-validation",
        "compatibility",
        "shakedown",
        "poc",
        "package_results.sh",
    ):
        if required_text not in inner_script:
            errors.append(f"gated run is missing phase/control: {required_text}")
    if "kill -TERM -- \"-$PID\"" not in cancel_script:
        errors.append("cancel script does not request controlled process-group termination")
    for required_text in (
        '"phase": "forced-cancel"',
        "partial evidence was packaged",
        "package_results.sh",
    ):
        if required_text not in cancel_script:
            errors.append(f"cancel script is missing forced-cancel evidence control: {required_text}")
    for required_text in (
        "JUPYTER_PASSWORD",
        "password_required = True",
        "allow_remote_access = True",
        "trust_xheaders = True",
        "RUNPOD_SECRET",
    ):
        if required_text not in container_start:
            errors.append(f"container entrypoint is missing Jupyter/secret control: {required_text}")
    if "vllm serve" in container_start:
        errors.append("container entrypoint must not automatically start a model")

    server_source = _read("src/agent_worm_poc/server.py")
    for required_text in (
        '"JUPYTER_PASSWORD"',
        '"RUNPOD_API_KEY"',
        '"GITHUB_TOKEN"',
        'server_env.pop',
    ):
        if required_text not in server_source:
            errors.append(f"model-server subprocess credential stripping is missing: {required_text}")

    preflight = _read("src/agent_worm_poc/preflight.py")
    for required_text in ("gpu_is_a100", "torch_cuda_allocation_smoke", "workspace_mount"):
        if required_text not in preflight:
            errors.append(f"preflight is missing paid-run safety check: {required_text}")
    engine_source = _read("src/agent_worm_poc/engine.py")
    if '"research_question": experiment.get("research_question")' not in engine_source:
        errors.append("POC manifest does not record the exact research question")

    status_script = _read("scripts/runpod/status.sh")
    for required_text in ("SESSION_NAME", "latest_archive.sha256", "Checksum:"):
        if required_text not in status_script:
            errors.append(f"status script is missing current-session artifact handling: {required_text}")

    code, detail = _run([sys.executable, "-m", "compileall", "-q", str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "tests")])
    if code:
        errors.append(f"Python compilation failed: {detail}")

    hashes: list[str] = []
    files_manifest: list[dict] = []
    for path in iter_release_files():
        relative = path.relative_to(ROOT).as_posix()
        digest = sha256_file(path)
        hashes.append(f"{digest}  {relative}")
        files_manifest.append(
            {"path": relative, "sha256": digest, "bytes": path.stat().st_size}
        )
    atomic_write_text(ROOT / "SOURCE_HASHES.sha256", "\n".join(hashes) + "\n")
    manifest = {
        "schema_version": 2,
        "project": "agent-worm-poc",
        "version": __version__,
        "created_at": utc_now(),
        "base_image": EXPECTED_BASE,
        "file_count": len(files_manifest),
        "files": files_manifest,
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
        "validated_controls": [
            "complete runnable source is present",
            "one immutable prebuilt vLLM base image is pinned",
            "no dependency installation occurs on the paid RunPod path",
            "four models, four roles, four conditions, and 24 placements are fixed",
            "synthetic nonfunctional impact only",
            "password-protected proxy-aware JupyterLab with unresolved-secret rejection",
            "model subprocess credential minimization",
            "forced-cancel status and partial-evidence packaging",
            "preflight, timeout, status, cancellation, recovery, and evidence packaging controls",
            "strict output schemas without a canary field",
            "source and output integrity manifests",
        ],
        "limitations": [
            "The Docker image build cannot be executed in this audit environment and must pass GitHub Actions.",
            "Real model loading, VRAM use, chat-template behavior, and JSON-schema compliance require the A100 compatibility gate.",
            "The POC is feasibility evidence and uses one repetition by default; it is not the final white-paper dataset.",
            "Current model repositories and RunPod availability can change after this release; exact model revisions are frozen at run time.",
        ],
    }
    atomic_write_json(ROOT / "RELEASE_MANIFEST.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
