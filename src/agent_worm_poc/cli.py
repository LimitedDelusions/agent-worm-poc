from __future__ import annotations
from pathlib import Path
import argparse,csv,json,os,re,signal,time
from .config import load_models,load_experiment,load_prompts,load_schemas
from .cases import build_main_cases,build_positive_pair_cases,build_shakedown_cases,build_compatibility_cases
from .adapters import FakeAdapter,OpenAICompatibleAdapter
from .server import VLLMServerManager
from .engine import ExperimentRunner
from .scoring import score_record
from .analysis import summarize
from .review import build_blinded_review
from .runtime import freeze_revisions,record_environment
from .evidence import package_results
from .release_audit import audit_release
from .scientific_gates import evaluate_shakedown_records
from .util import write_json,utc_stamp


def root_from_arg(value:str|None)->Path:
    return Path(value).resolve() if value else Path(__file__).resolve().parents[2]


def _load(root:Path):
    return (load_models(root/"configs/models.json"),load_experiment(root/"configs/experiment.json"),
            load_prompts(root/"configs/prompts.json"),load_schemas(root/"configs/schemas.json"))


def _write_scores(path:Path,scores:list[dict]):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=sorted({key for row in scores for key in row}) if scores else []
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(scores)


def _case_manifest(cases):
    return [{"workflow_id":case.workflow_id,"block_id":case.block_id,
             "randomization_block_id":case.randomization_block_id,
             "placement_id":case.placement_id,
             "pair_id":f"intake-{case.role_models['intake']}__relay-{case.role_models['relay']}",
             "role_models":case.role_models,"policy":case.policy,
             "scenario_kind":case.scenario_kind,"carrier_variant":case.carrier_variant,
             "carrier_id":case.carrier.carrier_id if case.carrier else None,
             "authorization_reference":case.carrier.authorization_reference if case.carrier else None,
             "base_document_id":case.base_document_id,"repetition":case.repetition,
             "stage_seeds":case.stage_seeds,"baseline_type":case.baseline_type,
             "phase":case.phase,"terminal_stage":case.terminal_stage} for case in cases]


_RUN_ID_PATTERN=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PRECREATED_RUN_DIR_ENV="AGENT_WORM_PRECREATED_RUN_DIR"
_PRECREATED_SESSION_FILES={"launch.json","gated-run.log","gated-run.pid"}


def _prepare_run_dir(output_root:Path,run_id:str)->Path:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("AGENT_WORM_RUN_ID must be a single safe path component")
    output_root=output_root.resolve();run_dir=output_root/run_id
    if run_dir.parent!=output_root:
        raise ValueError("Run directory escaped the configured output root")
    if os.environ.get(_PRECREATED_RUN_DIR_ENV)!="1":
        run_dir.mkdir(parents=True,exist_ok=False);return run_dir
    if run_dir.is_symlink() or not run_dir.is_dir() or run_dir.resolve().parent!=output_root:
        raise FileExistsError("Precreated RunPod run directory is missing, linked, or outside the output root")
    entries=list(run_dir.iterdir())
    if any(entry.name!="session" for entry in entries):
        raise FileExistsError("Precreated RunPod run directory contains unexpected entries")
    session_dir=run_dir/"session"
    if session_dir.is_symlink() or not session_dir.is_dir():
        raise FileExistsError("Precreated RunPod session directory is missing or linked")
    for entry in session_dir.iterdir():
        if (entry.name not in _PRECREATED_SESSION_FILES or entry.is_symlink()
                or not entry.is_file()):
            raise FileExistsError("Precreated RunPod session directory contains unexpected entries")
    launch_path=session_dir/"launch.json"
    if launch_path.is_symlink() or not launch_path.is_file():
        raise FileExistsError("Precreated RunPod session is missing launch.json")
    try:launch=json.loads(launch_path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:
        raise ValueError("Precreated RunPod launch.json is invalid") from exc
    if not isinstance(launch,dict) or launch.get("session_id")!=run_id:
        raise ValueError("Precreated RunPod launch session does not match AGENT_WORM_RUN_ID")
    return run_dir


def run_cases(root:Path,cases:list,adapter_name:str,output_dir:Path,frozen_models=None,
              compatibility:bool=False):
    models,config,prompts,schemas=_load(root)
    if frozen_models is not None:models=frozen_models
    output_dir.mkdir(parents=True,exist_ok=True)
    write_json(output_dir/"cases_manifest.json",_case_manifest(cases))
    if adapter_name=="fake":adapter=FakeAdapter();manager=None
    else:
        api_key=os.environ.get("POC_LOCAL_API_KEY","local-poc")
        adapter=OpenAICompatibleAdapter(api_key=api_key,
            timeout=config["runtime"]["request_timeout_seconds"],
            retries=config["runtime"]["max_transport_retries"])
        manager=VLLMServerManager(output_dir,port=config["runtime"]["server_port"],api_key=api_key,
            start_timeout=config["runtime"]["server_start_timeout_seconds"],
            idle_memory_mib_max=config["runtime"]["gpu_idle_memory_mib_max"])
    runner=ExperimentRunner(models,adapter,prompts,schemas,config,output_dir,manager)
    records=runner.run_compatibility(cases) if compatibility else runner.run(cases)
    expected=json.loads((root/"configs/expected_facts.json").read_text(encoding="utf-8"))
    scores=[score_record(record,expected) for record in records]
    _write_scores(output_dir/"workflow_scores_raw.csv",scores)
    summary=summarize(scores,output_dir,config)
    write_json(output_dir/"phase_summary.json",summary)
    return records,scores,summary


def run_phase(root:Path,phase:str,adapter_name:str,output_dir:Path,frozen_models=None):
    models,config,_,_=_load(root);slots=[m.slot for m in (frozen_models or models)]
    data_dir=root/"data/base_documents"
    builders={"compatibility":build_compatibility_cases,"positive_pair":build_positive_pair_cases,
              "shakedown":build_shakedown_cases,"main":build_main_cases}
    cases=builders[phase](config,slots,data_dir)
    return run_cases(root,cases,adapter_name,output_dir,frozen_models,
                     compatibility=(phase=="compatibility"))


def compatibility_gate(scores:list[dict],config:dict)->dict:
    total=len(scores);valid=sum(bool(row["all_stages_valid"]) for row in scores)
    benign=sum(bool(row["benign_end_to_end"]) for row in scores);by_model={}
    for slot in sorted({row["intake_model"] for row in scores}):
        rows=[row for row in scores if row["intake_model"]==slot]
        by_model[slot]={"n":len(rows),
            "valid_rate":sum(bool(row["all_stages_valid"]) for row in rows)/len(rows),
            "benign_rate":sum(bool(row["benign_end_to_end"]) for row in rows)/len(rows)}
    passed=bool(total and valid/total>=config["gates"]["benign_role_schema_rate_min"]
                and benign/total>=config["gates"]["benign_end_to_end_rate_min"]
                and all(value["valid_rate"]>=config["gates"]["benign_role_schema_rate_min"]
                        and value["benign_rate"]>=config["gates"]["benign_end_to_end_rate_min"]
                        for value in by_model.values()))
    return {"passed":passed,"n":total,"valid_rate":valid/total if total else 0.0,
            "benign_rate":benign/total if total else 0.0,"by_model":by_model}


def positive_gate(scores:list[dict],config:dict,slots:list[str])->dict:
    rows=[row for row in scores if row["phase"]=="positive_pair"]
    expected_per_pair=max(1,len(config.get("carrier_variants",[]))*int(config.get("positive_control_repetitions",1)))
    pairs={}
    for src in slots:
        for dst in slots:
            values=[row for row in rows if row["intake_model"]==src and row["relay_model"]==dst]
            valid=[row for row in values if row["all_stages_valid"]]
            successes=sum(bool(row["second_hop_viable"]) for row in values)
            rate=successes/len(values) if values else 0.0
            pairs[f"{src}->{dst}"]={"n":len(values),"valid_n":len(valid),
                "successes":successes,"rate":rate}
    overall=sum(bool(row["second_hop_viable"]) for row in rows)/len(rows) if rows else 0.0
    invalid_rate=sum(not bool(row["all_stages_valid"]) for row in rows)/len(rows) if rows else 1.0
    pair_min=float(config["gates"]["positive_each_ordered_pair_rate_min"])
    passed=bool(rows and overall>=config["gates"]["positive_two_hop_rate_min"]
                and invalid_rate<=config["gates"]["invalid_output_rate_max"]
                and len(pairs)==len(slots)**2
                and all(value["n"]==expected_per_pair and value["rate"]>=pair_min
                        for value in pairs.values()))
    return {"passed":passed,"n":len(rows),"overall_rate":overall,"invalid_rate":invalid_rate,
            "expected_n_per_pair":expected_per_pair,
            "minimum_pair_rate":min((value["rate"] for value in pairs.values()),default=0.0),
            "required_pair_rate":pair_min,"ordered_pairs":pairs}


def shakedown_gate(scores:list[dict],config:dict)->dict:
    rows=[row for row in scores if row["phase"]=="shakedown"]
    return evaluate_shakedown_records(rows,config)


def gated(root:Path,output_root:Path,adapter_name:str="real")->int:
    def terminate(_signum,_frame):raise KeyboardInterrupt("Run terminated by timeout or operator")
    signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
    run_id=os.environ.get("AGENT_WORM_RUN_ID") or f"{utc_stamp()}-{os.getpid()}"
    run_dir=_prepare_run_dir(output_root,run_id)
    started=time.time();record_environment(run_dir/"environment")
    models,config,_,_=_load(root)
    status={"run_id":run_id,"release":config["release"],"started_epoch":started,
            "status":"running","gates":{},"adapter":adapter_name}
    write_json(run_dir/"RUN_STATUS.json",status)
    try:
        audit=audit_release(root);write_json(run_dir/"environment/release_audit.json",audit)
        if not audit["passed"]:raise RuntimeError("Release audit failed before model work")
        frozen=freeze_revisions(models,run_dir/"environment") if adapter_name=="real" else models
        _,scores,_=run_phase(root,"compatibility",adapter_name,run_dir/"01_compatibility",frozen)
        gate=compatibility_gate(scores,config);status["gates"]["compatibility"]=gate;write_json(run_dir/"RUN_STATUS.json",status)
        if not gate["passed"]:raise RuntimeError("Compatibility gate failed")

        slots=[model.slot for model in frozen];data_dir=root/"data/base_documents"
        calibration_cases=(build_positive_pair_cases(config,slots,data_dir)+
                           build_shakedown_cases(config,slots,data_dir))
        _,calibration_scores,_=run_cases(root,calibration_cases,adapter_name,
                                         run_dir/"02_calibration",frozen)
        positive=positive_gate(calibration_scores,config,slots)
        shakedown=shakedown_gate(calibration_scores,config)
        status["gates"]["positive_pair"]=positive;status["gates"]["shakedown"]=shakedown
        write_json(run_dir/"RUN_STATUS.json",status)
        if not positive["passed"]:raise RuntimeError("Positive-control gate failed; assay sensitivity is insufficient")
        if not shakedown["passed"]:raise RuntimeError("Calibration gate failed; main matrix intentionally aborted")

        _,main_scores,summary=run_phase(root,"main",adapter_name,run_dir/"03_main",frozen)
        review=build_blinded_review(run_dir/"03_main/stage_events.jsonl",
                                    run_dir/"03_main/workflow_scores.csv",
                                    run_dir/"04_semantic_review",config)
        write_json(run_dir/"04_semantic_review/review_summary.json",review)
        status["gates"]["main"]=summary["gates"];status["status"]="completed"
        status["ended_epoch"]=time.time()
    except BaseException as exc:
        status["status"]="aborted";status["error"]=f"{type(exc).__name__}: {exc}"
        status["ended_epoch"]=time.time()
    finally:
        elapsed=(status.get("ended_epoch",time.time())-started)/3600
        rate=os.environ.get("RUNPOD_HOURLY_RATE_USD") or os.environ.get("RUNPOD_HOURLY_RATE")
        status["elapsed_gpu_hours"]=elapsed
        status["estimated_compute_cost_usd"]=round(elapsed*float(rate),2) if rate else None
        write_json(run_dir/"RUN_STATUS.json",status)
        package_results(root,run_dir,output_root/f"agent-worm-results-{run_id}.zip")
    return 0 if status["status"]=="completed" else 2


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["fake-gated","real-gated","phase"])
    parser.add_argument("--root");parser.add_argument("--output-root",default="outputs/runs")
    parser.add_argument("--phase",choices=["compatibility","positive_pair","shakedown","main"])
    parser.add_argument("--adapter",choices=["fake","real"],default="fake")
    args=parser.parse_args(argv);root=root_from_arg(args.root);output=Path(args.output_root).resolve()
    if args.command=="fake-gated":return gated(root,output,"fake")
    if args.command=="real-gated":return gated(root,output,"real")
    if not args.phase:parser.error("--phase is required")
    run_phase(root,args.phase,args.adapter,output/args.phase);return 0


if __name__=="__main__":raise SystemExit(main())
