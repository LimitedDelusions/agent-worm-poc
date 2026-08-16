#!/usr/bin/env bash
set -Eeuo pipefail
BASE="/workspace/agent_worm_outputs";PID_FILE="$BASE/active.pid";LATEST_FILE="$BASE/latest_session.txt"
ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.8.2}"
[[ -f "$PID_FILE" ]] || { echo "No active PID file."; exit 0; }
PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ ! "$PID" =~ ^[0-9]+$ ]] || ! kill -0 "$PID" 2>/dev/null; then rm -f "$PID_FILE";echo "No active process.";exit 0;fi
echo "Requesting controlled stop for PID $PID; partial evidence should be packaged."
kill -TERM -- "-$PID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null || true
for _ in $(seq 1 150);do
  if ! kill -0 "$PID" 2>/dev/null;then rm -f "$PID_FILE";echo "Run stopped.";exit 0;fi
  sleep 2
done
echo "Controlled stop exceeded five minutes; forcing process termination." >&2
kill -KILL -- "-$PID" 2>/dev/null || kill -KILL "$PID" 2>/dev/null || true
rm -f "$PID_FILE"
pkill -TERM -f "[v]llm serve" 2>/dev/null || true
sleep 5
pkill -KILL -f "[v]llm serve" 2>/dev/null || true
if [[ -f "$LATEST_FILE" ]];then
  RUN_DIR="$(cat "$LATEST_FILE")"
  if [[ -d "$RUN_DIR" ]];then
    python "$ROOT/scripts/package_latest.py" --root "$ROOT" --run-dir "$RUN_DIR" --output "$BASE/agent-worm-results-$(basename "$RUN_DIR")-forced.zip" || true
  fi
fi
exit 1
