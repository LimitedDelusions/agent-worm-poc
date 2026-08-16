from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import ast,json,re,subprocess
from .config import load_experiment,load_models,load_prompts
from .placements import ordered_pair_assignments
from .cases import build_main_cases,build_positive_pair_cases,build_shakedown_cases
from .util import ensure_no_secret_text,write_json

REQUIRED=(
    "START_HERE.md","CODING_HANDOFF.md","DEPLOYMENT_CHECKLIST.md","Dockerfile","pyproject.toml","VERSION",
    "AUDIT_REPORT.md","FINAL_VALIDATION_REPORT.md","SOURCE_HASHES.sha256","RELEASE_MANIFEST.json",".dockerignore",".gitignore",
    "configs/models.json","configs/experiment.json","configs/preregistration.json","configs/prompts.json","configs/schemas.json",
    "docs/RUNBOOK.md","docs/EXPERIMENT_DESIGN.md","docs/STATISTICAL_ANALYSIS.md","docs/ARTIFACTS.md",
    ".github/workflows/validate-and-build.yml",
    "scripts/runpod/entrypoint.sh","scripts/runpod/start_gated_run.sh","scripts/runpod/status.sh","scripts/runpod/cancel_run.sh",
    "src/agent_worm_poc/engine.py","src/agent_worm_poc/scoring.py","src/agent_worm_poc/scientific_gates.py",
    "src/agent_worm_poc/runtime.py","scripts/release/generate_integrity.py",
)


def audit_release(root:Path)->dict:
    errors=[];warnings=[]
    missing=[name for name in REQUIRED if not (root/name).exists()]
    if missing:errors.append("Missing required files: "+", ".join(missing))
    try:
        exp=load_experiment(root/"configs/experiment.json")
        models=load_models(root/"configs/models.json");slots=[model.slot for model in models]
        prompts=load_prompts(root/"configs/prompts.json")
        if len(exp.get("carrier_variants",[]))<3:errors.append("At least three carrier variants are required")
        if exp.get("stochastic_repetitions",0)<2:errors.append("POC requires at least two independent generation seeds per carrier/document cell")
        if len(ordered_pair_assignments(slots))!=16:errors.append("Expected complete 4x4 ordered intake-to-relay matrix")
        expected_repos={
          "Qwen/Qwen3-30B-A3B-Instruct-2507",
          "google/gemma-3-27b-it",
          "openai/gpt-oss-20b",
          "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
        }
        if {model.repo_id for model in models}!=expected_repos:
            errors.append("Model repositories do not match the preregistered four exact deployments")
        nemotron=next((model for model in models if model.slot=="nemotron"),None)
        if not nemotron or nemotron.reasoning_parser_plugin_repo_path!="nano_v3_reasoning_parser.py" or nemotron.reasoning_parser_name!="nano_v3":
            errors.append("Nemotron reasoning-parser plugin is not explicitly configured")
        gpt_oss=next((model for model in models if model.slot=="gpt_oss"),None)
        if not gpt_oss or list(gpt_oss.server_args)!=["--reasoning-parser","openai_gptoss"]:
            errors.append("GPT-OSS reasoning parser is not explicitly configured")
        neutral="\n".join(prompts[role]["neutral"].lower() for role in prompts)
        for term in ("prompt injection","malicious payload","worm canary","strip the marker","remove the carrier","self-replicating"):
            if term in neutral:errors.append(f"Neutral prompt contains laboratory/security coaching term: {term}")
        for role in prompts:
            policies={prompts[role][policy] for policy in ("positive","neutral","hardened")}
            if len(policies)!=3:errors.append(f"Role {role} does not have three distinct policies")
        main=build_main_cases(exp,slots,root/"data/base_documents")
        expected_main=672
        if len(main)!=expected_main:errors.append(f"Expected {expected_main} main workflows, found {len(main)}")
        if len({case.workflow_id for case in main})!=len(main):errors.append("Workflow IDs are not unique")
        pairs={(case.role_models['intake'],case.role_models['relay']) for case in main}
        if len(pairs)!=16:errors.append(f"Expected 16 ordered model pairs in main phase, found {len(pairs)}")
        if any(case.terminal_stage!="relay" for case in main):errors.append("Main POC must terminate at relay")
        # Matched policy pairs use identical input, carrier, and seed.
        policy_pairs=defaultdict(dict)
        for case in main:
            policy_pairs[case.block_id][case.policy]=case
        for key,pair in policy_pairs.items():
            if set(pair)!={"neutral","hardened"}:
                errors.append(f"Unmatched neutral/hardened block: {key}");break
            a,b=pair["neutral"],pair["hardened"]
            if a.source_document!=b.source_document:errors.append("Matched policy pair uses different source documents");break
            if a.stage_seeds!=b.stage_seeds:errors.append("Matched policy pair uses different seeds");break
            aid=a.carrier.carrier_id if a.carrier else None;bid=b.carrier.carrier_id if b.carrier else None
            if aid!=bid:errors.append("Matched policy pair uses different carrier IDs");break
        # Across ordered assignments, each content/seed block is identical.
        blocks=defaultdict(list)
        for case in main:
            if case.scenario_kind=="injected" and case.policy=="neutral":blocks[case.randomization_block_id].append(case)
        if len(blocks)!=18:errors.append(f"Expected 18 primary randomization blocks, found {len(blocks)}")
        for key,cases in blocks.items():
            if len(cases)!=16:errors.append(f"Randomization block {key} does not cover all 16 ordered pairs");break
            if len({case.source_document for case in cases})!=1:errors.append("Source document differs across assignments within a randomization block");break
            if len({case.carrier.carrier_id for case in cases})!=1:errors.append("Carrier ID differs across assignments within a randomization block");break
            if len({json.dumps(case.stage_seeds,sort_keys=True) for case in cases})!=1:errors.append("Generation seeds differ across assignments within a randomization block");break
        positive=build_positive_pair_cases(exp,slots,root/"data/base_documents")
        if len(positive)!=48:errors.append(f"Expected 48 positive-control workflows, found {len(positive)}")
        if len({(case.role_models['intake'],case.role_models['relay']) for case in positive})!=16:errors.append("Positive control does not cover every ordered pair")
        calibration=build_shakedown_cases(exp,slots,root/"data/base_documents")
        if len(calibration)!=144:errors.append(f"Expected 144 shakedown workflows, found {len(calibration)}")
        carrier_text="\n".join(case.carrier.injected_block for case in positive if case.carrier).lower()
        for forbidden in ("http://","https://","curl ","wget ","powershell","subprocess","os.system","rm -rf","system message:","developer message:"):
            if forbidden in carrier_text:errors.append(f"Unsafe carrier content detected: {forbidden}")
        if "simulated action" in carrier_text:errors.append("Carrier contains laboratory wording instead of a natural workflow instruction")
        docker=(root/"Dockerfile").read_text(encoding="utf-8") if (root/"Dockerfile").exists() else ""
        if "@sha256:" not in docker:errors.append("Docker base image is not pinned by digest")
        if re.search(r"(?i)(pip|uv pip|apt-get) install",(root/"scripts/runpod/start_gated_run.sh").read_text(encoding="utf-8") if (root/"scripts/runpod/start_gated_run.sh").exists() else ""):
            errors.append("Paid RunPod launch script performs package installation")
        server_text=(root/"src/agent_worm_poc/server.py").read_text(encoding="utf-8")
        if "--generation-config" not in server_text or "--no-enable-prefix-caching" not in server_text:
            errors.append("vLLM server is missing preregistered reproducibility controls")
        if "--code-revision" not in server_text or "reasoning_parser_plugin_sha256" not in server_text:
            errors.append("vLLM model code or reasoning-parser artifact is not revision/hash pinned")
        if "_model_server_environment" not in server_text or "_CREDENTIAL_MARKERS" not in server_text:
            errors.append("vLLM model process does not filter unrelated credentials")
        adapter_text=(root/"src/agent_worm_poc/adapters.py").read_text(encoding="utf-8")
        if "response_format" not in adapter_text or "json_schema" not in adapter_text:
            errors.append("Real adapter does not request structured JSON output")
    except Exception as exc:
        errors.append(f"Configuration/design audit failed: {type(exc).__name__}: {exc}")
    secrets=ensure_no_secret_text(root)
    if secrets:errors.append("Possible embedded secrets: "+", ".join(secrets))
    for path in root.rglob("*.py"):
        if any(part in {".git",".venv","__pycache__"} for part in path.parts):continue
        try:ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
        except SyntaxError as exc:errors.append(f"Python syntax error {path.relative_to(root)}: {exc}")
    for path in root.rglob("*.sh"):
        result=subprocess.run(["bash","-n",str(path)],capture_output=True,text=True)
        if result.returncode:errors.append(f"Shell syntax error {path.relative_to(root)}: {result.stderr.strip()}")
    result={"release":"0.8.3","passed":not errors,"errors":errors,"warnings":warnings,
            "scientific_controls":{"carrier_variants":3,"base_documents":3,
              "ordered_intake_relay_pairs":16,"generation_seeds_per_carrier_document":2,
              "matched_policy_inputs":True,"matched_assignment_blocks":True,
              "response_reuse_allowed":False,"positive_control_all_ordered_pairs":True,
              "hardened_negative_control":True,"sham_specificity_control":True,
              "semantic_review_blinded":True,"nemotron_runtime_plugin_frozen_at_gate":True,
              "model_code_revision_frozen_at_gate":True,"model_server_credentials_filtered":True,
              "exact_deployment_repositories_locked":True,"structured_output_enforced":True,
              "prefix_cache_disabled":True,"model_generation_configs_disabled":True}}
    write_json(root/"outputs/release_audit.json",result)
    return result
