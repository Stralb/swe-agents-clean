from pathlib import Path
import os, json, shutil
import numpy as np, pandas as pd
from scipy import sparse
from v21_common import save_frame, write_json
from v21_analysis import *

root=Path('/mnt/data/v21_integration_mock'); shutil.rmtree(root,ignore_errors=True); src=root/'source';out=root/'out'
for p in ['00_manifest','01_raw','03_views/patch','03_views/syntax','03_views/text','03_views/paths','05_latent_topics','06_templates','09_associations']:(src/p).mkdir(parents=True,exist_ok=True)
write_json(src/'00_manifest/FINAL_STATUS_V2.json',{'status':'PASS','deep_discovery_complete':True,'outcome_overlay_performed':False,'security_outcomes_read':False})
pd.DataFrame([{'table':'scanner_findings','status':'BLOCKED_FORBIDDEN_TABLE'},{'table':'issues','status':'CORE_SAFE_READ'}]).to_csv(src/'00_manifest/TABLE_ACCESS_AUDIT.csv',index=False)
n=3809;rng=np.random.default_rng(1);case=np.arange(1,n+1);repo=rng.integers(1,201,size=n)
cases=pd.DataFrame({'case_id':case,'repo_id':repo,'issue_id':case+10000,'pr_id':case+20000});save_frame(cases,src/'01_raw/cases_linkage')
start=pd.Timestamp('2025-11-01',tz='UTC');days=rng.integers(0,300,size=n);pr_created=[(start+pd.Timedelta(int(d),'D')).isoformat() for d in days]
issue_created=[(start+pd.Timedelta(int(d-1),'D')).isoformat() for d in days]
cat=rng.choice(['x','y','z'],n);a=rng.normal(size=n);event=(rng.random(n)<.22).astype(int);trend=days/300+rng.normal(scale=.3,size=n)
raw=pd.DataFrame({'case_id':case,'repo_id':repo,'repo__language':rng.choice(['TypeScript','JavaScript'],n,p=[.8,.2]),'pr__created_at':pr_created,'issue__created_at':issue_created,'a':a,'a_dup':a,'event':event,'category':cat,'trend':trend,'issue__body__words':rng.poisson(100+days*.5)})
save_frame(raw,src/'01_raw/case_scalar_features')
feat=raw.drop(columns=['pr__created_at','issue__created_at']).copy();feat['numcat']=rng.normal(size=n)+pd.Series(cat).map({'x':0,'y':2,'z':4}).to_numpy();feat['template__demo']=(rng.random(n)<.08).astype(int);save_frame(feat,src/'09_associations/discovery_feature_table')
pd.DataFrame({'case_id':case,'patch_line_coverage_ratio':np.where(rng.random(n)<.98,1.0,.3)}).to_csv(src/'01_raw/patch_coverage.csv',index=False)
# Patch docs with recurring calls.
add=[];dele=[]
for i in range(n):
    s='foo()\npath.join(a,b)\n' if i%5==0 else 'bar()\n'
    if i%7==0:s+='JSON.stringify(x)\n'
    add.append(s);dele.append('old()\n' if i%8==0 else '')
save_frame(pd.DataFrame({'case_id':case,'add_raw':add,'del_raw':dele}),src/'03_views/patch/patch_documents')

def ss(base, X, feats):
    sparse.save_npz(base.with_suffix('.npz'),sparse.csr_matrix(X));np.save(base.with_name(base.name+'_case_ids.npy'),case);np.save(base.with_name(base.name+'_features.npy'),np.array(feats,dtype=object),allow_pickle=True);base.with_name(base.name+'_meta.json').write_text('{}')
# Common simple features in sparse views.
features=['foo','bar','path.join','json.stringify','old','node=call_expression','src','test','fix','feature']
A=np.zeros((n,len(features)),dtype=np.int8);D=np.zeros_like(A)
A[:,1]=1;A[::5,0]=1;A[::5,2]=1;A[::7,3]=1;D[::8,4]=1;A[:,5]=1;D[::8,5]=1;A[::3,6]=1;A[::4,7]=1;A[::6,8]=1;A[::9,9]=1
views={
'patch__patch_add_raw__word':('03_views/patch/patch_add_raw__word',A),
'patch__patch_del_raw__word':('03_views/patch/patch_del_raw__word',D),
'patch__patch_add_norm_tfidf':('03_views/patch/patch_add_norm_tfidf',A),
'patch__patch_del_norm_tfidf':('03_views/patch/patch_del_norm_tfidf',D),
'syntax__syntax_add_tfidf':('03_views/syntax/syntax_add_tfidf',A),
'syntax__syntax_del_tfidf':('03_views/syntax/syntax_del_tfidf',D),
'paths__path_token_tfidf':('03_views/paths/path_token_tfidf',A),
'paths__path_items_binary':('03_views/paths/path_items_binary',A),
'text__issue_body__word':('03_views/text/issue_body__word',A),
'text__issue_title__word':('03_views/text/issue_title__word',A),
'text__pr_body__word':('03_views/text/pr_body__word',A),
'patch__edit_shape_tfidf':('03_views/patch/edit_shape_tfidf',A),
}
reg=[]
for v,(rel,X) in views.items():
    base=src/rel;ss(base,X,features);reg.append({'view':v,'base':str(base),'rows':n,'features':len(features)})
pd.DataFrame(reg).to_csv(src/'05_latent_topics/sparse_registry.csv',index=False)
pd.DataFrame({'case_id':case,'text__reltext_ai_markers_marker_text__char__topic':rng.integers(0,4,n),'text__issue_body__word__topic':rng.integers(0,5,n)}).to_csv(src/'05_latent_topics/topic_assignments.csv',index=False)
# template group in patch add view
members=case[::50][:30]
pd.DataFrame([{'template_id':'patch__patch_add_raw__word__T00001','view':'patch__patch_add_raw__word','case_count':len(members),'repository_count':len(set(repo[members-1])),'cross_repository':1,'threshold':.9}]).to_csv(src/'06_templates/template_groups.csv',index=False)
pd.DataFrame({'template_id':['patch__patch_add_raw__word__T00001']*len(members),'view':['patch__patch_add_raw__word']*len(members),'case_id':members}).to_csv(src/'06_templates/template_members.csv',index=False)

os.environ['V21_REL_BOOTSTRAPS']='3';os.environ['V21_REL_NULLS']='3';os.environ['V21_PATTERN_BOOTSTRAPS']='3';os.environ['V21_PATTERN_NULLS']='3';os.environ['V21_TEMP_BOOTSTRAPS']='3'
for name,fn in [('audit',stage_audit),('redundancy',stage_redundancy),('associations',stage_associations),('patterns',stage_patterns),('motifs',stage_motifs),('templates',stage_templates),('temporal',stage_temporal),('stability',stage_stability),('catalog',stage_catalog),('report',stage_report)]:
    print('RUN',name);fn(src,out)
print((out/'00_audit/FINAL_STATUS_V21.json').read_text())
print('V21_INTEGRATION_TEST=PASS')
