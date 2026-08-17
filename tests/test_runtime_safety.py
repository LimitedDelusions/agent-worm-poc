import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
import time
import zipfile
import pytest
import agent_worm_poc.cli as cli
from agent_worm_poc.cli import (_BudgetTimeout,_RunStatusTracker,_atomic_write_json,_finalize_evidence,
                                _termination_outcome,claim_real_run_sentinel,emergency_package)
from agent_worm_poc.server import VLLMServerManager,_model_server_environment,_verify_runtime_artifacts
from agent_worm_poc.types import ModelSpec


def _fake_package(_root,run_dir,output_path):
 status=(run_dir/'RUN_STATUS.json').read_bytes();relative='run/RUN_STATUS.json'
 manifest={'file_count':1,'files':[{'path':relative,'size':len(status),
  'sha256':hashlib.sha256(status).hexdigest()}]}
 output_path.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output_path,'w',zipfile.ZIP_DEFLATED) as archive:
  archive.writestr('evidence_package/'+relative,status)
  archive.writestr('evidence_package/PACKAGE_MANIFEST.json',json.dumps(manifest))
 digest=hashlib.sha256(output_path.read_bytes()).hexdigest()
 metadata={'zip':str(output_path),'sha256':digest,'size':output_path.stat().st_size,
           'manifest_files':1}
 output_path.with_suffix(output_path.suffix+'.json').write_text(json.dumps(metadata)+'\n')
 output_path.with_suffix(output_path.suffix+'.sha256').write_text(f'{digest}  {output_path.name}\n')
 return metadata


def test_server_refuses_mutable_revision(tmp_path):
 model=ModelSpec('x','x','repo','RESOLVE_AT_GATE','RESOLVE_AT_GATE','x','auto',8192)
 with pytest.raises(RuntimeError):VLLMServerManager(tmp_path).start(model)


def test_model_server_environment_keeps_hf_token_only(monkeypatch):
 monkeypatch.setenv('HF_TOKEN','hf_read_only')
 monkeypatch.setenv('LD_LIBRARY_PATH','/usr/local/cuda/lib64')
 for name in ('JUPYTER_PASSWORD','RUNPOD_API_KEY','GITHUB_TOKEN','AWS_SESSION_TOKEN','OPENAI_API_KEY',
              'DATABASE_URL','SSH_AUTH_SOCK','KUBECONFIG','HTTPS_PROXY'):
  monkeypatch.setenv(name,'must-not-propagate')
 environment=_model_server_environment()
 assert environment['HF_TOKEN']=='hf_read_only'
 assert environment['LD_LIBRARY_PATH']=='/usr/local/cuda/lib64'
 assert all(name not in environment for name in ('JUPYTER_PASSWORD','RUNPOD_API_KEY','GITHUB_TOKEN',
  'AWS_SESSION_TOKEN','OPENAI_API_KEY','DATABASE_URL','SSH_AUTH_SOCK','KUBECONFIG','HTTPS_PROXY'))


def test_model_server_environment_requires_hf_token(monkeypatch):
 monkeypatch.delenv('HF_TOKEN',raising=False)
 with pytest.raises(RuntimeError,match='HF_TOKEN'):_model_server_environment()


def test_reasoning_parser_hash_is_rechecked(tmp_path):
 artifact=tmp_path/'parser.py';artifact.write_text('# frozen\n')
 from agent_worm_poc.util import sha256_file
 model=ModelSpec('x','x','repo','r'*40,'r'*40,'x','auto',8192,
  reasoning_parser_plugin_local_path=str(artifact),reasoning_parser_plugin_sha256=sha256_file(artifact))
 _verify_runtime_artifacts(model)
 artifact.write_text('# tampered\n')
 with pytest.raises(RuntimeError):_verify_runtime_artifacts(model)


def test_reasoning_parser_link_is_rejected(tmp_path):
 artifact=tmp_path/'parser.py';artifact.write_text('# frozen\n');link=tmp_path/'linked-parser.py'
 try:link.symlink_to(artifact)
 except (NotImplementedError,OSError) as exc:pytest.skip(f'symlinks unavailable: {exc}')
 from agent_worm_poc.util import sha256_file
 model=ModelSpec('x','x','repo','r'*40,'r'*40,'x','auto',8192,
  reasoning_parser_plugin_local_path=str(link),reasoning_parser_plugin_sha256=sha256_file(artifact))
 with pytest.raises(RuntimeError):_verify_runtime_artifacts(model)


def test_no_runtime_install_in_paid_scripts(root):
 text='\n'.join(path.read_text() for path in (root/'scripts/runpod').rglob('*.sh'))
 for forbidden in ('pip install','uv pip install','apt-get install','conda install'):assert forbidden not in text


def test_jupyter_requires_password_and_hf_secret(root):
 text=(root/'scripts/runpod/entrypoint.sh').read_text()
 assert 'JUPYTER_PASSWORD is required' in text and 'HF_TOKEN' in text


def test_cost_kill_switch_and_background_controls(root):
 text=(root/'scripts/runpod/start_gated_run.sh').read_text()
 assert 'timeout --signal=USR1' in text and 'MAX_GPU_HOURS' in text and 'MAX_TOTAL_COST_USD' in text
 assert 'nohup setsid' in text and 'AGENT_WORM_PRECREATED_RUN_DIR=1' in text
 assert 'Type the displayed hourly rate exactly' in text and 'AGENT_WORM_LAUNCH_ACK' in text
 assert 'hf_hub_download' in text and 'config.json' in text


def test_real_run_sentinel_is_atomic_and_permanent(tmp_path):
 sentinel=tmp_path/'claim.json';claim_real_run_sentinel(sentinel,{'session_id':'first'})
 with pytest.raises(FileExistsError):claim_real_run_sentinel(sentinel,{'session_id':'second'})
 assert json.loads(sentinel.read_text())=={'session_id':'first'}


def test_real_gated_rejects_direct_launcher_bypass(tmp_path,monkeypatch):
 monkeypatch.delenv('AGENT_WORM_RUN_ID',raising=False)
 monkeypatch.delenv('AGENT_WORM_PRECREATED_RUN_DIR',raising=False)
 with pytest.raises(RuntimeError,match='guarded RunPod launcher'):
  cli.gated(tmp_path,tmp_path/'outputs','real')


def test_status_tracker_records_heartbeat_phase_progress_and_budget(tmp_path):
 now=time.time();status={'started_epoch':now-10,'progress':{}}
 tracker=_RunStatusTracker(tmp_path/'RUN_STATUS.json',status,{
  'started_epoch':now-5,'active_timeout_seconds':100,'hard_timeout_seconds':200})
 tracker.event('phase_initialized',phase='compatibility',expected_requests=12,workflows=4)
 tracker.event('model_start',model_slot='gemma')
 tracker.event('request_start',model_slot='gemma',stage='intake',workflow_id='w1')
 tracker.event('request_complete',failed=False);tracker.persist()
 observed=json.loads((tmp_path/'RUN_STATUS.json').read_text())
 assert observed['current_phase']=='compatibility'
 assert observed['current_model']=='gemma' and observed['current_stage']=='intake'
 assert observed['progress']['phase_completed_requests']==1
 assert observed['progress']['current_workflow_id']=='w1'
 assert observed['heartbeat_epoch']>=now and observed['elapsed_seconds']>=9
 assert 0<observed['budget']['remaining_active_seconds']<=100
 assert observed['budget']['remaining_hard_seconds']>observed['budget']['remaining_active_seconds']


def test_atomic_status_write_retries_temporary_windows_sharing_violation(tmp_path,monkeypatch):
 path=tmp_path/'RUN_STATUS.json';actual_replace=cli.os.replace;attempts=[]
 def flaky_replace(source,destination):
  attempts.append((source,destination))
  if len(attempts)<3:raise PermissionError('temporary sharing violation')
  actual_replace(source,destination)
 monkeypatch.setattr(cli.os,'replace',flaky_replace)
 _atomic_write_json(path,{'status':'running'})
 assert json.loads(path.read_text())=={'status':'running'} and len(attempts)==3
 assert not list(tmp_path.glob('.RUN_STATUS.json.*.tmp'))


def test_atomic_status_write_uses_unique_files_under_concurrency(tmp_path):
 path=tmp_path/'RUN_STATUS.json'
 def writer(worker):
  for sequence in range(20):_atomic_write_json(path,{'worker':worker,'sequence':sequence})
 with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(writer,range(6)))
 final=json.loads(path.read_text())
 assert final['worker'] in range(6) and final['sequence'] in range(20)
 assert not list(tmp_path.glob('.RUN_STATUS.json.*.tmp'))


def test_completed_status_is_published_only_after_verified_evidence(tmp_path,monkeypatch):
 root=tmp_path/'root';root.mkdir();run=tmp_path/'runs'/'r1';run.mkdir(parents=True)
 status={'run_id':'r1','started_epoch':time.time(),'status':'packaging',
         'execution_status':'completed','evidence_status':'packaging',
         'outcome_classification':'valid_null_no_ordered_pair_rate_variation'}
 (run/'RUN_STATUS.json').write_text(json.dumps(status)+'\n')
 monkeypatch.setattr(cli,'package_results',_fake_package)
 output=tmp_path/'runs'/'agent-worm-results-r1.zip'
 assert _finalize_evidence(root,run,output,status) is True
 standalone=(run/'RUN_STATUS.json').read_bytes()
 with zipfile.ZipFile(output) as archive:
  packaged=archive.read('evidence_package/run/RUN_STATUS.json')
 assert standalone==packaged
 final=json.loads(standalone)
 assert final['execution_status']=='completed'
 assert final['evidence_status']=='verified' and final['status']=='completed'


def test_packaging_failure_cannot_claim_completed(tmp_path,monkeypatch):
 run=tmp_path/'r1';run.mkdir();status={'run_id':'r1','started_epoch':time.time(),
  'status':'packaging','execution_status':'completed','evidence_status':'packaging',
  'outcome_classification':'technical_failure'}
 def fail_package(*_args,**_kwargs):raise OSError('disk full')
 monkeypatch.setattr(cli,'package_results',fail_package)
 assert _finalize_evidence(tmp_path,run,tmp_path/'result.zip',status) is False
 final=json.loads((run/'RUN_STATUS.json').read_text())
 assert final['execution_status']=='completed'
 assert final['evidence_status']=='failed' and final['status']=='evidence_failed'


def test_finalizer_rejects_ambiguous_outcome(tmp_path,monkeypatch):
 run=tmp_path/'r1';run.mkdir();status={'run_id':'r1','started_epoch':time.time(),
  'status':'packaging','execution_status':'aborted','evidence_status':'packaging',
  'outcome_classification':'running'}
 monkeypatch.setattr(cli,'package_results',_fake_package)
 assert _finalize_evidence(tmp_path,run,tmp_path/'result.zip',status) is False
 final=json.loads((run/'RUN_STATUS.json').read_text())
 assert final['status']=='evidence_failed' and 'terminal outcome' in final['evidence_error']


def test_emergency_package_recovers_dead_runner_as_aborted(tmp_path,monkeypatch):
 root=tmp_path/'root';root.mkdir();(root/'VERSION').write_text('0.8.8\n')
 run=tmp_path/'runs'/'r1';run.mkdir(parents=True);output=tmp_path/'runs'/'forced.zip'
 monkeypatch.setattr(cli,'package_results',_fake_package)
 assert emergency_package(root,run,output)==0
 status=json.loads((run/'RUN_STATUS.json').read_text())
 assert status['execution_status']=='aborted' and status['status']=='aborted'
 assert status['evidence_status']=='verified' and status['error']
 assert status['outcome_classification']=='technical_failure'


def test_emergency_package_records_operator_cancellation(tmp_path,monkeypatch):
 root=tmp_path/'root';root.mkdir();(root/'VERSION').write_text('0.8.8\n')
 run=tmp_path/'runs'/'r1';run.mkdir(parents=True);output=tmp_path/'runs'/'forced.zip'
 monkeypatch.setenv('AGENT_WORM_EMERGENCY_OUTCOME','operator_cancelled')
 monkeypatch.setattr(cli,'package_results',_fake_package)
 assert emergency_package(root,run,output)==0
 status=json.loads((run/'RUN_STATUS.json').read_text())
 assert status['outcome_classification']=='operator_cancelled'


def test_budget_timeout_is_distinct_from_operator_and_technical_failure():
 assert _termination_outcome(_BudgetTimeout())=='budget_timeout'
 assert _termination_outcome(KeyboardInterrupt())=='operator_cancelled'
 assert _termination_outcome(RuntimeError())=='technical_failure'


def test_runpod_scripts_enforce_single_launch_and_recover_dead_runner(root):
 start=(root/'scripts/runpod/start_gated_run.sh').read_text()
 cancel=(root/'scripts/runpod/cancel_run.sh').read_text()
 status=(root/'scripts/runpod/status.sh').read_text()
 assert 'flock -n' in start and 'claim_real_run_sentinel' in start
 assert "len(rows)!=1" in start and "'A100'" in start and '300 * 1024 * 1024 * 1024' in start
 assert 'torch.cuda.is_available()' in start and 'torch.cuda.is_bf16_supported()' in start
 assert 'timeout --signal=USR1' in start
 assert 'GRACE_SECONDS:-420' in cancel and 'GRACE_SECONDS > 330' in cancel
 assert 'member_is_runner' in cancel and 'pgrep -g "$PID"' in cancel
 assert "${ARGS[1]}" in cancel and 'RUNNER_MATCHES' in cancel
 assert 'for MEMBER in $(' not in cancel and 'for CANDIDATE in $(' not in cancel
 assert 'continuing with orphan cleanup and evidence recovery' in cancel
 assert 'emergency-package' in cancel and "'[v]llm[[:space:]]+serve'" in cancel
 assert 'Existing canonical evidence is already complete and verified' in cancel
 assert 'RECOVERY_RC=0' in (root/'scripts/runpod/stage_and_send_evidence.sh').read_text()
 for field in ('heartbeat','current_phase','current_model','current_stage','remaining_active_seconds',
               'outcome_classification'):
  assert field in status


def test_gpu_memory_query_failure_is_fatal(tmp_path,monkeypatch):
 def fail(*_args,**_kwargs):raise subprocess.CalledProcessError(1,'nvidia-smi')
 monkeypatch.setattr(subprocess,'check_output',fail)
 with pytest.raises(RuntimeError,match='Could not query GPU memory'):
  VLLMServerManager(tmp_path).ensure_idle()


def test_operational_scripts_exist(root):
 for name in ('entrypoint.sh','start_gated_run.sh','status.sh','cancel_run.sh',
              'stage_and_send_evidence.sh'):
  assert (root/'scripts/runpod'/name).exists()


def test_container_exposes_python_runtime_alias(root):
 text=(root/'Dockerfile').read_text()
 assert 'ln -sf "$(command -v python3)" /usr/local/bin/python' in text
 assert 'python --version' in text


def test_ci_and_container_use_module_pytest_for_repo_root_imports(root):
 workflow=(root/'.github/workflows/validate-and-build.yml').read_text()
 docker=(root/'Dockerfile').read_text()
 assert 'python -m pytest -q' in workflow
 assert 'PYTHONPATH=/opt/agent-worm-poc/src python -m pytest -q' in docker


def test_server_uses_reproducibility_controls(root):
 text=(root/'src/agent_worm_poc/server.py').read_text()
 assert '--generation-config' in text and 'vllm' in text and '--code-revision' in text
 assert '--no-enable-prefix-caching' in text
 assert '_model_server_environment' in text and 'reasoning_parser_plugin_sha256' in text
 assert '"<redacted>"' in text
 assert 'finally' in (root/'src/agent_worm_poc/engine.py').read_text()
