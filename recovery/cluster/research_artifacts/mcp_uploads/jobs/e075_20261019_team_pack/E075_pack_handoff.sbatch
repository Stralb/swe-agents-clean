#!/bin/bash
#SBATCH --job-name=E075_result_archive
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,zipfile
H=Path('/home-mscluster/astrauss')
P=H/'e075_one_game_runs'
W=H/'e074_human_training'
T=H/'research_artifacts/mcp_uploads/jobs'
O=H/'E075_ONE_GAME_CLUSTER_HANDOFF_20261019.zip'
def hashfile(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files={}
def add(name,p):
 if not p.is_file():raise FileNotFoundError(p)
 files[name]=p
for name in ('E074_TRAINING_COMPLETE_FREEZE.json','E074_VALIDATED_HUMAN_GATE.json','E074_OFFLINE_POLICY_PROBE.json'):
 add('E074/'+name,W/name)
for mode in ('bc','ddqn','shuffled','no_history'):
 add('E074/history_'+mode+'.pt',W/'trained_human'/('history_'+mode+'.pt'))
add('E074/native_71736.json',W/'native_dev/E074_s5i5_native_dev_71736.json')
add('E074/native_71736.jsonl',W/'native_dev/E074_s5i5_native_dev_71736.jsonl')
SRC=T/'e075_20261019_onegame_capability/E075_vc33_capability_v2.py'
assert hashfile(SRC)=='ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7'
add('E075/E075_vc33_capability_v2.py',SRC)
for name,path in (
 ('E075_first_run.sbatch',T/'e075_20261019_onegame_capability/E075_run_vc33_activation.sbatch'),
 ('E075_two_replicas.sbatch',T/'e075_20261019_two_replicas/E075_vc33_two_replicas.sbatch'),
 ('forensic_71745.txt',T/'e075_20261019_procedure_forensic/logs/71745.out'),
 ('post_level_71746.txt',T/'e075_20261019_l3_wall_forensics/logs/71746.out')):
 add('E075/'+name,path)
rows={}
for seed,sub in ((28901,'E075_VC33_71743'),(28902,'E075_VC33_71744_seed28902'),(28903,'E075_VC33_71744_seed28903')):
 folder=P/sub
 rep=json.loads((folder/'E075_REPORT.json').read_text())
 assert rep['same_initial_frame'] and rep['development_game_only']=='vc33'
 rows[seed]={r['mode']:r['levels_completed'] for r in rep['rows']}
 for p in sorted(folder.iterdir()):
  if p.is_file() and p.suffix in ('.json','.jsonl','.npz'):
   add('E075/three_seed_runs/'+sub+'/'+p.name,p)
assert rows[28901]['repeat']==rows[28902]['repeat']==rows[28903]['repeat']==2
readme=('E075 one-game native verification - 19 October 2026\n'
 'Wits Slurm 71743,71744,71745,71746. Development game vc33, env seed 0, 160 scorer actions, 161 including initial reset.\n'
 'Results - 7 levels in game, none fully won:\n'+json.dumps(rows,indent=2)+'\n'
 'ALL modes use legal public observations; no game-specific script, cloned simulator, teacher or human demonstration.\n'
 'E075 is hand-designed diagnostic, NOT an RL algorithm or evidence of unseen-game generalization.\n'
 'Repeat-until-observed-event-stops reaches 2 levels in 3/3 seeds; blind repeat ties 2/3.\n'
 'L3 was not reached; 68-69 actions remained after L2 with effectful interactions.\n'
 'E074 native source-five s5i5 60-call comparison was 0 levels in all five arms; all 4 offline models are frozen.\n'
 'Assignments still require separate genuinely learned DQN and PPO plus staged improvements.\n')
if O.exists():
 print('ARCHIVE_ALREADY_EXISTS_PRESERVED',O,hashfile(O));raise SystemExit(0)
with zipfile.ZipFile(O,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.writestr('README.txt',readme)
 manifest={}
 for name,path in sorted(files.items()):
  z.write(path,name)
  manifest[name]={'sha256':hashfile(path),'bytes':path.stat().st_size}
 z.writestr('MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(O) as z:assert z.testzip() is None
print('ARCHIVE_READY',O,'bytes',O.stat().st_size,'sha256',hashfile(O),'file_count',len(files)+2)
PY