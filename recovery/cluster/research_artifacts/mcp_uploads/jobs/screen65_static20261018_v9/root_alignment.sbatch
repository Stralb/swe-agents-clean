#!/bin/bash
#SBATCH --job-name=screen65_match_roots
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
python3 - <<'PY'
import os,json,csv,pathlib,collections
root=pathlib.Path.home()/'research_artifacts/prevention_pilot_phase2'
out=root/('screen65_root_alignment_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
rows=list(csv.DictReader((root/'case_screen_results_v1/FULL_ROOT_CENSUS.csv').open(newline='',encoding='utf8')))
candidates=[3581,8152,22223,16633,32759,3429,12344,31207,20094]
results=[]
for cid in candidates:
 r=json.loads((root/'screen65_codeql_job70675'/('CASE_%05d'%cid)/'RESULT.json').read_text())
 original=[x for x in rows if int(x['case_id'])==cid and x['eligibility_decision']=='PROVISIONAL']
 alerts=r.get('findings',{}).get('new_strong_findings',[])
 for a in alerts:
  matched=[x for x in original if a['rule']==x['target_rule']]
  matched_samefile=[x for x in matched if a['path']==x['changed_file']]
  results.append({'case_id':cid,'repo':original[0]['repository'] if original else '',
   'alert_rule':a['rule'],'alert_path':a['path'],'alert_line':a['line'],
   'matches_historical_rule':bool(matched),
   'matches_historical_rule_and_file':bool(matched_samefile),
   'historical_rule_files':[[x['target_rule'],x['changed_file']] for x in original],
   'source_type':r['source_type']})
(out/'ROOT_ALIGNMENT.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2),flush=True)
PY