#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess
import sys
from agent_worm_poc.release_audit import audit_release
root=Path(__file__).resolve().parents[1]
result=audit_release(root)
print(json.dumps(result,indent=2))
if not result['passed']:raise SystemExit(1)
if (root/'RELEASE_MANIFEST.json').exists():
    raise SystemExit(subprocess.run([sys.executable,str(root/'scripts/release/generate_integrity.py'),'--check']).returncode)
