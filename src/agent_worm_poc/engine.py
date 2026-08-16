from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from typing import Any
import json, random, time, traceback
from .types import WorkflowCase, WorkflowRecord, StageEvent, ROLES, ModelSpec
from .prompts import build_messages, next_input
from .validation import validate_schema, semantic_validation
from .util import append_jsonl, stable_token, write_json

class ExperimentRunner:
    def __init__(self, models:list[ModelSpec], adapter, prompts:dict, schemas:dict, config:dict,
                 output_dir:Path, server_manager=None):
        self.models={m.slot:m for m in models}; self.adapter=adapter; self.prompts=prompts; self.schemas=schemas
        self.config=config; self.output_dir=output_dir; self.server_manager=server_manager
        output_dir.mkdir(parents=True,exist_ok=True)
        self.events_path=output_dir/"stage_events.jsonl"; self.failures_path=output_dir/"failures.jsonl"
        self.request_ids:set[str]=set()
    def _input_for(self, record:WorkflowRecord, stage:str)->Any:
        if stage=="intake": return record.case.source_document
        prev={"relay":"intake","planner":"relay","executor":"planner"}[stage]
        ev=record.stages.get(prev)
        if not ev or not ev.parsed or not ev.schema_valid or not ev.semantic_valid:
            raise RuntimeError(f"Previous stage {prev} unavailable or invalid")
        return next_input(prev,ev.parsed)
    def _run_one(self, record:WorkflowRecord, stage:str)->StageEvent:
        case=record.case; model=self.models[case.role_models[stage]]; input_value=self._input_for(record,stage)
        messages=build_messages(stage,case,input_value,self.prompts,self.schemas)
        request_id=stable_token("REQ",case.workflow_id,stage,model.slot,case.stage_seeds[stage],length=16)
        if request_id in self.request_ids: raise AssertionError(f"Response reuse/duplicate request ID: {request_id}")
        self.request_ids.add(request_id)
        raw=""; parsed=None; schema_ok=False; semantic_ok=False; err=None; latency=0.0; pt=ct=None
        try:
            completion=self.adapter.complete(model,messages,case.stage_seeds[stage],self.config["temperature"],
                self.config["top_p"],self.config["max_output_tokens"][stage],
                {"stage":stage,"case":case,"input_value":input_value,"request_id":request_id,
                 "schema":self.schemas[stage]})
            raw=completion.raw_text; parsed=completion.parsed; latency=completion.latency_seconds
            pt=completion.prompt_tokens; ct=completion.completion_tokens
            schema_ok,schema_errors=validate_schema(parsed,self.schemas[stage])
            semantic_ok,semantic_errors=semantic_validation(stage,parsed) if schema_ok else (False,[])
            errors=schema_errors+semantic_errors
            if errors: err="; ".join(errors)
        except Exception as e:
            err=f"{type(e).__name__}: {e}"
            append_jsonl(self.failures_path,{"workflow_id":case.workflow_id,"stage":stage,"request_id":request_id,
                "error":err,"traceback":traceback.format_exc()})
        event=StageEvent(workflow_id=case.workflow_id,request_id=request_id,phase=case.phase,stage=stage,
            model_slot=model.slot,model_repo=model.repo_id,model_revision=model.revision,served_name=model.served_name,
            seed=case.stage_seeds[stage],policy=case.policy,scenario_kind=case.scenario_kind,
            carrier_variant=case.carrier_variant,placement_id=case.placement_id,baseline_type=case.baseline_type,
            repetition=case.repetition,input_text=str(input_value),system_prompt=messages[0]["content"],
            raw_response=raw,parsed=parsed,schema_valid=schema_ok,semantic_valid=semantic_ok,error=err,
            latency_seconds=latency,prompt_tokens=pt,completion_tokens=ct,reused_response=False)
        append_jsonl(self.events_path,event.to_dict()); return event
    def _required_stages(self,case:WorkflowCase)->list[str]:
        stages=list(ROLES)
        return stages[:stages.index(case.terminal_stage)+1]

    def _write_records(self,records:dict[str,WorkflowRecord],load_manifest:list[dict]):
        write_json(self.output_dir/"model_load_manifest.json",load_manifest)
        with (self.output_dir/"workflow_records.jsonl").open("w",encoding="utf-8") as fh:
            for rec in records.values():fh.write(json.dumps(rec.to_dict(),ensure_ascii=False)+"\n")

    def run_compatibility(self,cases:list[WorkflowCase])->list[WorkflowRecord]:
        """Run homogeneous full workflows with one server load per model."""
        records={c.workflow_id:WorkflowRecord(case=c) for c in cases};by_slot=defaultdict(list)
        for rec in records.values():
            slots=set(rec.case.role_models.values())
            if len(slots)!=1 or rec.case.terminal_stage!="executor":
                raise ValueError("Compatibility cases must be homogeneous full workflows")
            by_slot[next(iter(slots))].append(rec)
        load_manifest=[];slots=list(by_slot);random.Random(self.config["master_seed"]).shuffle(slots)
        for slot in slots:
            model=self.models[slot]
            started=time.time();requests=0;batch=by_slot[slot]
            try:
                if self.server_manager:self.server_manager.start(model)
                random.Random(self.config["master_seed"]+sum(map(ord,slot))).shuffle(batch)
                for rec in batch:
                    for stage in self._required_stages(rec.case):
                        ev=self._run_one(rec,stage);rec.stages[stage]=ev;requests+=1
                        if not ev.schema_valid or not ev.semantic_valid:break
            finally:
                if self.server_manager:self.server_manager.stop()
            load_manifest.append({"phase":"compatibility","model_slot":slot,"started_epoch":started,
                                  "ended_epoch":time.time(),"requests":requests})
        self._write_records(records,load_manifest);return list(records.values())

    def run(self,cases:list[WorkflowCase],stop_after_stage:str|None=None)->list[WorkflowRecord]:
        records={c.workflow_id:WorkflowRecord(case=c) for c in cases};stages=list(ROLES)
        if stop_after_stage:stages=stages[:stages.index(stop_after_stage)+1]
        load_manifest=[]
        for stage in stages:
            groups=defaultdict(list)
            for rec in records.values():
                if stage not in self._required_stages(rec.case):continue
                try:self._input_for(rec,stage)
                except Exception:
                    if stage!="intake":continue
                groups[rec.case.role_models[stage]].append(rec)
            slots=list(groups);random.Random(self.config["master_seed"]+stages.index(stage)).shuffle(slots)
            for slot in slots:
                model=self.models[slot]
                started=time.time();completed=0;batch=groups[slot]
                try:
                    if self.server_manager:self.server_manager.start(model)
                    random.Random(self.config["master_seed"]+sum(map(ord,stage+slot))).shuffle(batch)
                    for rec in batch:
                        ev=self._run_one(rec,stage);rec.stages[stage]=ev;completed+=1
                finally:
                    if self.server_manager:self.server_manager.stop()
                load_manifest.append({"stage":stage,"model_slot":slot,"started_epoch":started,
                                      "ended_epoch":time.time(),"requests":completed})
        self._write_records(records,load_manifest);return list(records.values())
