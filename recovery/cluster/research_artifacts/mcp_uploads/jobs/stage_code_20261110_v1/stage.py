import os,json,re,hashlib,shutil,subprocess,time
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts')
miner=Path('/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart')
out=root/'mcp_uploads/jobs/stage_code_20261110_v1'
stage=out/'payload'
stage.mkdir(exist_ok=False)
items=[];blocked=[];errors=[]
patterns=[r'gh[pousr]_[A-Za-z0-9_]{20,}',r'github_pat_[A-Za-z0-9_]{30,}',r'hf_[A-Za-z0-9]{20,}',r'sk-[A-Za-z0-9_-]{24,}',r'AKIA[0-9A-Z]{16}',r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'(?i)(?:password|passwd|secret|access_token|api_key|github_token|hf_token)\s*[:=]\s*["\x27][A-Za-z0-9+/=_-]{12,}["\x27]']
skip={'.git','node_modules','__pycache__','.venv','venv','.cache','site-packages','dist','build','vendor'}
for base,label in [(root,'research_artifacts'),(miner,'miner')]:
 for d,dirs,files in os.walk(base,followlinks=False):
  p=Path(d)
  dirs[:]=[n for n in dirs if n not in skip and not any(s in n.lower() for s in ['cache','codeql_db','query-pack','snapshot','spool']) ]
  if p==out:dirs[:]=[];continue
  if (p/'.git').exists() and p!=miner:dirs[:]=[];continue
  if label=='miner' and p==miner:dirs[:]=[n for n in dirs if n in {'src','scripts','ui','tests','analysis','slurm','config','configs'}]
  for n in files:
   f=p/n
   if f.is_symlink() or not n.endswith(('.py','.sbatch','.slurm','.sh','.sql','.toml','.yml','.yaml','.ini')):continue
   try:
    size=f.stat().st_size
    if size>2_000_000:continue
    data=f.read_bytes()
    text=data.decode('utf-8')
    rel=Path('recovery/cluster')/label/f.relative_to(base)
    rec={'path':str(rel),'source':str(f),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    if any(re.search(pat,text) for pat in patterns):
     blocked.append(rec);continue
    dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    items.append(rec)
   except (OSError,UnicodeError) as e:errors.append({'path':str(f),'error':type(e).__name__})
manifest={'created':time.time(),'included':items,'quarantined':blocked,'errors':errors,'policy':'Original bytes preserved; obvious embedded credentials excluded; all originals untouched.'}
(stage/'recovery/cluster/manifest.json').write_text(json.dumps(manifest,indent=2))
(out/'summary.json').write_text(json.dumps({'files':len(items),'bytes':sum(x['bytes'] for x in items),'quarantined':blocked,'errors':errors,'top':items[:15]},indent=2))
print(json.dumps({'files':len(items),'bytes':sum(x['bytes'] for x in items),'quarantined':len(blocked),'errors':len(errors)}),flush=True)
