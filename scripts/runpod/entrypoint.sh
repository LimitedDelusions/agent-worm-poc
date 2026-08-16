#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="0.8.2"
SOURCE_DIR="/opt/agent-worm-poc"
PROJECT_DIR="/workspace/agent_worm_poc_v${VERSION}"
TEMP_DIR="${PROJECT_DIR}.incoming"
OUTPUT_BASE="/workspace/agent_worm_outputs"
JUPYTER_CONFIG_DIR="/tmp/agent-worm-jupyter"

if [[ -z "${JUPYTER_PASSWORD:-}" || ${#JUPYTER_PASSWORD} -lt 16 || "${JUPYTER_PASSWORD}" == *"RUNPOD_SECRET"* || "${JUPYTER_PASSWORD}" == *"{{"* ]]; then
  echo "ERROR: JUPYTER_PASSWORD is required, must resolve from a RunPod secret, and must contain at least 16 characters." >&2
  exit 64
fi
if [[ -z "${HF_TOKEN:-}" || "${HF_TOKEN}" != hf_* ]]; then
  echo "ERROR: HF_TOKEN must resolve from a read-only Hugging Face secret." >&2
  exit 64
fi
if [[ ! -f /opt/agent-worm-runtime.json ]]; then
  echo "ERROR: prebuilt runtime marker missing. Do not install vLLM on paid GPU time." >&2
  exit 70
fi
if [[ ! -f "$SOURCE_DIR/SOURCE_HASHES.sha256" ]]; then
  echo "ERROR: validated source manifest is missing from the image." >&2
  exit 70
fi
mkdir -p /workspace "$OUTPUT_BASE" "$JUPYTER_CONFIG_DIR" "${HF_HOME:-/workspace/hf-cache}"
rm -rf "$TEMP_DIR"
cp -a "$SOURCE_DIR" "$TEMP_DIR"
rm -rf "$PROJECT_DIR"
mv "$TEMP_DIR" "$PROJECT_DIR"
chmod -R u+rwX "$PROJECT_DIR"
(cd "$PROJECT_DIR" && python scripts/release/generate_integrity.py --check >/tmp/agent-worm-manifest-check.txt)
(cd "$PROJECT_DIR" && sha256sum -c SOURCE_HASHES.sha256 >/tmp/agent-worm-source-check.txt)
export AGENT_WORM_PROJECT_ROOT="$PROJECT_DIR"
export AGENT_WORM_WORKSPACE="/workspace"
export HF_HOME="${HF_HOME:-/workspace/hf-cache}"
export PYTHONPATH="$PROJECT_DIR/src"
export CONTAINER_IMAGE="${AGENT_WORM_IMAGE_REF:-unknown}"
if [[ -f /opt/agent-worm-runtime.json ]]; then
  export GIT_COMMIT="$(python - <<'PYCODE'
import json
print(json.load(open('/opt/agent-worm-runtime.json')).get('git_revision','unknown'))
PYCODE
)"
fi

HASHED_PASSWORD=$(/opt/jupyter-venv/bin/python - <<'PYCODE'
import os
from jupyter_server.auth import passwd
print(passwd(os.environ['JUPYTER_PASSWORD']))
PYCODE
)
export HASHED_PASSWORD JUPYTER_CONFIG_DIR
/opt/jupyter-venv/bin/python - <<'PYCODE'
import os
from pathlib import Path
path=Path(os.environ['JUPYTER_CONFIG_DIR'])/'jupyter_server_config.py'
value=os.environ['HASHED_PASSWORD']
path.write_text('\n'.join([
 'c.ServerApp.ip = "0.0.0.0"','c.ServerApp.port = 8888','c.ServerApp.port_retries = 0',
 'c.ServerApp.open_browser = False','c.ServerApp.allow_root = True',
 'c.ServerApp.allow_remote_access = True','c.ServerApp.trust_xheaders = True',
 'c.ServerApp.root_dir = "/workspace"','c.ServerApp.quit_button = False',
 f'c.PasswordIdentityProvider.hashed_password = {value!r}',
 'c.PasswordIdentityProvider.password_required = True','c.IdentityProvider.token = ""','']),encoding='utf-8')
PYCODE
unset HASHED_PASSWORD
cat <<INFO
Agent Worm POC v${VERSION} is ready.
Project: ${PROJECT_DIR}
Outputs: ${OUTPUT_BASE}
No model or experiment starts automatically.
INFO
exec /usr/bin/tini -- /opt/jupyter-venv/bin/jupyter lab --config="$JUPYTER_CONFIG_DIR/jupyter_server_config.py"
