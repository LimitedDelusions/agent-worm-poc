from __future__ import annotations
from pathlib import Path
from .types import ModelSpec
from .util import load_json

def load_models(path: str | Path) -> list[ModelSpec]:
    data=load_json(path)
    models=[]
    for row in data["models"]:
        row=dict(row)
        row["server_args"]=tuple(row.get("server_args", []))
        models.append(ModelSpec(**row))
    slots=[m.slot for m in models]
    if len(models)!=4 or len(set(slots))!=4:
        raise ValueError("Exactly four unique model slots are required")
    return models

def load_experiment(path: str | Path) -> dict:
    data=load_json(path)
    if data.get("release") != "0.8.7":
        raise ValueError("Experiment config release mismatch")
    return data

def load_prompts(path: str | Path) -> dict:
    return load_json(path)["roles"]

def load_schemas(path: str | Path) -> dict:
    return load_json(path)
