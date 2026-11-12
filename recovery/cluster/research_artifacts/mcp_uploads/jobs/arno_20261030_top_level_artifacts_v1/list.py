#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import os,json,hashlib
R=Path.home()/'research_artifacts'
OUT=R/'mcp_uploads/jobs/arno_20261030_top_level_artifacts_v1/REPORT.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
files=[];dirs=[]
for p in sorted(R.iterdir()):
 if p.is_symlink():continue
 if p.is_file():
  size=p.stat().st_size
  files.append({'file':p.name,'bytes':size,'sha256':sha(p) if size<=300000000 else None})
 elif p.is_dir():dirs.append(p.name)
report={'status':'ROOT_DIRECT_SOURCE_FILES_INVENTORY','utc':datetime.now(timezone.utc).isoformat(),
 'directories_count':len(dirs),'files_count':len(files),'files':files,'directories':dirs,
 'limit':'Only direct files under research_artifacts; files above 300MB have metadata, not content hash. No source modifications.'}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open('x') as f:json.dump(report,f,indent=2)
print(json.dumps({'files':len(files),'dirs':len(dirs),'archives':sum(x['file'].endswith(('.zip','.tar.gz','.tgz')) for x in files),'total_file_bytes':sum(x['bytes'] for x in files)}),flush=True)
