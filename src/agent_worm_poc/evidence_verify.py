from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import re
import stat
import zipfile


_SIDECAR = re.compile(r"^(?P<sha>[0-9a-fA-F]{64})  (?P<name>[^\r\n]+)$")
_TRANSFER_ROW = re.compile(r"^(?P<sha>[0-9a-fA-F]{64})  (?P<name>[^\r\n]+)$")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        name
        and "\\" not in name
        and not path.is_absolute()
        and ".." not in path.parts
    )


def verify_transfer_manifest(directory: str | Path) -> dict[str, Any]:
    """Verify every transferred file against the Pod-generated SHA256SUMS."""
    root = Path(directory).resolve(strict=True)
    manifest = root / "SHA256SUMS"
    if not manifest.is_file() or manifest.is_symlink():
        raise RuntimeError(f"Missing or linked transfer manifest: {manifest}")
    expected: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = _TRANSFER_ROW.fullmatch(line)
        if not match:
            raise RuntimeError(f"Malformed transfer checksum row: {line!r}")
        relative = match.group("name").removeprefix("./").replace("\\", "/")
        if not _safe_member(relative) or relative == "SHA256SUMS" or relative in expected:
            raise RuntimeError(f"Unsafe or duplicate transfer path: {relative!r}")
        expected[relative] = match.group("sha").lower()
    if len(expected) != len({name.casefold() for name in expected}):
        raise RuntimeError("Transfer manifest contains case-colliding paths")
    actual: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path == manifest or not path.is_file():
            continue
        if path.is_symlink():
            raise RuntimeError(f"Transferred file is a symbolic link: {path}")
        relative = path.relative_to(root).as_posix()
        actual[relative] = path
    if set(actual) != set(expected):
        raise RuntimeError(
            "Transfer file set differs from SHA256SUMS: "
            f"missing={sorted(set(expected)-set(actual))}, "
            f"extra={sorted(set(actual)-set(expected))}"
        )
    for relative, path in actual.items():
        if _sha256_file(path) != expected[relative]:
            raise RuntimeError(f"Transferred file checksum mismatch: {relative}")
    return {"passed": True, "manifest": str(manifest), "file_count": len(expected)}


def verify_evidence(
    zip_path: str | Path,
    expected_version: str | None = None,
    status_path: str | Path | None = None,
) -> dict[str, Any]:
    """Fully verify a transferred evidence ZIP and its three external companions."""
    archive_path = Path(zip_path).resolve(strict=True)
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    metadata_path = archive_path.with_suffix(archive_path.suffix + ".json")
    status_path = Path(status_path).resolve(strict=True) if status_path else archive_path.parent / "RUN_STATUS.json"
    for path in (checksum_path, metadata_path, status_path):
        if not path.is_file():
            raise RuntimeError(f"Missing evidence companion: {path}")

    match = _SIDECAR.fullmatch(checksum_path.read_text(encoding="utf-8").strip())
    if not match or match.group("name") != archive_path.name:
        raise RuntimeError("Malformed evidence checksum sidecar or ZIP filename mismatch")
    actual_zip_sha = _sha256(archive_path.read_bytes())
    if actual_zip_sha != match.group("sha").lower():
        raise RuntimeError("Evidence ZIP checksum mismatch")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("sha256") != actual_zip_sha:
        raise RuntimeError("Evidence ZIP metadata checksum mismatch")
    if int(metadata.get("size", -1)) != archive_path.stat().st_size:
        raise RuntimeError("Evidence ZIP metadata size mismatch")
    if Path(str(metadata.get("zip", ""))).name != archive_path.name:
        raise RuntimeError("Evidence ZIP metadata filename mismatch")

    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos if not info.is_dir()]
        if len(names) != len(set(names)) or len(names) != len({name.casefold() for name in names}):
            raise RuntimeError("Evidence ZIP contains duplicate or case-colliding members")
        for info in infos:
            if not _safe_member(info.filename):
                raise RuntimeError(f"Unsafe evidence ZIP member: {info.filename}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"Evidence ZIP contains a symbolic link: {info.filename}")
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Evidence ZIP CRC failure: {bad}")

        manifest_name = "evidence_package/PACKAGE_MANIFEST.json"
        if manifest_name not in names:
            raise RuntimeError("Evidence ZIP is missing PACKAGE_MANIFEST.json")
        package_manifest = json.loads(archive.read(manifest_name))
        rows = package_manifest.get("files", [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise RuntimeError("Package manifest files must be a list of objects")
        if int(package_manifest.get("file_count", -1)) != len(rows):
            raise RuntimeError("Package manifest file count mismatch")
        if int(metadata.get("manifest_files", -1)) != len(rows):
            raise RuntimeError("Evidence metadata manifest count mismatch")
        expected_members: set[str] = set()
        for row in rows:
            relative = str(row["path"]).replace("\\", "/")
            member = f"evidence_package/{relative}"
            if not _safe_member(member) or member in expected_members:
                raise RuntimeError(f"Invalid package-manifest path: {relative}")
            expected_members.add(member)
            data = archive.read(member)
            if len(data) != int(row["size"]) or _sha256(data) != row["sha256"]:
                raise RuntimeError(f"Package manifest mismatch: {relative}")
        actual_payload = set(names) - {manifest_name}
        if actual_payload != expected_members:
            raise RuntimeError("Package manifest does not exactly cover ZIP payload")

        packaged_status = archive.read("evidence_package/run/RUN_STATUS.json")
        if packaged_status != status_path.read_bytes():
            raise RuntimeError("Standalone RUN_STATUS.json differs from packaged status")

        snapshot_prefix = "evidence_package/source_snapshot/"
        release_manifest = json.loads(
            archive.read(snapshot_prefix + "RELEASE_MANIFEST.json")
        )
        source_rows = release_manifest.get("files", [])
        if not isinstance(source_rows, list) or any(not isinstance(row, dict) for row in source_rows):
            raise RuntimeError("Release manifest files must be a list of objects")
        release_paths = {str(row["path"]).replace("\\", "/") for row in source_rows}
        if len(release_paths) != len(source_rows):
            raise RuntimeError("Release manifest contains duplicate paths")
        expected_snapshot = release_paths | {"RELEASE_MANIFEST.json", "SOURCE_HASHES.sha256"}
        actual_snapshot = {
            name.removeprefix(snapshot_prefix)
            for name in names
            if name.startswith(snapshot_prefix)
        }
        if actual_snapshot != expected_snapshot:
            raise RuntimeError("Source snapshot set differs from RELEASE_MANIFEST.json")
        for row in source_rows:
            relative = str(row["path"]).replace("\\", "/")
            data = archive.read(snapshot_prefix + relative)
            if len(data) != int(row["size"]) or _sha256(data) != row["sha256"]:
                raise RuntimeError(f"Source snapshot release mismatch: {relative}")
        hash_lines = archive.read(snapshot_prefix + "SOURCE_HASHES.sha256").decode("utf-8")
        hash_map: dict[str, str] = {}
        for line in hash_lines.splitlines():
            digest, separator, relative = line.partition("  ")
            relative = relative.replace("\\", "/")
            if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest) or relative in hash_map:
                raise RuntimeError("Malformed SOURCE_HASHES.sha256 in evidence snapshot")
            hash_map[relative] = digest
        manifest_map = {str(row["path"]).replace("\\", "/"): row["sha256"] for row in source_rows}
        if hash_map != manifest_map:
            raise RuntimeError("SOURCE_HASHES.sha256 differs from release manifest")
        version = archive.read(snapshot_prefix + "VERSION").decode("utf-8").strip()
        if release_manifest.get("release") != version:
            raise RuntimeError("Release manifest version differs from snapshot VERSION")
        if expected_version is not None and version != expected_version:
            raise RuntimeError(f"Evidence release is {version}, expected {expected_version}")

    status = json.loads(status_path.read_text(encoding="utf-8"))
    run_id = str(status.get("run_id", ""))
    if not run_id or archive_path.name not in {
        f"agent-worm-results-{run_id}.zip",
        f"agent-worm-results-{run_id}-forced.zip",
    }:
        raise RuntimeError("Evidence ZIP filename does not match RUN_STATUS run_id")
    if status.get("release") != version:
        raise RuntimeError("RUN_STATUS release differs from source snapshot VERSION")
    if status.get("status") not in {"completed", "aborted"}:
        raise RuntimeError("RUN_STATUS is not final")
    expected_execution = "completed" if status.get("status") == "completed" else "aborted"
    if status.get("execution_status") != expected_execution:
        raise RuntimeError("RUN_STATUS execution status is missing or inconsistent")
    if status.get("evidence_status") != "verified":
        raise RuntimeError("RUN_STATUS does not mark evidence as verified")
    outcome = status.get("outcome_classification")
    if not isinstance(outcome, str) or not outcome or outcome == "running":
        raise RuntimeError("RUN_STATUS outcome classification is not terminal")
    return {
        "passed": True,
        "zip": str(archive_path),
        "sha256": actual_zip_sha,
        "size": archive_path.stat().st_size,
        "package_manifest_files": len(rows),
        "release_manifest_files": len(source_rows),
        "release": version,
        "run_id": run_id,
        "status": status.get("status"),
        "outcome_classification": status.get("outcome_classification"),
    }
