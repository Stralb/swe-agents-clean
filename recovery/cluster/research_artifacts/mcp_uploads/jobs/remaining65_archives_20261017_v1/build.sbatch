#!/bin/bash
#SBATCH --job-name=rem65_sources
#SBATCH --partition=batch
#SBATCH --array=0-61%8
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:25:00
export PYTHONUNBUFFERED=1
python3 - <<'PY'
import os,json,pathlib,tempfile,zipfile,tarfile,urllib.request,hashlib,time
from urllib.parse import quote
root=pathlib.Path.home()/'research_artifacts/prevention_pilot_phase2'
meta=json.loads((root/'remaining65_metadata_job70235/PRIVATE_CASE_METADATA_65.json').read_text())
eligible=[m for m in meta if m['candidate_packet_eligible']]
assert len(eligible)==62
i=int(os.environ['SLURM_ARRAY_TASK_ID'])
m=eligible[i];cid=m['case_id'];source=m['repository'];base=m['pr_base_sha']
out=root/'remaining65_archives_oct17_v1'
out.mkdir(exist_ok=True)
case_out=out/('CASE_%05d.zip'%cid)
status=out/('CASE_%05d.status.json'%cid)
record={'case':cid,'repo':source,'base_sha':base,'queue_rank':m['queue_rank'],'issue_number':m['issue_number'],
        'pr_number':m['pr_number'],'issue_created_before_pr':m['issue_before_pr'],
        'prepr_issue_text_temporally_supported':m['prepr_issue_text_temporally_supported'],'state':'START'}
def save():status.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
try:
 assert source.count('/')==1 and len(base)>=12
 tmp=pathlib.Path(tempfile.mkdtemp(prefix='casearchive_%d_'%cid,dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 archive=tmp/'src.tar.gz'
 url='https://codeload.github.com/'+quote(source,safe='/')+'/tar.gz/'+quote(base,safe='')
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Research-Repository-Replay/1.0'})
   with urllib.request.urlopen(req,timeout=170) as resp,archive.open('wb') as f:
    seen=0
    while True:
     blob=resp.read(1024*1024)
     if not blob:break
     seen+=len(blob)
     if seen>105*1024*1024:raise ValueError('SOURCE_GZIP_OVER_105MB')
     f.write(blob)
   break
  except Exception:
   archive.unlink(missing_ok=True)
   if attempt==2:raise
   time.sleep(3*(attempt+1))
 record['source_gzip_bytes']=archive.stat().st_size
 issue=(m['issue_title'].strip()+'\n\n'+m['issue_body'].strip()+'\n').encode('utf8')
 assert len(issue)<400000
 records=0;size=0
 tempzip=tmp/'case.zip'
 with zipfile.ZipFile(tempzip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5,allowZip64=True) as z:
  z.writestr('ISSUE.md',issue)
  with tarfile.open(archive,'r:gz') as t:
   for member in t:
    parts=pathlib.PurePosixPath(member.name).parts
    if len(parts)<2:continue
    relative=pathlib.PurePosixPath(*parts[1:])
    if relative.is_absolute() or '..' in relative.parts or '\\' in str(relative):raise ValueError('UNSAFE_ARCHIVE_PATH')
    dest='REPO/'+str(relative)
    if member.isdir():continue
    if member.isfile():
     records+=1
     size+=member.size
     if records>25000 or size>420*1024*1024 or member.size>42*1024*1024:raise ValueError('REPO_EXCEEDS_SCREENING_LIMITS')
     with t.extractfile(member) as f:z.writestr(dest,f.read())
    elif member.issym():
     link=pathlib.PurePosixPath(member.linkname)
     if link.is_absolute() or '..' in link.parts:continue
     info=zipfile.ZipInfo(dest)
     info.create_system=3
     info.external_attr=0o120777<<16
     z.writestr(info,member.linkname)
    elif member.islnk():continue
    else:continue
 if tempzip.stat().st_size>72*1024*1024:raise ValueError('PACKED_ZIP_OVER_72MB')
 with zipfile.ZipFile(tempzip) as verify:
  assert verify.testzip() is None and len(verify.namelist())>=4
 assert not case_out.exists()
 tempzip.replace(case_out)
 record.update({'state':'READY','archive_name':case_out.name,'archive_bytes':case_out.stat().st_size,
                'archive_sha256':hashlib.sha256(case_out.read_bytes()).hexdigest(),
                'source_file_count':records,'source_uncompressed_bytes':size,'issue_bytes':len(issue)})
except BaseException as e:
 record.update({'state':'FAILED','error':str(e)[:500]})
 case_out.unlink(missing_ok=True)
save()
print(cid,record['state'],record.get('archive_bytes',0),record.get('error',''),flush=True)
PY
