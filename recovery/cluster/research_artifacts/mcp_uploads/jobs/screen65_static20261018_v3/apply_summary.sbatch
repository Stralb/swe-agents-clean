#!/bin/bash
#SBATCH --job-name=screen65_apply_summary
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:03:00
python3 - <<'PY'
import json,csv,collections,os
from pathlib import Path
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
inp=root/'screen65_preflight_job70608'
out=root/('screen65_preflight_summary_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
results=[json.loads(p.read_text()) for p in sorted(inp.glob('CASE_*.json'))]
assert len(results)==65,len(results)
s={'cases':len(results),'by_stage':dict(collections.Counter(q['stage'] for q in results)),
  'by_source':dict(collections.Counter(q['source_type'] for q in results)),
  'failures':[{'case':x['case_id'],'stage':x['stage'],'error':x.get('error','')[:300]} for x in results if x['stage']!='APPLIES']}
(out/'SUMMARY.json').write_text(json.dumps(s,indent=2)+'\n')
with (out/'RESULTS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['case_id','stage','source_type','claimed_status','source_files','git_apply_check_rc','error'],extrasaction='ignore')
 w.writeheader();w.writerows(results)
print(json.dumps(s),flush=True)
PY