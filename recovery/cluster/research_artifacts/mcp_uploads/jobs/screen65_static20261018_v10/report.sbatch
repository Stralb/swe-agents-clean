#!/bin/bash
#SBATCH --job-name=screen65_report
#SBATCH --partition=batch
#SBATCH --dependency=afterok:70694
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
python3 - <<'PY'
from pathlib import Path
import json,csv,io,zipfile,hashlib,os,collections
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
summary_dir=root/'screen65_codeql_summary_job70694'
scan=root/'screen65_codeql_job70675'
align=root/'screen65_root_alignment_job70756'
details=root/'screen65_triage_details_job70754'
out=root/('screen65_shareable_report_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
summary=json.loads((summary_dir/'SCREEN65_CODEQL_SUMMARY.json').read_text())
assert summary['total']==65
rows=list(csv.DictReader((summary_dir/'SCREEN65_CODEQL_RESULTS.csv').open(newline='')))
assert len(rows)==65
positives=[q for q in rows if q['state']=='SCAN_COMPLETE' and int(q.get('new_strong_count') or 0)>0]
both=[q for q in positives if int(q.get('new_weak_count') or 0)>0]
current=[q for q in rows if q['state']!='SCAN_COMPLETE']
history=json.loads((align/'ROOT_ALIGNMENT.json').read_text())
samefile=[x for x in history if x['matches_historical_rule_and_file']]
report={
 'completed':sum(q['state']=='SCAN_COMPLETE' for q in rows),
 'total':65,
 'scanner_positive_cases':len(positives),
 'scanner_positive_complete_source':sum(q['source_type']=='FULL_FROZEN_SNAPSHOT' for q in positives),
 'scanner_positive_filtered_source':sum(q['source_type']!='FULL_FROZEN_SNAPSHOT' for q in positives),
 'positive_cases':[{'case_id':int(x['case_id']),'new_strong_count':int(x['new_strong_count']),'new_weak_count':int(x['new_weak_count'] or 0),
                    'rules':x['new_rule_summary'],'historical_rule_class_overlap':int(x['new_target_rule_findings'] or 0)>0,
                    'source_type':x['source_type']} for x in positives],
 'strict_historical_rule_and_file_overlap_count_in_triaged_cases':len(samefile),
 'warnings':'Scanner findings are not adjudicated vulnerabilities. Filtered sources and partial implementations require full-source replay, functionality and historical issue-body verification.'
}
(out/'RESEARCH_SUMMARY.json').write_text(json.dumps(report,indent=2)+'\n')
with zipfile.ZipFile(out/'SCREEN65_CODEQL_REVIEW.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for file in ['SCREEN65_CODEQL_RESULTS.csv','SCREEN65_CODEQL_SUMMARY.json']:
  z.write(summary_dir/file,file)
 z.write(out/'RESEARCH_SUMMARY.json','RESEARCH_SUMMARY.json')
 z.write(align/'ROOT_ALIGNMENT.json','ROOT_ALIGNMENT.json')
 for rec in rows:
  p=scan/('CASE_%05d'%int(rec['case_id']))/'RESULT.json'
  if p.exists():z.write(p,'case_results/'+p.parent.name+'.json')
 for p in details.glob('CASE_*_TRIAGE.json'):
  z.write(p,'triage/'+p.name)
 for p in details.glob('CASE_*.json'):
  z.write(p,'triage/'+p.name)
with zipfile.ZipFile(out/'SCREEN65_CODEQL_REVIEW.zip') as z: assert z.testzip() is None
print(json.dumps({'status':'REPORT_READY','path':str(out/'SCREEN65_CODEQL_REVIEW.zip'),'bytes':(out/'SCREEN65_CODEQL_REVIEW.zip').stat().st_size,'sha256':hashlib.sha256((out/'SCREEN65_CODEQL_REVIEW.zip').read_bytes()).hexdigest(),'summary':report},indent=2),flush=True)
PY