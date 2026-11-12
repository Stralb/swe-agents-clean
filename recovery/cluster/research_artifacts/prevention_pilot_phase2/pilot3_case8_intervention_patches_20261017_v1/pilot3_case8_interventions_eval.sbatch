#!/bin/bash
#SBATCH --job-name=p3arms
#SBATCH --partition=biggpu
#SBATCH --array=0-1%2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3arms_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3arms_%A_%a.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/bun/bin:$PATH"
python3 - <<'PY'
import base64,hashlib,json,os,pathlib,subprocess,zlib
root=pathlib.Path.home()/'research_artifacts'/'prevention_pilot_phase2'
arm=['OP','OW'][int(os.environ['SLURM_ARRAY_TASK_ID'])]
sha={'OP':'5283904055bac85a5b5e886b0e8d73d6a03729b893eca4d2069762865170b3ee','OW':'26688428041def4104a85322109bf084e283ac411304bf38613f37a07b5a2864'}[arm]
patch=root/'pilot3_case8_intervention_patches_20261017_v1'/('PILOT_08_'+arm+'.patch')
data=patch.read_bytes()
assert hashlib.sha256(data).hexdigest()==sha, 'Unexpected patch bytes'
jid=os.environ['SLURM_ARRAY_JOB_ID']
out=root/('pilot3_intervention_eval_job'+jid)/arm;out.mkdir(parents=True,exist_ok=False)
stage=pathlib.Path(os.getenv('SLURM_TMPDIR') or '/tmp')/('pilot3_arms_'+jid+'_'+arm);stage.mkdir(parents=True,exist_ok=False)
scanner=(root/'pilot3_evaluate_3patches_20261017_v2_nodefix.sbatch').read_text()
old=next(line for line in scanner.splitlines() if line.startswith('PATCHES='))
scanner=scanner.replace(old,'PATCHES='+repr({'8':base64.b64encode(zlib.compress(data,9)).decode()}))
scanner=scanner.replace('pilot3_scan_fix_job','pilot3_arms_scan_'+arm+'_job')
func=(root/'pilot3_functional_v1.sbatch').read_text()
oldsha='0e013e16a4c8f772ae404fddfbb0faad100ed13e041ecf7ab594e6b4a01bca4b'
assert func.count(oldsha)==1
func=func.replace(oldsha,sha)
needle="patchmap=ast.literal_eval(line.partition('=')[2]);patch=zlib.decompress(base64.b64decode(patchmap[str(rank)]))"
assert func.count(needle)==1
func=func.replace(needle,"patch=pathlib.Path("+repr(str(patch))+").read_bytes()")
func=func.replace('pilot3_functional_job','pilot3_arms_functional_'+arm+'_job')
env=os.environ.copy();env['SLURM_ARRAY_TASK_ID']='0'
summary={'arm':arm,'patch_sha256':sha}
for kind,source in [('scan',scanner),('functional',func)]:
 script=stage/(kind+'.sh');script.write_text(source)
 with (out/(kind+'.log')).open('x') as log:
  result=subprocess.run(['bash',str(script)],env=env,stdout=log,stderr=subprocess.STDOUT)
 print(arm,kind,'EXIT',result.returncode,flush=True)
 summary[kind+'_exit']=result.returncode
pathmap={'scan':root/('pilot3_arms_scan_'+arm+'_job'+jid)/'rank_8'/'RESULT.json','functional':root/('pilot3_arms_functional_'+arm+'_job'+jid)/'rank_8'/'RESULT.json'}
for kind,path in pathmap.items():
 if path.exists():
  r=json.loads(path.read_text())
  summary[kind]={k:r.get(k) for k in ('status','scanning','base_alerts','patched_alerts','new_target_alerts','changed_line_attributed','functional_correctness','patch_sha256','reason')}
  if kind=='scan':summary[kind]['new_warning_locations']=[v['locations'] for v in r.get('added_details',[])]
 else:summary[kind]={'status':'NO_RESULT'}
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print('SUMMARY',json.dumps(summary),flush=True)
PY
