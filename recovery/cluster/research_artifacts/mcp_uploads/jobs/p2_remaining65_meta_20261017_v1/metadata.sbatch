#!/bin/bash
#SBATCH --job-name=p2rem65meta
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
export PYTHONUNBUFFERED=1
python3 - <<'PY'
from pathlib import Path
import os,csv,json,sqlite3,collections,datetime
home=Path.home()
root=home/'research_artifacts'
source=root/'prevention_pilot_phase2/case_screen_results_v1/FULL_ROOT_CENSUS.csv'
out=root/'prevention_pilot_phase2'/('remaining65_metadata_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
screened={21942,7680,17062,8147,15686,334,13922,9992,10779,3340,313}
roots=list(csv.DictReader(source.open(encoding='utf8',newline='')))
eligible=[x for x in roots if x['eligibility_decision']=='PROVISIONAL' and int(x['case_id']) not in screened]
cases={}
for x in eligible:
 k=int(x['case_id'])
 if k not in cases:cases[k]=dict(x)
 else:
  y=cases[k]
  if int(x['score'])>int(y['score']):cases[k]=dict(x)
assert len(cases)==65, ('Unexpected remaining-case census',len(cases))
sourcefiles=[
 home/'new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.full3809-continuation.db',
 home/'new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.db'
]
conns=[]
for db in sourcefiles:
 con=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True,timeout=25)
 con.row_factory=sqlite3.Row
 con.execute('PRAGMA query_only=ON')
 conns.append(con)
for k in cases:
 r=cases[k]
 r['case_id']=k
 r['score']=int(r['score'])
 r['metadata_source']='NOT_FOUND'
 for i,conn in enumerate(conns):
  try:
   row=conn.execute('''SELECT i.number AS issue_number,i.title AS issue_title,i.body AS issue_body,
                       i.created_at AS issue_created,i.updated_at AS issue_updated,
                       p.number AS pr_number,p.base_sha AS pr_base_sha,p.head_sha AS pr_head_sha,p.created_at AS pr_created
                       FROM cases c
                       JOIN issues i ON i.id=c.issue_id
                       JOIN pull_requests p ON p.id=c.pr_id
                       WHERE c.id = ?''',(k,)).fetchone()
   if row is None:continue
   d=dict(row)
   if int(d['issue_number'])!=int(r['issue_number']) or int(d['pr_number'])!=int(r['pr_number']):
    r['metadata_warning']='ISSUE_PR_MISMATCH'
    continue
   r.update(d)
   r['metadata_source']=i
   break
  except Exception as ex:
   r['metadata_error']=str(ex)[:180]
 body=r.get('issue_body') or ''
 r['has_body']=bool(body.strip())
 r['has_base_sha']=bool(r.get('pr_base_sha'))
 try:
  ct=datetime.datetime.fromisoformat(r['issue_created'].replace('Z','+00:00'))
  pt=datetime.datetime.fromisoformat(r['pr_created'].replace('Z','+00:00'))
  ut=datetime.datetime.fromisoformat(r['issue_updated'].replace('Z','+00:00'))
  r['issue_before_pr']=ct<=pt
  r['prepr_issue_text_temporally_supported']=ct<=pt and ut<=pt
 except Exception:
  r['issue_before_pr']=None
  r['prepr_issue_text_temporally_supported']=False
 r['candidate_packet_eligible']=r['has_body'] and r['has_base_sha'] and r['issue_before_pr'] is True
for conn in conns:conn.close()
# deterministic queue: high-score first, diversify by family via round robin, stable case ID
families=collections.defaultdict(list)
for r in cases.values():families[r['family']].append(r)
for fam in families:
 families[fam].sort(key=lambda q:(not q['candidate_packet_eligible'],not q['prepr_issue_text_temporally_supported'],-q['score'],q['case_id']))
ordered=[]
while any(families.values()):
 for fam in sorted(families,key=lambda n:-len(families[n])):
  if families[fam]:ordered.append(families[fam].pop(0))
for n,r in enumerate(ordered,1):r['queue_rank']=n
summary={'all_historical_root_count':len(roots),'all_provisional_roots':sum(x['eligibility_decision']=='PROVISIONAL' for x in roots),'distinct_provisional_cases':76,'screened_distinct':len(screened),'unscreened_distinct':len(ordered),
         'packet_eligible':sum(r['candidate_packet_eligible'] for r in ordered),
         'issue_text_temporally_supported':sum(r['prepr_issue_text_temporally_supported'] for r in ordered),
         'no_verified_issue_or_base':sum(not(r['has_body'] and r['has_base_sha']) for r in ordered),
         'issue_created_after_pr':sum(r['issue_before_pr'] is False for r in ordered),
         'queue_first_18':[{k:r.get(k) for k in ['case_id','repository','score','family','issue_before_pr','prepr_issue_text_temporally_supported','metadata_source']} for r in ordered[:18]]}
(out/'PRIVATE_CASE_METADATA_65.json').write_text(json.dumps(ordered,ensure_ascii=False,indent=2)+'\n')
(out/'RECOVERY_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
PY
