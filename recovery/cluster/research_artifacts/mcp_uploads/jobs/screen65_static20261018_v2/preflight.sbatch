#!/bin/bash
#SBATCH --job-name=screen65_apply
#SBATCH --partition=batch
#SBATCH --array=0-64%10
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:20:00
python3 - <<'PY'
from pathlib import Path,PurePosixPath
import os,json,zipfile,subprocess,tempfile,hashlib,re
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
stage=root/'screen65_static_analysis_job70606'
cases=json.loads((stage/'TRANSFER_MANIFEST.json').read_text())['patches']
i=int(os.environ['SLURM_ARRAY_TASK_ID'])
c=cases[i];cid=c['case_id']
out=root/('screen65_preflight_job'+os.environ['SLURM_ARRAY_JOB_ID'])
out.mkdir(exist_ok=True)
report={'case_id':cid,'variant':'RECOVERY_PASS','claimed_status':c['claimed_status'],'stage':'STARTED'}
try:
 patch=stage/'patches'/('CASE_%05d.patch'%cid)
 assert hashlib.sha256(patch.read_bytes()).hexdigest()==c['sha256']
 full=root/'remaining65_archives_oct17_v1'/('CASE_%05d.zip'%cid)
 source=full if full.exists() else root/'remaining65_targeted14_v1'/('CASE_%05d.zip'%cid)
 assert source.exists(),('MISSING_SOURCE',cid)
 report['source_type']='FULL_SNAPSHOT' if source==full else 'FILTERED_SNAPSHOT'
 report['archive_bytes']=source.stat().st_size
 work=Path(tempfile.mkdtemp(prefix='case%05d_'%cid,dir=os.environ.get('SLURM_TMPDIR') or '/tmp'))
 count=0;total=0
 with zipfile.ZipFile(source) as z:
  for f in z.infolist():
   if not f.filename.startswith('REPO/') or f.is_dir():continue
   rel=PurePosixPath(f.filename)
   if rel.is_absolute() or '..' in rel.parts:raise ValueError('BAD_ZIP_PATH')
   dest=work/f.filename
   count+=1;total+=f.file_size
   if count>80000 or total>900*1024*1024:raise ValueError('SOURCE_TOO_LARGE')
   dest.parent.mkdir(parents=True,exist_ok=True)
   dest.write_bytes(z.read(f))
 report['source_files']=count
 report['uncompressed_bytes']=total
 rep=work/'REPO'
 p=subprocess.run(['git','apply','--check',str(patch)],cwd=rep,capture_output=True,text=True,timeout=150)
 report['git_apply_check_rc']=p.returncode
 report['error']=p.stderr[-5000:] if p.returncode else ''
 report['stage']='APPLIES' if p.returncode==0 else 'DOES_NOT_APPLY'
except BaseException as e:
 report['stage']='ERROR'
 report['error']=repr(e)[:1800]
(out/('CASE_%05d.json'%cid)).write_text(json.dumps(report,indent=2)+'\n')
print('CHECK',cid,report['stage'],report.get('error','')[:150],flush=True)
PY