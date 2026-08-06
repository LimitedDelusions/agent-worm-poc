#!/usr/bin/env bash
set -Eeuo pipefail

BASE="/workspace/agent_worm_outputs"
LATEST_FILE="$BASE/latest_session.txt"
PID_FILE="$BASE/active.pid"

if [[ ! -f "$LATEST_FILE" ]]; then
  echo "No Agent Worm POC session has been started."
  exit 1
fi
OUTPUT_ROOT="$(cat "$LATEST_FILE")"
PID="$(cat "$PID_FILE" 2>/dev/null || true)"
ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.6.0}"
RUNNING=0
if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null; then
  CMDLINE="$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null || true)"
  if [[ "$CMDLINE" == *"$ROOT/scripts/runpod/gated_run_inner.sh"* ]]; then
    RUNNING=1
  fi
fi

echo "Session: $OUTPUT_ROOT"
if [[ "$RUNNING" -eq 1 ]]; then
  echo "Process: RUNNING (PID $PID)"
else
  echo "Process: NOT RUNNING"
fi

echo
echo "Status:"
if [[ -f "$OUTPUT_ROOT/session_status.json" ]]; then
  cat "$OUTPUT_ROOT/session_status.json"
else
  echo "Status file not created yet."
fi

echo
echo "Gated-run cost:"
if [[ "$RUNNING" -eq 0 && -f "$OUTPUT_ROOT/session/cost_estimate.json" ]]; then
  cat "$OUTPUT_ROOT/session/cost_estimate.json"
  echo "The Pod can continue billing after the gated run ends. Download evidence and terminate it."
else
  python - "$OUTPUT_ROOT/session/launch.json" <<'PY'
import json, sys, time
from pathlib import Path
path=Path(sys.argv[1])
if not path.exists():
    print("Launch metadata not available yet.")
    raise SystemExit
value=json.loads(path.read_text(encoding="utf-8"))
hours=max(0.0, (time.time()-float(value.get("started_epoch", time.time())))/3600)
rate=value.get("runpod_hourly_rate_usd")
if rate is None:
    print(f"Elapsed: {hours:.2f} hours; hourly rate was not recorded.")
else:
    print(f"Elapsed: {hours:.2f} hours; estimated gated-run compute: ${hours*float(rate):.2f} at ${float(rate):.4f}/hour.")
print("RunPod Billing is authoritative.")
PY
fi

echo
echo "Recent log:"
tail -n 80 "$OUTPUT_ROOT/session/gated-run.log" 2>/dev/null || true

echo
echo "GPU:"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || true

echo
echo "Result archive for this session:"
SESSION_NAME="$(basename "$OUTPUT_ROOT")"
shopt -s nullglob
archives=(/workspace/agent-worm-results-"$SESSION_NAME"-*.zip)
if (( ${#archives[@]} == 0 )); then
  echo "None yet."
else
  latest_archive="${archives[0]}"
  for candidate in "${archives[@]}"; do
    if [[ "$candidate" -nt "$latest_archive" ]]; then
      latest_archive="$candidate"
    fi
  done
  ls -lh "$latest_archive"
  if [[ -f "$latest_archive.sha256" ]]; then
    ls -lh "$latest_archive.sha256"
    echo "Checksum:"
    cat "$latest_archive.sha256"
  fi
fi
