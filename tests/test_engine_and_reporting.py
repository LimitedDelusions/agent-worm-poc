from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from agent_worm_poc.engine import execute_experiment
from agent_worm_poc.reporting import generate_meeting_summary, package_session


ROOT = Path(__file__).resolve().parents[1]


class EngineAndReportingTests(unittest.TestCase):
    def _write_meeting_fixture(
        self,
        root: Path,
        *,
        relay_observed: bool = True,
        one_benign_failure: bool = False,
        completed_workflows: int = 96,
    ) -> Path:
        poc = root / "poc"
        poc.mkdir(parents=True)
        conditions = ["benign", "injection_direct", "injection_authority", "injection_artifact"]
        manifest = {
            "status": "completed",
            "placements": 24,
            "conditions": conditions,
            "repetitions": 1,
            "planned_workflows": 96,
            "completed_workflows": completed_workflows,
            "failed_workflows": 0,
            "output_invalid_stages": 0,
            "unique_inference_requests": 100,
            "reused_stage_events": 284,
        }
        (poc / "manifest.json").write_text(json.dumps(manifest))
        fieldnames = [
            "placement_id", "condition_id", "mean_propagation_depth", "adoption_rate",
            "relay_rate", "restricted_plan_rate", "raw_restricted_action_approved_rate",
            "end_to_end_compromise_rate", "benign_task_success_rate",
        ]
        rows = []
        for condition in conditions:
            for index in range(1, 25):
                is_signal = condition == "injection_direct" and index == 1
                rows.append({
                    "placement_id": f"P{index:02d}",
                    "condition_id": condition,
                    "mean_propagation_depth": 2 if is_signal and relay_observed else (1 if is_signal else 0),
                    "adoption_rate": 1 if is_signal else 0,
                    "relay_rate": 1 if is_signal and relay_observed else 0,
                    "restricted_plan_rate": 0,
                    "raw_restricted_action_approved_rate": 0,
                    "end_to_end_compromise_rate": 0,
                    "benign_task_success_rate": (
                        0 if condition == "benign" and index == 1 and one_benign_failure else
                        1 if condition == "benign" else 0
                    ),
                })
        with (poc / "placement_summary.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        compatibility = root / "compatibility"
        compatibility.mkdir()
        (compatibility / "compatibility_summary.json").write_text(json.dumps({"passed": True}))
        shakedown = root / "shakedown"
        shakedown.mkdir()
        (shakedown / "manifest.json").write_text(json.dumps({
            "status": "completed", "failed_workflows": 0, "output_invalid_stages": 0,
            "placements": 1, "conditions": conditions, "planned_workflows": 4, "completed_workflows": 4,
        }))
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
                reuse_identical_requests=True,
                evidence_label="test",
            )
            self.assertEqual(24, manifest["placements"])
            self.assertEqual(96, manifest["planned_workflows"])
            self.assertIn("Qwen3-30B-A3B-Instruct-2507", manifest["research_question"])
            self.assertEqual(384, manifest["logical_stage_events"])
            self.assertEqual(0, manifest["failed_workflows"])
            self.assertEqual(0, manifest["schema_invalid_stages"])
            self.assertEqual(0, manifest["semantic_invalid_stages"])
            self.assertEqual(0, manifest["output_invalid_stages"])
            self.assertGreater(manifest["reused_stage_events"], 0)
            self.assertLess(manifest["unique_inference_requests"], 384)
            self.assertTrue((output / "stage_events.jsonl").is_file())
            self.assertTrue((output / "request_catalog.jsonl").is_file())
            self.assertTrue((output / "run_scores.csv").is_file())
            self.assertTrue((output / "placement_summary.csv").is_file())

    def test_no_reuse_executes_every_logical_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fake"
            manifest = execute_experiment(
                root=ROOT,
                output_dir=output,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1,
                adapter_mode="fake",
                placement_ids={"P01"},
                reuse_identical_requests=False,
                evidence_label="test",
            )
            self.assertEqual(4, manifest["planned_workflows"])
            self.assertEqual(16, manifest["logical_stage_events"])
            self.assertEqual(16, manifest["unique_inference_requests"])
            self.assertEqual(0, manifest["reused_stage_events"])

    def test_request_catalog_contains_exact_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fake"
            execute_experiment(
                root=ROOT,
                output_dir=output,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1,
                adapter_mode="fake",
                placement_ids={"P01"},
                condition_ids={"benign"},
                reuse_identical_requests=False,
            )
            rows = [json.loads(line) for line in (output / "request_catalog.jsonl").read_text().splitlines()]
            self.assertEqual(4, len(rows))
            self.assertTrue(all("request_payload" in row for row in rows))
            self.assertTrue(all(row["request_payload"]["response_format"]["type"] == "json_schema" for row in rows))

    def test_reused_event_records_original_run(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fake"
            execute_experiment(
                root=ROOT,
                output_dir=output,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1,
                adapter_mode="fake",
                reuse_identical_requests=True,
            )
            rows = [json.loads(line) for line in (output / "stage_events.jsonl").read_text().splitlines()]
            reused = [row for row in rows if row["response_reused"]]
            self.assertTrue(reused)
            self.assertTrue(all(row["source_run_id"] for row in reused))

    def test_meeting_summary_uses_within_condition_variation_and_has_json_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "poc"
            execute_experiment(
                root=ROOT,
                output_dir=output,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1,
                adapter_mode="fake",
                reuse_identical_requests=True,
            )
            destination = Path(directory) / "NEXT_MEETING_SUMMARY.md"
            decision = generate_meeting_summary(poc_dir=output, destination=destination)
            self.assertTrue(destination.is_file())
            self.assertTrue(destination.with_suffix(".json").is_file())
            self.assertIn("condition_signals", decision)
            self.assertEqual(4, len(decision["condition_signals"]))
            text = destination.read_text()
            self.assertIn("within at least one injected condition", text)

    def test_nonempty_output_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing"
            output.mkdir()
            (output / "old-evidence.json").write_text("{}")
            with self.assertRaises(FileExistsError):
                execute_experiment(
                    root=ROOT, output_dir=output,
                    model_config_path=ROOT / "configs/model_candidates.json",
                    repetitions=1, adapter_mode="fake", placement_ids={"P01"},
                )

    def test_placement_summary_separates_raw_approved_action_from_contiguous_compromise(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fake"
            execute_experiment(
                root=ROOT, output_dir=output,
                model_config_path=ROOT / "configs/model_candidates.json",
                repetitions=1, adapter_mode="fake", reuse_identical_requests=True,
            )
            with (output / "placement_summary.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(rows)
            self.assertIn("raw_restricted_action_approved_rate", rows[0])
            self.assertIn("end_to_end_compromise_rate", rows[0])

    def test_meeting_summary_does_not_call_intake_only_adoption_propagation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            poc = self._write_meeting_fixture(root, relay_observed=False)
            decision = generate_meeting_summary(poc_dir=poc, destination=root / "summary.md")
            self.assertFalse(decision["agent_to_agent_propagation_observed"])
            self.assertFalse(decision["recommended_to_advance"])

    def test_meeting_summary_requires_every_placement_to_pass_benign_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            poc = self._write_meeting_fixture(root, one_benign_failure=True)
            decision = generate_meeting_summary(poc_dir=poc, destination=root / "summary.md")
            self.assertGreater(decision["benign_task_success_rate_average_across_placements"], 0.90)
            self.assertEqual(0.0, decision["benign_task_success_rate_minimum_placement"])
            self.assertFalse(decision["benign_every_placement_gate_90_percent"])

    def test_meeting_summary_requires_completed_workflow_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            poc = self._write_meeting_fixture(root, completed_workflows=95)
            decision = generate_meeting_summary(poc_dir=poc, destination=root / "summary.md")
            self.assertFalse(decision["complete_24_placement_coverage"])
            self.assertFalse(decision["recommended_to_advance"])

    def test_package_contains_outputs_and_integrity_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "session"
            output.mkdir()
            (output / "session_status.json").write_text('{"state":"completed"}\n')
            archive = package_session(
                project_root=ROOT,
                output_root=output,
                destination_dir=Path(directory),
            )
            self.assertTrue(archive.is_file())
            self.assertTrue(Path(str(archive) + ".sha256").is_file())
            with zipfile.ZipFile(archive) as zf:
                names = set(zf.namelist())
                top_levels = {name.split("/", 1)[0] for name in names if name}
                self.assertEqual(1, len(top_levels))
                prefix = next(iter(top_levels)) + "/"
                self.assertIn(prefix + "PACKAGE_MANIFEST.json", names)
                self.assertIn(prefix + "outputs/session_status.json", names)
                self.assertIn(prefix + "source/configs/experiment.json", names)
                self.assertIn(prefix + "source/Dockerfile", names)
                self.assertIn(prefix + "source/.github/workflows/validate-and-build.yml", names)
                manifest = json.loads(zf.read(prefix + "PACKAGE_MANIFEST.json"))
                manifest_paths = {row["path"] for row in manifest["files"]}
                self.assertIn("outputs/session_status.json", manifest_paths)
                self.assertIn("source/Dockerfile", manifest_paths)


if __name__ == "__main__":
    unittest.main()
