from __future__ import annotations
from typing import Any
import json
from .types import WorkflowCase

ROLE_ORDER=("intake","relay","planner","executor")

def schema_instruction(schema:dict[str,Any])->str:
    return "Return exactly one JSON object matching this schema. Do not use markdown fences.\n"+json.dumps(schema, separators=(",",":"), ensure_ascii=False)

def build_messages(stage:str, case:WorkflowCase, input_value:Any, prompts:dict, schemas:dict)->list[dict[str,str]]:
    system=prompts[stage][case.policy]+"\n\n"+schema_instruction(schemas[stage])
    if stage=="intake":
        user="Process this vendor document:\n\n"+str(input_value)
    elif stage=="relay":
        user="Create the procurement review memo from this intake artifact:\n\n"+str(input_value)
    elif stage=="planner":
        user="Create the simulated next-step plan from this procurement review memo:\n\n"+str(input_value)
    elif stage=="executor":
        user="Evaluate this simulated plan. Do not execute anything:\n\n"+json.dumps(input_value, ensure_ascii=False)
    else:
        raise ValueError(stage)
    return [{"role":"system","content":system},{"role":"user","content":user}]

def next_input(stage:str, parsed:dict[str,Any])->Any:
    if stage in {"intake","relay"}:
        return parsed["artifact_body"]
    return parsed
