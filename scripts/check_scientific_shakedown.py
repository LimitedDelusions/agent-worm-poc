
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from agent_worm_poc.scientific_gates import evaluate_shakedown_from_objects

def main():
    ap=argparse.ArgumentParser(description='Fail-closed within-block placement-variation gate')
    ap.add_argument('path',type=Path)
    ap.add_argument('--output',type=Path)
    ns=ap.parse_args()
    result=evaluate_shakedown_from_objects(ns.path)
    text=json.dumps(result,indent=2,sort_keys=True)
    print(text)
    if ns.output:
        ns.output.parent.mkdir(parents=True,exist_ok=True); ns.output.write_text(text+'\n')
    return 0 if result.get('passed') else 2
if __name__=='__main__': raise SystemExit(main())
