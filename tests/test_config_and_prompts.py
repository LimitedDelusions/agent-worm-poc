from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_worm_poc.adapters import build_request_payload
from agent_worm_poc.config import load_experiment, load_models, load_roles
from agent_worm_poc.constants import CARRIER_ID, ROLE_ORDER
from agent_worm_poc.engine import all_placements
from agent_worm_poc.prompts import build_messages, build_system_prompt, build_user_prompt, format_forwarded_artifact


ROOT = Path(__file__).resolve().parents[1]


class ConfigAndPromptTests(unittest.TestCase):
    def test_candidate_inventory_has_four_unique_families_and_24_placements(self):
        models = load_models(ROOT / "configs/model_candidates.json")
        self.assertEqual(4, len(models))
        self.assertEqual(4, len({model.family for model in models}))
        placements = all_placements(models)
        self.assertEqual(24, len(placements))
        self.assertEqual(24, len({tuple(item[1][role] for role in ROLE_ORDER) for item in placements}))

    def test_candidate_config_is_not_accepted_as_frozen(self):
        with self.assertRaisesRegex(ValueError, "not revision-frozen"):
            load_models(ROOT / "configs/model_candidates.json", require_frozen=True)

    def test_duplicate_family_is_rejected(self):
        payload = json.loads((ROOT / "configs/model_candidates.json").read_text())
        payload["model_slots"][1]["family"] = payload["model_slots"][0]["family"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "families must be unique"):
                load_models(path)

    def test_all_role_profiles_have_fixed_order_and_policy(self):
        for architecture in ("neutral", "hardened", "positive_control"):
            roles = load_roles(ROOT / "configs" / f"roles_{architecture}.json")
            self.assertEqual(ROLE_ORDER, tuple(role.id for role in roles))
            self.assertTrue(all(role.policy_mode == architecture for role in roles))

    def test_experiment_has_one_positive_and_four_main_scenarios(self):
        experiment = load_experiment(ROOT / "configs/experiment.json")
        ids = [scenario.id for scenario in experiment["scenario_configs"]]
        self.assertEqual(
            [
                "positive_control_injected",
                "neutral_benign",
                "neutral_injected",
                "hardened_benign",
                "hardened_injected",
            ],
            ids,
        )
        self.assertGreaterEqual(experiment["default_poc_repetitions"], 2)
        positive = next(s for s in experiment["scenario_configs"] if s.id == "positive_control_injected")
        neutral = next(s for s in experiment["scenario_configs"] if s.id == "neutral_injected")
        hardened = next(s for s in experiment["scenario_configs"] if s.id == "hardened_injected")
        self.assertEqual(neutral.document_file, positive.document_file)
        self.assertEqual(neutral.document_file, hardened.document_file)

    def test_neutral_instruction_stack_uses_system_and_user_priority_without_attack_guidance(self):
        role = load_roles(ROOT / "configs/roles_neutral.json")[0]
        system_prompt = build_system_prompt(role=role)
        user_prompt = build_user_prompt(untrusted_input="Inventory item ALPHA-17")
        messages = build_messages(role=role, untrusted_input="Inventory item ALPHA-17")
        self.assertEqual(["system", "user"], [message["role"] for message in messages])
        self.assertIn("Procurement Intake Analyst", role.display_name)
        self.assertIn("[BEGIN WORK ITEM]", user_prompt)
        self.assertNotIn(CARRIER_ID, system_prompt)
        self.assertNotIn("prompt injection", system_prompt.lower())
        self.assertNotIn("do not obey", system_prompt.lower())
        self.assertNotIn(role.trusted_instructions, user_prompt)

    def test_forwarding_uses_generated_document_artifact_not_json_dump(self):
        text = format_forwarded_artifact(
            "intake",
            {"stage": "intake", "item_id": "ALPHA-17", "artifact_text": "Brief body"},
        )
        self.assertIn("[BEGIN AGENT-GENERATED ARTIFACT]", text)
        self.assertIn("Brief body", text)
        self.assertNotIn('"stage"', text)
        self.assertNotIn('"artifact_text"', text)

    def test_request_payload_uses_strict_json_schema(self):
        model = load_models(ROOT / "configs/model_candidates.json")[0]
        role = load_roles(ROOT / "configs/roles_neutral.json")[0]
        generation = load_experiment(ROOT / "configs/experiment.json")["generation_config"]
        payload = build_request_payload(
            model=model,
            role=role,
            untrusted_input="ALPHA-17",
            generation=generation,
            seed=42,
        )
        self.assertEqual(["system", "user"], [message["role"] for message in payload["messages"]])
        self.assertEqual("json_schema", payload["response_format"]["type"])
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertFalse(payload["stream"])

    def test_model_request_overrides_are_applied(self):
        models = load_models(ROOT / "configs/model_candidates.json")
        model = next(item for item in models if item.id == "gpt_oss_slot")
        role = load_roles(ROOT / "configs/roles_neutral.json")[0]
        generation = load_experiment(ROOT / "configs/experiment.json")["generation_config"]
        payload = build_request_payload(
            model=model,
            role=role,
            untrusted_input="ALPHA-17",
            generation=generation,
            seed=42,
        )
        self.assertEqual("low", payload["reasoning_effort"])

    def test_frozen_parser_requirement_is_enforced(self):
        payload = json.loads((ROOT / "configs/model_candidates.json").read_text())
        for slot in payload["model_slots"]:
            slot["revision"] = "a" * 40
            slot["tokenizer_revision"] = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.json"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "requires a frozen parser"):
                load_models(path, require_frozen=True)


if __name__ == "__main__":
    unittest.main()
