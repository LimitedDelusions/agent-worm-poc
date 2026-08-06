from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .types import ModelSlot
from .util import append_jsonl, sha256_file, utc_now


class ServerError(RuntimeError):
    pass


def gpu_memory_used_mib() -> int:
    command = [
        "nvidia-smi",
        "--query-gpu=memory.used",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    values = [int(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    return max(values) if values else 0


def port_is_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


class VllmServerManager:
    def __init__(
        self,
        *,
        output_dir: Path,
        port: int = 8000,
        api_key: str = "local-poc",
        startup_timeout_seconds: int = 1800,
        shutdown_timeout_seconds: int = 180,
        prestart_memory_limit_mib: int = 4096,
    ) -> None:
        self.output_dir = output_dir
        self.port = port
        self.api_key = api_key
        self.startup_timeout_seconds = startup_timeout_seconds
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.prestart_memory_limit_mib = prestart_memory_limit_mib
        self.logs_dir = output_dir / "server_logs"
        self.lifecycle_path = output_dir / "server_lifecycle.jsonl"

    def _command(self, model: ModelSlot) -> list[str]:
        if not model.revision or not model.tokenizer_revision:
            raise ServerError(f"model {model.id} is not revision-frozen")
        vllm_binary = os.environ.get("VLLM_BINARY", "vllm")
        command = [
            vllm_binary,
            "serve",
            model.repo_id,
            "--revision",
            model.revision,
            "--tokenizer-revision",
            model.tokenizer_revision,
            "--served-model-name",
            model.served_model_name,
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--api-key",
            self.api_key,
            "--tensor-parallel-size",
            "1",
            "--max-model-len",
            "8192",
            "--max-num-seqs",
            "1",
            "--gpu-memory-utilization",
            "0.90",
            "--enforce-eager",
            "--generation-config",
            "vllm",
        ]
        if model.trust_remote_code:
            command.extend(["--trust-remote-code", "--code-revision", model.revision])
        parser_path = None
        if model.parser_file:
            parser = Path(model.parser_file).resolve()
            if not parser.is_file():
                raise ServerError(f"parser file is missing for {model.id}: {parser}")
            if not model.parser_sha256:
                raise ServerError(f"parser hash is missing for {model.id}")
            actual_hash = sha256_file(parser)
            if actual_hash != model.parser_sha256:
                raise ServerError(
                    f"parser hash mismatch for {model.id}: expected {model.parser_sha256}, got {actual_hash}"
                )
            parser_path = str(parser)
        for arg in model.launch_args:
            if "{parser_path}" in arg and not parser_path:
                raise ServerError(f"launch argument requires parser_path for {model.id}")
            command.append(arg.replace("{parser_path}", parser_path or ""))
        return command

    def _wait_ready(self, process: subprocess.Popen, log_path: Path) -> None:
        deadline = time.monotonic() + self.startup_timeout_seconds
        url = f"http://127.0.0.1:{self.port}/v1/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_error = "server not ready"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                tail = ""
                if log_path.exists():
                    tail = "\n".join(log_path.read_text(errors="replace").splitlines()[-80:])
                raise ServerError(f"vLLM exited with code {process.returncode}. Log tail:\n{tail}")
            try:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=10) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                last_error = str(exc)
            time.sleep(5)
        raise ServerError(f"vLLM did not become ready within timeout: {last_error}")

    def _stop(self, process: subprocess.Popen) -> None:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=30)

    def _wait_memory_release(self) -> tuple[int | None, bool, str | None]:
        deadline = time.monotonic() + self.shutdown_timeout_seconds
        last: int | None = None
        last_error: str | None = None
        while time.monotonic() < deadline:
            try:
                last = gpu_memory_used_mib()
                last_error = None
            except Exception as exc:  # preserve the original server error when present
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(5)
                continue
            if last <= self.prestart_memory_limit_mib:
                return last, True, None
            time.sleep(5)
        return last, False, last_error

    @contextmanager
    def serve(self, model: ModelSlot, *, phase: str) -> Iterator[str]:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if not port_is_available(self.port):
            raise ServerError(
                f"refusing to start {model.id}: TCP port {self.port} is already in use"
            )
        prestart = gpu_memory_used_mib()
        if prestart > self.prestart_memory_limit_mib:
            raise ServerError(
                f"refusing to load {model.id}: GPU already uses {prestart} MiB "
                f"(limit {self.prestart_memory_limit_mib} MiB)"
            )
        command = self._command(model)
        log_path = self.logs_dir / f"{phase}-{model.id}.log"
        start_time = utc_now()
        started = time.monotonic()
        process: subprocess.Popen | None = None
        original_error: BaseException | None = None
        peak_memory_after_ready: int | None = None
        try:
            server_env = dict(os.environ)
            # The model server needs the read-only HF_TOKEN for first-time model
            # retrieval, but it does not need interactive or provider credentials.
            for sensitive_name in (
                "JUPYTER_PASSWORD",
                "RUNPOD_API_KEY",
                "PUBLIC_KEY",
                "GITHUB_TOKEN",
            ):
                server_env.pop(sensitive_name, None)
            server_env["CUDA_VISIBLE_DEVICES"] = "0"
            with log_path.open("w", encoding="utf-8") as log_handle:
                process = subprocess.Popen(
                    command,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                    env=server_env,
                )
            self._wait_ready(process, log_path)
            peak_memory_after_ready = gpu_memory_used_mib()
            append_jsonl(
                self.lifecycle_path,
                [{
                    "event": "server_ready",
                    "phase": phase,
                    "model_slot": model.id,
                    "repo_id": model.repo_id,
                    "revision": model.revision,
                    "tokenizer_revision": model.tokenizer_revision,
                    "pid": process.pid,
                    "command": command,
                    "log_path": str(log_path),
                    "prestart_gpu_memory_used_mib": prestart,
                    "gpu_memory_used_after_ready_mib": peak_memory_after_ready,
                    "started_at": start_time,
                    "ready_after_seconds": round(time.monotonic() - started, 3),
                }],
            )
            yield f"http://127.0.0.1:{self.port}"
        except BaseException as exc:
            original_error = exc
            raise
        finally:
            if process is not None:
                self._stop(process)
            memory_after, release_ok, release_error = self._wait_memory_release()
            append_jsonl(
                self.lifecycle_path,
                [{
                    "event": "server_stopped",
                    "phase": phase,
                    "model_slot": model.id,
                    "repo_id": model.repo_id,
                    "revision": model.revision,
                    "stopped_at": utc_now(),
                    "gpu_memory_used_after_ready_mib": peak_memory_after_ready,
                    "gpu_memory_after_stop_mib": memory_after,
                    "gpu_memory_release_ok": release_ok,
                    "gpu_memory_release_error": release_error,
                    "error": (
                        f"{type(original_error).__name__}: {original_error}"
                        if original_error is not None
                        else None
                    ),
                }],
            )
            if not release_ok and original_error is None:
                detail = (
                    f"last measured usage {memory_after} MiB"
                    if memory_after is not None
                    else f"memory query failed: {release_error}"
                )
                raise ServerError(
                    f"GPU memory did not release after stopping {model.id}: {detail}"
                )
