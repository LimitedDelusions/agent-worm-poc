#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.8.4}"
BASE="/workspace/agent_worm_outputs"
PID_FILE="$BASE/active.pid"
LATEST_FILE="$BASE/latest_session.txt"
MAX_GPU_HOURS="${MAX_GPU_HOURS:-8}"
MAX_TOTAL_COST_USD="${MAX_TOTAL_COST_USD:-25}"
RATE="${RUNPOD_HOURLY_RATE_USD:-${RUNPOD_HOURLY_RATE:-}}"
SESSION_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN_DIR="$BASE/$SESSION_ID"

fail(){ echo "ERROR: $*" >&2; exit 64; }
[[ -d "$ROOT" ]] || fail "project directory not found: $ROOT"
[[ -f "$ROOT/SOURCE_HASHES.sha256" ]] || fail "SOURCE_HASHES.sha256 is missing"
[[ "${AGENT_WORM_IMAGE_REF:-}" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || fail "AGENT_WORM_IMAGE_REF must be the exact GHCR digest"
[[ "$RATE" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "set RUNPOD_HOURLY_RATE_USD to the displayed total hourly rate"
[[ "$MAX_TOTAL_COST_USD" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "MAX_TOTAL_COST_USD must be numeric"
[[ "$MAX_GPU_HOURS" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "MAX_GPU_HOURS must be numeric"
command -v timeout >/dev/null || fail "GNU timeout is unavailable"
command -v setsid >/dev/null || fail "setsid is unavailable"
if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$OLD_PID" =~ ^[0-9]+$ ]] && kill -0 "$OLD_PID" 2>/dev/null; then fail "a gated run is already active as PID $OLD_PID"; fi
  rm -f "$PID_FILE"
fi
read -r BUDGET_SECONDS ACTIVE_SECONDS <<<"$(python - "$RATE" "$MAX_TOTAL_COST_USD" "$MAX_GPU_HOURS" <<'PYCODE'
import math,sys
rate,cap,hours=map(float,sys.argv[1:])
if min(rate,cap,hours)<=0:raise SystemExit('rate, cap, and hours must be positive')
hard=min(math.floor(hours*3600),math.floor(cap/rate*3600))
grace=600
if hard<1800:
    raise SystemExit('configured limits allow less than 30 minutes; increase the cap or hours before launch')
print(hard, hard-grace)
PYCODE
)"
mkdir -p "$RUN_DIR/session"
printf '%s\n' "$RUN_DIR" > "$LATEST_FILE"
ACTIVE_SECONDS="$ACTIVE_SECONDS" python - "$RUN_DIR/session/launch.json" "$SESSION_ID" "$RATE" "$MAX_TOTAL_COST_USD" "$BUDGET_SECONDS" <<'PYCODE'
import json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
path,session,rate,cap,seconds=sys.argv[1:]
Path(path).write_text(json.dumps({
 'schema_version':1,'session_id':session,'started_at':datetime.now(timezone.utc).isoformat(),
 'started_epoch':time.time(),'runpod_hourly_rate_usd':float(rate),'maximum_cost_usd':float(cap),
 'hard_timeout_seconds':int(seconds),'active_timeout_seconds':int(os.environ['ACTIVE_SECONDS']),
 'container_image_reference':os.environ['AGENT_WORM_IMAGE_REF'],
 'project_root':os.environ.get('AGENT_WORM_PROJECT_ROOT','/workspace/agent_worm_poc_v0.8.4')},indent=2)+'\n')
PYCODE
nohup setsid env AGENT_WORM_RUN_ID="$SESSION_ID" AGENT_WORM_PRECREATED_RUN_DIR=1 RUNPOD_HOURLY_RATE_USD="$RATE" \
  PYTHONPATH="$ROOT/src" timeout --signal=TERM --kill-after=10m "$ACTIVE_SECONDS" \
  python "$ROOT/scripts/run_gated.py" real-gated --root "$ROOT" --output-root "$BASE" \
  > "$RUN_DIR/session/gated-run.log" 2>&1 &
PID=$!
printf '%s\n' "$PID" > "$PID_FILE"
printf '%s\n' "$PID" > "$RUN_DIR/session/gated-run.pid"
cat <<INFO
Started Agent Worm POC v0.8.4.
Session: $SESSION_ID
PID: $PID
Maximum gated-run cost: \$$MAX_TOTAL_COST_USD at \$$RATE/hour
Active-run timeout: $ACTIVE_SECONDS seconds; hard stop including packaging grace: $BUDGET_SECONDS seconds
Monitor: bash $ROOT/scripts/runpod/status.sh
Cancel safely: bash $ROOT/scripts/runpod/cancel_run.sh
INFO
