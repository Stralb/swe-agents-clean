#!/bin/bash
#SBATCH --job-name=screen65_details
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
python3 - <<'PY'
from pathlib import Path
import os,json,re,zipfile
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
stage=root/'screen65_static_analysis_job70606'
results=root/'screen65_codeql_job70675'
out=root/('screen65_triage_details_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
ids=[3581,8152,22223,16633,20094,32759,3429,12344,31207]
meta={int(x['case_id']):x for x in json.loads((root/'remaining65_metadata_job70235/PRIVATE_CASE_METADATA_65.json').read_text())}
for cid in ids:
 s=json.loads((results/('CASE_%05d'%cid)/'RESULT.json').read_text())
 m=meta[cid]
 source=root/'remaining65_archives_oct17_v1'/('CASE_%05d.zip'%cid)
 if not source.exists():source=root/'remaining65_targeted14_v1'/('CASE_%05d.zip'%cid)
 with zipfile.ZipFile(source) as z:issue=z.read('ISSUE.md').decode('utf8',errors='replace')
 patch=(stage/'patches'/('CASE_%05d.patch'%cid)).read_text(errors='replace')
 files={}
 current=None
 for line in patch.splitlines():
  mm=re.match(r'^diff --git a/(.*?) b/(.*)$',line)
  if mm:
   current=mm.group(2);files[current]=[]
  if current is not None:files[current].append(line)
 changed={k:'\n'.join(v) for k,v in files.items()}
 findings=s.get('findings',{}).get('new_strong_findings',[])
 obj={'case':cid,'repo':m['repository'],'issue':issue[:2400],
  'historical_rule':m['target_rule'],'historical_path':m['changed_file'],
  'source_type':s['source_type'],'claim':s['claimed_status'],'before':s['findings']['before_total'],
  'after':s['findings']['after_total'],'new_strong':s['findings']['new_strong_count'],
  'new_weak':s['findings']['new_weak_count'],'findings':findings,
  'modified_paths':list(changed),'patch_lines':len(patch.splitlines()),
  'relevant_patch_excerpts':{v['path']:changed.get(v['path'],'')[:5000] for v in findings},
  'patch_head':patch[:1500],'issue_before_pr':m['issue_before_pr'],
  'issue_timestamp_verified':m['prepr_issue_text_temporally_supported']}
 (out/('CASE_%05d.json'%cid)).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
 print('TRIAGE',cid,obj['repo'],'patchfiles',len(changed),'new',obj['new_strong'],flush=True)
PY