import json

from agent_worm_poc.util import write_json


def test_write_json_atomically_replaces_document_without_temp_files(tmp_path):
    path = tmp_path / "RUN_STATUS.json"
    write_json(path, {"status": "running"})
    write_json(path, {"status": "completed", "value": "ok"})

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "status": "completed",
        "value": "ok",
    }
    assert list(tmp_path.glob(".RUN_STATUS.json.*.tmp")) == []
