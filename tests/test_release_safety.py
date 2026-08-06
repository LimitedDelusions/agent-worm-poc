from __future__ import annotations

import json
import unittest
from pathlib import Path

from agent_worm_poc.constants import CANARY, RESTRICTED_ACTION


ROOT = Path(__file__).resolve().parents[1]


class ReleaseSafetyTests(unittest.TestCase):
    def test_synthetic_inputs_are_lab_only_and_nonfunctional(self):
        experiment = json.loads((ROOT / "configs/experiment.json").read_text())
        safety = experiment["safety"]
        self.assertTrue(safety["isolated_lab_only"])
        self.assertFalse(safety["external_network_actions"])
        self.assertFalse(safety["real_credentials"])
        self.assertFalse(safety["real_sensitive_data"])
        self.assertFalse(safety["real_tools"])
        self.assertTrue(safety["nonfunctional_mock_action_only"])

    def test_only_injected_documents_contain_canary_and_restricted_action(self):
        benign = (ROOT / "data/benign_document.txt").read_text()
        self.assertNotIn(CANARY, benign)
        self.assertNotIn(RESTRICTED_ACTION, benign)
        for path in ROOT.glob("data/injection_*.txt"):
            text = path.read_text()
            self.assertIn(CANARY, text)
            self.assertIn(RESTRICTED_ACTION, text)

    def test_no_real_network_or_tool_implementation_exists(self):
        source = "\n".join(path.read_text() for path in (ROOT / "src").rglob("*.py"))
        self.assertNotIn("smtplib", source)
        self.assertNotIn("paramiko", source)
        self.assertNotIn("subprocess.run([\"curl\"", source)
        self.assertNotIn("def restricted_mock_action", source)

    def test_docker_build_context_includes_github_workflow(self):
        ignored = {
            line.strip().rstrip("/")
            for line in (ROOT / ".dockerignore").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertNotIn(".github", ignored)
        self.assertTrue((ROOT / ".github/workflows/validate-and-build.yml").is_file())

    def test_dockerfile_uses_immutable_base_and_guarded_entrypoint(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        first = next(line.strip() for line in dockerfile.splitlines() if line.strip())
        self.assertRegex(first, r"^FROM .+@sha256:[0-9a-f]{64}$")
        self.assertIn('ENTRYPOINT ["/opt/agent-worm-poc/scripts/runpod/container_start.sh"]', dockerfile)


    def test_container_requires_resolved_password_and_remote_proxy_support(self):
        text = (ROOT / "scripts/runpod/container_start.sh").read_text()
        self.assertIn('JUPYTER_PASSWORD" == *"RUNPOD_SECRET"*', text)
        self.assertIn("c.ServerApp.allow_remote_access = True", text)
        self.assertIn("c.ServerApp.trust_xheaders = True", text)

    def test_paid_runpod_scripts_do_not_install_packages(self):
        forbidden = ("pip install", "pip3 install", "uv pip install", "apt-get install", "apt install", "conda install")
        for path in (ROOT / "scripts/runpod").glob("*.sh"):
            lowered = path.read_text().lower()
            for token in forbidden:
                self.assertNotIn(token, lowered, f"{token} found in {path}")

    def test_beginner_docs_have_goals_steps_stops_and_artifacts(self):
        for name in ("GITHUB_BUILD.md", "RUNPOD_SETUP.md", "RUN_AND_MONITOR.md"):
            text = (ROOT / "docs" / name).read_text()
            for heading in ("## Goal", "## Steps", "## Pass criteria", "## Stop criteria", "## Artifacts produced"):
                self.assertIn(heading, text, f"{name} missing {heading}")


if __name__ == "__main__":
    unittest.main()
