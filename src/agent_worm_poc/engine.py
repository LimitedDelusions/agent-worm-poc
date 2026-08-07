from __future__ import annotations

import itertools
import json
import os
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, ContextManager

from .adapters import FakeAdapter, ModelAdapter, OpenAICompatibleAdapter, build_request_payload
from .config import load_experiment, load_models, load_roles
from .constants import PROJECT_VERSION, ROLE_ORDER
from .prompts import format_forwarded_artifact
from .schemas import validate_role_output, validate_role_semantics
from .scoring import score_run, summarize_intake_relay_pairs, summarize_scores
from .types import (
    GenerationConfig,
    ModelResponse,
    ModelSlot,
    RoleConfig,
    RunScore,
    ScenarioConfig,
    StageEvent,
)
from .util import (
    append_jsonl,
    atomic_write_json,
    canonical_json,
    file_record,
    prepare_new_output_dir,
    sha256_text,
    utc_now,
    write_csv,
)


@dataclass
class RunState:
    run_id: str
    placement_id: str
    placement_index: int
    placement: dict[str, str]
    scenario: ScenarioConfig
    repetition: int
    current_input: str
    events: list[StageEvent] = field(default_factory=list)
    failed: bool = False
    failure_reason: str | None = None


@dataclass(frozen=True)
class CachedResponse:
    response: ModelResponse
    first_run_id: str
    request_payload: dict


def all_placements(models: list[ModelSlot]) -> list[tuple[str, dict[str, str]]]:
    if len(models) != len(ROLE_ORDER):
        raise ValueError("the POC requires exactly four models and four roles")
    placements = []
    for index, permutation in enumerate(itertools.permutations(model.id for model in models), start=1):
        placements.append((f"P{index:02d}", dict(zip(ROLE_ORDER, permutation, strict=True))))
    return placements


def _load_selected_scenarios(
    root: Path,
    experiment: dict,
    scenario_ids: set[str] | None,
) -> tuple[list[ScenarioConfig], dict[str, str], dict[str, list[RoleConfig]], dict[str, Path]]:
    scenarios: list[ScenarioConfig] = list(experiment["scenario_configs"])
    if scenario_ids is not None:
        scenarios = [scenario for scenario in scenarios if scenario.id in scenario_ids]
    if not scenarios:
        raise ValueError("no scenarios selected")
    found = {scenario.id for scenario in scenarios}
    if scenario_ids is not None and found != scenario_ids:
        raise ValueError(f"unknown scenario ids: {sorted(scenario_ids - found)}")

    documents: dict[str, str] = {}
    role_sets: dict[str, list[RoleConfig]] = {}
    role_paths: dict[str, Path] = {}
    for scenario in scenarios:
        document_path = root / scenario.document_file
        if not document_path.is_file():
            raise FileNotFoundError(f"scenario document not found: {document_path}")
        documents[scenario.id] = document_path.read_text(encoding="utf-8")

        roles_path = root / scenario.roles_file
        roles = load_roles(roles_path)
        if any(role.policy_mode != scenario.architecture_id for role in roles):
            raise ValueError(
                f"scenario {scenario.id} architecture {scenario.architecture_id!r} "
                f"does not match role config {roles_path}"
            )
        prior = role_paths.get(scenario.architecture_id)
        if prior is not None and prior != roles_path:
            raise ValueError(
                f"architecture {scenario.architecture_id} maps to multiple role files"
            )
        role_paths[scenario.architecture_id] = roles_path
        role_sets[scenario.architecture_id] = roles
    return scenarios, documents, role_sets, role_paths


def _seed(
    base_seed: int,
    scenario_index: int,
    repetition: int,
    role_index: int,
    placement_index: int,
) -> int:
    """Create a stable but independent seed for every logical stage.

    Placement is included so the real POC does not silently reuse one generation
    as evidence for multiple placements.
    """
    return (
        base_seed
        + scenario_index * 1_000_000
        + repetition * 10_000
        + placement_index * 100
        + role_index
    )


def _request_payload_for(
    model: ModelSlot,
    role: RoleConfig,
    input_text: str,
    generation: GenerationConfig,
    seed: int,
) -> dict:
    return build_request_payload(
        model=model,
        role=role,
        untrusted_input=input_text,
        generation=generation,
        seed=seed,
    )


def execute_experiment(
    *,
    root: Path,
    output_dir: Path,
    model_config_path: Path,
    repetitions: int,
    adapter_mode: str,
    lifecycle_factory: Callable[[ModelSlot, str], ContextManager[str]] | None = None,
    placement_ids: set[str] | None = None,
    placements_override: list[tuple[str, dict[str, str]]] | None = None,
    scenario_ids: set[str] | None = None,
    reuse_identical_requests: bool = False,
    evidence_label: str = "engineering",
) -> dict:
    if repetitions < 1:
        raise ValueError("repetitions must be at least one")
    if adapter_mode not in {"fake", "real"}:
        raise ValueError("adapter_mode must be 'fake' or 'real'")

    prepare_new_output_dir(output_dir)
    started_at = utc_now()
    experiment_path = root / "configs" / "experiment.json"
    models = load_models(model_config_path, require_frozen=(adapter_mode == "real"))
    experiment = load_experiment(experiment_path)
    generation: GenerationConfig = experiment["generation_config"]
    scenarios, documents, role_sets, role_paths = _load_selected_scenarios(
        root, experiment, scenario_ids
    )
    base_seed = int(experiment["base_seed"])
    all_scenario_index = {
        scenario.id: index for index, scenario in enumerate(experiment["scenario_configs"])
    }

    placements = placements_override if placements_override is not None else all_placements(models)
    if placement_ids:
        placements = [item for item in placements if item[0] in placement_ids]
    if not placements:
        raise ValueError("no placements selected")

    expected_model_ids = {model.id for model in models}
    placement_index_by_id: dict[str, int] = {}
    for placement_index, (placement_id, placement) in enumerate(placements, start=1):
        placement_index_by_id[placement_id] = placement_index
        if set(placement) != set(ROLE_ORDER):
            raise ValueError(f"placement {placement_id} does not map all four roles")
        if set(placement.values()) != expected_model_ids:
            raise ValueError(f"placement {placement_id} must use each model exactly once")

    states: list[RunState] = []
    for placement_id, placement in placements:
        for scenario in scenarios:
            for repetition in range(repetitions):
                states.append(
                    RunState(
                        run_id=f"{placement_id}-{scenario.id}-R{repetition + 1:02d}",
                        placement_id=placement_id,
                        placement_index=placement_index_by_id[placement_id],
                        placement=placement,
                        scenario=scenario,
                        repetition=repetition,
                        current_input=documents[scenario.id],
                    )
                )

    events_path = output_dir / "stage_events.jsonl"
    requests_path = output_dir / "request_catalog.jsonl"
    failures_path = output_dir / "failures.json"
    cache: dict[str, CachedResponse] = {}
    failures: list[dict] = []
    inference_count = 0

    for role_index, role_id in enumerate(ROLE_ORDER):
        for model in models:
            batch = [
                state
                for state in states
                if not state.failed and state.placement[role_id] == model.id
            ]
            if not batch:
                continue

            if adapter_mode == "fake":
                context: ContextManager[str] = _NullContext("fake://local")
            else:
                if lifecycle_factory is None:
                    raise ValueError("real adapter requires lifecycle_factory")
                context = lifecycle_factory(model, f"{role_index + 1:02d}-{role_id}")

            try:
                with context as base_url:
                    adapter: ModelAdapter = (
                        FakeAdapter()
                        if adapter_mode == "fake"
                        else OpenAICompatibleAdapter(base_url=base_url)
                    )
                    for state in batch:
                        role = role_sets[state.scenario.architecture_id][role_index]
                        seed = _seed(
                            base_seed,
                            all_scenario_index[state.scenario.id],
                            state.repetition,
                            role_index,
                            state.placement_index,
                        )
                        request_payload = _request_payload_for(
                            model, role, state.current_input, generation, seed
                        )
                        expected_fingerprint = sha256_text(canonical_json(request_payload))
                        cached = cache.get(expected_fingerprint)
                        reused = bool(reuse_identical_requests and cached)
                        response: ModelResponse | None = None
                        source_run_id: str | None = None
                        event_error: str | None = None
                        schema_errors: list[str] = []
                        semantic_errors: list[str] = []
                        forwarded_text: str | None = None
                        try:
                            if reused and cached:
                                response = cached.response
                                source_run_id = cached.first_run_id
                            else:
                                fingerprint, response = adapter.generate(
                                    model=model,
                                    role=role,
                                    untrusted_input=state.current_input,
                                    generation=generation,
                                    seed=seed,
                                )
                                if fingerprint != expected_fingerprint:
                                    raise RuntimeError("request fingerprint changed between build and send")
                                cache[expected_fingerprint] = CachedResponse(
                                    response=response,
                                    first_run_id=state.run_id,
                                    request_payload=request_payload,
                                )
                                inference_count += 1
                                append_jsonl(
                                    requests_path,
                                    [
                                        {
                                            "request_fingerprint": expected_fingerprint,
                                            "first_run_id": state.run_id,
                                            "placement_id": state.placement_id,
                                            "scenario_id": state.scenario.id,
                                            "architecture_id": state.scenario.architecture_id,
                                            "input_type": state.scenario.input_type,
                                            "role_id": role.id,
                                            "policy_mode": role.policy_mode,
                                            "model_slot": model.id,
                                            "model_repo": model.repo_id,
                                            "model_revision": model.revision,
                                            "seed": seed,
                                            "request_payload": request_payload,
                                            "latency_ms": response.latency_ms,
                                            "prompt_tokens": response.prompt_tokens,
                                            "completion_tokens": response.completion_tokens,
                                            "total_tokens": response.total_tokens,
                                            "created_at": utc_now(),
                                        }
                                    ],
                                )
                            schema_errors = validate_role_output(role.id, response.parsed)
                            semantic_errors = (
                                [] if schema_errors else validate_role_semantics(role.id, response.parsed)
                            )
                            if schema_errors:
                                event_error = "schema validation failed"
                            elif semantic_errors:
                                event_error = "semantic validation failed"
                            else:
                                forwarded_text = format_forwarded_artifact(role.id, response.parsed)
                        except Exception as exc:
                            event_error = f"{type(exc).__name__}: {exc}"

                        event = StageEvent(
                            run_id=state.run_id,
                            placement_id=state.placement_id,
                            scenario_id=state.scenario.id,
                            architecture_id=state.scenario.architecture_id,
                            input_type=state.scenario.input_type,
                            repetition=state.repetition,
                            role_id=role.id,
                            policy_mode=role.policy_mode,
                            model_slot=model.id,
                            model_repo=model.repo_id,
                            model_revision=model.revision,
                            seed=seed,
                            input_text=state.current_input,
                            trusted_instructions=role.trusted_instructions,
                            request_fingerprint=expected_fingerprint,
                            response_reused=reused,
                            source_request_fingerprint=(expected_fingerprint if reused else None),
                            source_run_id=source_run_id,
                            output=response.parsed if response else None,
                            forwarded_text=forwarded_text,
                            raw_output=response.raw_content if response else None,
                            raw_response=response.raw_response if response else None,
                            schema_valid=bool(response) and not schema_errors,
                            schema_errors=schema_errors,
                            semantic_valid=bool(response) and not schema_errors and not semantic_errors,
                            semantic_errors=semantic_errors,
                            latency_ms=(0.0 if reused and response else response.latency_ms if response else None),
                            request_id=response.request_id if response else None,
                            finish_reason=response.finish_reason if response else None,
                            prompt_tokens=response.prompt_tokens if response else None,
                            completion_tokens=response.completion_tokens if response else None,
                            total_tokens=response.total_tokens if response else None,
                            error=event_error,
                        )
                        state.events.append(event)
                        append_jsonl(events_path, [event.to_dict()])
                        if event_error:
                            state.failed = True
                            state.failure_reason = f"{role.id}: {event_error}"
                            failures.append(
                                {
                                    "run_id": state.run_id,
                                    "placement_id": state.placement_id,
                                    "scenario_id": state.scenario.id,
                                    "architecture_id": state.scenario.architecture_id,
                                    "role_id": role.id,
                                    "model_slot": model.id,
                                    "error": event_error,
                                    "schema_errors": schema_errors,
                                    "semantic_errors": semantic_errors,
                                }
                            )
                        else:
                            state.current_input = forwarded_text or ""
            except Exception as exc:
                lifecycle_error = f"{type(exc).__name__}: {exc}"
                for state in batch:
                    if not state.failed:
                        state.failed = True
                        state.failure_reason = f"server {model.id}: {lifecycle_error}"
                        failures.append(
                            {
                                "run_id": state.run_id,
                                "placement_id": state.placement_id,
                                "scenario_id": state.scenario.id,
                                "architecture_id": state.scenario.architecture_id,
                                "role_id": role_id,
                                "model_slot": model.id,
                                "error": lifecycle_error,
                                "traceback": traceback.format_exc(),
                            }
                        )
                atomic_write_json(failures_path, failures)
                raise

    scores: list[RunScore] = []
    for state in states:
        scores.append(
            score_run(
                state.events,
                placement_id=state.placement_id,
                placement=state.placement,
                scenario_id=state.scenario.id,
                architecture_id=state.scenario.architecture_id,
                input_type=state.scenario.input_type,
                repetition=state.repetition,
                failure_reason=state.failure_reason,
            )
        )
    score_rows = [score.to_dict() for score in scores]
    write_csv(output_dir / "run_scores.csv", score_rows)
    append_jsonl(output_dir / "run_scores.jsonl", score_rows)
    summary_rows = summarize_scores(scores)
    write_csv(output_dir / "placement_summary.csv", summary_rows)
    pair_rows = summarize_intake_relay_pairs(scores)
    write_csv(output_dir / "intake_relay_summary.csv", pair_rows)
    atomic_write_json(failures_path, failures)

    model_rows = [
        {
            "slot_id": model.id,
            "display_name": model.display_name,
            "family": model.family,
            "repo_id": model.repo_id,
            "served_model_name": model.served_model_name,
            "revision": model.revision,
            "tokenizer_revision": model.tokenizer_revision,
            "trust_remote_code": model.trust_remote_code,
            "launch_args": list(model.launch_args),
            "request_overrides": model.request_overrides,
            "parser_file": model.parser_file,
            "parser_sha256": model.parser_sha256,
        }
        for model in models
    ]
    scenario_records = []
    for scenario in scenarios:
        scenario_records.append(
            {
                "scenario_id": scenario.id,
                "architecture_id": scenario.architecture_id,
                "input_type": scenario.input_type,
                "phase": scenario.phase,
                "purpose": scenario.purpose,
                "roles_file": file_record(root / scenario.roles_file, relative_to=root),
                "document_file": file_record(root / scenario.document_file, relative_to=root),
            }
        )
    runtime_marker = None
    marker_path = Path("/opt/agent-worm-runtime.json")
    if marker_path.is_file():
        try:
            runtime_marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception:
            runtime_marker = {"error": "runtime marker could not be parsed"}

    manifest = {
        "schema_version": 3,
        "status": "completed" if not failures else "completed_with_failures",
        "started_at": started_at,
        "completed_at": utc_now(),
        "project_version": PROJECT_VERSION,
        "adapter_mode": adapter_mode,
        "evidence_label": evidence_label,
        "research_question": experiment.get("research_question"),
        "primary_outcome": experiment.get("primary_outcome"),
        "research_evidence": False,
        "container_image_reference": os.environ.get("AGENT_WORM_IMAGE_REF"),
        "runtime_marker": runtime_marker,
        "models": model_rows,
        "architectures": [
            {
                "architecture_id": architecture_id,
                "roles_file": file_record(path, relative_to=root),
                "roles": [asdict(role) for role in role_sets[architecture_id]],
            }
            for architecture_id, path in sorted(role_paths.items())
        ],
        "generation": asdict(generation),
        "base_seed": base_seed,
        "seed_formula": (
            "base + scenario_index*1000000 + repetition*10000 + "
            "placement_index*100 + role_index"
        ),
        "config_files": [
            file_record(experiment_path, relative_to=root),
            file_record(
                model_config_path,
                relative_to=root if root in model_config_path.parents else None,
            ),
        ],
        "scenario_records": scenario_records,
        "placements": len(placements),
        "placement_map": [
            {"placement_id": placement_id, **placement}
            for placement_id, placement in placements
        ],
        "scenarios": [scenario.id for scenario in scenarios],
        "repetitions": repetitions,
        "planned_workflows": len(states),
        "completed_workflows": sum(not score.failed for score in scores),
        "failed_workflows": sum(score.failed for score in scores),
        "logical_stage_events": sum(len(state.events) for state in states),
        "unique_inference_requests": inference_count,
        "intake_relay_pairs": len({(score.placement["intake"], score.placement["relay"]) for score in scores}),
        "reused_stage_events": sum(
            event.response_reused for state in states for event in state.events
        ),
        "schema_invalid_stages": sum(
            not event.schema_valid for state in states for event in state.events
        ),
        "semantic_invalid_stages": sum(
            not event.semantic_valid for state in states for event in state.events
        ),
        "output_invalid_stages": sum(
            not event.output_valid for state in states for event in state.events
        ),
        "reuse_identical_requests": reuse_identical_requests,
        "reuse_interpretation": (
            "Exact request memoization was enabled for engineering-only validation. "
            "Reused stages are not independent replications."
            if reuse_identical_requests
            else "Every logical stage issued a separate inference request."
        ),
        "warning": (
            "POC/engineering output only. Positive controls, compatibility, shakedown, "
            "and POC results must not be represented as final white-paper findings."
        ),
    }
    atomic_write_json(output_dir / "manifest.json", manifest)
    return manifest


class _NullContext:
    def __init__(self, value: str):
        self.value = value

    def __enter__(self) -> str:
        return self.value

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False
