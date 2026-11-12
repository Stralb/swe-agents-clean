#!/bin/bash
#SBATCH --job-name=arno_screen65_audit
#SBATCH --partition=stampede
#SBATCH --time=00:05:00
#SBATCH --mem=2G
python3 - <<'PY'
import re,tarfile,io,base64,lzma,hashlib,json,collections,datetime
from pathlib import Path
root=Path.home()/'research_artifacts'
inp=root/'mcp_uploads/screen65_iter3_20261019_transfer_v1'
parts=sorted(inp.glob('chunk_*.txt'))
assert len(parts)==47 and [int(x.stem.split('_')[1]) for x in parts]==list(range(1,48))
raw=b''.join(p.read_bytes().strip() for p in parts)
tarbytes=lzma.decompress(base64.b64decode(raw,validate=True))
with tarfile.open(fileobj=io.BytesIO(tarbytes),mode='r:') as tar:
 files=[]
 for m in tar.getmembers():
  if m.isfile():
   b=tar.extractfile(m).read()
   files.append({'name':m.name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),
     'first_line':b.split(b'\n')[0][:140].decode('utf-8','replace')})
 out=root/'mcp_uploads/jobs/arno_screen65_archive_audit_20261028'
 out.mkdir(parents=True,exist_ok=True)
 report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'transport_parts':47,'b64_chars':len(raw),'tar_bytes':len(tarbytes),
         'tar_sha256':hashlib.sha256(tarbytes).hexdigest(),
         'file_count':len(files),'files':files,
         'extensions':dict(collections.Counter(Path(x['name']).suffix.lower() for x in files)),
         'category':dict(collections.Counter(x['name'].split('_')[0] for x in files))}
 (out/'SCREEN65_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'files':len(files),'categories':report['category'],'sample':files[:8]},indent=2)[:7000])
PY