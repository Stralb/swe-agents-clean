#!/bin/bash
#SBATCH --job-name=arno7_archiveaudit
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --mem=3G
python3 - <<'PY'
from pathlib import Path
import zipfile,json,hashlib,collections
R=Path.home()/'research_artifacts'
src=R/'prevention_pilot_phase2/FINAL_SEVEN_CASE_RESEARCH_HANDOFF_20261020/COMPLETE_7_CASE_RESEARCH_HANDOFF_20261020.zip'
out=R/'mcp_uploads/jobs/arno_seven_final_archive_audit_v6_20261028'
out.mkdir(parents=True,exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
result={'source_path':str(src.relative_to(R)),'source_bytes':src.stat().st_size,
 'source_sha256':sha(src.read_bytes()),'members':[], 'status':'STARTED'}
with zipfile.ZipFile(src) as z:
 result['crc_bad_member']=z.testzip()
 if result['crc_bad_member'] is not None:raise RuntimeError('CRC failed '+result['crc_bad_member'])
 for i in z.infolist():
  if i.is_dir():continue
  name=i.filename
  if name.startswith('/') or '..' in Path(name).parts:raise RuntimeError('Unsafe path '+name)
  item={'name':name,'uncompressed_bytes':i.file_size,'archive_crc':hex(i.CRC)}
  if i.file_size<=1500000 and (name.endswith(('.json','.md','.csv','.sha256','.txt','.patch','.sarif'))):
   b=z.read(name)
   item['sha256']=sha(b)
   if name.endswith(('.json','.md','.csv','.txt','.sha256')):
    item['first_240']=b[:240].decode('utf-8','replace')
  result['members'].append(item)
result['status']='COMPLETE'
result['num_members']=len(result['members'])
result['extension_counts']=dict(collections.Counter(Path(x['name']).suffix for x in result['members']))
(out/'ARCHIVE_MANIFEST.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':result['status'],'source_sha256':result['source_sha256'],'members':result['num_members'],
 'names':[v['name'] for v in result['members']][:75],'extension_counts':result['extension_counts']},indent=2),flush=True)
PY