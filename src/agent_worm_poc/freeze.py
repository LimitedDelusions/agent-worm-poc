from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import load_models
from .util import atomic_write_json, file_record, sha256_file, utc_now


class FreezeError(RuntimeError):
    pass


def _request_bytes(url: str, token: str, *, timeout: int, attempts: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "agent-worm-poc/0.7.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = FreezeError(
                f"Hugging Face returned HTTP {exc.code} for {url}: {body[:500]}"
            )
            if exc.code < 500:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(2 ** attempt)
    raise FreezeError(f"Could not retrieve {url}: {last_error}")


def _request_json(url: str, token: str) -> dict[str, Any]:
    raw = _request_bytes(url, token, timeout=60)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreezeError(f"Invalid JSON returned for {url}: {exc}") from exc
    if not isinstance(value, dict):
        raise FreezeError(f"Expected a JSON object from {url}")
    return value


def _download(url: str, token: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = _request_bytes(url, token, timeout=300)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        temporary.write_bytes(raw)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise


def _resolve_url(repo_id: str, revision: str, filename: str) -> str:
    encoded_repo = urllib.parse.quote(repo_id, safe="/")
    encoded_file = urllib.parse.quote(filename, safe="/")
    return f"https://huggingface.co/{encoded_repo}/resolve/{revision}/{encoded_file}"


def freeze_models(*, candidate_path: Path, output_path: Path, setup_dir: Path) -> dict[str, Any]:
    token = os.environ.get("HF_TOKEN", "")
    if not token.startswith("hf_"):
        raise FreezeError("HF_TOKEN is missing or does not begin with hf_")
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    frozen = deepcopy(candidate)
    access_rows: list[dict[str, Any]] = []
    access_dir = setup_dir / "model_access"

    for slot in frozen["model_slots"]:
        repo_id = slot["repo_id"]
        encoded = urllib.parse.quote(repo_id, safe="/")
        info = _request_json(f"https://huggingface.co/api/models/{encoded}", token)
        sha = info.get("sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise FreezeError(f"No exact 40-character immutable SHA returned for {repo_id}: {sha!r}")
        slot["revision"] = sha
        slot["tokenizer_revision"] = sha

        probes: list[dict[str, Any]] = []
        for filename in ("config.json", "tokenizer_config.json"):
            destination = access_dir / f"{slot['id']}-{sha[:12]}-{filename}"
            _download(_resolve_url(repo_id, sha, filename), token, destination)
            probes.append(
                {
                    "filename": filename,
                    "local_path": str(destination),
                    "sha256": sha256_file(destination),
                    "bytes": destination.stat().st_size,
                }
            )

        if slot["id"] == "nvidia_slot":
            parser_name = "nano_v3_reasoning_parser.py"
            parser_path = setup_dir / "model_code" / f"{slot['id']}-{sha[:12]}-{parser_name}"
            _download(_resolve_url(repo_id, sha, parser_name), token, parser_path)
            slot["parser_file"] = str(parser_path)
            slot["parser_sha256"] = sha256_file(parser_path)
            probes.append(
                {
                    "filename": parser_name,
                    "local_path": str(parser_path),
                    "sha256": slot["parser_sha256"],
                    "bytes": parser_path.stat().st_size,
                }
            )

        access_rows.append(
            {
                "model_slot": slot["id"],
                "repo_id": repo_id,
                "revision": sha,
                "private": bool(info.get("private", False)),
                "gated": info.get("gated"),
                "pipeline_tag": info.get("pipeline_tag"),
                "library_name": info.get("library_name"),
                "checked_at": utc_now(),
                "probe_files": probes,
            }
        )

    frozen["status"] = "frozen-for-poc"
    frozen["frozen_at"] = utc_now()
    frozen["candidate_config"] = file_record(candidate_path)
    atomic_write_json(output_path, frozen)
    # Parse the final file through the same strict loader used by real runs.
    load_models(output_path, require_frozen=True)
    atomic_write_json(setup_dir / "model_access_and_revisions.json", access_rows)
    atomic_write_json(
        setup_dir / "frozen_models_manifest.json",
        {
            "schema_version": 1,
            "created_at": utc_now(),
            "candidate_config": file_record(candidate_path),
            "frozen_config": file_record(output_path),
            "models": access_rows,
            "notes": (
                "The Hugging Face token is not stored. Revisions, probe-file hashes, "
                "and any required parser code are preserved for reproducibility."
            ),
        },
    )
    return frozen
