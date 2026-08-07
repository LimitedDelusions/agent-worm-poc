#!/usr/bin/env bash
set -Eeuo pipefail

BASE="/workspace/agent_worm_outputs"
PID_FILE="$BASE/active.pid"
LATEST_FILE="$BASE/latest_session.txt"
ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.7.0}"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No active run PID file exists."
  exit 0
fi
PID="$(cat "$PID_FILE" 2>/dev/null || true)"
CMDLINE=""
if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null; then
  CMDLINE="$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null || true)"
fi
if [[ -z "$PID" || "$CMDLINE" != *"$ROOT/scripts/runpod/gated_run_inner.sh"* ]]; then
  echo "No active Agent Worm gated-run process was found; removing any stale PID file."
  rm -f "$PID_FILE"
  exit 0
fi

cat <<INFO
Requesting a controlled stop for PID $PID.
The run should stop the active vLLM server and package partial evidence.
Do not stop or terminate the RunPod Pod until status.sh reports NOT RUNNING.
INFO

kill -TERM -- "-$PID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null || true
for _ in $(seq 1 120); do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "Run stopped. Check the packaged evidence with:"
    echo "  bash $ROOT/scripts/runpod/status.sh"
    exit 0
  fi
  sleep 2
done

echo "Controlled stop did not finish within four minutes; forcing termination." >&2
kill -KILL -- "-$PID" 2>/dev/null || kill -KILL "$PID" 2>/dev/null || true
sleep 3
rm -f "$PID_FILE"
pkill -TERM -f '[v]llm serve' 2>/dev/null || true

if [[ -f "$LATEST_FILE" ]]; then
  OUTPUT_ROOT="$(cat "$LATEST_FILE")"
  if [[ -d "$OUTPUT_ROOT" ]]; then
    python - "$OUTPUT_ROOT" <<'PY_STATUS' || true
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

output_root = Path(sys.argv[1])
status_path = output_root / "session_status.json"
payload = {}
if status_path.is_file():
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
payload.update({
    "state": "failed",
    "phase": "forced-cancel",
    "message": (
        "Controlled cancellation did not finish within four minutes; the process group "
        "was force-killed and partial evidence was packaged."
    ),
    "updated_at": datetime.now(timezone.utc).isoformat(),
})
status_path.parent.mkdir(parents=True, exist_ok=True)
status_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY_STATUS
    echo "Attempting emergency partial-evidence packaging..." >&2
    bash "$ROOT/scripts/runpod/package_results.sh" "$OUTPUT_ROOT" || true
  fi
fi
exit 1
