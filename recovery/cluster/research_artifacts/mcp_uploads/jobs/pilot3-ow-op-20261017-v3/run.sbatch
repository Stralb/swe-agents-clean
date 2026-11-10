#!/bin/bash
#SBATCH --job-name=p3_OW_OP
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3int_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p3int_%j.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
python3 - <<'PY'
import ast,base64,hashlib,json,os,pathlib,re,subprocess,zlib
ROOT=pathlib.Path.home()/'research_artifacts'/'prevention_pilot_phase2'
STAGED=pathlib.Path.home()/'research_artifacts'/'mcp_uploads'/'jobs'/'pilot3-ow-op-20261017-v3'
EXPECTED={'OP':'5283904055bac85a5b5e886b0e8d73d6a03729b893eca4d2069762865170b3ee',
          'OW':'26688428041def4104a85322109bf084e283ac411304bf38613f37a07b5a2864'}
def payload(filename,key):
 s=(STAGED/filename).read_text(encoding='utf-8')
 name,sep,body=s.partition(' = ')
 assert sep and name==key
 return ast.literal_eval(body.strip())
PATCH_TEXT={
 'OP':payload('arm_op.py','PATCH'),
 'OW':payload('arm_ow_0.py','PATCH_PART')+payload('arm_ow_1.py','PATCH_PART')}
# Verify original uploaded bytes BEFORE accessing any historical results.
for arm in ('OP','OW'):
 digest=hashlib.sha256(PATCH_TEXT[arm].encode('utf-8')).hexdigest()
 assert digest==EXPECTED[arm],(arm,digest,EXPECTED[arm])
JOB=os.environ['SLURM_JOB_ID']
OUT=ROOT/('pilot3_interventions_job'+JOB)
OUT.mkdir(exist_ok=False,parents=True)
scanner_orig=(ROOT/'pilot3_evaluate_3patches_20261017_v2_nodefix.sbatch').read_text()
func_orig=(ROOT/'pilot3_functional_v1.sbatch').read_text()
NEEDLE="patchmap=ast.literal_eval(line.partition('=')[2]);patch=zlib.decompress(base64.b64decode(patchmap[str(rank)]))"
OLD_SHA='0e013e16a4c8f772ae404fddfbb0faad100ed13e041ecf7ab594e6b4a01bca4b'
assert func_orig.count(NEEDLE)==1
assert func_orig.count(OLD_SHA)==1
def execute(arm,tag,script):
 script_path=OUT/(arm+'_'+tag+'.sh')
 script_path.write_text(script)
 script_path.chmod(0o700)
 env=os.environ.copy()
 env['SLURM_ARRAY_TASK_ID']='0'
 env['SLURM_ARRAY_JOB_ID']=JOB+'_'+arm
 with (OUT/(arm+'_'+tag+'.log')).open('x') as f:
  done=subprocess.run(['bash',str(script_path)],env=env,stdout=f,stderr=subprocess.STDOUT)
 target=ROOT/(('pilot3_intscan_job' if tag=='scan' else 'pilot3_intfunc_job')+env['SLURM_ARRAY_JOB_ID'])/'rank_8'/'RESULT.json'
 if not target.exists():
  return {'status':'RESULT_MISSING','process_exit':done.returncode}
 obj=json.loads(target.read_text())
 return {'status':obj.get('status'),'process_exit':done.returncode,'result_path':str(target),
  'base_alerts':obj.get('base_alerts'),'patched_alerts':obj.get('patched_alerts'),
  'new_target_alerts':obj.get('new_target_alerts'),'changed_line_attributed':obj.get('changed_line_attributed'),
  'functional_correctness':obj.get('functional_correctness') or obj.get('functionality'),
  'new_locations':[x.get('locations') for x in obj.get('added_details',[])],
  'checks':[{k:z.get(k) for k in ('name','exit_code')} for z in obj.get('checks',[])],
  'reason':obj.get('reason')}
summary={'job':JOB,'case_id':21942,'base_sha':'639150316e6f14cdc78e7dba8c6263504895b2e1',
 'target_rule':'js/insecure-temporary-file',
 'baselines':{'R1':{'new_alerts':2,'targeted_tests':'29/29'},'R2':{'new_alerts':3,'targeted_tests':'28/28'}},
 'arms':{}}
for arm in ('OP','OW'):
 raw=PATCH_TEXT[arm].encode('utf-8')
 (OUT/(arm+'.patch')).write_bytes(raw)
 compressed=base64.b64encode(zlib.compress(raw,9)).decode('ascii')
 scanner,num=re.subn(r'(?m)^PATCHES=.*$',lambda m:'PATCHES='+repr({'8':compressed}),scanner_orig)
 assert num==1
 scanner=scanner.replace('pilot3_scan_fix_job','pilot3_intscan_job')
 sr=execute(arm,'scan',scanner)
 func=func_orig.replace(OLD_SHA,EXPECTED[arm])
 func=func.replace(NEEDLE,"patch=(ROOT/"+repr('pilot3_interventions_job'+JOB)+"/"+repr(arm+'.patch')+").read_bytes()")
 func=func.replace('pilot3_functional_job','pilot3_intfunc_job')
 fr=execute(arm,'functional',func)
 summary['arms'][arm]={'patch_sha256':EXPECTED[arm],'scan':sr,'functional':fr}
 (OUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
 print('ARM',arm,'SCAN',sr['status'],'NEW',sr.get('new_target_alerts'),
       'FUNCT',fr['status'],flush=True)
print('SUMMARY',json.dumps(summary),flush=True)
PY
