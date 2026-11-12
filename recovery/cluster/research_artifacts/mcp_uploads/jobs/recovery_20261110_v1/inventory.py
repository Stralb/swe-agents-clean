import os,json,hashlib,subprocess,sqlite3,time
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts')
out=root/'mcp_uploads/jobs/recovery_20261110_v1'
report={'time':time.time(),'sources':[],'databases':[],'git':[],'env':{}}
skip={'.git','node_modules','__pycache__','.venv','venv','.cache'}
for base,label in [(root,'research'),(Path('/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart'),'miner')]:
 for d,dirs,files in os.walk(base,followlinks=False):
  dirs[:]=[n for n in dirs if n not in skip and not any(s in n.lower() for s in ['repo_cache','repcache','query-pack','codeql_db']) ]
  p=Path(d)
  if (p/'.git').exists():
   def git(*a):
    r=subprocess.run(['git','-C',str(p),*a],capture_output=True,text=True,timeout=30)
    return r.stdout[:12000]
   report['git'].append({'path':str(p),'head':git('rev-parse','HEAD'),'status':git('status','--short'),'remotes':git('remote')})
  for n in files:
   f=p/n
   if f.is_symlink(): continue
   try: size=f.stat().st_size
   except OSError: continue
   if n.endswith(('.sqlite','.db')):
    report['databases'].append({'path':str(f),'bytes':size,'mtime':f.stat().st_mtime})
   if n.endswith(('.py','.sbatch','.slurm','.sh','.sql')) and size<2000000:
    data=f.read_bytes()
    report['sources'].append({'path':str(f),'bytes':size,'sha256':hashlib.sha256(data).hexdigest()})
for p in [Path('/home-mscluster/astrauss/.venvs/huggingface/bin/python'),Path('/home-mscluster/astrauss/.cache/huggingface/token')]:
 report['env'][str(p)]=p.exists()
(out/'inventory.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'sources':len(report['sources']),'databases':report['databases'],'git':report['git'],'env':report['env']}),flush=True)
