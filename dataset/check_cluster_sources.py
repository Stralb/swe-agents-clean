import sys,json,hashlib,urllib.request,subprocess,time
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts');job=root/'mcp_uploads/jobs/source_recheck_20261111_v1'
revision='18546a49a1929bf6413f48a6afa79b05c265b256'
base='https://raw.githubusercontent.com/Stralb/swe-agents-clean/'+revision+'/'
def get(path):return json.loads(urllib.request.urlopen(base+path,timeout=90).read())
manifest=get('recovery/cluster/manifest.json');audit=get('recovery/audit/LIVE_CLUSTER_AUDIT.json')
redacted={x['source']:x['source_sha256'] for x in manifest['redacted_sources']}
records={}
for x in manifest['included']:records[x['source']]={'expected':redacted.get(x['source'],x['sha256']),'published_path':x['path']}
for x in audit['supplement_files']:records.setdefault(x['path'],{'expected':x['sha256'],'published_path':x['published_path']})
allowed=[str(root)+'/', '/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/']
changed=[];missing=[];matched=0;miner=0;total=0
for source,x in sorted(records.items()):
 assert any(source.startswith(p) for p in allowed),'Unexpected source root'
 p=Path(source)
 if not p.is_file():missing.append({'source':source,'published_path':x['published_path']});continue
 data=p.read_bytes();total+=len(data);h=hashlib.sha256(data).hexdigest()
 if h!=x['expected']:changed.append({'source':source,'published_path':x['published_path'],'current_sha256':h,'expected_sha256':x['expected']})
 else:matched+=1
 if '/new/malicious-issue-miner-rate-smart/' in source:miner+=1
minerroot=Path('/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart')
raw=subprocess.check_output(['git','-C',str(minerroot),'ls-files','-c','-o','--exclude-standard','-z']).decode().split('\0')
extensions={'.ipynb','.c','.cpp','.h','.rs','.r','.jl','.pl','.py','.pyi','.sh','.sbatch','.slurm','.ps1','.js','.jsx','.ts','.tsx','.mjs','.cjs','.yml','.yaml','.toml','.ini','.cfg','.html','.css','.sql'}
extra=[]
import os
paths=set(filter(None,raw))
for directory,dirs,files in os.walk(minerroot):
 dirs[:]=[d for d in dirs if d not in {'.git','.venv','venv','node_modules','__pycache__','.cache','data'}]
 for filename in files:paths.add(str((Path(directory)/filename).relative_to(minerroot)))
for name in paths:
 p=minerroot/name
 if p.is_file() and (p.suffix.lower() in extensions or p.name in {'Makefile','Dockerfile','requirements.txt','pyproject.toml','package.json','package-lock.json'}) and str(p) not in records:
  extra.append({'source':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
sys.path.insert(0,str(root/'mcp_uploads/jobs/dataset_cleanup_20261111T195749Z_bec2d6/dependencies'))
from huggingface_hub import HfApi,hf_hub_download
api=HfApi();repo='Stralb/malicious-issue-miner-data';info=api.repo_info(repo,repo_type='dataset',files_metadata=True)
data=json.loads(Path(hf_hub_download(repo,'DATASET.json',repo_type='dataset',revision=info.sha)).read_text())
receipt=json.loads(Path(hf_hub_download(repo,'UPLOAD_RECEIPT.json',repo_type='dataset',revision=info.sha)).read_text())
import pyarrow.parquet as pq
casefile=Path(data['manifest']).parent.as_posix()+'/cases.parquet'
table=pq.read_table(hf_hub_download(repo,casefile,repo_type='dataset',revision=info.sha))
assert table.num_rows==3809 and sum(table.column('in_finding_positive_cohort').to_pylist())==192
report={'state':'COMPLETE','github_revision_checked':revision,'source_files_checked':len(records),'source_files_matched':matched,'live_miner_and_supplement_files_checked':miner,'bytes_hashed':total,'changed':changed,'missing':missing,'additional_current_miner_candidates':sorted(extra,key=lambda x:x['source']),'huggingface':{'exists':True,'private':info.private,'current_revision':info.sha,'default_config':data['default_config'],'case_rows':table.num_rows,'positive_cases':192,'verified_release_revision':receipt['commit'],'archived_files_verified':receipt['archived_files_verified']},'scope':'All paths in the preserved cluster and supplemental manifests, plus a fresh tracked, untracked and ignored source scan of the live miner, excluding dependency/cache/data directories. Other projects on the cluster are outside this scope.'}
(job/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
