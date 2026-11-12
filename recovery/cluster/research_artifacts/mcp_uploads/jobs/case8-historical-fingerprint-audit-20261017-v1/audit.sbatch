#!/bin/bash
#SBATCH --job-name=case8hist
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/case8hist_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/case8hist_%j.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import collections,difflib,hashlib,io,json,os,pathlib,re,shutil,subprocess,tarfile,urllib.request
from pathlib import Path
root=Path.home()/'research_artifacts'/'prevention_pilot_phase2'
base_sha='639150316e6f14cdc78e7dba8c6263504895b2e1'
head_sha='070e05998c1e5e679094259d609f9f8e5c64995d'
job=os.environ['SLURM_JOB_ID']
out=root/('case8_historical_fingerprint_audit_job'+job)
out.mkdir(parents=True,exist_ok=False)
tmp=Path(os.environ.get('SLURM_TMPDIR') or '/tmp')/('case8_historical_audit_'+job)
tmp.mkdir(parents=True,exist_ok=False)
codeql=Path.home()/'tools'/'codeql'/'codeql'
ql=Path.home()/'.codeql'/'packages'/'codeql'/'javascript-queries'/'2.3.11'/'Security'/'CWE-377'/'InsecureTemporaryFile.ql'
rule='js/insecure-temporary-file'
assert codeql.exists() and ql.exists()
arms={
 'O_R1':root/'pilot3_scan_fix_job69698'/'rank_8',
 'O_R2':root/'pilot3_scan_r2_job69745'/'rank_8',
 'O_PLUS_P':root/'pilot3_arms_scan_OP_job69794'/'rank_8',
 'O_PLUS_W':root/'pilot3_arms_scan_OW_job69811'/'rank_8'
}
paths={}
for name,folder in arms.items():
 assert (folder/'RESULT.json').exists(),(name,folder)
 paths[name]=json.loads((folder/'RESULT.json').read_text())
def load_sarif(p):
 data=json.loads(p.read_text())
 return [x for run in data.get('runs',[]) for x in run.get('results',[]) if x.get('ruleId')==rule]
def loc(a):
 return [(e.get('physicalLocation',{}).get('artifactLocation',{}).get('uri',''),e.get('physicalLocation',{}).get('region',{}).get('startLine')) for e in a.get('locations',[])]
def fingerprint(a):
 return a.get('partialFingerprints',{})
def closest(results,target):
 return [r for r in results if any('src/cli/skill-source.ts' in f and line==196 for f,line in loc(r))]
original=load_sarif(arms['O_R1']/'base.sarif')
original_w=closest(original,'historical')
assert original_w,'Historical primary was not present in frozen base!'
target_fp=fingerprint(original_w[0])
print('TARGET_BASE_FOUND',len(original_w),'fingerprint',target_fp,flush=True)
summary={'case_id':21942,'pr_number':388,'historical_rule':rule,'historical_finding_primary':'src/cli/skill-source.ts:196','historical_base_sha':base_sha,'historical_head_sha':head_sha,'original_pre_pr_target':{'count':len(original_w),'fingerprints':[fingerprint(x) for x in original_w]},'modern_arms':{}}
for name,folder in arms.items():
 R=paths[name]
 before=load_sarif(folder/'base.sarif')
 after=load_sarif(folder/'patched.sarif')
 h0=closest(before,'historical')
 h1=closest(after,'historical')
 changed=(folder/'changed_diff.log').read_text()
 edited_files=[line.split(' b/',1)[1] for line in changed.splitlines() if line.startswith('diff --git a/') and ' b/' in line]
 added=R.get('added_details',[])
 arm={
  'original_historical_warning_present':bool(h0),
  'original_historical_warning_primary_fingerprints':[fingerprint(x) for x in h0],
  'historical_warning_after_patch_present':bool(h1),
  'historical_warning_after_patch_primary_fingerprints':[fingerprint(x) for x in h1],
  'exact_original_historical_primary_fingerprint_present_after':any(fingerprint(x)==target_fp for x in h1),
  'patch_edited_historical_warning_file':'src/cli/skill-source.ts' in edited_files,
  'modified_paths':edited_files,
  'fresh_added_warning_locations':[[list(t) for t in loc(x)] for x in after if fingerprint(x) in [a.get('fingerprints') for a in added]],
  'target_rule_new_findings_count':R.get('new_target_alerts'),
  'all_new_findings_in_tests':all(all('__tests__/' in str(l.get('file','')) for l in a.get('locations',[])) for a in added)
 }
 summary['modern_arms'][name]=arm
 print('ARM',name,json.dumps(arm),flush=True)
def fetch(sha):
 req=urllib.request.Request('https://codeload.github.com/Soul-Brews-Studio/arra-oracle-skills-cli/tar.gz/'+sha,headers={'User-Agent':'Wits-Research-Historical-Audit'})
 with urllib.request.urlopen(req,timeout=150) as h:
  blob=h.read(80000001)
 assert len(blob)<80000001
 directory=tmp/sha
 directory.mkdir()
 with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as archive:
  for m in archive:
   parts=pathlib.PurePosixPath(m.name).parts
   if len(parts)<2 or '..' in parts:continue
   dest=directory.joinpath(*parts[1:])
   if m.isdir():dest.mkdir(parents=True,exist_ok=True)
   elif m.isfile():
    dest.parent.mkdir(parents=True,exist_ok=True)
    with archive.extractfile(m) as inp,dest.open('xb') as o:shutil.copyfileobj(inp,o)
 return directory,hashlib.sha256(blob).hexdigest()
base_source,base_download_sha=fetch(base_sha)
head_source,head_download_sha=fetch(head_sha)
summary['archive_sha256']={'base':base_download_sha,'head':head_download_sha}
p='src/cli/skill-source.ts'
b=(base_source/p).read_text(errors='replace').splitlines()
h=(head_source/p).read_text(errors='replace').splitlines()
summary['historical_file_unchanged_in_pr']=(b==h)
summary['historical_source_line_196_pre_pr']=b[195] if len(b)>=196 else None
summary['historical_source_line_196_head']=h[195] if len(h)>=196 else None
(out/'historical_skill_source.diff').write_text('\n'.join(difflib.unified_diff(b,h,fromfile='base/'+p,tofile='head/'+p))+'\n')
print('HISTORICAL_SOURCE_FILE_UNCHANGED',b==h,flush=True)
if (base_source/'src/cli/installer.ts').exists() and (head_source/'src/cli/installer.ts').exists():
 x=(base_source/'src/cli/installer.ts').read_text(errors='replace').splitlines()
 y=(head_source/'src/cli/installer.ts').read_text(errors='replace').splitlines()
 (out/'historical_installer.diff').write_text('\n'.join(difflib.unified_diff(x,y,fromfile='base/src/cli/installer.ts',tofile='head/src/cli/installer.ts'))+'\n')
def run(command,label,timeout):
 print('COMMAND',label,' '.join(map(str,command)),flush=True)
 proc=subprocess.run([str(x) for x in command],cwd=head_source,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',timeout=timeout)
 (out/(label+'.log')).write_text(proc.stdout)
 print('EXIT',label,proc.returncode,flush=True)
 if proc.returncode:raise RuntimeError(label+' failed '+proc.stdout[-900:])
db=tmp/'head_database'
run([codeql,'database','create',db,'--language=javascript-typescript','--source-root='+str(head_source),'--build-mode=none','--threads=4','--ram=15000'],'head_database_create',2400)
sarif=out/'historical_head.sarif'
run([codeql,'database','analyze',db,ql,'--format=sarif-latest','--output='+str(sarif),'--threads=4','--ram=15000'],'head_rule_analyze',1600)
hr=load_sarif(sarif)
hh=closest(hr,'hist')
summary['historical_head_target']={'count':len(hh),'fingerprints':[fingerprint(x) for x in hh],'same_fingerprint_as_pre_pr':any(fingerprint(x)==target_fp for x in hh)}
summary['historical_head_total_matching_rule']=len(hr)
before={json.dumps(fingerprint(x),sort_keys=True) for x in original}
hist_added=[x for x in hr if json.dumps(fingerprint(x),sort_keys=True) not in before]
summary['historical_pr_new_rule_alerts']=[{'locations':loc(x),'fingerprint':fingerprint(x)} for x in hist_added]
summary['historical_pr_new_rule_alerts_total']=len(hist_added)
for which,arr in [('pre_pr_base',original_w),('historical_head',hh)]:
 (out/(which+'_target_full_sarif.json')).write_text(json.dumps(arr,indent=2)+'\n')
(out/'AUDIT.json').write_text(json.dumps(summary,indent=2)+'\n')
print('HISTORICAL_HEAD_PRIMARY_COUNT',len(hh),'MATCHES_OLD',summary['historical_head_target']['same_fingerprint_as_pre_pr'],'NEW_WARNINGS',len(hist_added),flush=True)
print('AUDIT_COMPLETE',out,flush=True)
PY
