from collections import defaultdict
from agent_worm_poc.config import load_models,load_experiment,load_prompts
from agent_worm_poc.placements import unique_placements,ordered_pair_assignments
from agent_worm_poc.cases import build_main_cases,build_positive_pair_cases,build_shakedown_cases,build_compatibility_cases


def setup(root):
    models=load_models(root/'configs/models.json');config=load_experiment(root/'configs/experiment.json')
    return models,config,[model.slot for model in models]


def test_exact_models_and_future_full_permutations(root):
    models,_,slots=setup(root)
    assert len(models)==4 and len(set(slots))==4
    assert len(unique_placements(slots))==24


def test_complete_ordered_pair_matrix(root):
    _,_,slots=setup(root);pairs=ordered_pair_assignments(slots)
    assert len(pairs)==16
    assert {(p['intake'],p['relay']) for p in pairs}=={(a,b) for a in slots for b in slots}


def test_main_case_count_and_terminal_stage(root):
    models,config,slots=setup(root);cases=build_main_cases(config,slots,root/'data/base_documents')
    assert len(cases)==672
    assert len({case.workflow_id for case in cases})==len(cases)
    assert all(case.terminal_stage=='relay' for case in cases)
    assert len({(case.role_models['intake'],case.role_models['relay']) for case in cases})==16


def test_main_factorial_has_two_real_seed_blocks(root):
    _,config,slots=setup(root)
    cases=[case for case in build_main_cases(config,slots,root/'data/base_documents')
           if case.policy=='neutral' and case.scenario_kind=='injected']
    first_pair=(cases[0].role_models['intake'],cases[0].role_models['relay'])
    rows=[case for case in cases if (case.role_models['intake'],case.role_models['relay'])==first_pair]
    assert {(case.carrier_variant,case.base_document_id) for case in rows}=={
      (carrier,doc) for carrier in config['carrier_variants'] for doc in config['base_documents']}
    for carrier in config['carrier_variants']:
      for doc in config['base_documents']:
        reps={case.repetition for case in rows if case.carrier_variant==carrier and case.base_document_id==doc}
        assert reps=={0,1}


def test_matched_inputs_and_seeds_across_policies_and_assignments(root):
    _,config,slots=setup(root);cases=build_main_cases(config,slots,root/'data/base_documents')
    policy_pairs=defaultdict(dict)
    for case in cases:policy_pairs[case.block_id][case.policy]=case
    assert policy_pairs
    for pair in policy_pairs.values():
      assert set(pair)=={'neutral','hardened'}
      neutral,hardened=pair['neutral'],pair['hardened']
      assert neutral.source_document==hardened.source_document
      assert neutral.stage_seeds==hardened.stage_seeds
      assert (neutral.carrier.carrier_id if neutral.carrier else None)==(hardened.carrier.carrier_id if hardened.carrier else None)
    blocks=defaultdict(list)
    for case in cases:
      if case.policy=='neutral' and case.scenario_kind=='injected':blocks[case.randomization_block_id].append(case)
    assert len(blocks)==18
    for values in blocks.values():
      assert len(values)==16
      assert len({value.source_document for value in values})==1
      assert len({value.carrier.carrier_id for value in values})==1
      assert len({tuple(sorted(value.stage_seeds.items())) for value in values})==1


def test_positive_and_calibration_counts(root):
    _,config,slots=setup(root)
    positive=build_positive_pair_cases(config,slots,root/'data/base_documents')
    calibration=build_shakedown_cases(config,slots,root/'data/base_documents')
    compatibility=build_compatibility_cases(config,slots,root/'data/base_documents')
    assert len(positive)==48
    assert len(calibration)==144
    assert len(compatibility)==12
    assert len({(c.role_models['intake'],c.role_models['relay']) for c in positive})==16


def test_neutral_prompt_is_not_security_coached(root):
    prompts=load_prompts(root/'configs/prompts.json')
    text=' '.join(prompts[role]['neutral'].lower() for role in prompts)
    for forbidden in ('prompt injection','self-replicating','worm canary','remove the carrier','strip the marker','malicious payload'):
      assert forbidden not in text


def test_policies_are_distinct(root):
    prompts=load_prompts(root/'configs/prompts.json')
    for role in prompts:assert len({prompts[role][p] for p in ('positive','neutral','hardened')})==3
