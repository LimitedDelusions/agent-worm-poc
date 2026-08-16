from __future__ import annotations
from pathlib import Path
from dataclasses import replace
import json, os, subprocess, sys, time
from huggingface_hub import HfApi, hf_hub_download
from .types import ModelSpec
from .util import sha256_file, write_json


def freeze_revisions(models:list[ModelSpec], output_dir:Path)->list[ModelSpec]:
    """Freeze model/tokenizer revisions and any required runtime code artifacts.

    Runtime artifacts are downloaded from the same immutable model revision, hashed,
    stored inside the run evidence tree, and passed to vLLM by absolute path.
    """
    token=os.environ.get("HF_TOKEN")
    if not token: raise RuntimeError("HF_TOKEN is required")
    api=HfApi(token=token); frozen=[]; rows=[]
    runtime_root=output_dir/"runtime_files"
    for model in models:
        info=api.model_info(model.repo_id, files_metadata=False)
        revision=info.sha
        if not revision or len(revision)<20:
            raise RuntimeError(f"Could not resolve immutable revision for {model.repo_id}")
        server_args=list(model.server_args);artifacts=[];plugin_local_path=None;plugin_sha256=None
        plugin_path=model.reasoning_parser_plugin_repo_path
        parser_name=model.reasoning_parser_name
        if bool(plugin_path) != bool(parser_name):
            raise RuntimeError(f"{model.slot} must define both reasoning parser plugin path and parser name")
        if plugin_path and parser_name:
            local_dir=runtime_root/model.slot
            local_dir.mkdir(parents=True, exist_ok=True)
            downloaded=Path(hf_hub_download(
                repo_id=model.repo_id, filename=plugin_path, revision=revision,
                token=token, local_dir=local_dir,
            )).resolve()
            if not downloaded.is_file():
                raise RuntimeError(f"Runtime plugin was not downloaded for {model.slot}: {plugin_path}")
            plugin_local_path=str(downloaded);plugin_sha256=sha256_file(downloaded)
            artifacts.append({
                "repo_path":plugin_path,
                "local_path":plugin_local_path,
                "sha256":plugin_sha256,
                "size":downloaded.stat().st_size,
            })
            server_args.extend(["--reasoning-parser-plugin",str(downloaded),
                                "--reasoning-parser",parser_name])
        frozen_model=replace(model,revision=revision,tokenizer_revision=revision,
                             server_args=tuple(server_args),
                             reasoning_parser_plugin_local_path=plugin_local_path,
                             reasoning_parser_plugin_sha256=plugin_sha256)
        frozen.append(frozen_model)
        rows.append({
            "slot":model.slot,"repo_id":model.repo_id,"revision":revision,
            "tokenizer_revision":revision,"served_name":model.served_name,
            "dtype":model.dtype,"max_model_len":model.max_model_len,
            "server_args":list(frozen_model.server_args),
            "request_extra":model.request_extra,"runtime_artifacts":artifacts,
        })
    output_dir.mkdir(parents=True,exist_ok=True)
    write_json(output_dir/"model_revisions.json",rows)
    return frozen


def record_environment(output_dir:Path):
    output_dir.mkdir(parents=True,exist_ok=True)
    image_ref=os.environ.get("AGENT_WORM_IMAGE_REF") or os.environ.get("CONTAINER_IMAGE") or "unknown"
    digest=image_ref.rsplit("@",1)[1] if "@sha256:" in image_ref else os.environ.get("CONTAINER_IMAGE_DIGEST","unknown")
    marker_path=Path("/opt/agent-worm-runtime.json")
    marker=None
    if marker_path.exists():
        try: marker=json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception as exc: marker={"read_error":f"{type(exc).__name__}: {exc}"}
    write_json(output_dir/"environment.json",{
      "python":sys.version,"container_image_reference":image_ref,
      "container_image_digest":digest,
      "git_commit":os.environ.get("GIT_COMMIT") or (marker or {}).get("git_revision") or "unknown",
      "hourly_rate_usd":os.environ.get("RUNPOD_HOURLY_RATE_USD") or os.environ.get("RUNPOD_HOURLY_RATE") or "unknown",
      "runtime_marker":marker,"started_epoch":time.time(),
    })
    for name,cmd in (("nvidia-smi.txt",["nvidia-smi"]),("pip-freeze.txt",[sys.executable,"-m","pip","freeze"])):
        try:(output_dir/name).write_text(subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT,timeout=120),encoding="utf-8")
        except Exception as exc:(output_dir/name).write_text(f"ERROR: {exc}\n",encoding="utf-8")
