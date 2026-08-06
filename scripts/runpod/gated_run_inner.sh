#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.6.0}"
OUTPUT_ROOT="${AGENT_WORM_OUTPUT_ROOT:?AGENT_WORM_OUTPUT_ROOT is required}"
STATUS_FILE="$OUTPUT_ROOT/session_status.json"
ACTIVE_PID_FILE="/workspace/agent_worm_outputs/active.pid"

export PYTHONPATH="$ROOT/src"
mkdir -p "$OUTPUT_ROOT/session"

write_status() {
  local state="$1"
  local phase="$2"
  local message="$3"
  python - "$STATUS_FILE" "$state" "$phase" "$message" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
path=Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
value={
  "state": sys.argv[2],
  "phase": sys.argv[3],
  "message": sys.argv[4],
  "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
}
tmp=path.with_suffix(path.suffix+".tmp")
tmp.write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
tmp.replace(path)
PY
}

cleanup_vllm() {
  local pids=()
  mapfile -t pids < <(pgrep -f '[v]llm serve' || true)
  if (( ${#pids[@]} > 0 )); then
    echo "Stopping residual vLLM process(es): ${pids[*]}" >&2
    kill -TERM "${pids[@]}" 2>/dev/null || true
    for _ in $(seq 1 30); do
      mapfile -t pids < <(pgrep -f '[v]llm serve' || true)
      (( ${#pids[@]} == 0 )) && break
      sleep 2
    done
    mapfile -t pids < <(pgrep -f '[v]llm serve' || true)
    if (( ${#pids[@]} > 0 )); then
      kill -KILL "${pids[@]}" 2>/dev/null || true
    fi
  fi
}

write_cost_estimate() {
  python - "$OUTPUT_ROOT/session/launch.json" "$OUTPUT_ROOT/session/cost_estimate.json" <<'PY'
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path
launch_path, output_path = map(Path, sys.argv[1:])
value = json.loads(launch_path.read_text(encoding="utf-8")) if launch_path.exists() else {}
end = time.time()
start = float(value.get("started_epoch", end))
hours = max(0.0, (end - start) / 3600.0)
rate = value.get("runpod_hourly_rate_usd")
estimate = None if rate is None else round(hours * float(rate), 4)
result = {
    "schema_version": 2,
    "started_at": value.get("started_at"),
    "ended_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "elapsed_hours_from_gated_start": round(hours, 4),
    "hourly_rate_usd": rate,
    "estimated_gated_run_compute_cost_usd": estimate,
    "excludes": "Pod time before start_gated_run.sh and after packaging completes",
    "note": "Estimate only. RunPod Billing is the authoritative charge.",
}
output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
PY
}

finish() {
  local original_code=$?
  local final_code=$original_code
  local package_output package_code active_pid
  trap - EXIT INT TERM
  set +e

  cleanup_vllm
  write_cost_estimate

  if [[ $original_code -eq 0 ]]; then
    write_status "completed" "done" "All gates and the POC completed; packaging evidence."
  elif [[ $original_code -eq 124 || $original_code -eq 130 || $original_code -eq 137 || $original_code -eq 143 ]]; then
    write_status "failed" "timeout-or-cancel" "The run was stopped or exceeded its runtime limit; packaging partial evidence."
  else
    write_status "failed" "gate-failure" "A gate failed with exit code $original_code; packaging partial evidence."
  fi

  package_output="$(bash "$ROOT/scripts/runpod/package_results.sh" "$OUTPUT_ROOT" 2>&1)"
  package_code=$?
  if [[ $package_code -ne 0 ]]; then
    echo "Evidence packaging failed:" >&2
    echo "$package_output" >&2
    write_status "failed" "package" "Evidence packaging failed after the run stopped."
    [[ $final_code -eq 0 ]] && final_code=74
  else
    echo "$package_output"
  fi

  active_pid="$(cat "$ACTIVE_PID_FILE" 2>/dev/null || true)"
  if [[ -n "$active_pid" ]] && { [[ "$active_pid" == "${PPID:-}" ]] || [[ "$active_pid" == "$$" ]] || ! kill -0 "$active_pid" 2>/dev/null; }; then
    rm -f "$ACTIVE_PID_FILE"
  fi
  exit "$final_code"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

write_status "running" "preflight" "Checking image integrity, storage, secrets, cost metadata, runtime, and GPU."
python -m agent_worm_poc.cli --project-root "$ROOT" --output-root "$OUTPUT_ROOT" preflight

write_status "running" "freeze" "Checking Hugging Face access and freezing immutable model, tokenizer, code, and parser revisions."
python -m agent_worm_poc.cli --project-root "$ROOT" --output-root "$OUTPUT_ROOT" freeze-models

write_status "running" "tests" "Running unit and integration tests before any model download."
python -m unittest discover -s "$ROOT/tests" -v \
  2>&1 | tee "$OUTPUT_ROOT/session/unit-tests.txt"

write_status "running" "fake-validation" "Validating all 24 placements and all four conditions without real inference."
python -m agent_worm_poc.cli --project-root "$ROOT" --output-root "$OUTPUT_ROOT" fake-validation

write_status "running" "compatibility" "Loading each model sequentially and testing every role plus benign workflow competency."
python -m agent_worm_poc.cli --project-root "$ROOT" --output-root "$OUTPUT_ROOT" compatibility

write_status "running" "shakedown" "Running one cross-model placement across all four conditions."
python -m agent_worm_poc.cli --project-root "$ROOT" --output-root "$OUTPUT_ROOT" shakedown

write_status "running" "poc" "Running all 24 model placements across the benign and three injected conditions."
python -m agent_worm_poc.cli --project-root "$ROOT" --output-root "$OUTPUT_ROOT" poc \
  --repetitions "${POC_REPETITIONS:-1}"
