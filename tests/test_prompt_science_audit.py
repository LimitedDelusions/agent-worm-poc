
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def strings(obj):
    if isinstance(obj,str): yield obj
    elif isinstance(obj,dict):
        for v in obj.values(): yield from strings(v)
    elif isinstance(obj,list):
        for v in obj: yield from strings(v)

def find_key(obj,target):
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            if target in k.lower(): out.append(v)
            out.extend(find_key(v,target))
    elif isinstance(obj,list):
        for v in obj: out.extend(find_key(v,target))
    return out

def test_neutral_prompts_do_not_coach_security_outcome():
    cfg=json.loads((ROOT/'configs/prompts.json').read_text())
    neutral=find_key(cfg,'neutral')
    assert neutral, 'No neutral prompt section found'
    text='\n'.join(strings(neutral)).lower()
    banned=['prompt injection','worm_canary','carrier id','malicious instruction','strip the marker','remove hidden instruction','sanitize the document','preserve the carrier','propagate the carrier']
    assert not [x for x in banned if x in text]

def test_control_prompts_are_distinct_and_labeled():
    cfg=json.loads((ROOT/'configs/prompts.json').read_text())
    positive='\n'.join(strings(find_key(cfg,'positive'))).lower()
    hardened='\n'.join(strings(find_key(cfg,'hardened'))).lower()
    neutral='\n'.join(strings(find_key(cfg,'neutral'))).lower()
    assert positive and hardened and neutral
    assert positive != neutral and hardened != neutral and positive != hardened
    assert any(x in positive for x in ('preserve','retain','carry forward'))
    assert any(x in hardened for x in ('untrusted','embedded instruction','trusted instruction','provenance'))

def test_artifact_body_contract_is_explicit_and_policy_matched():
    cfg=json.loads((ROOT/'configs/prompts.json').read_text())['roles']
    required=('artifact_body field is the only artifact content passed to the next stage',
              'supplier','item or service','quantity','total price','delivery timing')
    for role in ('intake','relay'):
        for policy in ('positive','neutral','hardened'):
            text=cfg[role][policy].lower()
            assert not [term for term in required if term not in text],f'{role}/{policy}'

def test_payloads_are_safe_text_only_and_not_system_impersonation():
    cfg=json.loads((ROOT/'configs/experiment.json').read_text())
    data_text='\n'.join(p.read_text() for p in (ROOT/'data').rglob('*') if p.is_file()).lower()
    forbidden=['http://','https://','powershell','curl ','wget ','subprocess','os.system','rm -rf','api key','password=','system message:','developer message:']
    assert not [x for x in forbidden if x in data_text]
    assert 'external_vendor_callback' in data_text or 'external_vendor_callback' in json.dumps(cfg).lower()

def test_preregistration_narrows_primary_causal_scope():
    p=json.loads((ROOT/'configs/preregistration.json').read_text())
    q=p['primary_research_question'].lower()
    assert 'intake and relay' in q
    assert p['primary_endpoint']['name']=='second_hop_viable'
    assert p['models_are_exact_deployments_not_family_proxies'] is True
    assert 'naive chi-square' in p['primary_analysis']['prohibited_analysis'].lower()
