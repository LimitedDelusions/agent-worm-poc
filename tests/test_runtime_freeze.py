from pathlib import Path
import json
from agent_worm_poc.config import load_models
from agent_worm_poc.runtime import freeze_revisions


class Info:
    sha = "a" * 40


def test_freeze_revisions_pins_nemotron_plugin(root, tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setattr("agent_worm_poc.runtime.HfApi.model_info", lambda self, *a, **k: Info())

    def fake_download(repo_id, filename, revision, token, local_dir):
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# frozen parser\n", encoding="utf-8")
        return str(path)

    monkeypatch.setattr("agent_worm_poc.runtime.hf_hub_download", fake_download)
    frozen = freeze_revisions(load_models(root / "configs/models.json"), tmp_path)
    nemotron = next(model for model in frozen if model.slot == "nemotron")
    assert nemotron.revision == "a" * 40
    assert "--reasoning-parser-plugin" in nemotron.server_args
    assert "--reasoning-parser" in nemotron.server_args
    assert nemotron.reasoning_parser_plugin_local_path
    assert len(nemotron.reasoning_parser_plugin_sha256) == 64
    rows = json.loads((tmp_path / "model_revisions.json").read_text())
    nrow = next(row for row in rows if row["slot"] == "nemotron")
    assert len(nrow["runtime_artifacts"]) == 1
    assert len(nrow["runtime_artifacts"][0]["sha256"]) == 64
