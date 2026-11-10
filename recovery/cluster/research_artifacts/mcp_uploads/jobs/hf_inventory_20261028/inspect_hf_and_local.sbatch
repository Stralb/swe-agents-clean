#!/bin/bash
#SBATCH --job-name=hf_inventory_readonly
#SBATCH --partition=stampede
#SBATCH --time=00:06:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/hf_inventory_20261028/slurm-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/hf_inventory_20261028/slurm-%j.err

python3 - <<'PY'
from pathlib import Path
import collections, json, os, sqlite3, traceback
root=Path.home()/'research_artifacts'/'mcp_uploads'/'jobs'/'hf_inventory_20261028'
root.mkdir(parents=True, exist_ok=True)
repo='Stralb/malicious-issue-miner-data'
report={'purpose':'read-only HF inventory and local SQLite introspection','repo':repo,'files':[],'errors':[]}
try:
    from huggingface_hub import HfApi
    api=HfApi()
    info=api.dataset_info(repo_id=repo, files_metadata=True)
    report['hf_access']='authenticated_or_public_success'
    report['hf_sha']=getattr(info,'sha',None)
    report['hf_private']=getattr(info,'private',None)
    report['hf_last_modified']=str(getattr(info,'last_modified',None))
    report['hf_card_data']=str(getattr(info,'card_data',None))[:4000]
    for obj in getattr(info,'siblings',[]) or []:
        lfs=getattr(obj,'lfs',None)
        item={'path':str(getattr(obj,'rfilename','')),'size':getattr(obj,'size',None),'blob_id':getattr(obj,'blob_id',None)}
        if lfs is not None: item['lfs_size']=getattr(lfs,'size',None)
        report['files'].append(item)
    sizes=collections.Counter()
    for f in report['files']:
        sizes[f['path'].split('/')[0]]+=1
    report['top_level_counts']=dict(sizes)
    try:
        from huggingface_hub import hf_hub_download
        if any(x['path']=='README.md' for x in report['files']):
            readme=hf_hub_download(repo_id=repo,filename='README.md',repo_type='dataset')
            report['readme_excerpt']=Path(readme).read_text(errors='replace')[:5000]
    except Exception as exc: report['errors'].append('README retrieval: '+str(exc)[:450])
except Exception as exc:
    report['hf_access']='not_verified'
    report['errors'].append('HF inventory: '+type(exc).__name__+': '+str(exc)[:700])

dbs=[
    ('hf_aug17',Path.home()/'new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db'),
    ('final_aug29',Path.home()/'new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db')
]
report['local_dbs']={}
for name,path in dbs:
    d={'exists':path.is_file()}
    if d['exists']:
        d['size_bytes']=path.stat().st_size
        try:
            con=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=4)
            d['table_names']=[x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
            for table in ('cases','repos','issues','pull_requests','scanner_findings','scanner_runs','case_notes'):
                if table in d['table_names']:
                    try:d[table+'_rows']=con.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                    except Exception as exc:d[table+'_error']=str(exc)[:200]
            if 'cases' in d['table_names']:
                d['case_status_counts']=[list(x) for x in con.execute('SELECT status,COUNT(*) FROM cases GROUP BY status LIMIT 20').fetchall()]
            if 'scanner_findings' in d['table_names']:
                d['introduced_finding_rows']=con.execute('SELECT COUNT(*) FROM scanner_findings WHERE introduced=1').fetchone()[0]
                d['introduced_distinct_case_ids']=con.execute('SELECT COUNT(DISTINCT case_id) FROM scanner_findings WHERE introduced=1').fetchone()[0]
            con.close()
        except Exception as exc:d['error']=type(exc).__name__+': '+str(exc)[:500]
    report['local_dbs'][name]=d
out=root/'INVENTORY_READONLY.json'
out.write_text(json.dumps(report,indent=2,default=str)+'\n')
print('inventory_path='+str(out))
print('hf_access='+str(report.get('hf_access')))
print('hf_file_count='+str(len(report['files'])))
print('local_db_counts='+json.dumps({k:{x:v for x,v in d.items() if x.endswith('_rows') or x in ('exists','introduced_finding_rows','introduced_distinct_case_ids')} for k,d in report['local_dbs'].items()}))
print('errors='+json.dumps(report['errors']))
PY
