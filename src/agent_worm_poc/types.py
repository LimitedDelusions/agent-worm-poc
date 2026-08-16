from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Role = Literal["intake", "relay", "planner", "executor"]
Policy = Literal["positive", "neutral", "hardened"]
ScenarioKind = Literal["clean", "sham", "injected"]

ROLES: tuple[Role, ...] = ("intake", "relay", "planner", "executor")

@dataclass(frozen=True)
class ModelSpec:
    slot: str
    display_name: str
    repo_id: str
    revision: str
    tokenizer_revision: str
    served_name: str
    dtype: str
    max_model_len: int
    server_args: tuple[str, ...] = ()
    request_extra: dict[str, Any] = field(default_factory=dict)
    reasoning_parser_plugin_repo_path: str | None = None
    reasoning_parser_name: str | None = None
    reasoning_parser_plugin_local_path: str | None = None
    reasoning_parser_plugin_sha256: str | None = None

@dataclass(frozen=True)
class CarrierSpec:
    carrier_id: str
    authorization_reference: str
    variant: str
    action: str = "external_vendor_callback"
    injected_block: str = ""

@dataclass(frozen=True)
class WorkflowCase:
    workflow_id: str
    block_id: str
    randomization_block_id: str
    placement_id: str
    role_models: dict[str, str]
    policy: Policy
    scenario_kind: ScenarioKind
    carrier_variant: str | None
    base_document_id: str
    source_document: str
    carrier: CarrierSpec | None
    repetition: int
    stage_seeds: dict[str, int]
    baseline_type: str = "heterogeneous"
    phase: str = "main"
    terminal_stage: Role = "relay"

@dataclass
class StageEvent:
    workflow_id: str
    request_id: str
    phase: str
    stage: Role
    model_slot: str
    model_repo: str
    model_revision: str
    served_name: str
    seed: int
    policy: Policy
    scenario_kind: ScenarioKind
    carrier_variant: str | None
    placement_id: str
    baseline_type: str
    repetition: int
    input_text: str
    system_prompt: str
    raw_response: str
    parsed: dict[str, Any] | None
    schema_valid: bool
    semantic_valid: bool
    error: str | None
    latency_seconds: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reused_response: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class WorkflowRecord:
    case: WorkflowCase
    stages: dict[str, StageEvent] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": asdict(self.case),
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
        }
