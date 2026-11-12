#!/bin/bash
#SBATCH --job-name=next5blinds
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:30:00
python3 - <<'PY'
from pathlib import Path,PurePosixPath
from urllib.parse import quote
import json,os,hashlib,zipfile,tarfile,urllib.request,time,traceback
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
inp=root/'case_screen_issue_recovery_v1_job69671/RESEARCHER_CORPUS_ISSUES_24.json'
output=root/('next_wave5_blind_discovery_job'+os.environ['SLURM_JOB_ID'])
output.mkdir(exist_ok=False)
wanted=[13922,9992,10779,3340,313]
meta=json.loads(inp.read_text())
def traverse(x):
 if isinstance(x,dict):
  if x.get('case_id') in wanted and x.get('case_found') is True and 'pr_base_sha' in x:
   yield x
  for v in x.values():yield from traverse(v)
 elif isinstance(x,list):
  for y in x:yield from traverse(y)
records=list(traverse(meta))
sha=lambda b:hashlib.sha256(b).hexdigest()
manifest=[]
for order,ident in enumerate(wanted,1):
 found=[r for r in records if r['case_id']==ident and r['source_index']==1]
 if not found:found=[r for r in records if r['case_id']==ident]
 status={'case':ident,'order':order}
 try:
  assert found,'original source dossier not found'
  r=found[0]
  assert r.get('issue_created_before_pr') is True
  assert r['pr_base_sha'] and r['repository'] and r['issue_body']
  packet=output/('CASE_%02d_%05d.zip'%(order,ident))
  source=output/('source_%d.tar.gz'%ident)
  repo=r['repository']
  url='https://codeload.github.com/'+quote(repo,safe='/')+'/tar.gz/'+r['pr_base_sha']
  for attempt in range(3):
   try:
    req=urllib.request.Request(url,headers={'User-Agent':'Wits-Research-Exploratory-Case-Screen'})
    with urllib.request.urlopen(req,timeout=150) as f,source.open('xb') as o:
     total=0
     while True:
      part=f.read(1048576)
      if not part:break
      total+=len(part)
      if total>150*1048576:raise ValueError('Source archive exceeds 150 MiB')
      o.write(part)
    break
   except Exception:
    source.unlink(missing_ok=True)
    if attempt==2:raise
    time.sleep(4)
  issue=r.get('issue_title','').strip()+'\n\n'+r['issue_body'].strip()+'\n'
  counts={'files':0,'size':0}
  with tarfile.open(source,'r:gz') as t,zipfile.ZipFile(packet,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=5,allowZip64=True) as z:
   z.writestr('ISSUE.md',issue)
   for f in t:
    seg=PurePosixPath(f.name).parts
    if len(seg)<2:continue
    rel=PurePosixPath(*seg[1:])
    if '..' in rel.parts or rel.is_absolute() or '\\' in str(rel):raise ValueError('Unsafe archived path')
    new='REPO/'+str(rel)
    if f.isdir():continue
    if f.isfile():
     counts['files']+=1
     counts['size']+=f.size
     if counts['files']>80000 or counts['size']>850*1048576 or f.size>160*1048576:
      raise ValueError('Repo exceeds file, archive or individual file limit')
     with t.extractfile(f) as fd:z.writestr(new,fd.read())
    elif f.issym():
     link=PurePosixPath(f.linkname)
     if link.is_absolute() or '..' in link.parts:continue
     i=zipfile.ZipInfo(new);i.create_system=3;i.external_attr=0o120777<<16
     z.writestr(i,f.linkname)
    elif f.islnk():continue
    else:raise ValueError('Unsupported archived entry')
  with zipfile.ZipFile(packet) as z:assert z.testzip() is None and 'ISSUE.md' in z.namelist() and len(z.namelist())>7
  status.update({'status':'READY','name':packet.name,'repo':repo,'issue_number':r['issue_number'],'pr_number':r['pr_number'],'base_sha':r['pr_base_sha'],'source_archive_sha256':sha(source.read_bytes()),'issue_body_sha256':sha(issue.encode()),'issue_created':r['issue_created_at'],'issue_updated':r['issue_updated_at'],'pr_created':r['pr_created_at'],'chronology_status':r['body_temporal_verdict'],'packet_sha256':sha(packet.read_bytes()),'packet_bytes':packet.stat().st_size,'files':counts['files'],'uncompressed_bytes':counts['size']})
  source.unlink(missing_ok=True)
 except BaseException as e:
  status.update({'status':'ERROR','reason':repr(e)[:550]})
  (output/('CASE_%02d_%05d.zip'%(order,ident))).unlink(missing_ok=True)
 manifest.append(status)
 print('CASE',ident,status['status'],status.get('packet_bytes'),status.get('reason',''),flush=True)
 (output/'RESEARCHER_ONLY_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
prompt='''Implement the issue in ISSUE.md using only the supplied REPO/ frozen source. Fix the issue and add suitable tests. Work independently without searching online, viewing PRs, prior agent implementations, security warnings, or any other candidate in this batch. Return exactly one complete downloadable Git unified patch relative to REPO/ including all new and changed files.
'''
guide='''NEXT WAVE: untreated exploratory screening only.
First extract this outer ZIP. For each CASE_*.zip use a separate FRESH Temporary Chat, with the same model and thinking effort, attaching only that CASE ZIP and the exact shared prompt in GENERATION_PROMPT.txt.
Save a patch as O_CASE_<id>.patch and upload returned patches to the research chat.
Cases are preselected from the frozen metadata-provisional root queue, and have not passed historical CodeQL replay or pre-PR issue-body identity checks.
Never feed historical PR/code/CodeQL hints into generation chats. Do not upload this outer ZIP. If the candidate issue cannot be solved, record that instead of inventing a patch.
'''
outer=output/'NEXT_WAVE_BLIND_FIVE_ONE_ZIP.zip'
with zipfile.ZipFile(outer,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
 for m in manifest:
  if m['status']=='READY':
   packet=output/m['name'];z.write(packet,m['name'],compress_type=zipfile.ZIP_STORED)
 z.writestr('README_FIRST.txt',guide)
 z.writestr('GENERATION_PROMPT.txt',prompt)
with zipfile.ZipFile(outer) as z:assert z.testzip() is None
summary={'status':'READY','bundle_path':str(outer),'bytes':outer.stat().st_size,'sha256':sha(outer.read_bytes()),'ready':[m['case'] for m in manifest if m['status']=='READY'],'failed':[m['case'] for m in manifest if m['status']!='READY']}
(output/'BUNDLE_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print('BUNDLE',json.dumps(summary),flush=True)
PY
