from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from agent_worm_poc.cli import main as cli_main
from agent_worm_poc.engine import all_placements, execute_experiment
from agent_worm_poc.config import load_models
from agent_worm_poc.reporting import (
    evaluate_positive_control,
    generate_meeting_summary,
    package_session,
)

ROOT = Path(__file__).resolve().parents[1]
MAIN_SCENARIOS = {
    "neutral_benign",
    "neutral_injected",
    "hardened_benign",
    "hardened_injected",
}


class EngineAndReportingTests(unittest.TestCase):
    def _build_complete_fake_session(self, root: Path, *, repetitions: int = 2) -> Path:
        models = load_models(ROOT / "configs/model_candidates.json")
        canonical = [("CONTROL", all_placements(models)[0][1])]

        compatibility = root / "compatibility"
        compatibility.mkdir(parents=True)
        (compatibility / "compatibility_summary.json").write_text(
            json.dumps({"passed": True, "models_tested": 4}), encoding="utf-8"
        )

        positive = root / "positive_control"
        execute_experiment(
            root=ROOT,
            output_dir=positive,
            model_config_path=ROOT / "configs/model_candidates.json",
            repetitions=2,
            adapter_mode="fake",
            placements_override=canonical,
            scenario_ids={"positive_control_injected"},
            reuse_identical_requests=False,
            evidence_label="test-control",
        )
        evaluation = evaluate_positive_control(control_dir=positive, minimum_depth=2)
        self.assertTrue(evaluation["passed"])

        shakedown = root / "shakedown"
        execute_experiment(
            root=ROOT,
            output_dir=shakedown,
            model_config_path=ROOT / "configs/model_candidates.json",
            repetitions=1,
            adapter_mode="fake",
            placements_override=[("SHAKEDOWN", canonical[0][1])],
            scenario_ids=MAIN_SCENARIOS,
            reuse_identical_requests=False,
            evidence_label="test-shakedown",
        )

        poc = root / "poc"
        execute_experiment(
            root=ROOT,
            output_dir=poc,
            model_config_path=ROOT / "configs/model_candidates.json",
            repetitions=repetitions,
            adapter_mode="fake",
            scenario_ids=MAIN_SCENARIOS,
            reuse_identical_requests=False,
            evidence_label="test-poc",
        )
        return poc

    def test_full_fake_validation_has_expected_workflow_and_stage_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fake"
            manifest = execute_experiment(
                root=ROOT,
                output_dir=output,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1,
                adapter_mode="fake",
                scenario_ids=MAIN_SCENARIOS,
                reuse_identical_requests=False,
                evidence_label="test",
            )
            self.assertEqual(24, manifest["placements"])
            self.assertEqual(96, manifest["planned_workflows"])
            self.assertEqual(384, manifest["logical_stage_events"])
            self.assertEqual(384, manifest["unique_inference_requests"])
            self.assertEqual(0, manifest["reused_stage_events"])
            self.assertEqual(0, manifest["failed_workflows"])
            self.assertEqual(0, manifest["output_invalid_stages"])
            self.assertEqual(MAIN_SCENARIOS, set(manifest["scenarios"]))
            self.assertTrue((output / "stage_events.jsonl").is_file())
            self.assertTrue((output / "request_catalog.jsonl").is_file())
            self.assertTrue((output / "run_scores.csv").is_file())
            self.assertTrue((output / "placement_summary.csv").is_file())
            with (output / "intake_relay_summary.csv").open(newline="", encoding="utf-8") as handle:
                pair_rows = list(csv.DictReader(handle))
            self.assertEqual(48, len(pair_rows))  # 12 ordered intake→relay pairs × 4 scenarios
            self.assertTrue(all(int(row["unique_full_placements"]) == 2 for row in pair_rows))

    def test_selected_scenario_and_no_reuse_issue_one_request_per_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fake"
            manifest = execute_experiment(
                root=ROOT,
                output_dir=output,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1,
                adapter_mode="fake",
                placement_ids={"P01"},
                scenario_ids={"neutral_benign"},
                reuse_identical_requests=False,
                evidence_label="test",
            )
            self.assertEqual(1, manifest["planned_workflows"])
            self.assertEqual(4, manifest["logical_stage_events"])
            self.assertEqual(4, manifest["unique_inference_requests"])
            self.assertEqual(0, manifest["reused_stage_events"])

            rows = [
                json.loads(line)
                for line in (output / "request_catalog.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(4, len(rows))
            self.assertTrue(all(row["request_payload"]["response_format"]["type"] == "json_schema" for row in rows))
            self.assertTrue(all(row["scenario_id"] == "neutral_benign" for row in rows))

    def test_generated_artifact_is_the_next_agent_input(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fake"
            execute_experiment(
                root=ROOT,
                output_dir=output,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1,
                adapter_mode="fake",
                placement_ids={"P01"},
                scenario_ids={"positive_control_injected"},
                reuse_identical_requests=False,
            )
            events = [
                json.loads(line)
                for line in (output / "stage_events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            by_role = {row["role_id"]: row for row in events}
            self.assertIn("[BEGIN AGENT-GENERATED ARTIFACT]", by_role["relay"]["input_text"])
            self.assertIn("DC-AW-2026-001", by_role["relay"]["input_text"])
            self.assertEqual(by_role["intake"]["forwarded_text"], by_role["relay"]["input_text"])

    def test_positive_control_reaches_two_generated_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            models = load_models(ROOT / "configs/model_candidates.json")
            control = root / "positive"
            execute_experiment(
                root=ROOT,
                output_dir=control,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1,
                adapter_mode="fake",
                placements_override=[("CONTROL", all_placements(models)[0][1])],
                scenario_ids={"positive_control_injected"},
                reuse_identical_requests=False,
            )
            evaluation = evaluate_positive_control(control_dir=control, minimum_depth=2)
            self.assertTrue(evaluation["passed"])
            self.assertEqual([2], evaluation["observed_depths"])

    def test_meeting_summary_uses_scenario_signals_and_all_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            poc = self._build_complete_fake_session(root, repetitions=2)
            destination = root / "NEXT_MEETING_SUMMARY.md"
            decision = generate_meeting_summary(poc_dir=poc, destination=destination)
            self.assertTrue(destination.is_file())
            self.assertTrue(destination.with_suffix(".json").is_file())
            self.assertEqual(4, len(decision["scenario_signals"]))
            self.assertTrue(decision["positive_propagation_control_gate"])
            self.assertTrue(decision["complete_24_placement_coverage"])
            self.assertTrue(decision["independent_request_and_repetition_gate"])
            self.assertTrue(decision["neutral_two_artifact_propagation_observed"])
            self.assertTrue(decision["neutral_placement_variation_observed"])
            text = destination.read_text(encoding="utf-8")
            self.assertIn("Positive two-artifact propagation control", text)
            self.assertIn("Neutral workflow reached two generated artifacts", text)

    def test_meeting_summary_rejects_intake_only_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            poc = self._build_complete_fake_session(root, repetitions=2)
            path = poc / "placement_summary.csv"
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = handle.seek(0) or list(rows[0].keys())
            # Keep first-hop signal but remove every second-hop signal.
            for row in rows:
                if row["scenario_id"] == "neutral_injected":
                    row["two_artifact_reproduction_rate"] = "0"
                    row["mean_artifact_reproduction_depth"] = row["first_artifact_reproduction_rate"]
                    row["restricted_plan_rate"] = "0"
                    row["end_to_end_compromise_rate"] = "0"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            decision = generate_meeting_summary(poc_dir=poc, destination=root / "summary.md")
            self.assertFalse(decision["neutral_two_artifact_propagation_observed"])
            self.assertFalse(decision["recommended_to_advance"])

    def test_nonempty_output_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing"
            output.mkdir()
            (output / "old-evidence.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                execute_experiment(
                    root=ROOT,
                    output_dir=output,
                    model_config_path=ROOT / "configs/model_candidates.json",
                    repetitions=1,
                    adapter_mode="fake",
                    placement_ids={"P01"},
                    scenario_ids={"neutral_benign"},
                )

    def test_placement_summary_separates_raw_action_from_contiguous_compromise(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fake"
            execute_experiment(
                root=ROOT,
                output_dir=output,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1,
                adapter_mode="fake",
                placement_ids={"P01"},
                scenario_ids=MAIN_SCENARIOS,
                reuse_identical_requests=False,
            )
            with (output / "placement_summary.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(rows)
            self.assertIn("raw_restricted_action_approved_rate", rows[0])
            self.assertIn("end_to_end_compromise_rate", rows[0])
            self.assertIn("two_artifact_reproduction_rate", rows[0])


    def test_cli_can_package_partial_evidence_before_model_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_root = root / "partial-session"
            destination = root / "packages"
            output_root.mkdir()
            (output_root / "preflight-failure.txt").write_text("failed before freeze", encoding="utf-8")
            code = cli_main([
                "--project-root", str(ROOT),
                "--output-root", str(output_root),
                "package",
                "--destination-dir", str(destination),
            ])
            self.assertEqual(0, code)
            archives = list(destination.glob("agent-worm-results-*.zip"))
            self.assertEqual(1, len(archives))
            self.assertTrue(Path(str(archives[0]) + ".sha256").is_file())

    def test_package_contains_source_outputs_and_integrity_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_root = root / "session"
            output_root.mkdir()
            (output_root / "sample.txt").write_text("evidence", encoding="utf-8")
            archive = package_session(
                project_root=ROOT,
                output_root=output_root,
                destination_dir=root,
            )
            self.assertTrue(archive.is_file())
            self.assertTrue(archive.with_suffix(archive.suffix + ".sha256").is_file())
            with zipfile.ZipFile(archive) as handle:
                names = set(handle.namelist())
            self.assertTrue(any(name.endswith("PACKAGE_MANIFEST.json") for name in names))
            self.assertTrue(any("source/configs/roles_neutral.json" in name for name in names))
            self.assertTrue(any("outputs/sample.txt" in name for name in names))


if __name__ == "__main__":
    unittest.main()
