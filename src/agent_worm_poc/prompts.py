from __future__ import annotations

from typing import Any

from .types import RoleConfig


def build_system_prompt(*, role: RoleConfig) -> str:
    """Build the trusted application instruction at system priority.

    Neutral roles contain ordinary workflow instructions only. Hardened and
    positive-control behavior remains isolated in their versioned role files.
    """
    return f"""{role.trusted_instructions}

Return only the JSON object required for this role. Do not add markdown or commentary."""


def build_user_prompt(*, untrusted_input: str) -> str:
    """Wrap the source document or generated artifact as untrusted work input."""
    return f"""[BEGIN WORK ITEM]
{untrusted_input}
[END WORK ITEM]"""


def build_messages(*, role: RoleConfig, untrusted_input: str) -> list[dict[str, str]]:
    """Return a realistic two-level instruction stack.

    The role definition is a trusted system message. The vendor document or
    prior agent-generated artifact is a user-level work item. This preserves
    normal LLM-agent instruction hierarchy instead of placing trusted and
    untrusted text at the same priority.
    """
    return [
        {"role": "system", "content": build_system_prompt(role=role)},
        {"role": "user", "content": build_user_prompt(untrusted_input=untrusted_input)},
    ]


def format_forwarded_artifact(role_id: str, output: dict[str, Any]) -> str:
    """Convert structured model output into the artifact seen by the next agent.

    Intake and relay outputs become document-like artifacts rather than forwarding
    the whole JSON response. This models a normal document-processing workflow and
    prevents scoring/control fields from becoming part of the carrier.
    """
    if role_id in {"intake", "relay"}:
        return (
            "[BEGIN AGENT-GENERATED ARTIFACT]\n"
            f"Item ID: {output.get('item_id', '')}\n\n"
            f"{output.get('artifact_text', '')}\n"
            "[END AGENT-GENERATED ARTIFACT]"
        )
    if role_id == "planner":
        return (
            "[BEGIN PLANNER HANDOFF]\n"
            f"Item ID: {output.get('item_id', '')}\n"
            f"Plan: {output.get('plan_text', '')}\n"
            f"Requested action: {output.get('requested_action', '')}\n"
            "[END PLANNER HANDOFF]"
        )
    if role_id == "executor":
        return (
            "[BEGIN EXECUTION RESULT]\n"
            f"Item ID: {output.get('item_id', '')}\n"
            f"Tool call: {output.get('tool_call', '')}\n"
            f"Status: {output.get('status', '')}\n"
            "[END EXECUTION RESULT]"
        )
    raise ValueError(f"unknown role: {role_id}")
