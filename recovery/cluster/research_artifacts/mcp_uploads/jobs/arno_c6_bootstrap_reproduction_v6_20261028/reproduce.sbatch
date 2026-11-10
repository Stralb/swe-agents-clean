#!/bin/bash
#SBATCH --job-name=arno_c6_bootstrap
#SBATCH --partition=stampede
#SBATCH --time=00:15:00
#SBATCH --mem=4G
python3 - <<'PY'
from pathlib import Path
import sqlite3,json,zlib,csv,io,random,statistics,collections,math,hashlib,datetime
R=Path.home()/'research_artifacts'
O=R/'mcp_uploads/jobs/arno_c6_bootstrap_reproduction_v6_20261028'
O.mkdir(parents=True,exist_ok=True)
c=sqlite3.connect(f'file:{R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"}?mode=ro',uri=True,timeout=120)
data=[json.loads(r[0]) for r in c.execute('SELECT original_row_json FROM arno_rq2_c6_pairs ORDER BY pair_index')]
if len(data)!=190:raise ValueError('Matched pair count changed')
src={p:zlib.decompress(b) for p,b in c.execute('SELECT source_path,content_zlib FROM arno_evidence_assets')}
source=next(b for p,b in src.items() if p.endswith('C6_REPOSITORY_BLOCKED_CI.csv'))
reported={r['variable']:r for r in csv.DictReader(io.StringIO(source.decode('utf-8-sig')))}
cols=[
 ('Issue purpose','issue_purpose','TVD'),
 ('Instruction specificity','instruction_specificity','TVD'),
 ('Goal alignment','goal_alignment','TVD'),
 ('Implementation category','implementation_pattern','TVD'),
 ('Formal human review before merge','human_review','Rate difference'),
 ('Issue→PR creation delay (hours)','issue_to_pr_delay_hours','Median paired difference'),
 ('Same issue/PR author','same_issue_pr_author','Rate difference'),
 ('Any requester prior repo activity','any_prior_repo_activity','Rate difference'),
 ('Primary agent/tool','primary_agent_tool','TVD')]
bad={'','NA','N/A','MISSING','null','None','Unknown','NOT_VERIFIABLE'}
def metric(rows,key,kind):
 pairs=[(r['positive_'+key],r['control_'+key]) for r in rows]
 pairs=[(x,y) for x,y in pairs if x not in bad and y not in bad]
 if not pairs:return float('nan')
 if kind=='TVD':
  a=collections.Counter(x for x,y in pairs);b=collections.Counter(y for x,y in pairs)
  return sum(abs(a[z]-b[z]) for z in a.keys()|b.keys())/(2*len(pairs))
 if kind=='Rate difference':
  return sum((str(x).lower() in ('yes','true','1'))-(str(y).lower() in ('yes','true','1')) for x,y in pairs)/len(pairs)
 return statistics.median(float(x)-float(y) for x,y in pairs)
parent={}
def find(x):
 parent.setdefault(x,x)
 if parent[x]!=x:parent[x]=find(parent[x])
 return parent[x]
def join(x,y):
 a=find(x);b=find(y)
 if a!=b:parent[b]=a
for r in data:join(r['positive_repository'],r['control_repository'])
groups=collections.defaultdict(list)
for i,r in enumerate(data):groups[find(r['positive_repository'])].append(i)
blocks=list(groups.values())
if len(blocks)!=95 or max(map(len,blocks))!=15:raise ValueError('Frozen repo graph block mismatch')
seed=20260903
rng=random.Random(seed)
boot={name:[] for name,_,_ in cols}
for it in range(5000):
 selected=[data[i] for _ in range(len(blocks)) for i in blocks[rng.randrange(len(blocks))]]
 for name,key,kind in cols:
  boot[name].append(metric(selected,key,kind))
def quantile(a,p):
 a=sorted(v for v in a if not math.isnan(v))
 at=(len(a)-1)*p
 lo=int(at);hi=min(lo+1,len(a)-1)
 return a[lo]*(1-(at-lo))+a[hi]*(at-lo)
comp=[]
for name,key,kind in cols:
 obs=metric(data,key,kind)
 row=reported[name]
 original=float(row['estimate'])
 lo=quantile(boot[name],.025);hi=quantile(boot[name],.975)
 oldlo=float(row['repo_blocked_ci95_low']);oldhi=float(row['repo_blocked_ci95_high'])
 comp.append({'variable':name,'effect':kind,'observed_recomputed':obs,'source_estimate':original,
  'point_estimate_matches':abs(obs-original)<1e-8,
  'independent_repo_blocked_ci95':[lo,hi],
  'frozen_repo_blocked_ci95':[oldlo,oldhi],
  'absolute_difference_ci_bounds':[abs(lo-oldlo),abs(hi-oldhi)],
  'same_bootstrap_realization_proven':False})
status='COUNT_BLOCKS_AND_POINT_ESTIMATES_REPRODUCED' if all(r['point_estimate_matches'] for r in comp) else 'POINT_ESTIMATE_DISCREPANCIES'
res={'status':status,'source':'arno_rq2_c6_pairs.orig_row_json; frozen C6_REPOSITORY_BLOCKED_CI.csv',
 'original_bootstrap_algorithm_not_ARCHIVED':True,'method':'Independent cluster bootstrap using frozen repository components, Python random.Random(seed), percentile 95% CI; numerical difference from frozen original replicates is expected.',
 'seed':seed,'replicates':5000,'blocks':len(blocks),'largest_block':max(map(len,blocks)),
 'comparisons':comp,'source_CI_sha256':hashlib.sha256(source).hexdigest(),
 'claim_caveat':'Do not claim byte-for-byte reproduction of original C6 bootstrap random stream.'}
(O/'REPOSITORY_BLOCKED_CI_REPRODUCTION.json').write_text(json.dumps(res,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':status,'point_estimates_matching':sum(x['point_estimate_matches'] for x in comp),
 'ci_differences':[(x['variable'],[round(z,4) for z in x['absolute_difference_ci_bounds']]) for x in comp]},ensure_ascii=False,indent=2))
PY