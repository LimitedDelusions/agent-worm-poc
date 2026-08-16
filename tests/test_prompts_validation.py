from agent_worm_poc.config import load_prompts,load_schemas,load_experiment,load_models
from agent_worm_poc.cases import build_main_cases
from agent_worm_poc.prompts import build_messages,next_input
from agent_worm_poc.validation import validate_schema,semantic_validation

def test_system_user_separation(root):
    prompts=load_prompts(root/'configs/prompts.json');schemas=load_schemas(root/'configs/schemas.json');cfg=load_experiment(root/'configs/experiment.json');models=load_models(root/'configs/models.json')
    case=next(c for c in build_main_cases(cfg,[m.slot for m in models],root/'data/base_documents') if c.policy=='neutral' and c.scenario_kind=='injected')
    messages=build_messages('intake',case,case.source_document,prompts,schemas)
    assert [m['role'] for m in messages]==['system','user']
    assert case.carrier.carrier_id not in messages[0]['content']
    assert case.carrier.carrier_id in messages[1]['content']

def test_schema_does_not_ask_model_to_report_carrier(root):
    schemas=load_schemas(root/'configs/schemas.json')
    text=str(schemas).lower()
    for term in ('carrier','canary','injection_detected','marker_detected'):assert term not in text

def test_schema_and_semantic_validation(root):
    schemas=load_schemas(root/'configs/schemas.json')
    obj={'artifact_title':'x','artifact_body':'a'*100,'supplier':'s','item':'i','quantity':'1','total_price':'$1','delivery':'today'}
    assert validate_schema(obj,schemas['intake'])[0]
    assert semantic_validation('intake',obj)[0]

def test_next_agent_receives_generated_artifact_only():
    parsed={'artifact_title':'x','artifact_body':'GENERATED ARTIFACT','supplier':'s'}
    assert next_input('intake',parsed)=='GENERATED ARTIFACT'
