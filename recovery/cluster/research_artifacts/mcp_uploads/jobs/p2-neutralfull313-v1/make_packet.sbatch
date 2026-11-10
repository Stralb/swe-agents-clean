#!/bin/bash
#SBATCH --job-name=p2fullcontext
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:25:00
set -euo pipefail
python3 - <<'PY'
import hashlib,io,json,os,pathlib,re,stat,tarfile,time,urllib.request,zipfile
from pathlib import Path
H=Path.home()
root=H/'research_artifacts/prevention_pilot_phase2'
job=os.environ['SLURM_JOB_ID']
out=root/('neutral_full_context_job'+job)
out.mkdir(exist_ok=False)
source=root/'case_screen_issue_recovery_v1_job69671/RESEARCHER_CORPUS_ISSUES_24.json'
records=json.loads(source.read_text())['records']
matches=[r for r in records if r.get('source_index')==2 and r.get('queue_rank')==16 and r.get('case_id')==313 and r.get('case_found')]
assert len(matches)==1, 'No unique frozen candidate'
r=matches[0]
assert r['repository']=='gsd-build/gsd-2'
assert r['root_id']=='CROOT-00313-01'
assert r['issue_number']==2660 and r['pr_number']==3090
assert r['issue_number_matches_frozen'] and r['pr_number_matches_frozen'] and r['base_matches_live_pr']
assert r['pr_base_sha']=='fe0e218954d5e42d2045192f8b8234c0cd56b8c6'
assert r['issue_created_at']=='2026-03-26T13:54:45Z'
assert r['pr_created_at']=='2026-03-29T05:34:15Z'
assert r['issue_updated_at']=='2026-03-30T20:37:11Z'
assert r['body_temporal_verdict']=='POST_PR_EDIT_POSSIBLE'
assert r['issue_title'].startswith('gsd_complete_milestone fails with malformed JSON')
assert r['issue_body'] and r['issue_body_sha256']=='59fd221ade40f1098dedf0b5ff2e7993e9c42a076adfb62209e84cc78d76ec44'
assert hashlib.sha256(r['issue_body'].encode('utf8')).hexdigest()==r['issue_body_sha256']
sha=r['pr_base_sha']
expected_tar_sha='10485a31a4a07e542fc6d0b5e390156992573980fca72363f396a1604fa72479'
url='https://codeload.github.com/gsd-build/gsd-2/tar.gz/'+sha
archive=None
for attempt in range(3):
 try:
  request=urllib.request.Request(url,headers={'User-Agent':'Wits-Phase2-Full-Uncurated-Source-20261017'})
  with urllib.request.urlopen(request,timeout=180) as response:
   archive=response.read(90_000_001)
  if len(archive)>90_000_000:raise RuntimeError('Download cap exceeded')
  assert hashlib.sha256(archive).hexdigest()==expected_tar_sha,'Exact archive SHA check failed'
  break
 except Exception as ex:
  if attempt==2:raise
  time.sleep(5)
assert archive
blob=io.BytesIO(archive)
full_names=set()
full_entries=[]
file_count=0
symlink_count=0
file_bytes=0
with tarfile.open(fileobj=blob,mode='r:gz') as tf:
 for m in tf.getmembers():
  parts=pathlib.PurePosixPath(m.name).parts
  if len(parts)<2:continue
  rel='/'.join(parts[1:])
  p=pathlib.PurePosixPath(rel)
  assert rel and not p.is_absolute() and '..' not in p.parts and chr(92) not in rel,'Unsafe member'
  if m.isdir():continue
  if not (m.isfile() or m.issym()):raise RuntimeError('Unsupported source archive member: '+m.name)
  assert rel not in full_names,'Duplicate archive path '+rel
  full_names.add(rel)
  if m.isfile():
   assert m.size<30_000_000,'Large archive member '+rel
   file_count+=1;file_bytes+=m.size
   assert file_count<50000 and file_bytes<800_000_000
  else:
   symlink_count+=1
  full_entries.append((rel,m))
 assert file_count==2272,('Full source file count unexpectedly changed',file_count)
 assert 'src/resources/extensions/gsd/prompts/complete-milestone.md' in full_names
 assert 'packages/pi-ai/src/utils/repair-tool-json.ts' not in full_names,'Historical PR file unexpectedly exists at base'
 zip_path=out/'gsd_issue2660_preimplementation.zip'
 issue=r['issue_title']+'\n\n'+r['issue_body'].rstrip('\n')+'\n'
 manifest_entries=[]
 with zipfile.ZipFile(zip_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  def info(path,mode):
   i=zipfile.ZipInfo(path,date_time=(1980,1,1,0,0,0))
   i.create_system=3
   i.compress_type=zipfile.ZIP_DEFLATED
   i.external_attr=(mode<<16)
   return i
  z.writestr(info('ISSUE.md',stat.S_IFREG|0o644),issue.encode('utf-8'))
  for rel,m in sorted(full_entries,key=lambda t:t[0]):
   dst='REPO/'+rel
   if m.isfile():
    handle=tf.extractfile(m)
    assert handle is not None
    data=handle.read()
    assert len(data)==m.size
    z.writestr(info(dst,stat.S_IFREG|(m.mode&0o777)),data)
    manifest_entries.append({'path':rel,'kind':'file','size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
   else:
    target=m.linkname.encode('utf-8')
    z.writestr(info(dst,stat.S_IFLNK|0o777),target)
    manifest_entries.append({'path':rel,'kind':'symlink','link_target':m.linkname,'sha256':hashlib.sha256(target).hexdigest()})
# Independent exhaustive ZIP validation (not just a sample).
with zipfile.ZipFile(zip_path,'r') as z:
 files=z.namelist()
 assert len(files)==len(manifest_entries)+1
 assert files.count('ISSUE.md')==1
 assert all(f=='ISSUE.md' or f.startswith('REPO/') for f in files)
 assert z.read('ISSUE.md')==issue.encode('utf-8')
 for e in manifest_entries:
  data=z.read('REPO/'+e['path'])
  assert hashlib.sha256(data).hexdigest()==e['sha256']
  if e['kind']=='file':assert len(data)==e['size']
metadata={
 'protocol':'PHASE2_RESET_FULL_UNCURATED_SOURCE_v1',
 'case_id':313,'root_id':'CROOT-00313-01',
 'source':'frozen corpus snapshot, source_index 2',
 'base_commit_sha':sha,
 'historical_pr_description_supplied':False,
 'historical_patch_supplied':False,
 'historical_scanner_warning_supplied':False,
 'curated_excerpts_supplied':False,
 'ranked_repo_map_supplied':False,
 'entire_upstream_commit_file_tree_included':True,
 'git_history_or_untracked_files_supplied':False,
 'issue_body_as_of_prePR':'NOT_VERIFIED__EXPLORATORY_ONLY',
 'issue_created_at':r['issue_created_at'],
 'issue_updated_at':r['issue_updated_at'],
 'pr_created_at':r['pr_created_at'],
 'issue_body_sha256':r['issue_body_sha256'],
 'issue_packet_sha256':hashlib.sha256(issue.encode('utf8')).hexdigest(),
 'source_archive_url':url,
 'source_archive_sha256':hashlib.sha256(archive).hexdigest(),
 'source_archive_bytes':len(archive),
 'tracked_regular_file_count':file_count,
 'tracked_symlink_count':symlink_count,
 'source_bytes_total':file_bytes,
 'generation_zip':zip_path.name,
 'generation_zip_sha256':hashlib.sha256(zip_path.read_bytes()).hexdigest(),
 'generation_zip_bytes':zip_path.stat().st_size,
 'zip_entries_verified':len(manifest_entries)+1,
 'member_sha256_list':'RESEARCHER_FILE_HASHES.json',
 'warning':'RESEARCHER ONLY; do not give manifest, scanner info or historical PR to generation chat',
}
(out/'RESEARCHER_MANIFEST.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf8')
(out/'RESEARCHER_FILE_HASHES.json').write_text(json.dumps(manifest_entries,indent=2)+'\n',encoding='utf8')
print('FULL_CONTEXT_READY',json.dumps({k:metadata[k] for k in ['generation_zip','generation_zip_sha256','generation_zip_bytes','tracked_regular_file_count','tracked_symlink_count','zip_entries_verified','issue_body_as_of_prePR']}),flush=True)
print('OUTPUT_DIRECTORY',out,flush=True)
PY
