import tarfile,csv,io,math,json
import numpy as np
from scipy.stats import chi2,binomtest,wilcoxon
p='/mnt/data/C6_MATCHED_POSITIVE_VS_CONTROL_v1.0.tar.gz'
with tarfile.open(p) as t:
 def csvfile(n):
  m=next(z for z in t.getmembers() if z.name.endswith('/'+n));return list(csv.DictReader(io.StringIO(t.extractfile(m).read().decode('utf-8-sig'))))
 rows=csvfile('C6_MATCHED_PAIR_MASTER_190.csv'); primary=csvfile('C6_PRIMARY_OMNIBUS_RESULTS.csv')
M={
'Issue purpose':('positive_issue_purpose','control_issue_purpose'),
'Instruction specificity':('positive_instruction_specificity','control_instruction_specificity'),
'Goal alignment':('positive_goal_alignment','control_goal_alignment'),
'Implementation category':('positive_implementation_pattern','control_implementation_pattern'),
'Formal human review before merge':('positive_human_review','control_human_review'),
'Issue→PR creation delay (hours)':('positive_issue_to_pr_delay_hours','control_issue_to_pr_delay_hours'),
'Same issue/PR author':('positive_same_issue_pr_author','control_same_issue_pr_author'),
'Any requester prior repo activity':('positive_any_prior_repo_activity','control_any_prior_repo_activity'),
'Primary agent/tool':('positive_primary_agent_tool','control_primary_agent_tool')}
results=[]
for r in primary:
 var=r['variable']; typ=r['type']; pkey,nkey=M[var]
 if typ=='categorical':
  obs=[(x[pkey],x[nkey]) for x in rows if x[pkey] and x[nkey]]
  cats=sorted({a for a,b in obs}|{b for a,b in obs})
  m=np.zeros((len(cats),len(cats)))
  ix={v:i for i,v in enumerate(cats)}
  for a,b in obs:m[ix[a],ix[b]]+=1
  k=len(cats);d=(m.sum(axis=1)-m.sum(axis=0))[:k-1]
  cov=np.array([[(m[i,:].sum()+m[:,i].sum()-2*m[i,i]) if i==j else -(m[i,j]+m[j,i]) for j in range(k-1)] for i in range(k-1)])
  stat=float(d@np.linalg.pinv(cov)@d);pv=float(chi2.sf(stat,k-1))
  info={'k':k,'statistic':stat,'frozen_statistic':float(r['test_statistic'])}
 elif typ=='binary':
  obs=[(x[pkey],x[nkey]) for x in rows if x[pkey] in ('Yes','No') and x[nkey] in ('Yes','No')]
  a=sum(x=='Yes' and y=='No' for x,y in obs)
  b=sum(x=='No' and y=='Yes' for x,y in obs)
  pv=float(binomtest(min(a,b),a+b,0.5).pvalue) if (a+b)>0 else 1.
  info={'discordant_positive_only':a,'discordant_control_only':b}
 elif typ=='continuous':
  obs=[(float(x[pkey]),float(x[nkey])) for x in rows if x[pkey] and x[nkey]]
  d=[x-y for x,y in obs]
  pv=float(wilcoxon(d,alternative='two-sided',zero_method='wilcox',method='auto').pvalue)
  info={'median_pair_diff':float(np.median(d))}
 orig=float(r['p_value']);ok=math.isclose(pv,orig,rel_tol=2e-4,abs_tol=2e-6)
 results.append({'variable':var,'type':typ,'n':len(obs),'frozen_n':int(r['n_pairs']),'p_recomputed':pv,'p_frozen':orig,'matches':ok,**info})
print(json.dumps(results,indent=2))
