#!/usr/bin/env bash
set -Eeuo pipefail

OUTPUT_ROOT="${1:-}"
ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.6.0}"
if [[ -z "$OUTPUT_ROOT" || ! -d "$OUTPUT_ROOT" ]]; then
  echo "Usage: $0 /workspace/agent_worm_outputs/SESSION_ID" >&2
  exit 2
fi
export PYTHONPATH="$ROOT/src"
python -m agent_worm_poc.cli \
  --project-root "$ROOT" \
  --output-root "$OUTPUT_ROOT" \
  package --destination-dir /workspace
