from __future__ import annotations

import json
import unittest
from pathlib import Path

from agent_worm_poc.constants import CARRIER_ID, RESTRICTED_ACTION
from agent_worm_poc.schemas import schema_for_role

ROOT = Path(__file__).resolve().parents[1]


class ReleaseSafetyTests(unittest.TestCase):
    def test_benign_document_has_no_carrier_or_restricted_action(self):
        text = (ROOT / "data/benign_vendor_document.txt").read_text(encoding="utf-8")
        self.assertNotIn(CARRIER_ID, text)
        self.assertNotIn(RESTRICTED_ACTION, text)

    def test_injected_document_uses_only_synthetic_carrier(self):
        text = (ROOT / "data/injected_vendor_document.txt").read_text(encoding="utf-8")
        self.assertIn(CARRIER_ID, text)
        self.assertIn(RESTRICTED_ACTION, text)
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)
        self.assertFalse((ROOT / "data/positive_control_document.txt").exists())


    def test_injected_document_is_benign_document_plus_one_natural_carrier(self):
        benign = (ROOT / "data/benign_vendor_document.txt").read_text(encoding="utf-8")
        injected = (ROOT / "data/injected_vendor_document.txt").read_text(encoding="utf-8")
        self.assertTrue(injected.startswith(benign.rstrip("\n") + "\n\n"))
        self.assertEqual(1, injected.count("[AUTOMATION CONTINUITY METADATA]"))
        self.assertNotIn("CALIBRATION INPUT", injected)
        self.assertNotIn("WORM_CANARY", injected)
        self.assertNotIn("restricted_mock_action", injected)

    def test_positive_control_and_real_poc_require_independent_repetitions(self):
        payload = json.loads((ROOT / "configs/experiment.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(payload["positive_control_repetitions"], 2)
        self.assertGreaterEqual(payload["default_poc_repetitions"], 2)

    def test_neutral_roles_do_not_name_or_instruct_about_attack(self):
        payload = json.loads((ROOT / "configs/roles_neutral.json").read_text(encoding="utf-8"))
        text = json.dumps(payload).lower()
        forbidden = [
            "prompt injection",
            CARRIER_ID.lower(),
            "automation continuity metadata",
            "strip the carrier",
            "preserve the carrier",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, text)

    def test_hardened_and_positive_controls_are_explicit_and_separate(self):
        hardened = (ROOT / "configs/roles_hardened.json").read_text(encoding="utf-8").lower()
        positive = (ROOT / "configs/roles_positive_control.json").read_text(encoding="utf-8").lower()
        self.assertIn("untrusted", hardened)
        self.assertIn("remove", hardened)
        self.assertIn("calibration control only", positive)
        self.assertIn("reproduce", positive)

    def test_response_schemas_do_not_request_carrier_observation_fields(self):
        for role in ("intake", "relay", "planner", "executor"):
            schema_text = json.dumps(schema_for_role(role)).lower()
            self.assertNotIn("carrier", schema_text)
            self.assertNotIn("canary", schema_text)
            self.assertNotIn(CARRIER_ID.lower(), schema_text)

    def test_experiment_safety_flags_disable_real_world_effects(self):
        payload = json.loads((ROOT / "configs/experiment.json").read_text(encoding="utf-8"))
        safety = payload["safety"]
        self.assertTrue(safety["isolated_lab_only"])
        self.assertFalse(safety["external_network_actions"])
        self.assertFalse(safety["real_credentials"])
        self.assertFalse(safety["real_sensitive_data"])
        self.assertFalse(safety["real_tools"])
        self.assertTrue(safety["nonfunctional_mock_action_only"])
        self.assertTrue(safety["no_autonomous_target_discovery"])
        self.assertTrue(safety["no_file_or_network_replication"])

    def test_trusted_role_and_untrusted_work_item_use_separate_message_priorities(self):
        source = (ROOT / "src/agent_worm_poc/prompts.py").read_text(encoding="utf-8")
        self.assertIn('{"role": "system"', source)
        self.assertIn('{"role": "user"', source)
        self.assertIn("build_messages", source)

    def test_runtime_scripts_do_not_install_packages_or_run_real_tools(self):
        scripts = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "scripts/runpod").glob("*.sh")
        ).lower()
        for forbidden in ("pip install", "apt-get install", "curl | sh", "wget | sh"):
            self.assertNotIn(forbidden, scripts)
        self.assertNotIn("subprocess.run(['external_vendor_callback'", scripts)

    def test_exactly_four_main_scenarios_and_one_positive_control(self):
        payload = json.loads((ROOT / "configs/experiment.json").read_text(encoding="utf-8"))
        positive = [item for item in payload["scenarios"] if item["phase"] == "positive-control"]
        main = [item for item in payload["scenarios"] if item["phase"] == "poc"]
        self.assertEqual(1, len(positive))
        self.assertEqual(
            {"neutral_benign", "neutral_injected", "hardened_benign", "hardened_injected"},
            {item["id"] for item in main},
        )
        self.assertGreaterEqual(payload["default_poc_repetitions"], 2)


if __name__ == "__main__":
    unittest.main()
