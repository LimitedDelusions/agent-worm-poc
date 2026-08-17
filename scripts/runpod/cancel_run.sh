#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.8.9}"
WORKSPACE="${AGENT_WORM_WORKSPACE:-/workspace}"
BASE="${AGENT_WORM_OUTPUT_BASE:-$WORKSPACE/agent_worm_outputs}"
PID_FILE="$BASE/active.pid"
LATEST_FILE="$BASE/latest_session.txt"
# VLLMServerManager.stop() can spend 120s waiting, 30s after SIGKILL, and
# another 180s waiting for GPU memory to release. Leave room for status and
# evidence finalization after that 330-second cleanup path.
GRACE_SECONDS="${AGENT_WORM_CANCEL_GRACE_SECONDS:-420}"

fail(){ echo "ERROR: $*" >&2; exit 64; }
[[ "$GRACE_SECONDS" =~ ^[0-9]+$ ]] || fail "AGENT_WORM_CANCEL_GRACE_SECONDS must be an integer"
(( GRACE_SECONDS > 330 )) || fail "cancellation grace must exceed the 330-second server cleanup path"
command -v python >/dev/null || fail "python is unavailable"

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
FORCED=0
RECOVERY_OUTCOME="technical_failure"

leader_identity(){
  [[ "$PID" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$PID" 2>/dev/null || return 1
  [[ "$(ps -o pgid= -p "$PID" 2>/dev/null | tr -d ' ')" == "$PID" ]] || return 1
  [[ "$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null || true)" == *"run_gated.py real-gated"* ]]
}

member_is_runner(){
  local CANDIDATE="$1"
  local -a ARGS=()
  [[ -r "/proc/$CANDIDATE/cmdline" ]] || return 1
  mapfile -d '' -t ARGS < "/proc/$CANDIDATE/cmdline" || return 1
  (( ${#ARGS[@]} >= 7 )) || return 1
  [[ "${ARGS[0]##*/}" == python* ]] || return 1
  [[ "${ARGS[1]}" == "$ROOT/scripts/run_gated.py" && "${ARGS[2]}" == "real-gated" ]] || return 1
  [[ "${ARGS[3]}" == "--root" && "${ARGS[4]}" == "$ROOT" ]] || return 1
  [[ "${ARGS[5]}" == "--output-root" && "${ARGS[6]}" == "$BASE" ]]
}

runner_identity(){
  [[ "$PID" =~ ^[0-9]+$ ]] || return 1
  mapfile -t RUNNER_MATCHES < <(
    while IFS= read -r MEMBER;do
      [[ -n "$MEMBER" ]] || continue
      member_is_runner "$MEMBER" && printf '%s\n' "$MEMBER"
    done < <(pgrep -g "$PID" 2>/dev/null || true)
  )
  (( ${#RUNNER_MATCHES[@]} == 1 )) && return 0
  (( ${#RUNNER_MATCHES[@]} == 0 )) && leader_identity
}

runner_group_alive(){
  [[ "$PID" =~ ^[0-9]+$ ]] && pgrep -g "$PID" >/dev/null 2>&1
}

if ! runner_identity;then
  mapfile -t DISCOVERED_GROUPS < <(
    {
      while IFS= read -r CANDIDATE;do
        [[ -n "$CANDIDATE" ]] || continue
        ps -o pgid= -p "$CANDIDATE" 2>/dev/null | tr -d ' '
      done < <(pgrep -f '[r]un_gated.py[[:space:]]+real-gated' 2>/dev/null || true)
    } | awk '/^[0-9]+$/' | sort -nu
  )
  if (( ${#DISCOVERED_GROUPS[@]} > 1 ));then
    fail "multiple gated-run process groups were discovered; preserve evidence and inspect manually"
  elif (( ${#DISCOVERED_GROUPS[@]} == 1 ));then
    PID="${DISCOVERED_GROUPS[0]}"
    echo "Recovered gated-run process group $PID without relying on active.pid."
  fi
fi

if runner_identity;then
  RECOVERY_OUTCOME="operator_cancelled"
  echo "Requesting controlled cancellation for gated-run process group $PID."
  kill -TERM -- "-$PID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null || true
  DEADLINE=$((SECONDS+GRACE_SECONDS))
  while runner_group_alive && (( SECONDS < DEADLINE ));do sleep 2;done
  if runner_group_alive;then
    FORCED=1
    echo "WARNING: controlled cancellation exceeded ${GRACE_SECONDS}s; forcing the remaining process group." >&2
    kill -KILL -- "-$PID" 2>/dev/null || kill -KILL "$PID" 2>/dev/null || true
    sleep 2
  fi
elif [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null;then
  echo "WARNING: active.pid refers to unrelated live PID $PID; it was not signalled." >&2
else
  echo "No active gated-run process was found; continuing with orphan cleanup and evidence recovery."
fi
rm -f "$PID_FILE"

# Always clean an orphan model server, including when the runner PID is stale or
# absent. This Pod is dedicated to exactly one visible GPU and one gated run.
if pgrep -f '[v]llm[[:space:]]+serve' >/dev/null 2>&1;then
  echo "Stopping orphan vLLM server processes."
  pkill -TERM -f '[v]llm[[:space:]]+serve' 2>/dev/null || true
  VLLM_DEADLINE=$((SECONDS+180))
  while pgrep -f '[v]llm[[:space:]]+serve' >/dev/null 2>&1 && (( SECONDS < VLLM_DEADLINE ));do
    sleep 2
  done
  if pgrep -f '[v]llm[[:space:]]+serve' >/dev/null 2>&1;then
    FORCED=1
    pkill -KILL -f '[v]llm[[:space:]]+serve' 2>/dev/null || true
  fi
fi

# Always attempt a verified emergency evidence package, even after a normal
# controlled exit or when active.pid was already dead.
[[ -f "$LATEST_FILE" ]] || fail "latest_session.txt is missing; no run can be packaged"
RUN_DIR="$(PYTHONPATH="$ROOT/src" python - "$BASE" "$LATEST_FILE" <<'PYCODE'
import sys
from pathlib import Path

base=Path(sys.argv[1]).resolve()
latest=Path(sys.argv[2])
candidate=Path(latest.read_text(encoding="utf-8").strip())
if candidate.is_symlink() or not candidate.is_dir():
    raise SystemExit("latest session is missing or linked")
resolved=candidate.resolve()
if resolved.parent != base:
    raise SystemExit("latest session is outside the configured output base")
print(resolved)
PYCODE
)" || fail "latest session path failed safety validation"
SESSION_ID="$(basename "$RUN_DIR")"
CANONICAL="$BASE/agent-worm-results-${SESSION_ID}.zip"
if [[ -s "$CANONICAL" && -s "$CANONICAL.sha256" && -s "$CANONICAL.json" && -s "$RUN_DIR/RUN_STATUS.json" ]];then
  if PYTHONPATH="$ROOT/src" python "$ROOT/scripts/release/verify_evidence.py" \
      "$CANONICAL" --expected-version "$(cat "$ROOT/VERSION")" \
      --status "$RUN_DIR/RUN_STATUS.json" >/tmp/agent-worm-existing-evidence-verification.json;then
    echo "Existing canonical evidence is already complete and verified: $CANONICAL"
    cat /tmp/agent-worm-existing-evidence-verification.json
    exit "$FORCED"
  fi
fi
OUTPUT="$BASE/agent-worm-results-${SESSION_ID}-forced.zip"
PACKAGE_RC=0
AGENT_WORM_EMERGENCY_OUTCOME="$RECOVERY_OUTCOME" PYTHONPATH="$ROOT/src" \
  python "$ROOT/scripts/run_gated.py" emergency-package \
  --root "$ROOT" --run-dir "$RUN_DIR" --output "$OUTPUT" || PACKAGE_RC=$?
if (( PACKAGE_RC != 0 ));then
  echo "ERROR: emergency evidence packaging or sidecar verification failed (exit $PACKAGE_RC)." >&2
  exit "$PACKAGE_RC"
fi

echo "Verified emergency evidence package: $OUTPUT"
if (( FORCED != 0 ));then
  echo "WARNING: force was required during cleanup; inspect RUN_STATUS.json and server logs." >&2
fi
exit "$FORCED"
