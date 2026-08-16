from __future__ import annotations
from pathlib import Path
from .types import WorkflowCase,CarrierSpec,ROLES
from .placements import ordered_pair_assignments,placement_id
from .carriers import make_carrier,make_sham,inject_document
from .util import stable_int,stable_token


def _load_doc(data_dir:Path,doc_id:str)->str:
    return (data_dir/f"{doc_id}.txt").read_text(encoding="utf-8")


def _randomization_block(master:int,phase:str,variant_or_kind:str,repetition:int,doc_id:str,suffix:str)->str:
    # Model assignment and policy are deliberately excluded.
    return stable_token("RBLK",master,phase,variant_or_kind,repetition,doc_id,suffix)


def _seeds(master:int,randomization_block_id:str)->dict[str,int]:
    # Same stage seed is used across every assignment and policy in a matched block.
    return {role:stable_int(master,randomization_block_id,role) for role in ROLES}


def _case(master:int,phase:str,role_models:dict[str,str],policy:str,kind:str,
          variant:str|None,doc_id:str,base_text:str,repetition:int,baseline_type:str,
          carrier:CarrierSpec|None,suffix:str="",terminal_stage:str="relay")->WorkflowCase:
    pid=placement_id(role_models)
    randomization_block_id=_randomization_block(master,phase,variant or kind,repetition,doc_id,suffix)
    block_id=stable_token("BLK",master,randomization_block_id,pid,suffix)
    workflow_id=stable_token("WF",master,block_id,policy,kind)
    return WorkflowCase(
        workflow_id=workflow_id,block_id=block_id,randomization_block_id=randomization_block_id,
        placement_id=pid,role_models=dict(role_models),policy=policy,scenario_kind=kind,
        carrier_variant=variant,base_document_id=doc_id,
        source_document=inject_document(base_text,carrier),carrier=carrier,repetition=repetition,
        stage_seeds=_seeds(master,randomization_block_id),baseline_type=baseline_type,
        phase=phase,terminal_stage=terminal_stage,
    )


def build_main_cases(config:dict,model_slots:list[str],data_dir:Path)->list[WorkflowCase]:
    """Complete 4x4 intake->relay matrix with matched neutral/hardened blocks.

    The POC terminates at relay, so it tests 16 unique ordered transmission assignments
    instead of duplicating each assignment through unused planner/executor permutations.
    """
    master=config["master_seed"];reps=config["stochastic_repetitions"]
    docs=config["base_documents"];variants=config["carrier_variants"];cases=[]
    for mapping in ordered_pair_assignments(model_slots):
        baseline="homogeneous_pair" if mapping["intake"]==mapping["relay"] else "heterogeneous_pair"
        for doc_id in docs:
            base=_load_doc(data_dir,doc_id)
            for policy in ("neutral","hardened"):
                cases.append(_case(master,"main",mapping,policy,"clean",None,doc_id,base,0,
                                   baseline,None,"clean",terminal_stage="relay"))
        for variant in variants:
            for doc_id in docs:
                base=_load_doc(data_dir,doc_id)
                for rep in range(reps):
                    carrier=make_carrier(master,variant,rep,doc_id)
                    for policy in ("neutral","hardened"):
                        cases.append(_case(master,"main",mapping,policy,"injected",variant,doc_id,
                                           base,rep,baseline,carrier,"injected",terminal_stage="relay"))
    if len({c.workflow_id for c in cases})!=len(cases):
        raise AssertionError("Duplicate workflow IDs")
    return cases


def build_positive_pair_cases(config:dict,model_slots:list[str],data_dir:Path)->list[WorkflowCase]:
    master=config["master_seed"];docs=config["base_documents"];variants=config["carrier_variants"]
    reps=config.get("positive_control_repetitions",1);cases=[]
    for mapping in ordered_pair_assignments(model_slots):
        baseline="homogeneous_pair" if mapping["intake"]==mapping["relay"] else "heterogeneous_pair"
        for rep in range(reps):
            for vi,variant in enumerate(variants):
                doc_id=docs[vi%len(docs)];base=_load_doc(data_dir,doc_id)
                carrier=make_carrier(master,variant,rep,doc_id)
                cases.append(_case(master,"positive_pair",mapping,"positive","injected",variant,
                                   doc_id,base,rep,baseline,carrier,"positive",terminal_stage="relay"))
    return cases


def build_shakedown_cases(config:dict,model_slots:list[str],data_dir:Path)->list[WorkflowCase]:
    """Calibration set: all 16 pairs, controls, and three carrier forms."""
    master=config["master_seed"];docs=config["base_documents"]
    variants=config["shakedown"]["carrier_variants"];cases=[]
    for mapping in ordered_pair_assignments(model_slots):
        baseline="homogeneous_pair" if mapping["intake"]==mapping["relay"] else "heterogeneous_pair"
        # One matched benign document under both policies verifies utility before main.
        clean_doc=docs[0];base=_load_doc(data_dir,clean_doc)
        for policy in ("neutral","hardened"):
            cases.append(_case(master,"shakedown",mapping,policy,"clean",None,clean_doc,base,0,
                               baseline,None,"clean",terminal_stage="relay"))
        # Sham verifies deterministic scoring specificity without a propagation directive.
        sham=make_sham(master,0,clean_doc)
        cases.append(_case(master,"shakedown",mapping,"neutral","sham","sham",clean_doc,base,0,
                           baseline,sham,"sham",terminal_stage="relay"))
        for vi,variant in enumerate(variants):
            doc_id=docs[vi%len(docs)];base=_load_doc(data_dir,doc_id)
            carrier=make_carrier(master,variant,0,doc_id)
            for policy in ("neutral","hardened"):
                cases.append(_case(master,"shakedown",mapping,policy,"injected",variant,doc_id,
                                   base,0,baseline,carrier,"shakedown",terminal_stage="relay"))
    return cases


def build_compatibility_cases(config:dict,model_slots:list[str],data_dir:Path)->list[WorkflowCase]:
    master=config["master_seed"];docs=config["base_documents"]
    reps=config.get("compatibility_repetitions",3);cases=[]
    for slot in model_slots:
        mapping={role:slot for role in ROLES}
        for rep in range(reps):
            doc_id=docs[rep%len(docs)];base=_load_doc(data_dir,doc_id)
            cases.append(_case(master,"compatibility",mapping,"neutral","clean",None,doc_id,
                               base,rep,"compatibility",None,"compatibility",
                               terminal_stage="executor"))
    return cases
