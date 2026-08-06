from __future__ import annotations

import itertools
import json
import os
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, ContextManager

from .adapters import AdapterError, FakeAdapter, ModelAdapter, OpenAICompatibleAdapter, build_request_payload
from .config import load_experiment, load_models, load_roles
from .constants import ROLE_ORDER
from .schemas import validate_role_output, validate_role_semantics
from .scoring import score_run, summarize_scores
from .types import GenerationConfig, ModelResponse, ModelSlot, RoleConfig, RunScore, StageEvent
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
    placement: dict[str, str]
    condition_id: str
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


def _load_conditions(root: Path, experiment: dict) -> list[tuple[int, str, str]]:
    conditions: list[tuple[int, str, str]] = []
    for index, raw in enumerate(experiment["conditions"]):
        condition_id = str(raw["id"])
        path = root / str(raw["file"])
        if not path.is_file():
            raise FileNotFoundError(f"condition file not found: {path}")
        conditions.append((index, condition_id, path.read_text(encoding="utf-8")))
    return conditions


def _seed(base_seed: int, condition_index: int, repetition: int, role_index: int) -> int:
    """Create a stable request seed independent of placement ordering.

    A placement is intentionally omitted: identical model/role/input/condition
    requests receive the same seed and can be safely identified for optional POC
    response reuse. The final white-paper study should disable response reuse and
    add independent repeated trials.
    """
    return base_seed + condition_index * 100_000 + repetition * 1_000 + role_index * 10


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
    condition_ids: set[str] | None = None,
    reuse_identical_requests: bool = True,
    evidence_label: str = "engineering",
) -> dict:
    if repetitions < 1:
        raise ValueError("repetitions must be at least one")
    if adapter_mode not in {"fake", "real"}:
        raise ValueError("adapter_mode must be 'fake' or 'real'")

    prepare_new_output_dir(output_dir)
    started_at = utc_now()
    roles_path = root / "configs" / "roles.json"
    experiment_path = root / "configs" / "experiment.json"
    roles = load_roles(roles_path)
    models = load_models(model_config_path, require_frozen=(adapter_mode == "real"))
    experiment = load_experiment(experiment_path)
    generation: GenerationConfig = experiment["generation_config"]
    all_conditions = _load_conditions(root, experiment)
    base_seed = int(experiment["base_seed"])

    placements = placements_override if placements_override is not None else all_placements(models)
    if placement_ids:
        placements = [item for item in placements if item[0] in placement_ids]
    conditions = all_conditions
    if condition_ids:
        conditions = [item for item in conditions if item[1] in condition_ids]
    if not placements:
        raise ValueError("no placements selected")
    if not conditions:
        raise ValueError("no conditions selected")

    expected_model_ids = {model.id for model in models}
    for placement_id, placement in placements:
        if set(placement) != set(ROLE_ORDER):
            raise ValueError(f"placement {placement_id} does not map all four roles")
        if set(placement.values()) != expected_model_ids:
            raise ValueError(f"placement {placement_id} must use each model exactly once")

    states: list[RunState] = []
    condition_index = {condition_id: original_index for original_index, condition_id, _ in all_conditions}
    for placement_id, placement in placements:
        for _, condition_id, document in conditions:
            for repetition in range(repetitions):
                states.append(
                    RunState(
                        run_id=f"{placement_id}-{condition_id}-R{repetition + 1:02d}",
                        placement_id=placement_id,
                        placement=placement,
                        condition_id=condition_id,
                        repetition=repetition,
                        current_input=document,
                    )
                )

    events_path = output_dir / "stage_events.jsonl"
    requests_path = output_dir / "request_catalog.jsonl"
    failures_path = output_dir / "failures.json"
    cache: dict[str, CachedResponse] = {}
    failures: list[dict] = []
    inference_count = 0

    for role_index, role in enumerate(roles):
        for model in models:
            batch = [
                state
                for state in states
                if not state.failed and state.placement[role.id] == model.id
            ]
            if not batch:
                continue

            if adapter_mode == "fake":
                context: ContextManager[str] = _NullContext("fake://local")
            else:
                if lifecycle_factory is None:
                    raise ValueError("real adapter requires lifecycle_factory")
                context = lifecycle_factory(model, f"{role_index + 1:02d}-{role.id}")

            try:
                with context as base_url:
                    adapter: ModelAdapter = (
                        FakeAdapter()
                        if adapter_mode == "fake"
                        else OpenAICompatibleAdapter(base_url=base_url)
                    )
                    for state in batch:
                        seed = _seed(
                            base_seed,
                            condition_index[state.condition_id],
                            state.repetition,
                            role_index,
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
                                    raise AdapterError(
                                        "request fingerprint changed between planning and execution"
                                    )
                                cache[fingerprint] = CachedResponse(
                                    response=response,
                                    first_run_id=state.run_id,
                                    request_payload=request_payload,
                                )
                                inference_count += 1
                                append_jsonl(
                                    requests_path,
                                    [
                                        {
                                            "request_fingerprint": fingerprint,
                                            "run_id_first_seen": state.run_id,
                                            "role_id": role.id,
                                            "model_slot": model.id,
                                            "model_repo": model.repo_id,
                                            "model_revision": model.revision,
                                            "seed": seed,
                                            "request_payload": request_payload,
                                            "response_request_id": response.request_id,
                                            "finish_reason": response.finish_reason,
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
                                []
                                if schema_errors
                                else validate_role_semantics(role.id, response.parsed)
                            )
                            if schema_errors:
                                event_error = "schema validation failed"
                            elif semantic_errors:
                                event_error = "semantic validation failed"
                        except Exception as exc:
                            event_error = f"{type(exc).__name__}: {exc}"

                        event = StageEvent(
                            run_id=state.run_id,
                            placement_id=state.placement_id,
                            condition_id=state.condition_id,
                            repetition=state.repetition,
                            role_id=role.id,
                            model_slot=model.id,
                            model_repo=model.repo_id,
                            model_revision=model.revision,
                            seed=seed,
                            input_text=state.current_input,
                            trusted_instructions=role.trusted_instructions,
                            request_fingerprint=expected_fingerprint,
                            response_reused=reused,
                            source_request_fingerprint=(
                                expected_fingerprint if reused else None
                            ),
                            source_run_id=source_run_id,
                            output=response.parsed if response else None,
                            raw_output=response.raw_content if response else None,
                            raw_response=response.raw_response if response else None,
                            schema_valid=bool(response) and not schema_errors,
                            schema_errors=schema_errors,
                            semantic_valid=bool(response) and not schema_errors and not semantic_errors,
                            semantic_errors=semantic_errors,
                            latency_ms=(
                                0.0 if reused and response else response.latency_ms if response else None
                            ),
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
                                    "condition_id": state.condition_id,
                                    "role_id": role.id,
                                    "model_slot": model.id,
                                    "error": event_error,
                                    "schema_errors": schema_errors,
                                    "semantic_errors": semantic_errors,
                                }
                            )
                        else:
                            state.current_input = canonical_json(response.parsed)
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
                                "condition_id": state.condition_id,
                                "role_id": role.id,
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
                condition_id=state.condition_id,
                repetition=state.repetition,
                failure_reason=state.failure_reason,
            )
        )
    score_rows = [score.to_dict() for score in scores]
    write_csv(output_dir / "run_scores.csv", score_rows)
    append_jsonl(output_dir / "run_scores.jsonl", score_rows)
    summary_rows = summarize_scores(scores)
    write_csv(output_dir / "placement_summary.csv", summary_rows)
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
    condition_records = []
    for _, condition_id, _ in conditions:
        condition = next(item for item in experiment["conditions"] if item["id"] == condition_id)
        condition_path = root / str(condition["file"])
        condition_records.append(
            {
                "condition_id": condition_id,
                "condition_type": condition.get("type"),
                **file_record(condition_path, relative_to=root),
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
        "schema_version": 2,
        "status": "completed" if not failures else "completed_with_failures",
        "started_at": started_at,
        "completed_at": utc_now(),
        "project_version": "0.6.0",
        "adapter_mode": adapter_mode,
        "evidence_label": evidence_label,
        "research_question": experiment.get("research_question"),
        "research_evidence": False,
        "container_image_reference": os.environ.get("AGENT_WORM_IMAGE_REF"),
        "runtime_marker": runtime_marker,
        "models": model_rows,
        "roles": [asdict(role) for role in roles],
        "generation": asdict(generation),
        "base_seed": base_seed,
        "seed_formula": "base + condition_index*100000 + repetition*1000 + role_index*10",
        "config_files": [
            file_record(roles_path, relative_to=root),
            file_record(experiment_path, relative_to=root),
            file_record(model_config_path, relative_to=root if root in model_config_path.parents else None),
        ],
        "condition_files": condition_records,
        "placements": len(placements),
        "placement_map": [
            {"placement_id": placement_id, **placement}
            for placement_id, placement in placements
        ],
        "conditions": [condition_id for _, condition_id, _ in conditions],
        "repetitions": repetitions,
        "planned_workflows": len(states),
        "completed_workflows": sum(not score.failed for score in scores),
        "failed_workflows": sum(score.failed for score in scores),
        "logical_stage_events": sum(len(state.events) for state in states),
        "unique_inference_requests": inference_count,
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
            "Exact request memoization is allowed only for this cost-limited POC. "
            "A reused stage is linked to the first real inference and is not an independent replication."
            if reuse_identical_requests
            else "Every logical stage issued a separate inference request."
        ),
        "warning": (
            "POC/engineering output only. Compatibility, shakedown, and POC results "
            "must not be represented as final white-paper findings."
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
