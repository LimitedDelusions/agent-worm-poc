from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .compatibility import run_compatibility
from .config import load_experiment, load_models, scenarios_for_phase
from .engine import all_placements, execute_experiment
from .freeze import freeze_models
from .preflight import run_preflight
from .reporting import evaluate_positive_control, generate_meeting_summary, package_session
from .server import VllmServerManager
from .util import atomic_write_json, prepare_new_output_dir, utc_now


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
    sub.add_parser("positive-control")
    sub.add_parser("shakedown")

    poc = sub.add_parser("poc")
    poc.add_argument("--repetitions", type=int, default=None)

    package = sub.add_parser("package")
    package.add_argument("--destination-dir", default="/workspace")
    return parser


def _main_scenario_ids(experiment: dict) -> set[str]:
    return {scenario.id for scenario in scenarios_for_phase(experiment, "poc")}


def _positive_scenario_id(experiment: dict) -> str:
    positive = scenarios_for_phase(experiment, "positive-control")
    if len(positive) != 1:
        raise RuntimeError("exactly one positive-control scenario is required")
    return positive[0].id


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.project_root).resolve()
    output_root = _output_root(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    frozen = output_root / "setup" / "frozen_models.json"
    experiment = load_experiment(root / "configs" / "experiment.json")

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
        base = output_root / "fake_validation"
        prepare_new_output_dir(base)
        models = load_models(root / "configs" / "model_candidates.json")
        canonical = [("CONTROL", all_placements(models)[0][1])]
        positive_manifest = execute_experiment(
            root=root,
            output_dir=base / "positive_control",
            model_config_path=root / "configs" / "model_candidates.json",
            repetitions=int(experiment["positive_control_repetitions"]),
            adapter_mode="fake",
            placements_override=canonical,
            scenario_ids={_positive_scenario_id(experiment)},
            reuse_identical_requests=False,
            evidence_label="simulated-positive-control-plumbing-only",
        )
        positive_evaluation = evaluate_positive_control(
            control_dir=base / "positive_control",
            minimum_depth=int(experiment["positive_control_min_artifact_reproduction_depth"]),
        )
        poc_manifest = execute_experiment(
            root=root,
            output_dir=base / "poc",
            model_config_path=root / "configs" / "model_candidates.json",
            repetitions=1,
            adapter_mode="fake",
            scenario_ids=_main_scenario_ids(experiment),
            reuse_identical_requests=False,
            evidence_label="simulated-plumbing-only",
        )
        result = {
            "schema_version": 2,
            "generated_at": utc_now(),
            "positive_control": positive_manifest,
            "positive_control_evaluation": positive_evaluation,
            "poc": poc_manifest,
            "passed": bool(
                positive_evaluation["passed"]
                and poc_manifest["failed_workflows"] == 0
                and poc_manifest["output_invalid_stages"] == 0
            ),
            "research_evidence": False,
        }
        atomic_write_json(base / "manifest.json", result)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 2

    if args.command == "package":
        archive = package_session(
            project_root=root,
            output_root=output_root,
            destination_dir=Path(args.destination_dir).resolve(),
        )
        print(archive)
        return 0

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
    canonical = [("CONTROL", placements[0][1])]

    if args.command == "positive-control":
        manifest = execute_experiment(
            root=root,
            output_dir=output_root / "positive_control",
            model_config_path=frozen,
            repetitions=int(experiment["positive_control_repetitions"]),
            adapter_mode="real",
            lifecycle_factory=_server_factory(output_root / "positive_control"),
            placements_override=canonical,
            scenario_ids={_positive_scenario_id(experiment)},
            reuse_identical_requests=False,
            evidence_label="real-model-calibration-control-not-research-evidence",
        )
        evaluation = evaluate_positive_control(
            control_dir=output_root / "positive_control",
            minimum_depth=int(experiment["positive_control_min_artifact_reproduction_depth"]),
        )
        print(json.dumps({"manifest": manifest, "evaluation": evaluation}, indent=2))
        if not evaluation["passed"]:
            raise RuntimeError("positive propagation control failed")
        return 0

    if args.command == "shakedown":
        manifest = execute_experiment(
            root=root,
            output_dir=output_root / "shakedown",
            model_config_path=frozen,
            repetitions=1,
            adapter_mode="real",
            lifecycle_factory=_server_factory(output_root / "shakedown"),
            placements_override=[("SHAKEDOWN", placements[0][1])],
            scenario_ids=_main_scenario_ids(experiment),
            reuse_identical_requests=False,
            evidence_label="real-model-cross-model-shakedown",
        )
        print(json.dumps(manifest, indent=2))
        return 0 if manifest["failed_workflows"] == 0 else 2

    if args.command == "poc":
        repetitions = (
            int(experiment["default_poc_repetitions"])
            if args.repetitions is None
            else args.repetitions
        )
        if repetitions < 2 or repetitions > 5:
            raise SystemExit("POC repetitions must be between 2 and 5")
        manifest = execute_experiment(
            root=root,
            output_dir=output_root / "poc",
            model_config_path=frozen,
            repetitions=repetitions,
            adapter_mode="real",
            lifecycle_factory=_server_factory(output_root / "poc"),
            scenario_ids=_main_scenario_ids(experiment),
            reuse_identical_requests=False,
            evidence_label="real-model-proof-of-concept-not-final-research",
        )
        generate_meeting_summary(
            poc_dir=output_root / "poc",
            destination=output_root / "NEXT_MEETING_SUMMARY.md",
        )
        print(json.dumps(manifest, indent=2))
        return 0 if manifest["failed_workflows"] == 0 else 2

    raise SystemExit(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
