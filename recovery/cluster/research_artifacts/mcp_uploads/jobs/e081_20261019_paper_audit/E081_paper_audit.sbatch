#!/bin/bash
#SBATCH --job-name=E081_paper_evidence_audit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:07:00
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import json,hashlib,glob
R=Path('/home-mscluster/astrauss')
paths={
 28901:R/'e080_course_development/E080_native_seed28901_71820',
 28902:R/'e080_course_development/E080_native_seed28902_71822',
 28903:R/'e080_course_development/E080_native_seed28903_71822'
}
for seed,folder in paths.items():
 info=json.loads((folder/'E080_RESULTS.json').read_text())
 for x in info['methods']:
  rec=json.loads((Path(x['checkpoint']).parent/'record.json').read_text())
  print('PAPER_E080_CURVE',json.dumps({
   'seed':seed,'algo':x['algo'],'trained':x['online_updated'],
   'curve':rec['diagnostics']['progress_curve'],
   'highwater':rec['counters']['high_water'],
   'native_score':rec['official_score']['score'],
   'run_status':rec['status'],
   'runtime_s':rec['cost']['wall_s'],
   'gpu_used':False,'model_params':rec['identity']['model_info'].get('parameters'),
   'first_reward_action':rec['diagnostics']['first_reward_action'],
   'click_fraction':rec['diagnostics']['click_fraction'],
   'e080_option_prior_activations':x['option_prior_enabled_when_effectful']},sort_keys=True),flush=True)
for seed,folder in [
 (28901,R/'e078_course_recovery/E078_native_vc33_160_seed28901_71805'),
 (28902,R/'e078_course_recovery/E078_native_vc33_160_seed28902_71808'),
 (28903,R/'e078_course_recovery/E078_native_vc33_160_seed28903_71808')]:
 info=json.loads((folder/'E078_REPORT.json').read_text())
 for item in info['rows']:
  if item['disabled_gradient']:continue
  if item['stage']=='intrinsic_effect_proposals':
   rec=json.loads((folder/item['run_id']/'record.json').read_text())
   print('PAPER_E078_CURVE',json.dumps({
    'seed':seed,'algo':item['algo'],'stage':item['stage'],
    'curve':rec['diagnostics']['progress_curve'],
    'rewarded':rec['diagnostics']['rewarded_transitions'],
    'native_score':item['official_sdk_score']},sort_keys=True),flush=True)
for file in [
 'rlj.sty','rlj.bst','rlj.cls'
]:
 arr=list(R.glob('**/'+file))
 print('RLC_STYLE_SEARCH',file,[str(x) for x in arr[:15]],flush=True)
print('E081_AUDIT_END',flush=True)
PY