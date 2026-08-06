#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.6.0}"
MAX_RUNTIME="${AGENT_WORM_MAX_RUNTIME:-6h}"
POC_REPS="${POC_REPETITIONS:-1}"
SESSION_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUTPUT_ROOT="/workspace/agent_worm_outputs/$SESSION_ID"
PID_FILE="/workspace/agent_worm_outputs/active.pid"
LATEST_FILE="/workspace/agent_worm_outputs/latest_session.txt"

fail() {
  echo "ERROR: $*" >&2
  exit 64
}

[[ -d "$ROOT" ]] || fail "project directory not found: $ROOT"
[[ -f "$ROOT/SOURCE_HASHES.sha256" ]] || fail "project integrity file is missing"
[[ "${AGENT_WORM_IMAGE_REF:-}" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] \
  || fail "AGENT_WORM_IMAGE_REF must be the exact lowercase GHCR digest from RUNPOD_IMAGE.txt"
[[ "$MAX_RUNTIME" =~ ^[1-9][0-9]*[smhd]$ ]] \
  || fail "AGENT_WORM_MAX_RUNTIME must look like 90m, 6h, or 1d"
[[ "$POC_REPS" =~ ^[1-3]$ ]] \
  || fail "POC_REPETITIONS must be 1, 2, or 3 for this cost-controlled POC"
[[ "${RUNPOD_HOURLY_RATE:-}" =~ ^[0-9]+([.][0-9]+)?$ ]] \
  || fail "set RUNPOD_HOURLY_RATE to the total hourly price displayed by RunPod"
if ! python - <<'PY' >/dev/null
import os
rate=float(os.environ['RUNPOD_HOURLY_RATE'])
if rate <= 0:
    raise SystemExit(1)
PY
then
  fail "RUNPOD_HOURLY_RATE must be greater than zero"
fi
command -v timeout >/dev/null 2>&1 || fail "GNU timeout is unavailable in this container"
command -v setsid >/dev/null 2>&1 || fail "setsid is unavailable in this container"

is_agent_worm_pid() {
  local pid="$1" cmdline
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$ROOT/scripts/runpod/gated_run_inner.sh"* ]]
}

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if is_agent_worm_pid "$OLD_PID"; then
    echo "ERROR: a gated run is already active as PID $OLD_PID." >&2
    echo "Use: bash $ROOT/scripts/runpod/status.sh" >&2
    exit 73
  fi
  echo "Removing stale active-run PID file."
  rm -f "$PID_FILE"
fi

mkdir -p "$OUTPUT_ROOT/session"
printf '%s\n' "$OUTPUT_ROOT" > "$LATEST_FILE"

export SESSION_ID MAX_RUNTIME POC_REPS OUTPUT_ROOT
python - "$OUTPUT_ROOT/session/launch.json" <<'PY'
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

value = {
    "schema_version": 2,
    "session_id": os.environ["SESSION_ID"],
    "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "started_epoch": time.time(),
    "maximum_runtime": os.environ["MAX_RUNTIME"],
    "poc_repetitions": int(os.environ["POC_REPS"]),
    "runpod_hourly_rate_usd": float(os.environ["RUNPOD_HOURLY_RATE"]),
    "runpod_pod_id": os.environ.get("RUNPOD_POD_ID"),
    "runpod_gpu_name": os.environ.get("RUNPOD_GPU_NAME"),
    "container_image_reference": os.environ["AGENT_WORM_IMAGE_REF"],
    "project_root": os.environ.get("AGENT_WORM_PROJECT_ROOT", "/workspace/agent_worm_poc_v0.6.0"),
    "note": "Cost timing begins when this gated command starts, not when the Pod was first created.",
}
Path(sys.argv[1]).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
PY

nohup setsid env \
  AGENT_WORM_PROJECT_ROOT="$ROOT" \
  AGENT_WORM_OUTPUT_ROOT="$OUTPUT_ROOT" \
  AGENT_WORM_MAX_RUNTIME="$MAX_RUNTIME" \
  POC_REPETITIONS="$POC_REPS" \
  PYTHONPATH="$ROOT/src" \
  timeout --signal=TERM --kill-after=10m "$MAX_RUNTIME" \
  bash "$ROOT/scripts/runpod/gated_run_inner.sh" \
  > "$OUTPUT_ROOT/session/gated-run.log" 2>&1 &
PID=$!
printf '%s\n' "$PID" > "$PID_FILE"
printf '%s\n' "$PID" > "$OUTPUT_ROOT/session/gated-run.pid"

cat <<INFO
Started Agent Worm POC gated run.

Session: $SESSION_ID
PID: $PID
Maximum runtime: $MAX_RUNTIME
POC repetitions: $POC_REPS
Output directory: $OUTPUT_ROOT

Monitor progress:
  bash $ROOT/scripts/runpod/status.sh

Cancel safely and package partial evidence:
  bash $ROOT/scripts/runpod/cancel_run.sh
INFO
