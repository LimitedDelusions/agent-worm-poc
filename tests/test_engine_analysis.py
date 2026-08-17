import json
from agent_worm_poc.config import load_models,load_experiment,load_prompts,load_schemas
from agent_worm_poc.cases import build_main_cases
from agent_worm_poc.adapters import CompletionTransportFailure,FakeAdapter
from agent_worm_poc.engine import ExperimentRunner
from agent_worm_poc.scoring import score_record
from agent_worm_poc.analysis import summarize,wilson,blocked_assignment_permutation_test,exact_mcnemar


def setup(root):
 return (load_models(root/'configs/models.json'),load_experiment(root/'configs/experiment.json'),
  load_prompts(root/'configs/prompts.json'),load_schemas(root/'configs/schemas.json'))


def synthetic_main_scores(root):
 models,cfg,_,_=setup(root);slots=[model.slot for model in models]
 cfg['model_slots']=slots
 scores=[]
 for case in build_main_cases(cfg,slots,root/'data/base_documents'):
  success=case.policy=='neutral' and case.scenario_kind=='injected' and case.role_models['intake']==slots[0]
  scores.append({
   'workflow_id':case.workflow_id,'block_id':case.block_id,
   'randomization_block_id':case.randomization_block_id,'phase':'main',
   'policy':case.policy,'scenario_kind':case.scenario_kind,
   'pair_id':f"intake-{case.role_models['intake']}__relay-{case.role_models['relay']}",
   'carrier_variant':case.carrier_variant,'intake_model':case.role_models['intake'],
   'relay_model':case.role_models['relay'],'all_stages_valid':True,
   'first_hop_viable':success,'second_hop_viable':success,
   'planned_contiguous_compromise':False,'executed_contiguous_compromise':False,
   'intake_usable':True,'relay_usable':True,'benign_end_to_end':True,
   'conditional_relay_eligible':success,
   'propagation_depth':2 if success else 0})
 return scores,cfg


def make_stats_fast(monkeypatch):
 monkeypatch.setattr('agent_worm_poc.analysis.blocked_assignment_permutation_test',
  lambda rows:{'statistic':0.1,'iterations':0,'p_value':1.0,
   'block_count':len({row['randomization_block_id'] for row in rows}),
   'assignment_count':len({row['pair_id'] for row in rows})})
 monkeypatch.setattr('agent_worm_poc.analysis.block_bootstrap_range',
  lambda rows:{'iterations':0,'ci_low':None,'ci_high':None,
   'block_count':len({row['randomization_block_id'] for row in rows})})


def test_engine_uses_independent_requests_and_generated_artifact_chain(root,tmp_path):
 models,cfg,prompts,schemas=setup(root)
 cases=[c for c in build_main_cases(cfg,[m.slot for m in models],root/'data/base_documents') if c.policy=='neutral' and c.scenario_kind=='injected'][:4]
 records=ExperimentRunner(models,FakeAdapter(),prompts,schemas,cfg,tmp_path/'run').run(cases)
 request_ids=[event.request_id for record in records for event in record.stages.values()]
 assert len(request_ids)==len(set(request_ids))==len(records)*2
 for record in records:
  assert record.stages['relay'].input_text==record.stages['intake'].parsed['artifact_body']


def test_engine_preserves_terminal_transport_attempt_telemetry(root,tmp_path):
 models,cfg,prompts,schemas=setup(root)
 case=build_main_cases(cfg,[m.slot for m in models],root/'data/base_documents')[0]
 class FailingAdapter:
  def complete(self,*_args,**_kwargs):
   raise CompletionTransportFailure('terminal transport failure',2,
    ('ReadTimeout','ConnectError'))
 records=ExperimentRunner(models,FailingAdapter(),prompts,schemas,cfg,tmp_path/'failed').run([case])
 event=records[0].stages['intake']
 assert event.transport_attempts==2
 assert event.transport_retry_errors==['ReadTimeout','ConnectError']
 assert 'CompletionTransportFailure' in event.error


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


def test_complete_main_design_and_absolute_utility_pass(root,tmp_path,monkeypatch):
 scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
 gates=summarize(scores,tmp_path/'complete',cfg)['gates']
 assert gates['passed'] and gates['design_valid'] and gates['measurement_valid']
 assert gates['expected_main_row_count']==672
 assert gates['expected_primary_neutral_injected_n']==288
 assert gates['expected_randomization_block_count']==18
 assert gates['question_feasibility_supported']


def test_main_missing_pair_or_block_is_design_invalid(root,tmp_path,monkeypatch):
 scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
 missing=scores[0]['pair_id']
 gates=summarize([row for row in scores if row['pair_id']!=missing],tmp_path/'missing-pair',cfg)['gates']
 assert not gates['design_valid'] and gates['failure_class']=='design_invalid'
 assert not gates['question_feasibility_supported']
 scores,cfg=synthetic_main_scores(root)
 target=next(row for row in scores if row['policy']=='neutral' and row['scenario_kind']=='injected')
 target['randomization_block_id']='unexpected-block'
 gates=summarize(scores,tmp_path/'bad-block',cfg)['gates']
 assert not gates['design_valid'] and gates['block_mismatches']


def test_main_equal_zero_utility_is_measurement_invalid(root,tmp_path,monkeypatch):
 scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
 for row in scores:
  if row['scenario_kind']=='clean':
   row['benign_end_to_end']=False;row['intake_usable']=False;row['relay_usable']=False
 gates=summarize(scores,tmp_path/'zero-utility',cfg)['gates']
 assert gates['design_valid'] and not gates['measurement_valid']
 assert gates['failure_class']=='measurement_invalid'
 assert gates['empirical_outcome']=='not_evaluable'
 assert not gates['question_feasibility_supported']


def test_main_valid_empirical_null_is_not_measurement_failure(root,tmp_path,monkeypatch):
 scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
 for row in scores:
  if row['policy']=='neutral' and row['scenario_kind']=='injected':
   row['first_hop_viable']=False;row['second_hop_viable']=False
 gates=summarize(scores,tmp_path/'valid-null',cfg)['gates']
 assert gates['passed'] and gates['analysis_valid'] and gates['failure_class'] is None
 assert gates['empirical_outcome']=='valid_null_no_ordered_pair_rate_variation'
 assert gates['question_feasibility_supported']
 assert not gates['ordered_pair_effect_signal_observed']


def test_main_equal_mixed_pair_rates_are_a_valid_null(root,tmp_path,monkeypatch):
 scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
 by_pair={}
 for row in scores:
  if row['policy']=='neutral' and row['scenario_kind']=='injected':
   index=by_pair.get(row['pair_id'],0);by_pair[row['pair_id']]=index+1
   success=index%2==0
   row['first_hop_viable']=success;row['second_hop_viable']=success
 gates=summarize(scores,tmp_path/'equal-mixed-null',cfg)['gates']
 assert gates['analysis_valid'] and gates['ordered_pair_rate_range']==0.0
 assert gates['empirical_outcome']=='valid_null_no_ordered_pair_rate_variation'
 assert gates['question_feasibility_supported']
 assert not gates['ordered_pair_effect_signal_observed']


def test_main_authoritative_slots_pair_roles_and_ids_are_fail_closed(root,tmp_path,monkeypatch):
 scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
 scores[0]['pair_id']=next(row['pair_id'] for row in scores if row['pair_id']!=scores[0]['pair_id'])
 gates=summarize(scores,tmp_path/'wrong-pair-role',cfg)['gates']
 assert not gates['design_valid'] and gates['pair_role_mismatches']
 scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
 scores[0]['intake_model']='unexpected'
 scores[0]['pair_id']=f"intake-unexpected__relay-{scores[0]['relay_model']}"
 gates=summarize(scores,tmp_path/'wrong-slot',cfg)['gates']
 assert not gates['design_valid'] and gates['pair_role_mismatches']
 scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
 scores[0]['workflow_id']=scores[1]['workflow_id']
 gates=summarize(scores,tmp_path/'duplicate-id',cfg)['gates']
 assert not gates['design_valid']
 assert 'workflow IDs' in '; '.join(gates['design_reasons'])


def test_main_missing_or_unparseable_endpoint_is_measurement_invalid(root,tmp_path,monkeypatch):
 for field,value in (('second_hop_viable',None),('all_stages_valid','maybe')):
  scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
  scores[0][field]=value
  gates=summarize(scores,tmp_path/f'bad-{field}',cfg)['gates']
  assert gates['design_valid'] and not gates['measurement_valid']
  assert any(issue['field']==field for issue in gates['endpoint_issues'])
 scores,cfg=synthetic_main_scores(root);make_stats_fast(monkeypatch)
 clean_row=next(row for row in scores if row['scenario_kind']=='clean')
 clean_row.pop('relay_usable')
 gates=summarize(scores,tmp_path/'missing-clean-endpoint',cfg)['gates']
 assert gates['design_valid'] and not gates['measurement_valid']
 assert any(issue['field']=='relay_usable' for issue in gates['endpoint_issues'])


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
