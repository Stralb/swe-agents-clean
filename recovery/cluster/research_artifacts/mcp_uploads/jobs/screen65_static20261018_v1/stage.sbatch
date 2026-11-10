#!/bin/bash
#SBATCH --job-name=screen65_stage
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
python3 - <<'PY'
from pathlib import Path
import os,hashlib,base64,zipfile,json,re,csv,io
root=Path.home()/'research_artifacts'
stage=root/'mcp_uploads/screen65_20261018_v1'
out=root/'prevention_pilot_phase2'/('screen65_static_analysis_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
chunks=[stage/('b64_chunk_%02d.txt'%i) for i in range(33)]
assert all(p.exists() for p in chunks),'MISSING_TRANSFER_CHUNKS'
counts=[p.stat().st_size for p in chunks]
assert counts==[9000]*32+[5772],('BAD_CHUNK_LENGTHS',counts)
encoded=''.join(p.read_text().strip() for p in chunks)
payload=base64.b64decode(encoded,validate=True)
expected='d53768f38d5b0261052fb967328eaeba20ebd79fd9dbaf022dc76d8062e92716'
digest=hashlib.sha256(payload).hexdigest()
assert digest==expected,('INPUT_ARCHIVE_SHA_MISMATCH',digest)
zipfile_path=out/'SCREEN_ALL_65_CASES_FINAL.zip'
with zipfile_path.open('xb') as f:f.write(payload)
patch_dir=out/'patches';patch_dir.mkdir()
rows=[]
with zipfile.ZipFile(zipfile_path) as z:
 assert z.testzip() is None,'ZIP_CORRUPT'
 patches=[i for i in z.infolist() if i.filename.startswith('patches/') and i.filename.endswith('.patch')]
 assert len(patches)==65,('PATCH_COUNT_WRONG',len(patches))
 index={int(r['case_id']):r for r in csv.DictReader(io.StringIO(z.read('RESULTS_INDEX.csv').decode()))}
 assert len(index)==65,('INDEX_NOT_65',len(index))
 seen=set()
 for info in patches:
  data=z.read(info.filename)
  match=re.search(r'(?:O_)?CASE_(\d+)\.patch$',info.filename)
  assert match,('NAME_UNRECOGNIZED',info.filename)
  cid=int(match.group(1))
  assert cid in index and cid not in seen and data.startswith(b'diff --git '),(cid,info.filename)
  seen.add(cid)
  path=patch_dir/('CASE_%05d.patch'%cid)
  path.write_bytes(data)
  rows.append({'case_id':cid,'patch_filename':info.filename,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
               'claimed_status':index[cid]['status'],'source':index[cid]['changed_files']})
 assert seen==set(index)
manifest={'status':'VERIFIED','cases':65,'sha256':digest,'payload_bytes':len(payload),'patches':sorted(rows,key=lambda a:a['case_id'])}
(out/'TRANSFER_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('VERIFIED_65_PATCHES',digest,'bytes',len(payload),'output',out,flush=True)
PY