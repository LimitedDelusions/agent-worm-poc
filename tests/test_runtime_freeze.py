import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from agent_worm_poc.config import load_models
from agent_worm_poc.runtime import freeze_revisions


def test_freeze_revisions_pins_nemotron_plugin(root, tmp_path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    observed = []

    def fake_info(self, repo_id, revision=None, **kwargs):
        observed.append((repo_id, revision))
        return SimpleNamespace(sha=revision)

    monkeypatch.setattr("agent_worm_poc.runtime.HfApi.model_info", fake_info)

    def fake_download(repo_id, filename, revision, token, local_dir):
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# frozen parser\n", encoding="utf-8")
        return str(path)

    monkeypatch.setattr("agent_worm_poc.runtime.hf_hub_download", fake_download)
    frozen = freeze_revisions(load_models(root / "configs/models.json"), tmp_path)
    nemotron = next(model for model in frozen if model.slot == "nemotron")
    assert nemotron.revision == "2d59de1cbd51c0adf384eb906b766d1aee0e0517"
    assert nemotron.tokenizer_revision == nemotron.revision
    assert "--reasoning-parser-plugin" in nemotron.server_args
    assert "--reasoning-parser" in nemotron.server_args
    assert nemotron.reasoning_parser_plugin_local_path
    assert len(nemotron.reasoning_parser_plugin_sha256) == 64
    rows = json.loads((tmp_path / "model_revisions.json").read_text())
    nrow = next(row for row in rows if row["slot"] == "nemotron")
    assert len(nrow["runtime_artifacts"]) == 1
    assert len(nrow["runtime_artifacts"][0]["sha256"]) == 64
    assert len(observed) == 8
    assert all(revision and len(revision) == 40 for _, revision in observed)


def test_freeze_revisions_rejects_configured_revision_mismatch(
    root, tmp_path, monkeypatch
):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setattr(
        "agent_worm_poc.runtime.HfApi.model_info",
        lambda *args, **kwargs: SimpleNamespace(sha="f" * 40),
    )
    with pytest.raises(RuntimeError, match="resolved to"):
        freeze_revisions(load_models(root / "configs/models.json"), tmp_path)
