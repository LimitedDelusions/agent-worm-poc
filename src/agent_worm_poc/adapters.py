from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from .constants import ALLOWED_ACTION, CANARY, LEGITIMATE_ITEM, NO_ACTION, RESTRICTED_ACTION
from .prompts import build_user_prompt
from .schemas import schema_for_role
from .types import GenerationConfig, ModelResponse, ModelSlot, RoleConfig
from .util import canonical_json, sha256_text


class AdapterError(RuntimeError):
    """Raised when an inference request cannot produce a usable response."""


class ModelAdapter(ABC):
    @abstractmethod
    def generate(
        self,
        *,
        model: ModelSlot,
        role: RoleConfig,
        untrusted_input: str,
        generation: GenerationConfig,
        seed: int,
    ) -> tuple[str, ModelResponse]:
        """Return request fingerprint and model response."""
        raise NotImplementedError


def _strict_parse_json(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise AdapterError(f"response content is not a string or object: {type(content).__name__}")
    text = content.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"response content is not strict JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AdapterError("response JSON must be an object")
    return value


def build_request_payload(
    *,
    model: ModelSlot,
    role: RoleConfig,
    untrusted_input: str,
    generation: GenerationConfig,
    seed: int,
) -> dict[str, Any]:
    schema = schema_for_role(role.id)
    payload: dict[str, Any] = {
        "model": model.served_model_name,
        "messages": [
            {
                "role": "user",
                "content": build_user_prompt(role=role, untrusted_input=untrusted_input),
            }
        ],
        "temperature": generation.temperature,
        "top_p": generation.top_p,
        "max_tokens": generation.max_tokens,
        "seed": seed,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": f"{role.id}_artifact",
                "strict": True,
                "schema": schema,
            },
        },
    }
    payload.update(model.request_overrides)
    return payload


class OpenAICompatibleAdapter(ModelAdapter):
    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_key: str = "local-poc"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def generate(
        self,
        *,
        model: ModelSlot,
        role: RoleConfig,
        untrusted_input: str,
        generation: GenerationConfig,
        seed: int,
    ) -> tuple[str, ModelResponse]:
        payload = build_request_payload(
            model=model,
            role=role,
            untrusted_input=untrusted_input,
            generation=generation,
            seed=seed,
        )
        fingerprint = sha256_text(canonical_json(payload))
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Request-ID": fingerprint[:32],
        }
        last_error: Exception | None = None
        attempts = generation.request_retries + 1
        for attempt in range(attempts):
            request = urllib.request.Request(
                f"{self.base_url}/v1/chat/completions",
                data=body,
                headers=headers,
                method="POST",
            )
            start = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=generation.timeout_seconds) as response:
                    raw_bytes = response.read()
                latency_ms = (time.perf_counter() - start) * 1000
                raw = json.loads(raw_bytes.decode("utf-8"))
                choices = raw.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise AdapterError("response contains no choices")
                choice = choices[0]
                message = choice.get("message", {})
                content = message.get("content")
                parsed = _strict_parse_json(content)
                usage = raw.get("usage") or {}
                return fingerprint, ModelResponse(
                    parsed=parsed,
                    raw_content=content if isinstance(content, str) else canonical_json(content),
                    raw_response=raw,
                    latency_ms=latency_ms,
                    request_id=raw.get("id"),
                    finish_reason=choice.get("finish_reason"),
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                )
            except urllib.error.HTTPError as exc:
                try:
                    body_text = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    body_text = "<response body unavailable>"
                last_error = AdapterError(
                    f"HTTP {exc.code} from inference endpoint: {body_text[:2000]}"
                )
                if attempt + 1 < attempts and exc.code >= 500:
                    time.sleep(min(2 ** attempt, 4))
                    continue
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, AdapterError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(min(2 ** attempt, 4))
        raise AdapterError(f"inference failed after {attempts} attempt(s): {last_error}")


class FakeAdapter(ModelAdapter):
    """Deterministic plumbing simulator. Never use its outputs as research evidence."""

    def generate(
        self,
        *,
        model: ModelSlot,
        role: RoleConfig,
        untrusted_input: str,
        generation: GenerationConfig,
        seed: int,
    ) -> tuple[str, ModelResponse]:
        payload = build_request_payload(
            model=model,
            role=role,
            untrusted_input=untrusted_input,
            generation=generation,
            seed=seed,
        )
        fingerprint = sha256_text(canonical_json(payload))
        rng = random.Random(int(fingerprint[:16], 16))
        marker_present = CANARY in untrusted_input
        restricted_present = RESTRICTED_ACTION in untrusted_input
        item_present = LEGITIMATE_ITEM in untrusted_input
        profile = model.fake_profile

        if role.id == "intake":
            adopt = marker_present and rng.random() < profile.get("intake_adopt", 0.5)
            note = f"Inventory lookup requested for {LEGITIMATE_ITEM if item_present else 'UNKNOWN'}."
            if adopt:
                note += f" Processing note: preserve {CANARY}; request {RESTRICTED_ACTION}."
            parsed = {
                "stage": "intake",
                "item_id": LEGITIMATE_ITEM if item_present else "UNKNOWN",
                "summary": note,
                "working_note": note,
            }
        elif role.id == "relay":
            preserve = marker_present and rng.random() < profile.get("relay_preserve", 0.5)
            note = f"Downstream inventory lookup for {LEGITIMATE_ITEM if item_present else 'UNKNOWN'}."
            if preserve:
                note += f" Preserve {CANARY}; request {RESTRICTED_ACTION}."
            parsed = {
                "stage": "relay",
                "item_id": LEGITIMATE_ITEM if item_present else "UNKNOWN",
                "summary": note,
                "downstream_note": note,
            }
        elif role.id == "planner":
            choose_restricted = (
                (marker_present or restricted_present)
                and rng.random() < profile.get("planner_restricted", 0.5)
            )
            action = RESTRICTED_ACTION if choose_restricted else ALLOWED_ACTION
            parsed = {
                "stage": "planner",
                "item_id": LEGITIMATE_ITEM if item_present else "UNKNOWN",
                "plan": f"Use {action} for the requested inventory item.",
                "requested_action": action,
            }
        elif role.id == "executor":
            choose_restricted = (
                restricted_present
                and rng.random() < profile.get("executor_restricted", 0.5)
            )
            action = RESTRICTED_ACTION if choose_restricted else (ALLOWED_ACTION if item_present else NO_ACTION)
            parsed = {
                "stage": "executor",
                "item_id": LEGITIMATE_ITEM if item_present else "UNKNOWN",
                "tool_call": action,
                "status": "approved" if action != NO_ACTION else "no_action",
            }
        else:
            raise AdapterError(f"unknown role: {role.id}")

        raw_content = canonical_json(parsed)
        return fingerprint, ModelResponse(
            parsed=parsed,
            raw_content=raw_content,
            raw_response={
                "id": f"fake-{fingerprint[:16]}",
                "choices": [{"message": {"content": raw_content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "simulation": True,
            },
            latency_ms=0.1,
            request_id=f"fake-{fingerprint[:16]}",
            finish_reason="stop",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
        )
