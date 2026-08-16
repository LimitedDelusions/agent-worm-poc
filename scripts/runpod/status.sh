#!/usr/bin/env bash
set -Eeuo pipefail
BASE="/workspace/agent_worm_outputs";LATEST_FILE="$BASE/latest_session.txt";PID_FILE="$BASE/active.pid"
[[ -f "$LATEST_FILE" ]] || { echo "No Agent Worm POC session has been started."; exit 1; }
RUN_DIR="$(cat "$LATEST_FILE")";PID="$(cat "$PID_FILE" 2>/dev/null || true)";RUNNING=0
if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null; then RUNNING=1; fi
echo "Session: $RUN_DIR";[[ $RUNNING -eq 1 ]] && echo "Process: RUNNING (PID $PID)" || echo "Process: NOT RUNNING"
echo;echo "Status:";cat "$RUN_DIR/RUN_STATUS.json" 2>/dev/null || echo "RUN_STATUS.json not created yet."
echo;echo "Recent log:";tail -n 100 "$RUN_DIR/session/gated-run.log" 2>/dev/null || true
echo;echo "GPU:";nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || true
echo;echo "Evidence archives:";find "$BASE" -maxdepth 1 -type f -name "agent-worm-results-$(basename "$RUN_DIR")*" -ls 2>/dev/null || true
if [[ $RUNNING -eq 0 ]]; then echo;echo "The process is not running. Download evidence and terminate the Pod to stop all billing.";fi
