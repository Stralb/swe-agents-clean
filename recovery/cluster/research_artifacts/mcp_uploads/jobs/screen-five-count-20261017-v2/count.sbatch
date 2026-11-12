#!/bin/bash
#SBATCH --job-name=p2census
#SBATCH --partition=bigbatch,batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
python3 - <<'PY'
from pathlib import Path
import csv,json,collections,os
base=Path.home()/'research_artifacts/prevention_pilot_phase2/case_screen_results_v1'
rows=list(csv.DictReader((base/'FULL_ROOT_CENSUS.csv').open(newline='')))
screened={'21942','7680','17062','8147','15686','334'}
provisional=[r for r in rows if r['eligibility_decision']=='PROVISIONAL']
queued=[r for r in provisional if r['status']=='SCREEN_QUEUE_PREAUDIT']
excluded=[r for r in rows if r['eligibility_decision']=='EXCLUDED']
seen=[r for r in provisional if r['case_id'] in screened]
remaining=[r for r in provisional if r['case_id'] not in screened]
data={
 'roots_all':len(rows),'distinct_historical_issue_pr_case_ids':len({r['case_id'] for r in rows}),
 'metadata_provisional_roots':len(provisional),
 'metadata_provisional_distinct_cases':len({r['case_id'] for r in provisional}),
 'excluded_roots':len(excluded),
 'preselected_queue_roots':len(queued),
 'preselected_queue_distinct_cases':len({r['case_id'] for r in queued}),
 'screened_case_ids':sorted({r['case_id'] for r in seen}),
 'screened_provisional_roots':len(seen),
 'remaining_provisional_roots':len(remaining),
 'remaining_provisional_distinct_case_ids':len({r['case_id'] for r in remaining}),
 'remaining_queue_roots':len([r for r in queued if r['case_id'] not in screened]),
 'remaining_reserve_roots':len([r for r in remaining if r['status']!='SCREEN_QUEUE_PREAUDIT']),
 'screened_not_in_provisional':sorted(screened-{r['case_id'] for r in seen}),
}
out=Path.home()/'research_artifacts/prevention_pilot_phase2'/('screen5_census_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
(out/'CENSUS_COUNTS.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data,indent=2),flush=True)
PY
