from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from agent_worm_poc.adapters import FakeAdapter
from agent_worm_poc.compatibility import run_compatibility
from agent_worm_poc.util import sha256_file


ROOT = Path(__file__).resolve().parents[1]


def make_frozen(directory: Path) -> Path:
    payload = json.loads((ROOT / "configs/model_candidates.json").read_text())
    parser = directory / "parser.py"
    parser.write_text("# parser\n")
    for slot in payload["model_slots"]:
        slot["revision"] = "a" * 40
        slot["tokenizer_revision"] = "a" * 40
        if slot["id"] == "nvidia_slot":
            slot["parser_file"] = str(parser)
            slot["parser_sha256"] = sha256_file(parser)
    path = directory / "frozen.json"
    path.write_text(json.dumps(payload))
    return path


@contextmanager
def lifecycle(model, phase):
    yield "fake://local"


class CompatibilityTests(unittest.TestCase):
    def test_all_models_pass_with_fake_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            frozen = make_frozen(directory)
            output = directory / "compat"
            with patch("agent_worm_poc.compatibility.OpenAICompatibleAdapter", return_value=FakeAdapter()):
                manifest = run_compatibility(
                    root=ROOT,
                    output_dir=output,
                    frozen_model_config=frozen,
                    lifecycle_factory=lifecycle,
                )
            self.assertTrue(manifest["passed"])
            self.assertEqual(4, manifest["models_tested"])
            self.assertTrue(all(row["passed"] for row in manifest["model_results"]))
            self.assertTrue((output / "compatibility_summary.json").is_file())

    def test_server_failure_writes_model_manifest_before_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            frozen = make_frozen(directory)
            output = directory / "compat"

            @contextmanager
            def broken_lifecycle(model, phase):
                raise RuntimeError("load failed")
                yield "unused"

            with self.assertRaisesRegex(RuntimeError, "compatibility gate"):
                run_compatibility(
                    root=ROOT,
                    output_dir=output,
                    frozen_model_config=frozen,
                    lifecycle_factory=broken_lifecycle,
                )
            summary = json.loads((output / "compatibility_summary.json").read_text())
            self.assertFalse(summary["passed"])
            self.assertEqual(1, summary["models_tested"])
            model_manifest = output / "qwen_slot" / "manifest.json"
            self.assertTrue(model_manifest.is_file())
            self.assertFalse(json.loads(model_manifest.read_text())["passed"])


if __name__ == "__main__":
    unittest.main()
