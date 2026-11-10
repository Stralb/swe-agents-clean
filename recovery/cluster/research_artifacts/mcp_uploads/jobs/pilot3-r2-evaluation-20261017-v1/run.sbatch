#!/bin/bash
#SBATCH --job-name=p3r2evaluate
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_r2_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/pilot3_r2_%j.err
set -euo pipefail
export SLURM_ARRAY_TASK_ID=0
export SLURM_ARRAY_JOB_ID="$SLURM_JOB_ID"
python3 - <<'PY'

import pathlib,os,ast,base64,zlib,hashlib,re,subprocess,json,sys
ROOT=pathlib.Path.home()/'research_artifacts'/'prevention_pilot_phase2'
JOB=os.environ['SLURM_JOB_ID']
OUT=ROOT/('pilot3_r2_job'+JOB)
OUT.mkdir(exist_ok=False,parents=True)
EMBED='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'
blob=zlib.decompress(base64.b64decode(EMBED))
assert hashlib.sha256(blob).hexdigest()=='5990e260d07289bfa98593a735b0a8dd76db84e3e7c7f752e69d284bb892ed1e'
(OUT/'PILOT_08_R2.patch').write_bytes(blob)
old=ROOT/'pilot3_evaluate_3patches_20261017_v2_nodefix.sbatch'
oldfunc=ROOT/'pilot3_functional_v1.sbatch'
payload=repr({'8':EMBED})
scanner=old.read_text()
scanner,n=re.subn(r'(?m)^PATCHES=.*$',lambda m:'PATCHES='+payload,scanner)
assert n==1
scanner=scanner.replace('pilot3_scan_fix_job','pilot3_scan_r2_job')
scanner=scanner.replace('pilot3_scan_fix_%A_%a','pilot3_scan_r2_%A_%a')
scanner=scanner.replace('#SBATCH --array=0-2%2','#SBATCH --array=0')
function=oldfunc.read_text()
needle="line=next((line for line in old.splitlines() if line.startswith('PATCHES=')),None)"
assert needle in function
function=function.replace(needle,"line='PATCHES='+ "+repr(payload))
function=function.replace('pilot3_functional_job','pilot3_functional_r2_job')
function=function.replace('pilot3_functional_%A_%a','pilot3_functional_r2_%A_%a')
function=function.replace('#SBATCH --array=0-2%2','#SBATCH --array=0')
work=pathlib.Path(os.environ.get('SLURM_TMPDIR') or '/tmp')/('pilot3_r2_scripts_'+JOB)
work.mkdir(parents=True,exist_ok=False)
p1=work/'scan.sh';p1.write_text(scanner);p2=work/'functional.sh';p2.write_text(function)
for tag,path in [('scan',p1),('functional',p2)]:
 print('RUN',tag,flush=True)
 with (OUT/(tag+'.log')).open('x') as f:
  result=subprocess.run(['bash',str(path)],stdout=f,stderr=subprocess.STDOUT)
 print('DONE',tag,'exit',result.returncode,flush=True)
result={}
for tag,location in [('scan',ROOT/('pilot3_scan_r2_job'+JOB)/'rank_8'/'RESULT.json'),('functional',ROOT/('pilot3_functional_r2_job'+JOB)/'rank_8'/'RESULT.json')]:
 if location.exists():
  data=json.loads(location.read_text())
  result[tag]={k:data.get(k) for k in ('status','functionality','functional_correctness','base_alerts','patched_alerts','new_target_alerts','changed_line_attributed','target_reproduced','patch_sha256','reason')}
 else:result[tag]={'status':'NO_RESULT'}
(OUT/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
print('SUMMARY',json.dumps(result),flush=True)

PY
