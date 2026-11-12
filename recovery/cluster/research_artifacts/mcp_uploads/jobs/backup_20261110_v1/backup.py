import json,time,sqlite3,hashlib,gzip,shutil,os
from pathlib import Path
from huggingface_hub import HfApi
root=Path('/home-mscluster/astrauss/research_artifacts')
out=root/'ARNO_MASTER_DB/snapshots/backup_20261110_v1'
out.mkdir(exist_ok=False)
status={'state':'starting','started':time.time(),'files':[],'repo':'Stralb/malicious-issue-miner-data','remote_prefix':'backups/arno-master-20261110-v1'}
def save():
 (out/'status.json').write_text(json.dumps(status,indent=2))
 print(status['state'],flush=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
 return h.hexdigest()
save()
try:
 api=HfApi()
 info=api.repo_info(repo_id=status['repo'],repo_type='dataset')
 if not info.private: raise RuntimeError('Expected existing PRIVATE dataset')
 for name in ['ARNO_RESEARCH_MASTER.sqlite','ARNO_EVIDENCE_VAULT_20261030.sqlite']:
  source=root/'ARNO_MASTER_DB'/name
  target=out/name
  status['state']='snapshot:'+name;save()
  before={'bytes':source.stat().st_size,'mtime_ns':source.stat().st_mtime_ns}
  src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=60)
  dst=sqlite3.connect(str(target))
  src.backup(dst,pages=16384,sleep=0.1)
  dst.close();src.close()
  status['state']='integrity:'+name;save()
  check=sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True)
  result=check.execute('PRAGMA integrity_check').fetchall()
  if result != [('ok',)]: raise RuntimeError('Snapshot integrity failed')
  tables=[r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
  counts={t:check.execute('SELECT COUNT(*) FROM "'+t.replace('"','""')+'"').fetchone()[0] for t in tables}
  check.close()
  entry={'name':name,'bytes':target.stat().st_size,'sha256':sha(target),'integrity_check':'ok','tables':counts,'source_before':before}
  status['files'].append(entry)
  status['state']='compress:'+name;save()
  zipped=out/(name+'.gz')
  with target.open('rb') as f,gzip.open(zipped,'wb',compresslevel=1) as g:shutil.copyfileobj(f,g,8*1024*1024)
  entry['gzip_bytes']=zipped.stat().st_size;entry['gzip_sha256']=sha(zipped)
  status['state']='upload:'+name;save()
  remote=status['remote_prefix']+'/'+zipped.name
  commit=api.upload_file(path_or_fileobj=str(zipped),path_in_repo=remote,repo_id=status['repo'],repo_type='dataset',commit_message='Preserve verified Arno research snapshot '+name)
  entry['hf_commit']=commit.oid;entry['remote_path']=remote
  remote_info=api.get_paths_info(repo_id=status['repo'],paths=[remote],repo_type='dataset',revision=commit.oid)[0]
  lfs=remote_info.lfs
  remote_sha=getattr(lfs,'sha256',None) if lfs else None
  if isinstance(lfs,dict):remote_sha=lfs.get('sha256')
  entry['remote_sha256']=remote_sha
  if remote_info.size!=entry['gzip_bytes'] or remote_sha!=entry['gzip_sha256']:raise RuntimeError('Remote object checksum mismatch')
  entry['remote_verified']=True;save()
 status['state']='complete';status['completed']=time.time();save()
 api.upload_file(path_or_fileobj=str(out/'status.json'),path_in_repo=status['remote_prefix']+'/manifest.json',repo_id=status['repo'],repo_type='dataset',commit_message='Record verified Arno snapshot checksums and table counts')
except Exception as e:
 status['state']='failed';status['error_type']=type(e).__name__;status['error']=str(e)[:1000];save();raise
