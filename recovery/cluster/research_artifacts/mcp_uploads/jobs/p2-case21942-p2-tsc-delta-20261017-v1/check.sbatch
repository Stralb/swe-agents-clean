#!/bin/bash
#SBATCH --job-name=p2tscaudit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
python3 - <<'PY'
from pathlib import Path
import json
r=Path.home()/'research_artifacts/prevention_pilot_phase2'
sets={
 'base':r/'case21942_p1_base_qa_job70090',
 'P1':r/'case21942_p1_eval_job70087',
 'P2':r/'case21942_p2_eval_job70092'
}
def lines(path,contains):
 return sorted(set(x for x in path.read_text(errors='replace').splitlines() if contains in x))
a={k:{'ts':lines(p/('typecheck.log'),'error TS'), 'fails':lines(p/('full.log' if k=='base' else 'full_bun_suite.log'),'3 tests failed:')} for k,p in sets.items()}
for k,v in a.items():
 print(k,'ts_errors',len(v['ts']),'extra_over_base',list(sorted(set(v['ts'])-set(a['base']['ts']))),'removed_from_base',len(set(a['base']['ts'])-set(v['ts'])),flush=True)
result={'tsc_extra_p2':sorted(set(a['P2']['ts'])-set(a['base']['ts'])),
 'tsc_removed_p2':sorted(set(a['base']['ts'])-set(a['P2']['ts'])),
 'tsc_extra_p1':sorted(set(a['P1']['ts'])-set(a['base']['ts'])),
 'counts':{k:len(v['ts']) for k,v in a.items()}}
out=r/'case21942_p2_eval_job70092'/'TSC_DIFFERENTIAL.json'
out.write_text(json.dumps(result,indent=2)+'\n')
PY
