from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .constants import PROJECT_VERSION
from .util import atomic_write_json, sha256_file, utc_now


class PreflightError(RuntimeError):
    pass


IMAGE_REF_RE = re.compile(r"^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_BASE_IMAGE = (
    "vllm/vllm-openai:v0.25.1-cu129@"
    "sha256:483a446d6b06a3757e4c7f5ca707e32443f49202bd382380dd969f90792e6a8d"
)


def _run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return (result.stdout or result.stderr).strip()


def _verify_source_hashes(project_root: Path) -> tuple[bool, dict[str, Any]]:
    checksum_path = project_root / "SOURCE_HASHES.sha256"
    manifest_path = project_root / "RELEASE_MANIFEST.json"
    if not checksum_path.is_file():
        return False, {"error": f"missing {checksum_path}"}
    checked = 0
    mismatches: list[dict[str, str]] = []
    missing: list[str] = []
    malformed: list[str] = []
    listed_paths: list[str] = []
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            malformed.append(line)
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or not relative:
            malformed.append(line)
            continue
        listed_paths.append(relative)
        path = project_root / relative
        try:
            path.resolve().relative_to(project_root.resolve())
        except ValueError:
            malformed.append(line)
            continue
        if not path.is_file():
            missing.append(relative)
            continue
        actual = sha256_file(path)
        checked += 1
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})

    release_manifest_ok = False
    release_manifest_detail: Any = "missing"
    if manifest_path.is_file():
        try:
            release_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected_paths = sorted(row["path"] for row in release_manifest.get("files", []))
            release_manifest_ok = (
                release_manifest.get("passed") is True
                and release_manifest.get("version") == PROJECT_VERSION
                and expected_paths == sorted(listed_paths)
            )
            release_manifest_detail = {
                "passed": release_manifest.get("passed"),
                "version": release_manifest.get("version"),
                "listed_file_count": len(expected_paths),
                "matches_checksum_file": expected_paths == sorted(listed_paths),
            }
        except Exception as exc:
            release_manifest_detail = f"invalid: {type(exc).__name__}: {exc}"

    ok = not (mismatches or missing or malformed) and checked > 0 and release_manifest_ok
    return ok, {
        "checksum_file": str(checksum_path),
        "files_checked": checked,
        "missing": missing,
        "mismatches": mismatches,
        "malformed_lines": malformed,
        "release_manifest": release_manifest_detail,
    }


def run_preflight(*, output_dir: Path, allow_no_gpu: bool = False) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def warn(name: str, detail: Any) -> None:
        warnings.append({"name": name, "detail": detail})

    project_root = Path(
        os.environ.get("AGENT_WORM_PROJECT_ROOT", "/workspace/agent_worm_poc_v0.7.0")
    ).resolve()
    add("project_root_exists", project_root.is_dir(), str(project_root))

    integrity_ok, integrity_detail = _verify_source_hashes(project_root)
    add("source_integrity", integrity_ok, integrity_detail)

    image_ref = os.environ.get("AGENT_WORM_IMAGE_REF", "")
    add(
        "recorded_immutable_container_image_reference",
        bool(IMAGE_REF_RE.fullmatch(image_ref)),
        image_ref or "missing",
    )

    workspace = Path(os.environ.get("AGENT_WORM_WORKSPACE", "/workspace")).resolve()
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        test_path = workspace / ".agent-worm-write-test"
        test_path.write_text("ok\n", encoding="utf-8")
        read_back = test_path.read_text(encoding="utf-8").strip()
        test_path.unlink()
        add("workspace_read_write", read_back == "ok", str(workspace))
    except Exception as exc:
        add("workspace_read_write", False, f"{type(exc).__name__}: {exc}")

    try:
        disk = shutil.disk_usage(workspace)
        free_gib = disk.free / (1024**3)
        add("workspace_free_space_gib", free_gib >= 220, round(free_gib, 2))
    except Exception as exc:
        add("workspace_free_space_gib", False, f"{type(exc).__name__}: {exc}")

    try:
        if shutil.which("findmnt"):
            mount_detail = _run(["findmnt", "-T", str(workspace), "-o", "TARGET,SOURCE,FSTYPE,OPTIONS", "-J"])
            warn("workspace_mount", json.loads(mount_detail))
        else:
            warn("workspace_mount_not_recorded", "findmnt is unavailable")
    except Exception as exc:
        warn("workspace_mount_not_recorded", f"{type(exc).__name__}: {exc}")

    try:
        shm = shutil.disk_usage("/dev/shm")
        shm_gib = shm.total / (1024**3)
        if shm_gib < 1:
            warn(
                "small_shared_memory",
                f"/dev/shm is {shm_gib:.2f} GiB. The POC uses single-GPU eager "
                "execution, but this value is preserved because low shared memory can affect vLLM.",
            )
    except Exception as exc:
        warn("shared_memory_not_measured", f"{type(exc).__name__}: {exc}")

    hf_home = Path(os.environ.get("HF_HOME", "")).resolve() if os.environ.get("HF_HOME") else None
    add(
        "hf_home_on_workspace",
        bool(hf_home and (hf_home == workspace or workspace in hf_home.parents)),
        str(hf_home) if hf_home else "missing",
    )

    token = os.environ.get("HF_TOKEN", "")
    add("hf_token_present", token.startswith("hf_") and len(token) >= 20, "present" if token else "missing")
    password = os.environ.get("JUPYTER_PASSWORD", "")
    add("jupyter_password_present", len(password) >= 16, f"length={len(password)}")

    runtime_marker = Path("/opt/agent-worm-runtime.json")
    marker: dict[str, Any] | None = None
    try:
        if runtime_marker.exists():
            marker = json.loads(runtime_marker.read_text(encoding="utf-8"))
    except Exception as exc:
        add("prebuilt_runtime_marker", False, f"invalid marker: {exc}")
    else:
        add("prebuilt_runtime_marker", bool(marker), marker or "missing")
    if marker:
        add(
            "runtime_project_version",
            marker.get("version") == PROJECT_VERSION,
            {"expected": PROJECT_VERSION, "actual": marker.get("version")},
        )
        add(
            "runtime_vllm_version",
            marker.get("vllm") == "0.25.1",
            {"expected": "0.25.1", "actual": marker.get("vllm")},
        )
        add(
            "runtime_base_image",
            marker.get("base_image") == EXPECTED_BASE_IMAGE,
            {"expected": EXPECTED_BASE_IMAGE, "actual": marker.get("base_image")},
        )
        revision = str(marker.get("git_revision") or "")
        add(
            "runtime_git_revision_recorded",
            bool(SHA_RE.fullmatch(revision)),
            revision or "missing",
        )

    for command in (
        "python",
        "vllm",
        "nvidia-smi",
        "timeout",
        "setsid",
        "pgrep",
        "zip",
        "unzip",
        "sha256sum",
    ):
        add(f"command_{command}", shutil.which(command) is not None, shutil.which(command))

    add(
        "cpu_architecture_amd64",
        platform.machine().lower() in {"x86_64", "amd64"},
        platform.machine(),
    )

    gpu_info: list[dict[str, Any]] = []
    if shutil.which("nvidia-smi"):
        try:
            text = _run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader,nounits",
                ]
            )
            for line in text.splitlines():
                name, memory, driver = [part.strip() for part in line.split(",", maxsplit=2)]
                gpu_info.append(
                    {"name": name, "memory_total_mib": int(memory), "driver": driver}
                )
        except Exception as exc:
            add("gpu_query", False, f"{type(exc).__name__}: {exc}")
    if gpu_info:
        add("exactly_one_gpu", len(gpu_info) == 1, gpu_info)
        add("gpu_is_a100", "A100" in gpu_info[0]["name"].upper(), gpu_info[0])
        add("gpu_memory_at_least_79gb", gpu_info[0]["memory_total_mib"] >= 79_000, gpu_info[0])
        try:
            processes = _run(
                [
                    "nvidia-smi",
                    "--query-compute-apps=pid,process_name,used_gpu_memory",
                    "--format=csv,noheader,nounits",
                ]
            )
            process_lines = [line for line in processes.splitlines() if line.strip()]
            add("no_preexisting_gpu_compute_processes", not process_lines, process_lines or "none")
        except subprocess.CalledProcessError:
            add("no_preexisting_gpu_compute_processes", True, "none reported")
        try:
            cuda_smoke = _run(
                [
                    "python",
                    "-c",
                    (
                        "import json, torch; "
                        "assert torch.cuda.is_available(); "
                        "x=torch.arange(1024, device='cuda', dtype=torch.float32); "
                        "y=(x*x).sum(); torch.cuda.synchronize(); "
                        "print(json.dumps({'torch': torch.__version__, "
                        "'cuda': torch.version.cuda, 'device': torch.cuda.get_device_name(0), "
                        "'result': float(y.cpu())}))"
                    ),
                ]
            )
            add("torch_cuda_allocation_smoke", True, json.loads(cuda_smoke))
        except Exception as exc:
            add("torch_cuda_allocation_smoke", False, f"{type(exc).__name__}: {exc}")
    elif allow_no_gpu:
        add("gpu_optional_ci", True, "No GPU required for CI validation")
    else:
        add("gpu_present", False, "No GPU detected")

    versions: dict[str, Any] = {"python": platform.python_version()}
    try:
        versions["vllm"] = _run(["python", "-c", "import vllm; print(vllm.__version__)"])
    except Exception as exc:
        versions["vllm_error"] = str(exc)
    add("vllm_version_0_25_1", versions.get("vllm") == "0.25.1", versions)

    hourly_rate_raw = os.environ.get("RUNPOD_HOURLY_RATE", "")
    hourly_rate: float | None = None
    try:
        hourly_rate = float(hourly_rate_raw)
    except ValueError:
        pass
    add(
        "runpod_hourly_rate_recorded",
        bool(hourly_rate and hourly_rate > 0),
        hourly_rate_raw or "missing",
    )
    if not os.environ.get("RUNPOD_POD_ID"):
        warn("runpod_pod_id_not_detected", "The runtime did not expose RUNPOD_POD_ID.")

    report = {
        "schema_version": 2,
        "created_at": utc_now(),
        "checks": checks,
        "warnings": warnings,
        "passed": all(item["ok"] for item in checks),
        "environment": {
            "project_root": str(project_root),
            "workspace": str(workspace),
            "hf_home": str(hf_home) if hf_home else None,
            "runpod_pod_id": os.environ.get("RUNPOD_POD_ID"),
            "runpod_gpu_count": os.environ.get("RUNPOD_GPU_COUNT"),
            "runpod_hourly_rate": hourly_rate,
            "container_image_reference": image_ref,
            "runtime_marker": marker,
            "gpu_info": gpu_info,
        },
    }
    atomic_write_json(output_dir / "preflight.json", report)
    if not report["passed"]:
        failed = [item for item in checks if not item["ok"]]
        raise PreflightError(f"preflight failed: {failed}")
    return report
