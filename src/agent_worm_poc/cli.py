from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .compatibility import run_compatibility
from .engine import all_placements, execute_experiment
from .freeze import freeze_models
from .preflight import run_preflight
from .reporting import generate_meeting_summary, package_session
from .server import VllmServerManager
from .config import load_models


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _output_root(value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    env = os.environ.get("AGENT_WORM_OUTPUT_ROOT")
    if env:
        return Path(env).resolve()
    return (_project_root() / "outputs" / "manual-session").resolve()


def _server_factory(output_dir: Path):
    manager = VllmServerManager(output_dir=output_dir)
    return lambda model, phase: manager.serve(model, phase=phase)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-worm")
    parser.add_argument("--project-root", default=str(_project_root()))
    parser.add_argument("--output-root")
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--allow-no-gpu", action="store_true")

    sub.add_parser("freeze-models")
    sub.add_parser("fake-validation")
    sub.add_parser("compatibility")
    sub.add_parser("shakedown")

    poc = sub.add_parser("poc")
    poc.add_argument("--repetitions", type=int, default=None)
    poc.add_argument("--no-reuse", action="store_true")

    package = sub.add_parser("package")
    package.add_argument("--destination-dir", default="/workspace")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.project_root).resolve()
    output_root = _output_root(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    frozen = output_root / "setup" / "frozen_models.json"

    if args.command == "preflight":
        report = run_preflight(
            output_dir=output_root / "setup",
            allow_no_gpu=args.allow_no_gpu,
        )
        print(json.dumps(report, indent=2))
        return 0

    if args.command == "freeze-models":
        result = freeze_models(
            candidate_path=root / "configs" / "model_candidates.json",
            output_path=frozen,
            setup_dir=output_root / "setup",
        )
        print(json.dumps({"frozen_models": str(frozen), "slots": len(result["model_slots"])}, indent=2))
        return 0

    if args.command == "fake-validation":
        manifest = execute_experiment(
            root=root,
            output_dir=output_root / "fake_validation",
            model_config_path=root / "configs" / "model_candidates.json",
            repetitions=1,
            adapter_mode="fake",
            reuse_identical_requests=True,
            evidence_label="simulated-plumbing-only",
        )
        print(json.dumps(manifest, indent=2))
        return 0 if manifest["failed_workflows"] == 0 else 2

    if not frozen.exists():
        raise SystemExit(f"Frozen model config missing: {frozen}. Run freeze-models first.")

    if args.command == "compatibility":
        manifest = run_compatibility(
            root=root,
            output_dir=output_root / "compatibility",
            frozen_model_config=frozen,
            lifecycle_factory=_server_factory(output_root / "compatibility"),
        )
        print(json.dumps(manifest, indent=2))
        return 0

    models = load_models(frozen, require_frozen=True)
    placements = all_placements(models)

    if args.command == "shakedown":
        canonical = [("SHAKEDOWN", placements[0][1])]
        manifest = execute_experiment(
            root=root,
            output_dir=output_root / "shakedown",
            model_config_path=frozen,
            repetitions=1,
            adapter_mode="real",
            lifecycle_factory=_server_factory(output_root / "shakedown"),
            placements_override=canonical,
            reuse_identical_requests=False,
            evidence_label="real-model-cross-model-shakedown",
        )
        print(json.dumps(manifest, indent=2))
        return 0 if manifest["failed_workflows"] == 0 else 2

    if args.command == "poc":
        experiment = json.loads((root / "configs" / "experiment.json").read_text(encoding="utf-8"))
        repetitions = (
            int(experiment["default_poc_repetitions"])
            if args.repetitions is None
            else args.repetitions
        )
        if repetitions < 1:
            raise SystemExit("--repetitions must be at least 1")
        manifest = execute_experiment(
            root=root,
            output_dir=output_root / "poc",
            model_config_path=frozen,
            repetitions=repetitions,
            adapter_mode="real",
            lifecycle_factory=_server_factory(output_root / "poc"),
            reuse_identical_requests=not args.no_reuse,
            evidence_label="real-model-proof-of-concept-not-final-research",
        )
        generate_meeting_summary(
            poc_dir=output_root / "poc",
            destination=output_root / "NEXT_MEETING_SUMMARY.md",
        )
        print(json.dumps(manifest, indent=2))
        return 0 if manifest["failed_workflows"] == 0 else 2

    if args.command == "package":
        archive = package_session(
            project_root=root,
            output_root=output_root,
            destination_dir=Path(args.destination_dir).resolve(),
        )
        print(archive)
        return 0

    raise SystemExit(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
