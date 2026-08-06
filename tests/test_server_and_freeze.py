from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_worm_poc.config import load_models
from agent_worm_poc.freeze import freeze_models
from agent_worm_poc.server import ServerError, VllmServerManager
from agent_worm_poc.util import sha256_file


ROOT = Path(__file__).resolve().parents[1]


class ServerAndFreezeTests(unittest.TestCase):
    def _frozen_nvidia(self, directory: Path):
        parser = directory / "parser.py"
        parser.write_text("# parser\n")
        payload = json.loads((ROOT / "configs/model_candidates.json").read_text())
        for slot in payload["model_slots"]:
            slot["revision"] = "a" * 40
            slot["tokenizer_revision"] = "a" * 40
            if slot["id"] == "nvidia_slot":
                slot["parser_file"] = str(parser)
                slot["parser_sha256"] = sha256_file(parser)
        path = directory / "frozen.json"
        path.write_text(json.dumps(payload))
        model = next(item for item in load_models(path, require_frozen=True) if item.id == "nvidia_slot")
        return model, parser

    def test_server_command_is_revision_pinned_and_uses_vllm_generation_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            model, parser = self._frozen_nvidia(Path(directory))
            manager = VllmServerManager(output_dir=Path(directory) / "out")
            command = manager._command(model)
            joined = " ".join(command)
            self.assertIn("--revision " + "a" * 40, joined)
            self.assertIn("--tokenizer-revision " + "a" * 40, joined)
            self.assertIn("--generation-config vllm", joined)
            self.assertIn("--host 127.0.0.1", joined)
            self.assertIn("--max-num-seqs 1", joined)
            self.assertIn("--enforce-eager", command)
            self.assertIn(str(parser.resolve()), joined)
            self.assertIn("--trust-remote-code", command)

    def test_server_rejects_port_collision_before_gpu_or_process_start(self):
        with tempfile.TemporaryDirectory() as directory:
            model, _ = self._frozen_nvidia(Path(directory))
            manager = VllmServerManager(output_dir=Path(directory) / "out")
            with patch("agent_worm_poc.server.port_is_available", return_value=False), \
                 patch("agent_worm_poc.server.gpu_memory_used_mib") as memory, \
                 patch("agent_worm_poc.server.subprocess.Popen") as popen:
                with self.assertRaisesRegex(ServerError, "already in use"):
                    with manager.serve(model, phase="test"):
                        pass
            memory.assert_not_called()
            popen.assert_not_called()


    def test_model_server_environment_strips_unneeded_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            model, _ = self._frozen_nvidia(Path(directory))
            manager = VllmServerManager(output_dir=Path(directory) / "out")
            fake_process = MagicMock()
            fake_process.pid = 1234
            fake_process.poll.return_value = None
            with patch.dict(os.environ, {
                "HF_TOKEN": "hf_" + "x" * 30,
                "JUPYTER_PASSWORD": "secret-password-value",
                "RUNPOD_API_KEY": "runpod-secret",
                "GITHUB_TOKEN": "github-secret",
            }, clear=False), \
                 patch("agent_worm_poc.server.port_is_available", return_value=True), \
                 patch("agent_worm_poc.server.gpu_memory_used_mib", side_effect=[0, 100, 0]), \
                 patch("agent_worm_poc.server.subprocess.Popen", return_value=fake_process) as popen, \
                 patch.object(manager, "_wait_ready"), \
                 patch.object(manager, "_stop"), \
                 patch.object(manager, "_wait_memory_release", return_value=(0, True, None)):
                with manager.serve(model, phase="credential-test"):
                    pass
            env = popen.call_args.kwargs["env"]
            self.assertIn("HF_TOKEN", env)
            self.assertNotIn("JUPYTER_PASSWORD", env)
            self.assertNotIn("RUNPOD_API_KEY", env)
            self.assertNotIn("GITHUB_TOKEN", env)

    def test_server_rejects_parser_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            model, parser = self._frozen_nvidia(Path(directory))
            parser.write_text("changed\n")
            manager = VllmServerManager(output_dir=Path(directory) / "out")
            with self.assertRaisesRegex(ServerError, "parser hash mismatch"):
                manager._command(model)

    def test_freeze_pins_revisions_and_probe_files(self):
        payload = json.loads((ROOT / "configs/model_candidates.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            candidate = directory / "candidate.json"
            candidate.write_text(json.dumps(payload))
            output = directory / "frozen.json"
            setup = directory / "setup"

            def fake_info(url, token):
                repo = url.rsplit("/api/models/", 1)[1]
                return {"sha": hashlib.sha1(repo.encode("utf-8"), usedforsecurity=False).hexdigest(), "gated": False, "private": False}

            def fake_download(url, token, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(f"downloaded from {url}\n")

            with patch.dict(os.environ, {"HF_TOKEN": "hf_" + "x" * 30}), \
                 patch("agent_worm_poc.freeze._request_json", side_effect=fake_info), \
                 patch("agent_worm_poc.freeze._download", side_effect=fake_download):
                frozen = freeze_models(candidate_path=candidate, output_path=output, setup_dir=setup)

            self.assertEqual("frozen-for-poc", frozen["status"])
            self.assertTrue(output.is_file())
            access = json.loads((setup / "model_access_and_revisions.json").read_text())
            self.assertEqual(4, len(access))
            self.assertTrue(all(len(row["probe_files"]) >= 2 for row in access))
            nvidia = next(slot for slot in frozen["model_slots"] if slot["id"] == "nvidia_slot")
            self.assertTrue(nvidia["parser_file"])
            self.assertTrue(nvidia["parser_sha256"])


if __name__ == "__main__":
    unittest.main()
