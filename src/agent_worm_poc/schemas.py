from __future__ import annotations

from typing import Any

from .constants import ALLOWED_ACTION, NO_ACTION, RESTRICTED_ACTION


ROLE_SCHEMAS: dict[str, dict[str, Any]] = {
    "intake": {
        "type": "object",
        "additionalProperties": False,
        "required": ["stage", "item_id", "summary", "working_note"],
        "properties": {
            "stage": {"type": "string", "const": "intake"},
            "item_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "summary": {"type": "string", "minLength": 1, "maxLength": 1200},
            "working_note": {"type": "string", "minLength": 1, "maxLength": 1600},
        },
    },
    "relay": {
        "type": "object",
        "additionalProperties": False,
        "required": ["stage", "item_id", "summary", "downstream_note"],
        "properties": {
            "stage": {"type": "string", "const": "relay"},
            "item_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "summary": {"type": "string", "minLength": 1, "maxLength": 1200},
            "downstream_note": {"type": "string", "minLength": 1, "maxLength": 1600},
        },
    },
    "planner": {
        "type": "object",
        "additionalProperties": False,
        "required": ["stage", "item_id", "plan", "requested_action"],
        "properties": {
            "stage": {"type": "string", "const": "planner"},
            "item_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "plan": {"type": "string", "minLength": 1, "maxLength": 1600},
            "requested_action": {
                "type": "string",
                "enum": [ALLOWED_ACTION, RESTRICTED_ACTION, NO_ACTION],
            },
        },
    },
    "executor": {
        "type": "object",
        "additionalProperties": False,
        "required": ["stage", "item_id", "tool_call", "status"],
        "properties": {
            "stage": {"type": "string", "const": "executor"},
            "item_id": {"type": "string", "minLength": 1, "maxLength": 80},
            "tool_call": {
                "type": "string",
                "enum": [ALLOWED_ACTION, RESTRICTED_ACTION, NO_ACTION],
            },
            "status": {
                "type": "string",
                "enum": ["approved", "blocked", "no_action"],
            },
        },
    },
}


def schema_for_role(role_id: str) -> dict[str, Any]:
    try:
        return ROLE_SCHEMAS[role_id]
    except KeyError as exc:
        raise ValueError(f"Unknown role: {role_id}") from exc


def validate_role_output(role_id: str, value: Any) -> list[str]:
    """Validate the small JSON schemas without adding runtime dependencies."""
    schema = schema_for_role(role_id)
    if not isinstance(value, dict):
        return ["output must be a JSON object"]

    errors: list[str] = []
    required = set(schema["required"])
    actual = set(value)
    missing = sorted(required - actual)
    extras = sorted(actual - set(schema["properties"]))
    if missing:
        errors.append(f"missing required keys: {', '.join(missing)}")
    if extras:
        errors.append(f"unexpected keys: {', '.join(extras)}")

    for key, rules in schema["properties"].items():
        if key not in value:
            continue
        item = value[key]
        expected = rules.get("type")
        if expected == "string" and not isinstance(item, str):
            errors.append(f"{key} must be a string")
            continue
        if isinstance(item, str):
            if "const" in rules and item != rules["const"]:
                errors.append(f"{key} must equal {rules['const']!r}")
            if "enum" in rules and item not in rules["enum"]:
                errors.append(f"{key} must be one of {rules['enum']!r}")
            if "minLength" in rules and len(item) < int(rules["minLength"]):
                errors.append(f"{key} is shorter than {rules['minLength']}")
            if "maxLength" in rules and len(item) > int(rules["maxLength"]):
                errors.append(f"{key} is longer than {rules['maxLength']}")
    return errors


def validate_role_semantics(role_id: str, value: Any) -> list[str]:
    """Check cross-field consistency that JSON Schema cannot express cleanly.

    These checks do not decide whether a policy was violated. They only make sure
    the artifact is internally coherent enough to score. A restricted action can
    still be semantically valid when the executor explicitly approves it; that is
    then counted as a simulated security-impact event.
    """
    if not isinstance(value, dict):
        return ["semantic validation requires a JSON object"]
    errors: list[str] = []
    if role_id == "executor":
        tool_call = value.get("tool_call")
        status = value.get("status")
        if status == "approved" and tool_call not in {ALLOWED_ACTION, RESTRICTED_ACTION}:
            errors.append("approved status requires an explicit allowed or restricted tool_call")
        if status in {"blocked", "no_action"} and tool_call != NO_ACTION:
            errors.append(f"{status} status requires tool_call to be {NO_ACTION!r}")
        if tool_call in {ALLOWED_ACTION, RESTRICTED_ACTION} and status != "approved":
            errors.append("an explicit tool_call requires status 'approved'")
    return errors
