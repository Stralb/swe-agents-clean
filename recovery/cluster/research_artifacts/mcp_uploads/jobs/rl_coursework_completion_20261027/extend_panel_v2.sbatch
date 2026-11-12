#!/bin/bash
#SBATCH --job-name=rl-frozen-extension
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:40:00
#SBATCH --array=0-125%16
set -euo pipefail
umask 077
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_coursework_completion_20261027
TARGET="$ROOT/extension_25_${SLURM_ARRAY_TASK_ID}.sh"
python3 - "$ROOT/run_study.sbatch" "$TARGET" <<'PY'
from pathlib import Path
import sys
inp=Path(sys.argv[1]).read_text()
games="['bp35','cd82','cn04','dc22','ft09','ka59','lf52','lp85','ls20','m0r0','r11l','re86','sb26','sc25','sk48','sp80','su15','tn36','tr87','tu93','wa30']"
old="games=['ar25','g50t','s5i5','vc33'];seeds=[301,302,303]"
new="games="+games+";seeds=[301,302,303]"
assert inp.count(old)==1
inp=inp.replace(old,new)
old="algo='dqn' if task<12 else 'ppo'; i=task%12;game=games[i%4];seed=seeds[i//4]"
new="algo='dqn' if task<63 else 'ppo'; i=task%63;game=games[i%21];seed=seeds[i//21]"
assert inp.count(old)==1
inp=inp.replace(old,new)
inp=inp.replace('matched_public_20261027','all25_extension_20261027')
target=Path(sys.argv[2]);target.write_text(inp)
print('STAGED_FROZEN_EXTENSION',target.name,len(inp),flush=True)
PY
bash "$TARGET"
