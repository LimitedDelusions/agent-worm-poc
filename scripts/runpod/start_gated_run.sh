#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${AGENT_WORM_PROJECT_ROOT:-/workspace/agent_worm_poc_v0.8.9}"
WORKSPACE="${AGENT_WORM_WORKSPACE:-/workspace}"
BASE="${AGENT_WORM_OUTPUT_BASE:-$WORKSPACE/agent_worm_outputs}"
PID_FILE="$BASE/active.pid"
LATEST_FILE="$BASE/latest_session.txt"
MAX_GPU_HOURS="${MAX_GPU_HOURS:-8}"
MAX_TOTAL_COST_USD="${MAX_TOTAL_COST_USD:-25}"
RATE="${RUNPOD_HOURLY_RATE_USD:-${RUNPOD_HOURLY_RATE:-}}"
SESSION_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN_DIR="$BASE/$SESSION_ID"

fail(){ echo "ERROR: $*" >&2; exit 64; }
[[ -d "$ROOT" ]] || fail "project directory not found: $ROOT"
[[ -d "$WORKSPACE" ]] || fail "workspace directory not found: $WORKSPACE"
[[ -f "$ROOT/SOURCE_HASHES.sha256" ]] || fail "SOURCE_HASHES.sha256 is missing"
[[ "${AGENT_WORM_IMAGE_REF:-}" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || fail "AGENT_WORM_IMAGE_REF must be the exact GHCR digest"
[[ "$RATE" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "set RUNPOD_HOURLY_RATE_USD to the displayed total hourly rate"
[[ "$MAX_TOTAL_COST_USD" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "MAX_TOTAL_COST_USD must be numeric"
[[ "$MAX_GPU_HOURS" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "MAX_GPU_HOURS must be numeric"
for command in python timeout setsid flock nvidia-smi findmnt df sha256sum;do
  command -v "$command" >/dev/null || fail "$command is unavailable"
done

mkdir -p "$BASE"
exec 9>"$BASE/.launch.lock"
flock -n 9 || fail "another launch attempt holds the atomic launch lock"

if [[ -f "$PID_FILE" ]];then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$OLD_PID" =~ ^[0-9]+$ ]] && kill -0 "$OLD_PID" 2>/dev/null;then
    OLD_COMMAND="$(tr '\0' ' ' < "/proc/$OLD_PID/cmdline" 2>/dev/null || true)"
    [[ "$OLD_COMMAND" == *"run_gated.py real-gated"* ]] && fail "a gated run is already active as PID $OLD_PID"
    fail "active.pid points to unrelated live PID $OLD_PID; inspect before launch"
  fi
  rm -f "$PID_FILE"
fi

read -r RELEASE RUNTIME_REVISION <<<"$(PYTHONPATH="$ROOT/src" python - "$ROOT" <<'PYCODE'
import json,os,re,sys
from pathlib import Path
root=Path(sys.argv[1])
declared=os.environ.get('AGENT_WORM_IMAGE_REF','')
version=(root/'VERSION').read_text(encoding='utf-8').strip()
manifest=json.loads((root/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
experiment=json.loads((root/'configs/experiment.json').read_text(encoding='utf-8'))
marker_path=Path('/opt/agent-worm-runtime.json')
if not marker_path.is_file():
    raise SystemExit('prebuilt runtime marker is missing')
marker=json.loads(marker_path.read_text(encoding='utf-8'))
if not version or manifest.get('release')!=version or experiment.get('release')!=version or marker.get('version')!=version:
    raise SystemExit('runtime, source, manifest, and experiment release values do not match')
revision=str(marker.get('git_revision',''))
if not re.fullmatch(r'[0-9a-f]{40}',revision):
    raise SystemExit('runtime marker does not contain an immutable Git revision')
for name in ('RUNPOD_IMAGE_NAME','RUNPOD_CONTAINER_IMAGE'):
    observed=os.environ.get(name)
    if observed and '@sha256:' in observed and observed!=declared:
        raise SystemExit(f'{name} does not match AGENT_WORM_IMAGE_REF')
print(version,revision)
PYCODE
)"
[[ "$RELEASE" =~ ^[0-9]+([.][0-9]+){2}$ ]] || fail "release value is invalid"

(cd "$ROOT" && python scripts/release/generate_integrity.py --check >/tmp/agent-worm-launch-manifest-check.txt)
(cd "$ROOT" && sha256sum -c SOURCE_HASHES.sha256 >/tmp/agent-worm-launch-source-check.txt)
(cd "$ROOT" && PYTHONPATH="$ROOT/src" python scripts/validate_release.py >/tmp/agent-worm-launch-release-audit.txt)
PYTHONPATH="$ROOT/src" python - "$ROOT/configs/models.json" <<'PYCODE'
import json,os,sys
from huggingface_hub import hf_hub_download
token=os.environ.get("HF_TOKEN","")
if not token.startswith("hf_"):
    raise SystemExit("HF_TOKEN is missing or unresolved")
for model in json.load(open(sys.argv[1],encoding="utf-8"))["models"]:
    hf_hub_download(
        repo_id=model["repo_id"],
        filename="config.json",
        revision=model["revision"],
        token=token,
    )
print("Pinned Hugging Face access: OK")
PYCODE

GPU_CSV="$(nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits)" || fail "nvidia-smi preflight failed"
PYTHONPATH="$ROOT/src" python - "$GPU_CSV" "$ROOT/configs/experiment.json" <<'PYCODE'
import json,sys
rows=[row.strip() for row in sys.argv[1].splitlines() if row.strip()]
if len(rows)!=1:raise SystemExit(f'exactly one visible GPU is required; found {len(rows)}')
parts=[value.strip() for value in rows[0].rsplit(',',2)]
if len(parts)!=3:raise SystemExit('could not parse nvidia-smi GPU preflight')
name,total,used=parts[0],int(parts[1]),int(parts[2])
idle_max=int(json.load(open(sys.argv[2],encoding='utf-8'))['runtime']['gpu_idle_memory_mib_max'])
if 'A100' not in name.upper() or total<80000:
    raise SystemExit(f'one A100 80GB is required; observed {name} with {total} MiB')
if used>idle_max:raise SystemExit(f'GPU is not idle: {used} MiB used; maximum is {idle_max} MiB')
PYCODE
if [[ -n "${RUNPOD_GPU_COUNT:-}" && "${RUNPOD_GPU_COUNT}" != "1" ]];then
  fail "RUNPOD_GPU_COUNT must equal 1"
fi
PYTHONPATH="$ROOT/src" python - <<'PYCODE'
import torch
if not torch.cuda.is_available():
    raise SystemExit('PyTorch cannot access CUDA in this Pod')
if torch.cuda.device_count()!=1:
    raise SystemExit(f'exactly one CUDA device is required; found {torch.cuda.device_count()}')
properties=torch.cuda.get_device_properties(0)
if properties.major<8 or not torch.cuda.is_bf16_supported():
    raise SystemExit(f'CUDA device lacks required A100/BF16 capability: {properties.name}')
probe=torch.ones((64,64),device='cuda',dtype=torch.bfloat16)
_=(probe@probe).sum().item()
torch.cuda.synchronize()
print(f'CUDA/PyTorch/BF16 probe: OK ({properties.name})')
PYCODE

MOUNT_TARGET="$(findmnt -n -o TARGET -T "$WORKSPACE")" || fail "workspace mount is unavailable"
[[ "$MOUNT_TARGET" == "$WORKSPACE" ]] || fail "$WORKSPACE is not a dedicated persistent mount"
AVAILABLE_BYTES="$(df --output=avail -B1 "$WORKSPACE" | tail -n 1 | tr -d '[:space:]')"
[[ "$AVAILABLE_BYTES" =~ ^[0-9]+$ ]] || fail "could not determine workspace free space"
(( AVAILABLE_BYTES >= 300 * 1024 * 1024 * 1024 )) || fail "workspace must have at least 300 GiB free"

read -r BUDGET_SECONDS ACTIVE_SECONDS <<<"$(python - "$RATE" "$MAX_TOTAL_COST_USD" "$MAX_GPU_HOURS" "$ROOT/configs/experiment.json" <<'PYCODE'
import json,math,sys
rate,cap,hours=map(float,sys.argv[1:4])
release_hours=float(json.load(open(sys.argv[4],encoding='utf-8'))['runtime']['max_gpu_hours'])
if min(rate,cap,hours)<=0:raise SystemExit('rate, cap, and hours must be positive')
if not 0.25<=rate<=25:raise SystemExit('displayed A100 hourly rate is outside the sanity range $0.25-$25')
if cap>25:raise SystemExit('MAX_TOTAL_COST_USD exceeds the release ceiling of $25')
if hours>release_hours:raise SystemExit(f'MAX_GPU_HOURS exceeds the release ceiling of {release_hours:g}')
hard=min(math.floor(hours*3600),math.floor(cap/rate*3600));grace=600
if hard<1800:raise SystemExit('configured limits allow less than 30 minutes; adjust the cap or hours before launch')
print(hard,hard-grace)
PYCODE
)"

cat <<CONFIRM
FINAL PAID-LAUNCH CHECK
  release: v${RELEASE}
  immutable image: ${AGENT_WORM_IMAGE_REF}
  displayed total rate: \$${RATE}/hour
  cost ceiling: \$${MAX_TOTAL_COST_USD}
  hard process budget: ${BUDGET_SECONDS} seconds
  this release/image can be launched only once
CONFIRM
if [[ -t 0 ]];then
  read -r -p "Type the displayed hourly rate exactly (${RATE}) to authorize this run: " RATE_CONFIRMATION
  [[ "$RATE_CONFIRMATION" == "$RATE" ]] || fail "hourly-rate confirmation did not match; nothing was launched"
else
  EXPECTED_ACK="START-v${RELEASE}-${RATE}-${MAX_TOTAL_COST_USD}"
  [[ "${AGENT_WORM_LAUNCH_ACK:-}" == "$EXPECTED_ACK" ]] || \
    fail "noninteractive launch requires AGENT_WORM_LAUNCH_ACK=$EXPECTED_ACK"
fi

IMAGE_DIGEST="${AGENT_WORM_IMAGE_REF##*@sha256:}"
SENTINEL="$BASE/.real-run-${RELEASE}-sha256-${IMAGE_DIGEST}.json"
[[ ! -e "$SENTINEL" ]] || fail "this release/container already has a real-run claim: $SENTINEL"
mkdir "$RUN_DIR";mkdir "$RUN_DIR/session"
ACTIVE_SECONDS="$ACTIVE_SECONDS" python - "$RUN_DIR/session/launch.json" "$SESSION_ID" "$RELEASE" "$RATE" "$MAX_TOTAL_COST_USD" "$BUDGET_SECONDS" "$RUNTIME_REVISION" "$SENTINEL" "$GPU_CSV" "$AVAILABLE_BYTES" <<'PYCODE'
import json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
path,session,release,rate,cap,seconds,revision,sentinel,gpu,available=sys.argv[1:]
Path(path).write_text(json.dumps({
 'schema_version':2,'session_id':session,'release':release,
 'started_at':datetime.now(timezone.utc).isoformat(),'started_epoch':time.time(),
 'runpod_hourly_rate_usd':float(rate),'maximum_cost_usd':float(cap),
 'hard_timeout_seconds':int(seconds),'active_timeout_seconds':int(os.environ['ACTIVE_SECONDS']),
 'container_image_reference':os.environ['AGENT_WORM_IMAGE_REF'],'runtime_git_revision':revision,
 'project_root':os.environ.get('AGENT_WORM_PROJECT_ROOT'),
 'workspace':os.environ.get('AGENT_WORM_WORKSPACE','/workspace'),
 'workspace_available_bytes':int(available),'gpu_preflight':gpu,'run_claim_sentinel':sentinel},indent=2)+'\n')
PYCODE
PYTHONPATH="$ROOT/src" python - "$SENTINEL" "$SESSION_ID" "$RELEASE" "$RUNTIME_REVISION" <<'PYCODE'
import os,sys,time
from pathlib import Path
from agent_worm_poc.cli import claim_real_run_sentinel
path,session,release,revision=sys.argv[1:]
claim_real_run_sentinel(Path(path),{
 'schema_version':1,'session_id':session,'release':release,'claimed_epoch':time.time(),
 'container_image_reference':os.environ['AGENT_WORM_IMAGE_REF'],'runtime_git_revision':revision})
PYCODE
printf '%s\n' "$RUN_DIR" > "$LATEST_FILE"

nohup setsid env AGENT_WORM_RUN_ID="$SESSION_ID" AGENT_WORM_PRECREATED_RUN_DIR=1 \
  AGENT_WORM_RUN_SENTINEL="$SENTINEL" RUNPOD_HOURLY_RATE_USD="$RATE" \
  AGENT_WORM_ACTIVE_SECONDS="$ACTIVE_SECONDS" AGENT_WORM_BUDGET_SECONDS="$BUDGET_SECONDS" \
  PYTHONPATH="$ROOT/src" timeout --signal=USR1 --kill-after=10m "$ACTIVE_SECONDS" \
  python "$ROOT/scripts/run_gated.py" real-gated --root "$ROOT" --output-root "$BASE" \
  > "$RUN_DIR/session/gated-run.log" 2>&1 9>&- &
PID=$!
printf '%s\n' "$PID" > "$RUN_DIR/session/gated-run.pid"
printf '%s\n' "$PID" > "$PID_FILE.tmp.$$";mv -f "$PID_FILE.tmp.$$" "$PID_FILE"
sleep 1
if ! kill -0 "$PID" 2>/dev/null;then
  echo "ERROR: gated runner exited during startup; the one-run claim is preserved" >&2
  tail -n 50 "$RUN_DIR/session/gated-run.log" >&2 || true
  exit 70
fi
cat <<INFO
Started Agent Worm POC v${RELEASE}.
Session: $SESSION_ID
PID: $PID
Immutable image: $AGENT_WORM_IMAGE_REF
One-run claim: $SENTINEL
Maximum gated-run cost: \$$MAX_TOTAL_COST_USD at \$$RATE/hour
Active-run timeout: $ACTIVE_SECONDS seconds; hard stop including packaging grace: $BUDGET_SECONDS seconds
Monitor: bash $ROOT/scripts/runpod/status.sh
Cancel safely: bash $ROOT/scripts/runpod/cancel_run.sh
INFO
