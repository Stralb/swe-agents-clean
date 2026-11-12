#!/bin/bash
#SBATCH --job-name=arno_find_final_evidence
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=3G
python3 - <<'PY'
import os,zipfile,tarfile,json,datetime,collections
from pathlib import Path
home=Path.home()
root=home/'research_artifacts'
out=root/'mcp_uploads/jobs/arno_find_final_new70_D7_20261028'
out.mkdir(parents=True,exist_ok=True)
bases=[
 (root,8),
 (home/'new/malicious-issue-miner-rate-smart/data',8),
 (home/'new/malicious-issue-miner-rate-smart',3),
 (home/'research',6),
 (home/'Documents',5),
 (home/'Downloads',5)
]
tokens=['new70','phase6','step1','step2','step3','canonical','mechanism','d7','adjudicat','final_root','coder_b','coder_a','root_census','attribution','complete_root','root_decision','risk_assessment','manual_review']
archive_terms=['new70','step1','step2','step3','phase6','d7','root_census','adjudic','final_root']
skip={'node_modules','.git','.venv','venv','__pycache__','checkouts','repos','git','gh_cache','npm','node','site-packages','dist','build','target','.cache','base_repo','worktrees','run_outputs'}
found=[]; directories=[]; archive_names=[];seen=set(); visited_files=0; visited_dirs=0
for base,maxdepth in bases:
 if not base.is_dir():continue
 for here,ds,fs in os.walk(base):
  path=Path(here)
  d=len(path.relative_to(base).parts)
  ds[:]=[x for x in ds if x not in skip and d<maxdepth]
  visited_dirs+=1
  lowdir=path.name.lower()
  if any(t in lowdir for t in ('new70','phase6','d7','adjudic','manual-review','root_census')):
   directories.append(str(path))
  for name in fs:
   visited_files+=1
   low=name.lower()
   f=path/name
   if any(t in low for t in tokens):
    if str(f) not in seen:
     found.append({'path':str(f),'bytes':f.stat().st_size});seen.add(str(f))
   if low.endswith(('.zip','.tar.gz','.tgz')) and f.stat().st_size<60_000_000 and ('new70' in low or 'phase' in low or 'root' in low or 'step' in low or 'd_' in low or 'arno' in low):
    try:
     if low.endswith('.zip'):
      with zipfile.ZipFile(f) as a:
       names=a.namelist()
     else:
      with tarfile.open(f,'r:gz') as a:
       names=a.getnames()
     matched=[n for n in names if any(t in n.lower() for t in archive_terms)]
     if matched:
      archive_names.append({'archive':str(f),'size':f.stat().st_size,'members_total':len(names),'matching_member_names':matched[:120]})
    except Exception as ex:archive_names.append({'archive':str(f),'error':str(ex)[:90]})
 report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'visited_files':visited_files,'visited_dirs':visited_dirs,'matched_files':len(found),'candidate_directories':len(directories),'archive_hits':len(archive_names),'files':sorted(found,key=lambda x:x['path']),'directories':sorted(set(directories)),'archive_members':archive_names}
 (out/'SOURCE_RECOVERY_INVENTORY.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 slim={'utc':report['utc'],'visited_files':visited_files,'matched_files':len(found),'archive_hits':len(archive_names),'top_candidates':[x for x in found if any(t in x['path'].lower() for t in ('final','new70','d7','adjudic'))][:160],'archive_hits_summary':[{'archive':a['archive'],'size':a.get('size'),'matched_members':len(a.get('matching_member_names',[])),'sample':a.get('matching_member_names',[])[:8]} for a in archive_names[:50]]}
 (out/'SOURCE_RECOVERY_SHORTLIST.json').write_text(json.dumps(slim,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'visited_files':visited_files,'matched_files':len(found),'archive_hits':len(archive_names),'output':str(out)},indent=2))
PY