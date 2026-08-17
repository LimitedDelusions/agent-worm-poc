from __future__ import annotations
from pathlib import Path
import json
import os
import signal
import subprocess
import time
import httpx
from .types import ModelSpec
from .util import sha256_file


_CREDENTIAL_MARKERS=("PASSWORD","TOKEN","SECRET","API_KEY","PRIVATE_KEY","CREDENTIAL")
_MODEL_SERVER_CREDENTIAL_ALLOWLIST={"HF_TOKEN"}
_MODEL_SERVER_ENV_ALLOWLIST={
    "HOME","USER","LOGNAME","PATH","SHELL","LANG","LC_ALL","TZ","TMPDIR",
    "LD_LIBRARY_PATH","LIBRARY_PATH","CUDA_HOME","CUDA_PATH",
    "HF_HOME","HF_HUB_CACHE","XDG_CACHE_HOME","TORCH_HOME","TRITON_CACHE_DIR",
    "PYTHONUNBUFFERED","PYTHONDONTWRITEBYTECODE","PYTHONHASHSEED",
}
_MODEL_SERVER_ENV_PREFIXES=("CUDA_","NVIDIA_","VLLM_","NCCL_","TORCH_","TRITON_","OMP_","MKL_")


def _model_server_environment()->dict[str,str]:
    environment={}
    for name,value in os.environ.items():
        upper=name.upper()
        if upper not in _MODEL_SERVER_CREDENTIAL_ALLOWLIST and any(
                marker in upper for marker in _CREDENTIAL_MARKERS):
            continue
        if upper in _MODEL_SERVER_CREDENTIAL_ALLOWLIST or upper in _MODEL_SERVER_ENV_ALLOWLIST \
                or upper.startswith(_MODEL_SERVER_ENV_PREFIXES):
            environment[name]=value
    if not environment.get("HF_TOKEN"):
        raise RuntimeError("HF_TOKEN is required by the isolated model-server environment")
    environment.setdefault("HF_HOME","/workspace/hf-cache")
    environment["CUDA_VISIBLE_DEVICES"]="0"
    return environment


def _verify_runtime_artifacts(model:ModelSpec):
    path=model.reasoning_parser_plugin_local_path
    expected=model.reasoning_parser_plugin_sha256
    if bool(path)!=bool(expected):
        raise RuntimeError(f"Incomplete reasoning-parser integrity metadata for {model.slot}")
    if not path:return
    artifact_path=Path(path)
    if artifact_path.is_symlink():
        raise RuntimeError(f"Reasoning-parser artifact is missing or linked for {model.slot}: {artifact_path}")
    artifact=artifact_path.resolve()
    if not artifact.is_file():
        raise RuntimeError(f"Reasoning-parser artifact is missing or linked for {model.slot}: {artifact}")
    actual=sha256_file(artifact)
    if actual!=expected:
        raise RuntimeError(f"Reasoning-parser artifact hash mismatch for {model.slot}")


class VLLMServerManager:
    def __init__(
        self,
        output_dir: Path,
        port: int = 8000,
        api_key: str = "local-poc",
        start_timeout: int = 3600,
        idle_memory_mib_max: int = 2500,
    ):
        self.output_dir = output_dir
        self.port = port
        self.api_key = api_key
        self.start_timeout = start_timeout
        self.idle_memory_mib_max = idle_memory_mib_max
        self.process: subprocess.Popen | None = None
        self.log_handle = None
        (output_dir / "server_logs").mkdir(parents=True, exist_ok=True)

    def _gpu_memory(self) -> int:
        try:
            output = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                timeout=20,
            )
            values = [int(value.strip()) for value in output.splitlines() if value.strip()]
            if not values:
                raise ValueError("nvidia-smi returned no GPU memory rows")
            return max(values)
        except Exception as exc:
            raise RuntimeError("Could not query GPU memory with nvidia-smi") from exc

    def ensure_idle(self):
        used = self._gpu_memory()
        if used > self.idle_memory_mib_max:
            raise RuntimeError(f"GPU is not idle before model load: {used} MiB used")

    def start(self, model: ModelSpec):
        if model.revision in {"", "RESOLVE_AT_GATE"} or model.tokenizer_revision in {
            "",
            "RESOLVE_AT_GATE",
        }:
            raise RuntimeError("Model and tokenizer revisions must be frozen before real inference")
        _verify_runtime_artifacts(model)
        self.stop()
        self.ensure_idle()
        log_path = self.output_dir / "server_logs" / f"{model.slot}.log"
        self.log_handle = log_path.open("a", encoding="utf-8")
        command = [
            "vllm",
            "serve",
            model.repo_id,
            "--revision",
            model.revision,
            "--code-revision",
            model.revision,
            "--tokenizer-revision",
            model.tokenizer_revision,
            "--served-model-name",
            model.served_name,
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--api-key",
            self.api_key,
            "--dtype",
            model.dtype,
            "--max-model-len",
            str(model.max_model_len),
            "--gpu-memory-utilization",
            "0.92",
            "--max-num-seqs",
            "4",
            "--generation-config",
            "vllm",
            "--no-enable-prefix-caching",
            "--disable-log-stats",
        ] + list(model.server_args)
        environment = _model_server_environment()
        logged_command=list(command)
        if "--api-key" in logged_command:
            logged_command[logged_command.index("--api-key")+1]="<redacted>"
        self.log_handle.write("COMMAND: " + json.dumps(logged_command) + "\n")
        self.log_handle.flush()
        self.process = subprocess.Popen(
            command,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            env=environment,
            start_new_session=True,
        )
        deadline = time.monotonic() + self.start_timeout
        url = f"http://127.0.0.1:{self.port}/v1/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last = ""
        try:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(f"vLLM exited for {model.slot}; see {log_path}")
                try:
                    response = httpx.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        body = response.json()
                        model_ids = {
                            row.get("id")
                            for row in body.get("data", [])
                            if isinstance(row, dict)
                        }
                        if model.served_name not in model_ids:
                            raise RuntimeError(
                                f"vLLM returned unexpected served models {sorted(model_ids)}"
                            )
                        return
                    last = f"HTTP {response.status_code}"
                except RuntimeError:
                    raise
                except Exception as exc:
                    last = str(exc)
                time.sleep(5)
            raise TimeoutError(f"Timed out starting {model.slot}: {last}")
        except BaseException:
            try:
                self.stop()
            except Exception as cleanup_exc:
                if self.log_handle:
                    self.log_handle.write(f"STARTUP CLEANUP ERROR: {cleanup_exc}\n")
                    self.log_handle.flush()
            raise

    def stop(self):
        process = self.process
        self.process = None
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=30)
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            used = self._gpu_memory()
            if used <= self.idle_memory_mib_max:
                return
            time.sleep(5)
        raise RuntimeError(
            f"GPU memory did not release after server stop: {self._gpu_memory()} MiB"
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop()
