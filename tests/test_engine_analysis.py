import json
from agent_worm_poc.config import load_models,load_experiment,load_prompts,load_schemas
from agent_worm_poc.cases import build_main_cases
from agent_worm_poc.adapters import FakeAdapter
from agent_worm_poc.engine import ExperimentRunner
from agent_worm_poc.scoring import score_record
from agent_worm_poc.analysis import summarize,wilson,blocked_assignment_permutation_test,exact_mcnemar


def setup(root):
 return (load_models(root/'configs/models.json'),load_experiment(root/'configs/experiment.json'),
  load_prompts(root/'configs/prompts.json'),load_schemas(root/'configs/schemas.json'))


def test_engine_uses_independent_requests_and_generated_artifact_chain(root,tmp_path):
 models,cfg,prompts,schemas=setup(root)
 cases=[c for c in build_main_cases(cfg,[m.slot for m in models],root/'data/base_documents') if c.policy=='neutral' and c.scenario_kind=='injected'][:4]
 records=ExperimentRunner(models,FakeAdapter(),prompts,schemas,cfg,tmp_path/'run').run(cases)
 request_ids=[event.request_id for record in records for event in record.stages.values()]
 assert len(request_ids)==len(set(request_ids))==len(records)*2
 for record in records:
  assert record.stages['relay'].input_text==record.stages['intake'].parsed['artifact_body']


def test_summary_writes_prespecified_outputs(root,tmp_path):
 models,cfg,prompts,schemas=setup(root)
 cases=[c for c in build_main_cases(cfg,[m.slot for m in models],root/'data/base_documents') if c.policy=='neutral' and c.scenario_kind=='injected'][:32]
 records=ExperimentRunner(models,FakeAdapter(),prompts,schemas,cfg,tmp_path/'run').run(cases)
 expected=json.loads((root/'configs/expected_facts.json').read_text())
 scores=[score_record(record,expected) for record in records]
 result=summarize(scores,tmp_path/'analysis',cfg)
 for name in ('transition_matrix.csv','assignment_summary.csv','prespecified_inference.json','NEXT_MEETING_SUMMARY.md'):
  assert (tmp_path/'analysis'/name).exists()
 assert result['workflow_count']==len(scores)


def test_wilson_and_exact_mcnemar():
 lo,hi=wilson(5,10);assert 0<lo<.5<hi<1
 assert exact_mcnemar(0,0)['p_value']==1.0
 assert exact_mcnemar(10,0)['p_value']<.01


def test_blocked_permutation_is_deterministic():
 rows=[]
 for block in ('b1','b2','b3'):
  for pair in ('a','b'):
   rows.append({'pair_id':pair,'randomization_block_id':block,'second_hop_viable':pair=='a'})
 first=blocked_assignment_permutation_test(rows,100,1)
 assert first==blocked_assignment_permutation_test(rows,100,1)
 assert first['assignment_count']==2 and first['block_count']==3
