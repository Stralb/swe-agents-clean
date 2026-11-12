#!/bin/bash
#SBATCH --job-name=screen65_interim
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
python3 - <<'PY'
from pathlib import Path
from collections import Counter,defaultdict
import json,csv,os
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
results=root/'screen65_codeql_job70675'
stage=json.loads((root/'screen65_static_analysis_job70606/TRANSFER_MANIFEST.json').read_text())
source=list(csv.DictReader((root/'case_screen_results_v1/FULL_ROOT_CENSUS.csv').open(newline='',encoding='utf8')))
case_rules=defaultdict(set)
for item in source:
 if item['eligibility_decision']=='PROVISIONAL':
  case_rules[int(item['case_id'])].add(item['target_rule'])
out=root/('screen65_codeql_summary_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
records=[]
for c in stage['patches']:
 cid=c['case_id'];p=results/('CASE_%05d'%cid)/'RESULT.json'
 if p.exists():
  s=json.loads(p.read_text())
 else:
  s={'case_id':cid,'stage':'MISSING_RESULT','source_type':'UNKNOWN','error':'Job did not write RESULT.json'}
 f=s.get('findings') or {}
 rules=case_rules.get(cid,set())
 added=f.get('new_by_rule_strong') or {}
 record={'case_id':cid,'source_type':s.get('source_type','UNKNOWN'),'generation_claim':c['claimed_status'],
  'state':s.get('stage'),'before_total':f.get('before_total'),'after_total':f.get('after_total'),
  'new_strong_count':f.get('new_strong_count'),'new_weak_count':f.get('new_weak_count'),
  'new_target_rule_findings':sum(added.get(r,0) for r in rules),'historical_target_rules':';'.join(sorted(rules)),
  'new_rule_summary':';'.join('%s:%d'%(k,v) for k,v in sorted(added.items())),
  'error':s.get('error',''),'patch_application_rc':(s.get('checks',{}).get('apply') or {}).get('rc')}
 records.append(record)
with (out/'SCREEN65_CODEQL_RESULTS.csv').open('w',newline='') as t:
 w=csv.DictWriter(t,fieldnames=records[0].keys());w.writeheader();w.writerows(records)
summary={'total':len(records),'by_state':dict(Counter(r['state'] for r in records)),
 'by_source_type':dict(Counter(r['source_type'] for r in records)),
 'strict_full_clean_cases':[r['case_id'] for r in records if r['state']=='SCAN_COMPLETE' and r['source_type']=='FULL_FROZEN_SNAPSHOT' and r['new_strong_count']==0 and r['new_weak_count']==0],
 'strict_full_new_finding_cases':[r['case_id'] for r in records if r['state']=='SCAN_COMPLETE' and r['source_type']=='FULL_FROZEN_SNAPSHOT' and (r['new_strong_count'] or 0)>0],
 'full_original_target_reproductions':[r['case_id'] for r in records if r['state']=='SCAN_COMPLETE' and r['source_type']=='FULL_FROZEN_SNAPSHOT' and r['new_target_rule_findings']>0],
 'filtered_source_provisional_new_findings':[r['case_id'] for r in records if r['state']=='SCAN_COMPLETE' and r['source_type']!='FULL_FROZEN_SNAPSHOT' and (r['new_strong_count'] or 0)>0],
 'noncompleted_cases':[{'case':r['case_id'],'state':r['state'],'error':r['error'][:220]} for r in records if r['state']!='SCAN_COMPLETE'],
 'suite':'javascript-security-extended','security_claim':'Differential scanner findings are not equal to confirmed vulnerabilities.'}
(out/'SCREEN65_CODEQL_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2),flush=True)
PY