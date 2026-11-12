#!/bin/bash
#SBATCH --job-name=codeql_all_diffs
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
python3 - <<'PY'
import json,collections,os,re
from pathlib import Path
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
out=root/('screen5_allrule_diffs_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
cases=[
 ('8147_O',root/'screen5_eval_8147_job70128/base.sarif',root/'screen5_eval_8147_job70128/patched.sarif'),
 ('8147_G',root/'screen5_eval_8147_job70128/base.sarif',root/'GW_screeneval_case8147_file2_job70176/patched.sarif'),
 ('8147_W',root/'screen5_eval_8147_job70128/base.sarif',root/'GW_screeneval_case8147_file3_job70177/patched.sarif'),
 ('15686_O',root/'screen5_eval_15686_job70129/base.sarif',root/'screen5_eval_15686_job70129/patched.sarif'),
 ('15686_file1',root/'screen5_eval_15686_job70129/base.sarif',root/'GW_screeneval_case15686_file1_job70178/patched.sarif'),
 ('15686_file2',root/'screen5_eval_15686_job70129/base.sarif',root/'GW_screeneval_case15686_file2_job70175/patched.sarif')
]
def entries(path):
 obj=json.loads(path.read_text())
 results=[]
 for run in obj.get('runs',[]):
  for r in run.get('results',[]):
   loc=(r.get('locations') or [{}])[0].get('physicalLocation',{})
   msg=r.get('message',{}).get('text','')
   f=r.get('partialFingerprints') or {}
   row={
    'rule':r.get('ruleId',''),
    'file':loc.get('artifactLocation',{}).get('uri',''),
    'line':loc.get('region',{}).get('startLine'),
    'msg':msg[:320],
    'primaryLocationLineHash':f.get('primaryLocationLineHash'),
    'primaryLocationStartColumnFingerprint':f.get('primaryLocationStartColumnFingerprint'),
    'otherFingerprints':f
   }
   results.append(row)
 return results
def strong_key(x):
 return (x['rule'],x['file'],x['primaryLocationLineHash'] or x['msg'],x['primaryLocationStartColumnFingerprint'] or '')
def weak_key(x):
 return (x['rule'],x['file'],x['msg'])
def difference(before,after,keyfunc):
 available=collections.Counter(keyfunc(x) for x in before)
 new=[]
 for x in after:
  key=keyfunc(x)
  if available[key]>0:available[key]-=1
  else:new.append(x)
 return new
summary=[]
for name,b,a in cases:
 before,after=entries(b),entries(a)
 added=difference(before,after,strong_key)
 low=difference(before,after,weak_key)
 pre_counts=collections.Counter(x['rule'] for x in before)
 aft_counts=collections.Counter(x['rule'] for x in after)
 row={'case':name,'before_all':len(before),'after_all':len(after),'introduced_all':len(added),'introduced_by_rule':dict(collections.Counter(x['rule'] for x in added)),
      'introduced':added,'weak_match_introduced_count':len(low),'weak_match_introduced_by_rule':dict(collections.Counter(x['rule'] for x in low)),'total_before_by_rule':dict(pre_counts),'total_after_by_rule':dict(aft_counts)}
 summary.append(row)
 print(name, 'counts',len(before),'->',len(after),'introduced',len(added),'byrule',row['introduced_by_rule'],'weak',len(low),flush=True)
(out/'ALL_RULE_DIFFERENTIAL_RESULTS.json').write_text(json.dumps(summary,indent=2)+'\n')
PY
