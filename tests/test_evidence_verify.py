import json
import hashlib
import shutil

import pytest

from agent_worm_poc.evidence import package_results
from agent_worm_poc.evidence_verify import verify_evidence,verify_transfer_manifest


def test_verify_evidence_checks_full_bundle(root, tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    status = {
        "run_id": "test-run",
        "release": version,
        "status": "completed",
        "execution_status": "completed",
        "evidence_status": "verified",
        "outcome_classification": "valid_null_no_ordered_pair_rate_variation",
    }
    (run / "RUN_STATUS.json").write_text(json.dumps(status) + "\n", encoding="utf-8")
    output = tmp_path / "agent-worm-results-test-run.zip"
    package_results(root, run, output)
    shutil.copy2(run / "RUN_STATUS.json", tmp_path / "RUN_STATUS.json")

    result = verify_evidence(output, version)

    assert result["passed"] is True
    assert result["run_id"] == "test-run"
    assert result["status"] == "completed"


def test_verify_evidence_rejects_standalone_status_mismatch(root, tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "RUN_STATUS.json").write_text('{"status":"completed"}\n', encoding="utf-8")
    output = tmp_path / "agent-worm-results-test-run.zip"
    package_results(root, run, output)
    (tmp_path / "RUN_STATUS.json").write_text('{"status":"aborted"}\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="differs"):
        verify_evidence(output)


def test_verify_transfer_manifest_requires_exact_file_set_and_hashes(tmp_path):
    nested=tmp_path/"run";nested.mkdir()
    first=tmp_path/"RUN_STATUS.json";first.write_text('{"status":"aborted"}\n')
    second=nested/"server.log";second.write_text("complete\n")
    rows=[]
    for path in (first,second):
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  ./{path.relative_to(tmp_path).as_posix()}")
    (tmp_path/"SHA256SUMS").write_text("\n".join(rows)+"\n")

    assert verify_transfer_manifest(tmp_path)["file_count"]==2
    second.write_text("tampered\n")
    with pytest.raises(RuntimeError,match="checksum mismatch"):
        verify_transfer_manifest(tmp_path)


def test_verify_evidence_rejects_ambiguous_or_inconsistent_final_status(root,tmp_path):
    run=tmp_path/"run";run.mkdir();version=(root/"VERSION").read_text().strip()
    status={"run_id":"test-run","release":version,"status":"aborted",
            "execution_status":"aborted","evidence_status":"verified",
            "outcome_classification":"running"}
    (run/"RUN_STATUS.json").write_text(json.dumps(status)+"\n")
    output=tmp_path/"agent-worm-results-test-run.zip";package_results(root,run,output)
    shutil.copy2(run/"RUN_STATUS.json",tmp_path/"RUN_STATUS.json")
    with pytest.raises(RuntimeError,match="outcome classification"):
        verify_evidence(output,version)
    status["outcome_classification"]="technical_failure";status["execution_status"]="completed"
    (run/"RUN_STATUS.json").write_text(json.dumps(status)+"\n")
    package_results(root,run,output);shutil.copy2(run/"RUN_STATUS.json",tmp_path/"RUN_STATUS.json")
    with pytest.raises(RuntimeError,match="execution status"):
        verify_evidence(output,version)
