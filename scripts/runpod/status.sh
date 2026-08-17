#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE="${AGENT_WORM_WORKSPACE:-/workspace}"
BASE="${AGENT_WORM_OUTPUT_BASE:-$WORKSPACE/agent_worm_outputs}"
LATEST_FILE="$BASE/latest_session.txt"
PID_FILE="$BASE/active.pid"
[[ -f "$LATEST_FILE" ]] || { echo "No Agent Worm POC session has been started."; exit 1; }

RUN_DIR="$(cat "$LATEST_FILE")"
PID="$(cat "$PID_FILE" 2>/dev/null || true)"
RUNNING=0
DISCOVERED_RUNNER=0
if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null;then
  COMMAND="$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null || true)"
  [[ "$COMMAND" == *"run_gated.py real-gated"* ]] && RUNNING=1
fi
DISCOVERED_PIDS="$(pgrep -f '[r]un_gated.py[[:space:]]+real-gated' 2>/dev/null | tr '\n' ' ' || true)"
if (( RUNNING == 0 )) && [[ -n "$DISCOVERED_PIDS" ]];then
  RUNNING=1;DISCOVERED_RUNNER=1
fi

echo "Session: $RUN_DIR"
if (( DISCOVERED_RUNNER == 1 ));then
  echo "Process: RUNNING (discovered PIDs: $DISCOVERED_PIDS; active.pid is missing or stale)"
elif (( RUNNING == 1 ));then
  echo "Process: RUNNING (PID $PID)"
elif [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null;then
  echo "Process: PID $PID IS UNRELATED (not signalled)"
else
  echo "Process: NOT RUNNING"
fi

STATUS_PATH="$RUN_DIR/RUN_STATUS.json"
echo
echo "Live status:"
if [[ -f "$STATUS_PATH" ]];then
  if ! python - "$STATUS_PATH" <<'PYCODE'
import json,sys,time
from pathlib import Path

status=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
progress=status.get("progress",{})
budget=status.get("budget",{})
heartbeat=status.get("heartbeat_epoch")
age=max(0,int(time.time()-float(heartbeat))) if heartbeat is not None else None
print(f"  overall: {status.get('status','unknown')}")
print(f"  execution: {status.get('execution_status','unknown')}")
print(f"  evidence: {status.get('evidence_status','unknown')}")
print(f"  outcome: {status.get('outcome_classification','unknown')}")
print(f"  phase/model/stage: {status.get('current_phase') or '-'} / {status.get('current_model') or '-'} / {status.get('current_stage') or '-'}")
print(f"  heartbeat: {status.get('heartbeat_utc') or '-'} (age {age if age is not None else '-'}s)")
print(f"  elapsed: {status.get('elapsed_seconds','-')}s")
print(f"  progress: {progress.get('completed_requests',0)}/{progress.get('expected_requests',0)} requests; "
      f"phase {progress.get('phase_completed_requests',0)}/{progress.get('phase_expected_requests',0)}; "
      f"failed {progress.get('failed_requests',0)}; workflow {progress.get('current_workflow_id') or '-'}")
print(f"  remaining: active {budget.get('remaining_active_seconds','-')}s; hard {budget.get('remaining_hard_seconds','-')}s")
if status.get("error"):
    print(f"  execution error: {status['error']}")
if status.get("evidence_error"):
    print(f"  evidence error: {status['evidence_error']}")
PYCODE
  then
    echo "  WARNING: RUN_STATUS.json is unreadable or invalid." >&2
  fi
else
  echo "  RUN_STATUS.json not created yet."
fi

echo
echo "Recent log:"
tail -n 100 "$RUN_DIR/session/gated-run.log" 2>/dev/null || true
echo
echo "GPU:"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || true
if pgrep -f '[v]llm[[:space:]]+serve' >/dev/null 2>&1 && (( RUNNING == 0 ));then
  echo "WARNING: orphan vLLM server process detected while the gated runner is not active." >&2
fi
echo
echo "Evidence archives and sidecars:"
find "$BASE" -maxdepth 1 -type f -name "agent-worm-results-$(basename "$RUN_DIR")*" -ls 2>/dev/null || true

if (( RUNNING == 0 ));then
  EVIDENCE_STATUS="$(python - "$STATUS_PATH" 2>/dev/null <<'PYCODE' || true
import json,sys
print(json.load(open(sys.argv[1],encoding="utf-8")).get("evidence_status","unknown"))
PYCODE
)"
  echo
  if [[ "$EVIDENCE_STATUS" == "verified" ]];then
    echo "The process is not running and evidence sidecars are verified. Transfer and independently verify them before terminating the Pod."
  else
    echo "WARNING: the process is not running but evidence is not verified. Run cancel_run.sh for recovery packaging before Pod termination." >&2
  fi
fi
