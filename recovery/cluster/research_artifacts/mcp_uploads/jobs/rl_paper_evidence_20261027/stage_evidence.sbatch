#!/bin/bash
#SBATCH --job-name=rlpaper-stage
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
python3 - <<'PY'
from pathlib import Path
import shutil
p=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
o=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_paper_evidence_20261027/originals')
paths=['README.md','configs/splits.json','src/dqn.py','src/ppo.py','src/adapter.py','src/run.py','src/config.py','src/dqn_v1/agent.py','src/dqn_v1/learner.py','src/dqn_v1/qnet.py',
'results/phase1_random_flat_uniform.json','results/phase1_random_type_uniform.json','results/baseline_compare/dqn_v0_s5209.json','results/baseline_compare/dqn_v1_s5209.json','results/e014/FINAL_REPORT.md','results/e014/stage3/SUMMARY.csv','results/e015/BEST_SYSTEM.json','results/e015/final_systems/best.json','results/e015/b3/SUMMARY.csv','results/e016/EXPERIMENT.json',
'E016_RUNBOOK.md','E017_RUNBOOK.md','E020_RESULTS.tar.gz','E021R_DEBUG_INFO.txt',
'E029_NOTES.md','E030_NOTES.md','E031_NOTES.md','E032_NOTES.md','E033_NOTES.md','E034_NOTES.md','E035_NOTES.md',
'configs/e029_systems.json','configs/e030_systems.json','configs/e031_systems.json','configs/e032_systems.json','configs/e035_systems.json']
for s in paths:
 f=p/s
 if f.is_file() and f.stat().st_size<1000000:
  dst=o/s
  dst.parent.mkdir(exist_ok=True,parents=True)
  shutil.copyfile(f,dst)
  print('STAGED',s,f.stat().st_size)
 else:
  print('SKIPPED',s)
print('PAPER_SOURCE_STAGE_COMPLETE')
PY
