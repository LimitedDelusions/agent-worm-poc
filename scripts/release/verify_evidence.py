#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT/"src") not in sys.path:sys.path.insert(0,str(ROOT/"src"))
from agent_worm_poc.evidence_verify import verify_evidence,verify_transfer_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a transferred Agent Worm evidence bundle")
    parser.add_argument("zip", type=Path, help="Exact agent-worm-results-<run-id>.zip path")
    parser.add_argument("--expected-version")
    parser.add_argument("--status", type=Path, help="Explicit standalone RUN_STATUS.json path")
    args = parser.parse_args()
    result=verify_evidence(args.zip,args.expected_version,args.status)
    transfer_manifest=args.zip.resolve().parent/"SHA256SUMS"
    if transfer_manifest.exists():
        result["transfer"]=verify_transfer_manifest(transfer_manifest.parent)
    else:
        result["transfer"]={"passed":None,"reason":"SHA256SUMS not present"}
    print(json.dumps(result,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
