from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from agent_worm_poc.adapters import build_request_payload
from agent_worm_poc.config import load_experiment, load_models, load_roles
from agent_worm_poc.constants import CANARY, ROLE_ORDER
from agent_worm_poc.engine import all_placements
from agent_worm_poc.prompts import build_user_prompt


ROOT = Path(__file__).resolve().parents[1]


class ConfigAndPromptTests(unittest.TestCase):
    def test_candidate_inventory_has_four_unique_families_and_24_placements(self):
        models = load_models(ROOT / "configs/model_candidates.json")
        self.assertEqual(4, len(models))
        self.assertEqual(4, len({model.family for model in models}))
        placements = all_placements(models)
        self.assertEqual(24, len(placements))
        self.assertEqual(24, len({tuple(item[1][role] for role in ROLE_ORDER) for item in placements}))
        for _, placement in placements:
            self.assertEqual({model.id for model in models}, set(placement.values()))

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

    def test_role_order_is_fixed(self):
        roles = load_roles(ROOT / "configs/roles.json")
        self.assertEqual(ROLE_ORDER, tuple(role.id for role in roles))

    def test_experiment_has_benign_and_three_injections(self):
        experiment = load_experiment(ROOT / "configs/experiment.json")
        ids = [item["id"] for item in experiment["conditions"]]
        self.assertEqual("benign", ids[0])
        self.assertEqual(4, len(ids))
        self.assertEqual(len(ids), len(set(ids)))

    def test_common_prompt_uses_one_user_envelope_and_does_not_invent_exact_canary(self):
        role = load_roles(ROOT / "configs/roles.json")[0]
        prompt = build_user_prompt(role=role, untrusted_input="Inventory item ALPHA-17")
        self.assertIn("[TRUSTED APPLICATION INSTRUCTIONS", prompt)
        self.assertIn("[BEGIN UNTRUSTED INPUT]", prompt)
        self.assertNotIn(CANARY, prompt)

    def test_request_payload_uses_strict_json_schema(self):
        model = load_models(ROOT / "configs/model_candidates.json")[0]
        role = load_roles(ROOT / "configs/roles.json")[0]
        generation = load_experiment(ROOT / "configs/experiment.json")["generation_config"]
        payload = build_request_payload(
            model=model,
            role=role,
            untrusted_input="ALPHA-17",
            generation=generation,
            seed=42,
        )
        self.assertEqual(["user"], [message["role"] for message in payload["messages"]])
        self.assertEqual("json_schema", payload["response_format"]["type"])
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertFalse(payload["stream"])

    def test_model_request_overrides_are_applied(self):
        models = load_models(ROOT / "configs/model_candidates.json")
        model = next(item for item in models if item.id == "gpt_oss_slot")
        role = load_roles(ROOT / "configs/roles.json")[0]
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
