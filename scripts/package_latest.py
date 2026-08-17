#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
from agent_worm_poc.evidence import package_results
p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--run-dir",required=True);p.add_argument("--output",required=True)
a=p.parse_args();print(json.dumps(package_results(Path(a.root),Path(a.run_dir),Path(a.output)),indent=2))
