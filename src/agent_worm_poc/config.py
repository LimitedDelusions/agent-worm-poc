from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import POLICY_MODES, ROLE_ORDER
from .types import GenerationConfig, ModelSlot, RoleConfig, ScenarioConfig


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def load_models(path: Path, *, require_frozen: bool = False) -> list[ModelSlot]:
    payload = load_json(path)
    slots_raw = payload.get("model_slots")
    if not isinstance(slots_raw, list) or len(slots_raw) != 4:
        raise ValueError("model config must contain exactly four model_slots")

    slots: list[ModelSlot] = []
    ids: set[str] = set()
    families: set[str] = set()
    served_names: set[str] = set()
    repos: set[str] = set()
    for raw in slots_raw:
        if not isinstance(raw, dict):
            raise ValueError("each model slot must be an object")
        slot_id = str(raw["id"]).strip()
        family = str(raw["family"]).strip()
        repo_id = str(raw["repo_id"]).strip()
        served_name = str(raw["served_model_name"]).strip()
        if not all([slot_id, family, repo_id, served_name]):
            raise ValueError("model id, family, repo_id, and served_model_name must be nonempty")
        if slot_id in ids:
            raise ValueError(f"duplicate model slot: {slot_id}")
        if family in families:
            raise ValueError(f"model families must be unique in this POC: {family}")
        if served_name in served_names:
            raise ValueError(f"duplicate served_model_name: {served_name}")
        if repo_id in repos:
            raise ValueError(f"duplicate model repository: {repo_id}")
        ids.add(slot_id)
        families.add(family)
        served_names.add(served_name)
        repos.add(repo_id)

        revision = raw.get("revision")
        tokenizer_revision = raw.get("tokenizer_revision") or revision
        if require_frozen and (not revision or not tokenizer_revision):
            raise ValueError(f"model slot {slot_id} is not revision-frozen")

        parser_file = raw.get("parser_file")
        parser_sha256 = raw.get("parser_sha256")
        launch_args = tuple(str(x) for x in raw.get("launch_args", []))
        if require_frozen and any("{parser_path}" in arg for arg in launch_args):
            if not parser_file or not parser_sha256:
                raise ValueError(f"model slot {slot_id} requires a frozen parser file and hash")

        fake_profile = {
            str(k): float(v) for k, v in dict(raw.get("fake_profile", {})).items()
        }
        for name, value in fake_profile.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"fake profile {slot_id}.{name} must be between 0 and 1")

        slots.append(
            ModelSlot(
                id=slot_id,
                display_name=str(raw["display_name"]).strip(),
                family=family,
                repo_id=repo_id,
                served_model_name=served_name,
                license=str(raw["license"]).strip(),
                revision=str(revision) if revision else None,
                tokenizer_revision=str(tokenizer_revision) if tokenizer_revision else None,
                trust_remote_code=bool(raw.get("trust_remote_code", False)),
                launch_args=launch_args,
                request_overrides=dict(raw.get("request_overrides", {})),
                parser_file=str(parser_file) if parser_file else None,
                parser_sha256=str(parser_sha256) if parser_sha256 else None,
                fake_profile=fake_profile,
            )
        )
    return slots


def load_roles(path: Path) -> list[RoleConfig]:
    payload = load_json(path)
    architecture_id = str(payload.get("architecture_id", "")).strip()
    if architecture_id not in POLICY_MODES:
        raise ValueError(
            f"role config {path} architecture_id must be one of {POLICY_MODES!r}"
        )
    raw_roles = payload.get("roles")
    if not isinstance(raw_roles, list):
        raise ValueError("roles must be a list")
    roles: list[RoleConfig] = []
    for raw in raw_roles:
        if not isinstance(raw, dict):
            raise ValueError("each role must be an object")
        policy_mode = str(raw.get("policy_mode", architecture_id)).strip()
        if policy_mode != architecture_id:
            raise ValueError(
                f"role {raw.get('id')} policy_mode {policy_mode!r} does not match "
                f"architecture_id {architecture_id!r}"
            )
        roles.append(
            RoleConfig(
                id=str(raw["id"]).strip(),
                display_name=str(raw["display_name"]).strip(),
                policy_mode=policy_mode,
                trusted_instructions=str(raw["trusted_instructions"]).strip(),
            )
        )
    if tuple(role.id for role in roles) != ROLE_ORDER:
        raise ValueError(f"roles must appear in fixed order {ROLE_ORDER}")
    if any(not role.display_name or not role.trusted_instructions for role in roles):
        raise ValueError("role display names and trusted instructions must be nonempty")
    return roles


def load_experiment(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if int(payload.get("schema_version", 0)) != 2:
        raise ValueError("experiment schema_version must be 2")

    generation = payload.get("generation")
    if not isinstance(generation, dict):
        raise ValueError("experiment generation must be an object")
    generation_config = GenerationConfig(
        temperature=float(generation["temperature"]),
        top_p=float(generation["top_p"]),
        max_tokens=int(generation["max_tokens"]),
        timeout_seconds=int(generation["timeout_seconds"]),
        request_retries=int(generation.get("request_retries", 1)),
    )
    if generation_config.temperature < 0:
        raise ValueError("temperature cannot be negative")
    if not 0 < generation_config.top_p <= 1:
        raise ValueError("top_p must be in (0, 1]")
    if generation_config.max_tokens < 1 or generation_config.timeout_seconds < 1:
        raise ValueError("max_tokens and timeout_seconds must be positive")
    if generation_config.request_retries < 0:
        raise ValueError("request_retries cannot be negative")

    raw_scenarios = payload.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ValueError("experiment must define scenarios")
    scenarios: list[ScenarioConfig] = []
    ids: set[str] = set()
    for raw in raw_scenarios:
        if not isinstance(raw, dict):
            raise ValueError("each scenario must be an object")
        scenario = ScenarioConfig(
            id=str(raw["id"]).strip(),
            architecture_id=str(raw["architecture_id"]).strip(),
            roles_file=str(raw["roles_file"]).strip(),
            document_file=str(raw["document_file"]).strip(),
            input_type=str(raw["input_type"]).strip(),
            phase=str(raw["phase"]).strip(),
            purpose=str(raw.get("purpose", "")).strip(),
        )
        if not scenario.id or scenario.id in ids:
            raise ValueError(f"scenario ids must be unique and nonempty: {scenario.id!r}")
        if scenario.architecture_id not in POLICY_MODES:
            raise ValueError(
                f"scenario {scenario.id} architecture_id must be one of {POLICY_MODES!r}"
            )
        if scenario.input_type not in {"benign", "injected"}:
            raise ValueError(f"scenario {scenario.id} input_type must be benign or injected")
        if scenario.phase not in {"positive-control", "poc"}:
            raise ValueError(f"scenario {scenario.id} phase is unsupported: {scenario.phase}")
        if not scenario.roles_file or not scenario.document_file:
            raise ValueError(f"scenario {scenario.id} is missing roles_file or document_file")
        ids.add(scenario.id)
        scenarios.append(scenario)

    expected_main = {
        "neutral_benign",
        "neutral_injected",
        "hardened_benign",
        "hardened_injected",
    }
    if {s.id for s in scenarios if s.phase == "poc"} != expected_main:
        raise ValueError(f"POC scenarios must be exactly {sorted(expected_main)}")
    positive = [s for s in scenarios if s.phase == "positive-control"]
    if len(positive) != 1 or positive[0].id != "positive_control_injected":
        raise ValueError("exactly one positive_control_injected scenario is required")

    if int(payload.get("base_seed", -1)) < 0:
        raise ValueError("base_seed must be a nonnegative integer")
    for key in (
        "default_poc_repetitions",
        "compatibility_benign_repetitions",
        "positive_control_repetitions",
        "positive_control_min_artifact_reproduction_depth",
    ):
        if int(payload.get(key, 0)) < 1:
            raise ValueError(f"{key} must be positive")

    payload["generation_config"] = generation_config
    payload["scenario_configs"] = scenarios
    return payload


def scenarios_for_phase(experiment: dict[str, Any], phase: str) -> list[ScenarioConfig]:
    return [s for s in experiment["scenario_configs"] if s.phase == phase]
