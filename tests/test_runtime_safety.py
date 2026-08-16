import pytest
from agent_worm_poc.server import VLLMServerManager,_model_server_environment,_verify_runtime_artifacts
from agent_worm_poc.types import ModelSpec


def test_server_refuses_mutable_revision(tmp_path):
 model=ModelSpec('x','x','repo','RESOLVE_AT_GATE','RESOLVE_AT_GATE','x','auto',8192)
 with pytest.raises(RuntimeError):VLLMServerManager(tmp_path).start(model)


def test_model_server_environment_keeps_hf_token_only(monkeypatch):
 monkeypatch.setenv('HF_TOKEN','hf_read_only')
 for name in ('JUPYTER_PASSWORD','RUNPOD_API_KEY','GITHUB_TOKEN','AWS_SESSION_TOKEN','OPENAI_API_KEY'):
  monkeypatch.setenv(name,'must-not-propagate')
 environment=_model_server_environment()
 assert environment['HF_TOKEN']=='hf_read_only'
 assert all(name not in environment for name in ('JUPYTER_PASSWORD','RUNPOD_API_KEY','GITHUB_TOKEN','AWS_SESSION_TOKEN','OPENAI_API_KEY'))


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
 assert 'timeout --signal=TERM' in text and 'MAX_GPU_HOURS' in text and 'MAX_TOTAL_COST_USD' in text
 assert 'nohup setsid' in text and 'AGENT_WORM_PRECREATED_RUN_DIR=1' in text


def test_operational_scripts_exist(root):
 for name in ('entrypoint.sh','start_gated_run.sh','status.sh','cancel_run.sh'):
  assert (root/'scripts/runpod'/name).exists()


def test_container_exposes_python_runtime_alias(root):
 text=(root/'Dockerfile').read_text()
 assert 'ln -sf "$(command -v python3)" /usr/local/bin/python' in text
 assert 'python --version' in text


def test_server_uses_reproducibility_controls(root):
 text=(root/'src/agent_worm_poc/server.py').read_text()
 assert '--generation-config' in text and 'vllm' in text and '--code-revision' in text
 assert '--no-enable-prefix-caching' in text
 assert '_model_server_environment' in text and 'reasoning_parser_plugin_sha256' in text
 assert 'finally' in (root/'src/agent_worm_poc/engine.py').read_text()
