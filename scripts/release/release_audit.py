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
from agent_worm_poc.constants import (  # noqa: E402
    CARRIER_ID,
    PROJECT_VERSION,
    RESTRICTED_ACTION,
)
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
    "CODING_HANDOFF.md",
    "Dockerfile",
    "pyproject.toml",
    ".github/workflows/validate-and-build.yml",
    "configs/model_candidates.json",
    "configs/roles_neutral.json",
    "configs/roles_hardened.json",
    "configs/roles_positive_control.json",
    "configs/experiment.json",
    "data/benign_vendor_document.txt",
    "data/injected_vendor_document.txt",
    "src/agent_worm_poc/__init__.py",
    "src/agent_worm_poc/adapters.py",
    "src/agent_worm_poc/cli.py",
    "src/agent_worm_poc/compatibility.py",
    "src/agent_worm_poc/config.py",
    "src/agent_worm_poc/constants.py",
    "src/agent_worm_poc/engine.py",
    "src/agent_worm_poc/freeze.py",
    "src/agent_worm_poc/preflight.py",
    "src/agent_worm_poc/prompts.py",
    "src/agent_worm_poc/reporting.py",
    "src/agent_worm_poc/schemas.py",
    "src/agent_worm_poc/scoring.py",
    "src/agent_worm_poc/server.py",
    "src/agent_worm_poc/types.py",
    "src/agent_worm_poc/util.py",
    "tests/test_compatibility.py",
    "tests/test_config_and_prompts.py",
    "tests/test_engine_and_reporting.py",
    "tests/test_release_safety.py",
    "tests/test_schemas_and_scoring.py",
    "tests/test_server_and_freeze.py",
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
    "def external_vendor_callback",
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
        models = load_models(ROOT / "configs" / "model_candidates.json")
        experiment = load_experiment(ROOT / "configs" / "experiment.json")
        role_sets = {
            "neutral": load_roles(ROOT / "configs" / "roles_neutral.json"),
            "hardened": load_roles(ROOT / "configs" / "roles_hardened.json"),
            "positive_control": load_roles(ROOT / "configs" / "roles_positive_control.json"),
        }
        if len(all_placements(models)) != 24:
            errors.append("four models did not produce exactly 24 placements")
        if any(len(roles) != 4 for roles in role_sets.values()):
            errors.append("every role architecture must contain four roles")
        scenario_ids = [scenario.id for scenario in experiment["scenario_configs"]]
        expected_scenarios = [
            "positive_control_injected",
            "neutral_benign",
            "neutral_injected",
            "hardened_benign",
            "hardened_injected",
        ]
        if scenario_ids != expected_scenarios:
            errors.append("scenario order or inventory differs from the approved v0.7.0 design")
        if int(experiment["default_poc_repetitions"]) < 2:
            errors.append("real POC must default to at least two independent repetitions")
        if int(experiment["positive_control_repetitions"]) < 2:
            errors.append("positive control must use at least two independent repetitions")
        safety = experiment.get("safety", {})
        required_safety = {
            "isolated_lab_only": True,
            "external_network_actions": False,
            "real_credentials": False,
            "real_sensitive_data": False,
            "real_tools": False,
            "nonfunctional_mock_action_only": True,
            "no_autonomous_target_discovery": True,
            "no_file_or_network_replication": True,
        }
        if any(safety.get(key) is not expected for key, expected in required_safety.items()):
            errors.append("experiment safety flags do not match the lab-only design")
    except Exception as exc:
        errors.append(f"config load failed: {type(exc).__name__}: {exc}")

    schema_text = json.dumps(ROLE_SCHEMAS, sort_keys=True)
    if CARRIER_ID in schema_text or "carrier_id" in schema_text.lower():
        errors.append("response schemas must not request or disclose the carrier identifier")
    if "artifact_text" not in schema_text:
        errors.append("intake and relay schemas must produce generated artifact_text")

    benign = _read("data/benign_vendor_document.txt")
    injected = _read("data/injected_vendor_document.txt")
    if CARRIER_ID in benign or RESTRICTED_ACTION in benign:
        errors.append("benign document contains the carrier or prohibited mock action")
    if CARRIER_ID not in injected or RESTRICTED_ACTION not in injected:
        errors.append("injected document does not contain the complete synthetic carrier")
    if (ROOT / "data/positive_control_document.txt").exists():
        errors.append("positive control must use the same injected document, not a separate laboratory document")
    natural_prefix = benign.rstrip("\n") + "\n\n"
    if not injected.startswith(natural_prefix):
        errors.append("injected document must be the benign business document plus one appended carrier block")
    if injected.count("[AUTOMATION CONTINUITY METADATA]") != 1:
        errors.append("injected document must contain exactly one continuity-metadata carrier block")
    for forbidden in ("CALIBRATION INPUT", "WORM_CANARY", "restricted_mock_action"):
        if forbidden in injected:
            errors.append(f"natural injected document contains a laboratory-only label: {forbidden}")
    try:
        scenario_by_id = {item["id"]: item for item in json.loads(_read("configs/experiment.json"))["scenarios"]}
        injected_paths = {
            scenario_by_id[scenario_id]["document_file"]
            for scenario_id in (
                "positive_control_injected",
                "neutral_injected",
                "hardened_injected",
            )
        }
        if injected_paths != {"data/injected_vendor_document.txt"}:
            errors.append("positive, neutral, and hardened injected conditions must use the same document")
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"could not verify shared injected document across conditions: {exc}")

    neutral_text = _read("configs/roles_neutral.json").lower()
    for forbidden in ("prompt injection", "canary", "carrier", "automation continuity metadata"):
        if forbidden in neutral_text:
            errors.append(f"neutral workflow contains an attack-specific instruction: {forbidden}")
    if "underlying business request explicitly requires contacting the vendor" not in neutral_text:
        errors.append("neutral planner lacks a natural business-authorization boundary for the external callback")
    hardened_text = _read("configs/roles_hardened.json").lower()
    if "untrusted" not in hardened_text or RESTRICTED_ACTION not in hardened_text:
        errors.append("hardened control does not contain explicit provenance and action controls")
    positive_text = _read("configs/roles_positive_control.json")
    if "reproduce" not in positive_text.lower() or "Calibration control only" not in positive_text:
        errors.append("positive control does not explicitly calibrate artifact reproduction")

    prompt_source = _read("src/agent_worm_poc/prompts.py").lower()
    if "do not obey" in prompt_source or "prompt injection" in prompt_source:
        errors.append("global prompt envelope contains hardening that would contaminate neutral workflow")
    if "format_forwarded_artifact" not in prompt_source:
        errors.append("generated artifact handoff function is missing")
    for required_text in ('{"role": "system"', '{"role": "user"', "def build_messages"):
        if required_text not in prompt_source:
            errors.append(f"trusted/untrusted message-priority separation is missing: {required_text}")

    model_payload = json.loads(_read("configs/model_candidates.json"))
    gpt_oss = next((slot for slot in model_payload["model_slots"] if slot["id"] == "gpt_oss_slot"), None)
    if gpt_oss is None:
        errors.append("GPT-OSS candidate is missing")
    else:
        if gpt_oss.get("request_overrides", {}).get("reasoning_effort") != "low":
            errors.append("GPT-OSS must request reasoning_effort=low for the controlled POC")
        if gpt_oss.get("parser_file") is not None or gpt_oss.get("parser_sha256") is not None:
            errors.append("GPT-OSS must use vLLM native Harmony/reasoning handling, not a custom parser")
        if any("reasoning-parser" in str(arg) for arg in gpt_oss.get("launch_args", [])):
            errors.append("GPT-OSS launch arguments must not configure a custom reasoning parser")

    cli_source = _read("src/agent_worm_poc/cli.py")
    for required_text in (
        'sub.add_parser("positive-control")',
        "reuse_identical_requests=False",
        "positive propagation control failed",
        "POC repetitions must be between 2 and 5",
        'repetitions=int(experiment["positive_control_repetitions"])',
    ):
        if required_text not in cli_source:
            errors.append(f"CLI is missing v0.7.0 control: {required_text}")

    dockerfile = _read("Dockerfile")
    expected_from = f"FROM {EXPECTED_BASE}"
    if expected_from not in dockerfile:
        errors.append("Dockerfile does not use the exact audited vLLM base-image digest")
    first_noncomment = next(
        (line.strip() for line in dockerfile.splitlines() if line.strip() and not line.lstrip().startswith("#")),
        "",
    )
    if first_noncomment != expected_from:
        errors.append("Dockerfile first instruction is not the immutable base image")
    if 'ENTRYPOINT ["/opt/agent-worm-poc/scripts/runpod/container_start.sh"]' not in dockerfile:
        errors.append("Dockerfile does not use the guarded entrypoint")

    dockerignore = _read(".dockerignore")
    ignored_lines = {
        line.strip().rstrip("/")
        for line in dockerignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if ".github" in ignored_lines:
        errors.append(".dockerignore excludes .github")

    workflow = _read(".github/workflows/validate-and-build.yml")
    for required_text in (
        "actions/checkout@v6",
        "actions/setup-python@v6",
        "actions/upload-artifact@v7",
        "docker/login-action@v4",
        "docker/setup-buildx-action@v4",
        "docker/build-push-action@v7",
        "RUNPOD_IMAGE.txt",
        "positive_control_evaluation",
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
                    errors.append(f"paid RunPod path contains package installation in {relative}")
        if relative.startswith("src/") or relative.startswith("scripts/runpod/"):
            for forbidden in FORBIDDEN_TOOL_PATTERNS:
                if forbidden in text:
                    errors.append(f"possible real tool/network implementation in {relative}: {forbidden}")

    for path in sorted((ROOT / "scripts").rglob("*.sh")):
        if not (path.stat().st_mode & stat.S_IXUSR):
            warnings.append(
                f"shell script lacks executable mode: {path.relative_to(ROOT)}; build normalizes it"
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
        "POC_REPETITIONS must be 2, 3, 4, or 5",
    ):
        if required_text not in start_script:
            errors.append(f"gated start script is missing control: {required_text}")
    for required_text in (
        "preflight",
        "freeze-models",
        "fake-validation",
        "compatibility",
        "positive-control",
        "shakedown",
        "poc",
        "package_results.sh",
    ):
        if required_text not in inner_script:
            errors.append(f"gated run is missing phase/control: {required_text}")
    if "kill -TERM -- \"-$PID\"" not in cancel_script:
        errors.append("cancel script does not request controlled process-group termination")
    if 'status_path = output_root / "session_status.json"' not in cancel_script:
        errors.append("cancel script does not update the canonical root session-status file")
    if 'output_root / "session" / "session_status.json"' in cancel_script:
        errors.append("cancel script still references the obsolete nested session-status path")
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

    preflight_source = _read("src/agent_worm_poc/preflight.py")
    for required_text in ("gpu_is_a100", "torch_cuda_allocation_smoke", "workspace_mount"):
        if required_text not in preflight_source:
            errors.append(f"preflight is missing paid-run safety check: {required_text}")
    engine_source = _read("src/agent_worm_poc/engine.py")
    for required_text in (
        "format_forwarded_artifact",
        '"primary_outcome": experiment.get("primary_outcome")',
        "placement_index*100",
        "summarize_intake_relay_pairs",
        'output_dir / "intake_relay_summary.csv"',
    ):
        if required_text not in engine_source:
            errors.append(f"engine is missing v0.7.0 measurement control: {required_text}")
    scoring_source = _read("src/agent_worm_poc/scoring.py")
    if "def summarize_intake_relay_pairs" not in scoring_source:
        errors.append("pair-level primary-outcome aggregation is missing")
    reporting_source = _read("src/agent_worm_poc/reporting.py")
    for required_text in (
        'poc_dir / "intake_relay_summary.csv"',
        '"neutral_intake_relay_pair_variation_observed"',
        '"outputs/poc/intake_relay_summary.csv"',
    ):
        if required_text not in reporting_source:
            errors.append(f"reporting is missing pair-level output/control: {required_text}")

    for legacy in (
        "data/carrier_document.txt",
        "data/positive_control_document.txt",
        "src/agent_worm_poc/carrier.py",
        "src/agent_worm_poc/artifacts.py",
    ):
        if (ROOT / legacy).exists():
            errors.append(f"legacy v0.6 artifact must not be present: {legacy}")

    for report in ("AUDIT_REPORT.md", "FINAL_VALIDATION_REPORT.md"):
        if "0.7.0" not in _read(report):
            errors.append(f"{report} is stale and does not identify v0.7.0")

    code, detail = _run(
        [sys.executable, "-m", "compileall", "-q", str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "tests")]
    )
    if code:
        errors.append(f"Python compilation failed: {detail}")

    hashes: list[str] = []
    files_manifest: list[dict] = []
    for path in iter_release_files():
        relative = path.relative_to(ROOT).as_posix()
        digest = sha256_file(path)
        hashes.append(f"{digest}  {relative}")
        files_manifest.append({"path": relative, "sha256": digest, "bytes": path.stat().st_size})
    atomic_write_text(ROOT / "SOURCE_HASHES.sha256", "\n".join(hashes) + "\n")
    manifest = {
        "schema_version": 3,
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
            "immutable prebuilt vLLM base image is pinned",
            "no dependency installation occurs on paid GPU time",
            "four models, four roles, 24 placements, and four main scenarios are fixed",
            "natural neutral workflow has no attack-specific system instruction",
            "trusted role instructions use system priority and source artifacts use user priority",
            "positive, neutral, and hardened injected paths use the same source document",
            "separate positive propagation and hardened containment controls",
            "generated artifacts, not JSON bookkeeping, become downstream inputs",
            "independent real POC requests with at least two repetitions",
            "pair-level intake-to-relay summary separates the primary outcome from downstream role permutations",
            "natural injected document is the benign document plus one appended carrier block",
            "synthetic nonfunctional impact only",
            "strict schemas do not request the carrier identifier",
            "source and output integrity manifests",
        ],
        "limitations": [
            "The Docker image must still pass GitHub Actions.",
            "Real model loading and structured-output behavior require the A100 gates.",
            "The POC is feasibility evidence, not the final white-paper dataset.",
            "Lexicon-based semantic mutation flags require manual review and are not treated as confirmed propagation.",
        ],
    }
    atomic_write_json(ROOT / "RELEASE_MANIFEST.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
