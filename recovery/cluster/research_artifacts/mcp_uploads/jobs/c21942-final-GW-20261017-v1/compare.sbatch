#!/bin/bash
#SBATCH --job-name=c21942GWcheck
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
python3 - <<'PY'
from pathlib import Path
import json,os,re
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
cases={
 'base':root/'case21942_p1_base_qa_job70090',
 'G':root/'case21942_GW_G_eval_job70109',
 'W':root/'case21942_GW_W_eval_job70110'
}
def parse(p):
 name='full.log' if p.name.startswith('case21942_p1_base') else 'full_bun_suite.log'
 body=(p/name).read_text(errors='replace')
 tsc=(p/'typecheck.log').read_text(errors='replace')
 focused=(p/('focused.log' if name=='full.log' else 'codex_focused_tests.log')).read_text(errors='replace')
 return {
  'full_passes':int(re.search(r'(\d+) pass\b',body).group(1)) if re.search(r'(\d+) pass\b',body) else None,
  'full_failures':int(re.search(r'(\d+) fail\b',body).group(1)) if re.search(r'(\d+) fail\b',body) else 0,
  'full_failure_names':sorted(set(line.strip() for line in body.splitlines() if line.startswith('(fail)'))),
  'ts_errors':sorted(set(line for line in tsc.splitlines() if 'error TS' in line)),
  'focus_passes':int(re.search(r'(\d+) pass\b',focused).group(1)) if re.search(r'(\d+) pass\b',focused) else None,
  'focus_failures':int(re.search(r'(\d+) fail\b',focused).group(1)) if re.search(r'(\d+) fail\b',focused) else 0
 }
results={k:parse(v) for k,v in cases.items()}
summ={'baseline':{k:v for k,v in results['base'].items() if k!='ts_errors'},
 'arms':{}}
for label in ['G','W']:
 v=results[label]
 summ['arms'][label]={k:vv for k,vv in v.items() if k!='ts_errors'}
 summ['arms'][label]['new_tsc_errors']=sorted(set(v['ts_errors'])-set(results['base']['ts_errors']))
 summ['arms'][label]['removed_tsc_errors']=sorted(set(results['base']['ts_errors'])-set(v['ts_errors']))
 summ['arms'][label]['new_full_test_failures']=sorted(set(v['full_failure_names'])-set(results['base']['full_failure_names']))
 summ['arms'][label]['ts_error_count']=len(v['ts_errors'])
summ['baseline']['ts_error_count']=len(results['base']['ts_errors'])
out=root/('case21942_GW_comparison_job'+os.environ['SLURM_JOB_ID'])
out.mkdir()
(out/'FINAL_COMPARISON.json').write_text(json.dumps(summ,indent=2)+'\n')
print(json.dumps(summ,indent=2),flush=True)
PY
