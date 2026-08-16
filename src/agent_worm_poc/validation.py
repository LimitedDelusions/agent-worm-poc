from __future__ import annotations
from typing import Any

def _is_type(value:Any, expected:Any)->bool:
    if isinstance(expected,list): return any(_is_type(value,x) for x in expected)
    return {
      "string": lambda v:isinstance(v,str), "null":lambda v:v is None,
      "array":lambda v:isinstance(v,list), "object":lambda v:isinstance(v,dict),
      "number":lambda v:isinstance(v,(int,float)) and not isinstance(v,bool),
      "integer":lambda v:isinstance(v,int) and not isinstance(v,bool),
      "boolean":lambda v:isinstance(v,bool),
    }.get(expected, lambda v:True)(value)

def validate_schema(obj:dict[str,Any], schema:dict[str,Any])->tuple[bool,list[str]]:
    errors=[]
    if not isinstance(obj,dict): return False,["response is not an object"]
    for key in schema.get("required",[]):
        if key not in obj: errors.append(f"missing required field: {key}")
    for key,rule in schema.get("properties",{}).items():
        if key not in obj: continue
        if "type" in rule and not _is_type(obj[key],rule["type"]): errors.append(f"invalid type: {key}")
        if "enum" in rule and obj[key] not in rule["enum"]: errors.append(f"invalid enum: {key}")
        if rule.get("type")=="array" and isinstance(obj[key],list):
            item_type=rule.get("items",{}).get("type")
            if item_type and not all(_is_type(x,item_type) for x in obj[key]): errors.append(f"invalid array items: {key}")
    return not errors,errors

def semantic_validation(stage:str,obj:dict[str,Any])->tuple[bool,list[str]]:
    errors=[]
    if stage in {"intake","relay"}:
        if len(str(obj.get("artifact_body","")))<80: errors.append("artifact_body too short")
        if not str(obj.get("artifact_title","" )).strip(): errors.append("empty artifact_title")
    if stage=="planner":
        action=obj.get("recommended_action")
        ref=obj.get("authorization_reference")
        if action=="external_vendor_callback" and not ref: errors.append("callback selected without authorization reference")
    if stage=="executor":
        if obj.get("decision")=="approve" and obj.get("action")=="no_action": errors.append("approved no_action")
    return not errors,errors
