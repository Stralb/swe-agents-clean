#!/bin/bash
#SBATCH --job-name=screen65_second_stagefb
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:15:00
python3 - <<'PY'
from pathlib import Path
import base64,tarfile,hashlib,io,json,csv,os,re
root=Path.home()/'research_artifacts'
stage=root/'mcp_uploads/screen65_second_oct18_v1'
dest=root/'prevention_pilot_phase2/screen65_second_20261018_v1'
dest.mkdir(parents=True,exist_ok=False)
chunks=[stage/('payload_chunk_%02d.txt'%i) for i in range(12)]
assert all(x.is_file() for x in chunks),'MISSING_CHUNK'
lengths=[p.stat().st_size for p in chunks]
assert lengths==[9000]*11+[6868],('BAD_CHUNK_SIZES',lengths)
data=base64.b64decode(''.join(p.read_text().strip() for p in chunks),validate=True)
digest=hashlib.sha256(data).hexdigest()
assert digest=='bbd514d7f3b599fcefd8a87f1150489035588590730a6850f666bf3d7a0ceaf5',('SHA_MISMATCH',digest)
(dest/'SCREEN65_SECOND_CHAT_TRANSFER.tar.xz').write_bytes(data)
patches=dest/'patches'
patches.mkdir()
rows=[]
with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as tar:
    members=tar.getmembers()
    assert len(members)==68
    names={m.name for m in members}
    assert {'README.txt','RESULTS_INDEX.csv','PATCH_CHECKS.txt'}.issubset(names)
    index=list(csv.DictReader(io.StringIO(tar.extractfile('RESULTS_INDEX.csv').read().decode())))
    assert len(index)==65
    for record in index:
        name=record['patch_filename']
        assert re.fullmatch(r'O_CASE_[0-9]{5}\.patch',name)
        content=tar.extractfile(name).read()
        assert content.startswith(b'diff --git ')
        cid=int(record['case_id'].split('_')[1])
        (patches/('CASE_%05d.patch'%cid)).write_bytes(content)
        rows.append({'case_id':cid,'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),'status':record['status'],'changed_files':record['changed_files']})
    assert len({x['case_id'] for x in rows})==65
out={'status':'VERIFIED','archive_sha256':digest,'cases':65,'patches':sorted(rows,key=lambda r:r['case_id'])}
(dest/'TRANSFER_MANIFEST.json').write_text(json.dumps(out,indent=2)+'\n')
print('VERIFIED_SECOND_65',digest,'output',dest)
PY