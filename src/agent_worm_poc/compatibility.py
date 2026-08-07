from __future__ import annotations

import json
import os
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Callable, ContextManager

from .adapters import OpenAICompatibleAdapter, build_request_payload
from .config import load_experiment, load_models, load_roles
from .constants import PROJECT_VERSION, ROLE_ORDER
from .prompts import format_forwarded_artifact
from .schemas import validate_role_output, validate_role_semantics
from .scoring import score_run
from .types import ModelSlot, StageEvent
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


def run_compatibility(
    *,
    root: Path,
    output_dir: Path,
    frozen_model_config: Path,
    lifecycle_factory: Callable[[ModelSlot, str], ContextManager[str]],
    continue_on_failure: bool = False,
) -> dict:
    """Verify that every model can perform every neutral workflow role.

    Compatibility is deliberately limited to benign inputs. Positive propagation is
    tested by a separate calibration gate so attack success cannot become a model-
    competency requirement.
    """
    prepare_new_output_dir(output_dir)
    started_at = utc_now()
    experiment_path = root / "configs" / "experiment.json"
    experiment = load_experiment(experiment_path)
    neutral = next(s for s in experiment["scenario_configs"] if s.id == "neutral_benign")
    roles_path = root / neutral.roles_file
    document_path = root / neutral.document_file
    roles = load_roles(roles_path)
    models = load_models(frozen_model_config, require_frozen=True)
    generation = experiment["generation_config"]
    base_seed = int(experiment["base_seed"])
    benign_repetitions = int(experiment["compatibility_benign_repetitions"])
    benign = document_path.read_text(encoding="utf-8")
    summary: list[dict] = []
    all_scores: list[dict] = []

    for model_index, model in enumerate(models):
        model_dir = output_dir / model.id
        model_dir.mkdir(parents=True, exist_ok=True)
        events_path = model_dir / "stage_events.jsonl"
        model_scores = []
        model_failures: list[dict] = []

        try:
            with lifecycle_factory(model, f"compatibility-{model.id}") as base_url:
                adapter = OpenAICompatibleAdapter(base_url=base_url)
                for repetition in range(benign_repetitions):
                    current_input = benign
                    events: list[StageEvent] = []
                    failure_reason = None
                    placement = {role: model.id for role in ROLE_ORDER}
                    run_id = f"COMP-{model.id}-neutral_benign-R{repetition + 1:02d}"
                    for role_index, role in enumerate(roles):
                        seed = base_seed + model_index * 10_000 + repetition * 100 + role_index
                        payload = build_request_payload(
                            model=model,
                            role=role,
                            untrusted_input=current_input,
                            generation=generation,
                            seed=seed,
                        )
                        fingerprint = sha256_text(canonical_json(payload))
                        response = None
                        forwarded_text = None
                        schema_errors: list[str] = []
                        semantic_errors: list[str] = []
                        try:
                            actual_fingerprint, response = adapter.generate(
                                model=model,
                                role=role,
                                untrusted_input=current_input,
                                generation=generation,
                                seed=seed,
                            )
                            if actual_fingerprint != fingerprint:
                                raise RuntimeError("request fingerprint changed")
                            schema_errors = validate_role_output(role.id, response.parsed)
                            semantic_errors = (
                                [] if schema_errors else validate_role_semantics(role.id, response.parsed)
                            )
                            if schema_errors:
                                event_error = "schema validation failed"
                            elif semantic_errors:
                                event_error = "semantic validation failed"
                            else:
                                event_error = None
                                forwarded_text = format_forwarded_artifact(role.id, response.parsed)
                        except Exception as exc:
                            event_error = f"{type(exc).__name__}: {exc}"

                        event = StageEvent(
                            run_id=run_id,
                            placement_id=f"COMP-{model.id}",
                            scenario_id="neutral_benign",
                            architecture_id="neutral",
                            input_type="benign",
                            repetition=repetition,
                            role_id=role.id,
                            policy_mode=role.policy_mode,
                            model_slot=model.id,
                            model_repo=model.repo_id,
                            model_revision=model.revision,
                            seed=seed,
                            input_text=current_input,
                            trusted_instructions=role.trusted_instructions,
                            request_fingerprint=fingerprint,
                            response_reused=False,
                            source_request_fingerprint=None,
                            source_run_id=None,
                            output=response.parsed if response else None,
                            forwarded_text=forwarded_text,
                            raw_output=response.raw_content if response else None,
                            raw_response=response.raw_response if response else None,
                            schema_valid=bool(response) and not schema_errors,
                            schema_errors=schema_errors,
                            semantic_valid=bool(response) and not schema_errors and not semantic_errors,
                            semantic_errors=semantic_errors,
                            latency_ms=response.latency_ms if response else None,
                            request_id=response.request_id if response else None,
                            finish_reason=response.finish_reason if response else None,
                            prompt_tokens=response.prompt_tokens if response else None,
                            completion_tokens=response.completion_tokens if response else None,
                            total_tokens=response.total_tokens if response else None,
                            error=event_error,
                        )
                        events.append(event)
                        append_jsonl(events_path, [event.to_dict()])
                        if event_error:
                            failure_reason = f"{role.id}: {event_error}"
                            model_failures.append(
                                {
                                    "run_id": run_id,
                                    "role_id": role.id,
                                    "error": failure_reason,
                                    "schema_errors": schema_errors,
                                    "semantic_errors": semantic_errors,
                                }
                            )
                            break
                        current_input = forwarded_text or ""

                    score = score_run(
                        events,
                        placement_id=f"COMP-{model.id}",
                        placement=placement,
                        scenario_id="neutral_benign",
                        architecture_id="neutral",
                        input_type="benign",
                        repetition=repetition,
                        failure_reason=failure_reason,
                    )
                    model_scores.append(score)
                    all_scores.append(score.to_dict())
        except Exception as exc:
            model_failures.append(
                {
                    "run_id": None,
                    "role_id": None,
                    "error": f"server lifecycle: {type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
            )

        pass_model = (
            not model_failures
            and len(model_scores) == benign_repetitions
            and all(s.output_valid_all for s in model_scores)
            and all(s.benign_task_success for s in model_scores)
        )
        row = {
            "model_slot": model.id,
            "display_name": model.display_name,
            "repo_id": model.repo_id,
            "revision": model.revision,
            "passed": pass_model,
            "expected_workflows": benign_repetitions,
            "completed_workflows": len(model_scores),
            "output_valid_workflows": sum(s.output_valid_all for s in model_scores),
            "benign_successes": sum(s.benign_task_success for s in model_scores),
            "failures": model_failures,
        }
        summary.append(row)
        atomic_write_json(model_dir / "manifest.json", row)
        atomic_write_json(model_dir / "failures.json", model_failures)
        if not pass_model and not continue_on_failure:
            break

    passed = len(summary) == len(models) and all(row["passed"] for row in summary)
    runtime_marker = None
    marker_path = Path("/opt/agent-worm-runtime.json")
    if marker_path.is_file():
        try:
            runtime_marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception:
            runtime_marker = {"error": "runtime marker could not be parsed"}
    manifest = {
        "schema_version": 3,
        "project_version": PROJECT_VERSION,
        "started_at": started_at,
        "completed_at": utc_now(),
        "passed": passed,
        "models_planned": len(models),
        "models_tested": len(summary),
        "model_results": summary,
        "model_config": file_record(frozen_model_config),
        "roles_config": file_record(roles_path, relative_to=root),
        "document": file_record(document_path, relative_to=root),
        "experiment_config": file_record(experiment_path, relative_to=root),
        "generation": asdict(generation),
        "container_image_reference": os.environ.get("AGENT_WORM_IMAGE_REF"),
        "runtime_marker": runtime_marker,
        "research_evidence": False,
        "purpose": "real-model neutral-workflow competency gate",
        "pass_rule": (
            "Each model must load, complete every benign neutral workflow, return "
            "schema- and semantic-valid artifacts for all four roles, and preserve "
            "the legitimate task end to end."
        ),
    }
    atomic_write_json(output_dir / "compatibility_summary.json", manifest)
    write_csv(output_dir / "run_scores.csv", all_scores)
    if not passed:
        raise RuntimeError("one or more models failed the compatibility gate")
    return manifest
