from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelSlot:
    id: str
    display_name: str
    family: str
    repo_id: str
    served_model_name: str
    license: str
    revision: str | None
    tokenizer_revision: str | None
    trust_remote_code: bool
    launch_args: tuple[str, ...] = ()
    request_overrides: dict[str, Any] = field(default_factory=dict)
    parser_file: str | None = None
    parser_sha256: str | None = None
    fake_profile: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RoleConfig:
    id: str
    display_name: str
    trusted_instructions: str


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float
    top_p: float
    max_tokens: int
    timeout_seconds: int
    request_retries: int


@dataclass
class ModelResponse:
    parsed: dict[str, Any]
    raw_content: str
    raw_response: dict[str, Any]
    latency_ms: float
    request_id: str | None
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass
class StageEvent:
    run_id: str
    placement_id: str
    condition_id: str
    repetition: int
    role_id: str
    model_slot: str
    model_repo: str
    model_revision: str | None
    seed: int
    input_text: str
    trusted_instructions: str
    request_fingerprint: str
    response_reused: bool
    source_request_fingerprint: str | None
    source_run_id: str | None
    output: dict[str, Any] | None
    raw_output: str | None
    raw_response: dict[str, Any] | None
    schema_valid: bool
    schema_errors: list[str]
    semantic_valid: bool
    semantic_errors: list[str]
    latency_ms: float | None
    request_id: str | None
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    error: str | None = None

    @property
    def output_valid(self) -> bool:
        return self.schema_valid and self.semantic_valid and not self.error

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["output_valid"] = self.output_valid
        return value


@dataclass
class RunScore:
    run_id: str
    placement_id: str
    condition_id: str
    repetition: int
    placement: dict[str, str]
    schema_valid_all: int
    semantic_valid_all: int
    output_valid_all: int
    raw_intake_marker: int
    raw_relay_marker: int
    raw_planner_restricted: int
    raw_executor_restricted_selected: int
    raw_executor_restricted_approved: int
    contiguous_adopted: int
    contiguous_relayed: int
    contiguous_planned: int
    contiguous_executed: int
    propagation_depth: int
    end_to_end_compromise: int
    independent_downstream_violation: int
    task_preservation_depth: int
    benign_task_success: int
    total_latency_ms: float
    logical_stage_events: int
    unique_inference_requests: int
    reused_stage_events: int
    failed: int
    failure_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
