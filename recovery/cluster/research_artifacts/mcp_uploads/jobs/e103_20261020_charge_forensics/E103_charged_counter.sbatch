#!/bin/bash
#SBATCH --job-name=E103_charge_forensics
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
export PYTHONUNBUFFERED=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import json
folder=Path('/home-mscluster/astrauss/e103_dev_harness_smoke/E103_smoke_71964/full')
trace=folder/'observed_actions.jsonl'
print('E103_FORENSIC_EXISTS',folder.exists(),trace.exists(),flush=True)
if trace.exists():
 arr=[json.loads(x) for x in trace.read_text().splitlines()]
 print('E103_FORENSIC_COUNTS',json.dumps({'rows':len(arr),
  'first':arr[0] if arr else None,'last':arr[-1] if arr else None,
  'positive_events':[(x['charged_action'],x['level_high_water']) for x in arr if x['native_reward']>0],
  'max_charged':max([x['charged_action'] for x in arr] or [-1])},default=str),flush=True)
PY