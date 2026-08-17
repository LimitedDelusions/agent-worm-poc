#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.8.9}"
WORKSPACE="${AGENT_WORM_WORKSPACE:-/workspace}"
BASE="${AGENT_WORM_OUTPUT_BASE:-$WORKSPACE/agent_worm_outputs}"
LATEST_FILE="$BASE/latest_session.txt"
PID_FILE="$BASE/active.pid"

fail(){ echo "ERROR: $*" >&2; exit 64; }
command -v python >/dev/null || fail "python is unavailable"
command -v runpodctl >/dev/null || fail "runpodctl is unavailable in the Pod"
[[ -f "$LATEST_FILE" ]] || fail "latest_session.txt is missing"

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if pgrep -f '[r]un_gated.py[[:space:]]+real-gated' >/dev/null 2>&1;then
  fail "a gated-run process is still active; monitor it instead of staging evidence"
fi
if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null;then
  COMMAND="$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null || true)"
  [[ "$COMMAND" == *"run_gated.py real-gated"* ]] && \
    fail "the gated run is still active; monitor it instead of staging evidence"
  fail "active.pid points to unrelated live PID $PID; inspect before transfer"
fi

RUN_DIR="$(PYTHONPATH="$ROOT/src" python - "$BASE" "$LATEST_FILE" <<'PYCODE'
import sys
from pathlib import Path
base=Path(sys.argv[1]).resolve()
candidate=Path(Path(sys.argv[2]).read_text(encoding='utf-8').strip())
if candidate.is_symlink() or not candidate.is_dir():
    raise SystemExit('latest session is missing or linked')
resolved=candidate.resolve()
if resolved.parent!=base:
    raise SystemExit('latest session is outside the configured output base')
print(resolved)
PYCODE
)" || fail "latest session path failed safety validation"
RUN_ID="$(basename "$RUN_DIR")"
STATUS="$RUN_DIR/RUN_STATUS.json"
[[ -s "$STATUS" ]] || fail "RUN_STATUS.json is missing; run cancel_run.sh for recovery"

EVIDENCE_STATUS="$(python - "$STATUS" <<'PYCODE'
import json,sys
print(json.load(open(sys.argv[1],encoding='utf-8')).get('evidence_status','unknown'))
PYCODE
)"
if [[ "$EVIDENCE_STATUS" != "verified" ]];then
  echo "Evidence is not verified; invoking the guarded recovery packager."
  RECOVERY_RC=0
  bash "$ROOT/scripts/runpod/cancel_run.sh" || RECOVERY_RC=$?
  EVIDENCE_STATUS="$(python - "$STATUS" <<'PYCODE'
import json,sys
print(json.load(open(sys.argv[1],encoding='utf-8')).get('evidence_status','unknown'))
PYCODE
)"
  [[ "$EVIDENCE_STATUS" == "verified" ]] || \
    fail "recovery did not produce verified evidence (cancel exit $RECOVERY_RC)"
  if (( RECOVERY_RC != 0 ));then
    echo "WARNING: cleanup required force (exit $RECOVERY_RC), but evidence verified; continuing transfer." >&2
  fi
fi

STAGE="$WORKSPACE/download-ready-${RUN_ID}-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$STAGE"
cp -a -- "$RUN_DIR" "$STAGE/run"
cp -p -- "$STATUS" "$STAGE/RUN_STATUS.json"

SELECTED=""
for ZIP in \
  "$BASE/agent-worm-results-${RUN_ID}-forced.zip" \
  "$BASE/agent-worm-results-${RUN_ID}.zip"
do
  [[ -s "$ZIP" && -s "$ZIP.sha256" && -s "$ZIP.json" ]] || continue
  cp -p -- "$ZIP" "$ZIP.sha256" "$ZIP.json" "$STAGE/"
  CANDIDATE="$STAGE/$(basename "$ZIP")"
  if PYTHONPATH="$ROOT/src" python "$ROOT/scripts/release/verify_evidence.py" \
      "$CANDIDATE" --expected-version "$(cat "$ROOT/VERSION")" \
      > "$STAGE/VERIFICATION.json";then
    SELECTED="$CANDIDATE"
    break
  fi
  rm -f -- "$CANDIDATE" "$CANDIDATE.sha256" "$CANDIDATE.json" "$STAGE/VERIFICATION.json"
done
[[ -n "$SELECTED" ]] || fail "no evidence ZIP matches the final standalone RUN_STATUS.json"

(
  cd "$STAGE"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum
) > "$STAGE/SHA256SUMS"

echo "Verified transfer folder: $STAGE"
echo "Evidence ZIP: $(basename "$SELECTED")"
cat "$STAGE/VERIFICATION.json"
echo
echo "Copy the one-time receive code printed below."
runpodctl send "$STAGE"
