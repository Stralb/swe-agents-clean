#!/bin/bash
#SBATCH --job-name=E095_astar_unit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
DIR=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e095_20261020_multistep_replanning
printf '%s  %s\n' ed5c36f581ee834f35f4a1ef34e8f71311487d68a8800ab529fbbee5e41b0cb0 "$DIR/E095_online_core_v1.py" | sha256sum -c -
printf '%s  %s\n' 126a274cabd68b34039a5acc712245c5039f5ff46c62559be07744d1764bd727 "$DIR/E095_native_runner_v1.py" | sha256sum -c -
"$PY" -B "$DIR/E095_native_runner_v1.py" --self-test
"$PY" -B - <<'PY'
from pathlib import Path
import importlib.util
p=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e095_20261020_multistep_replanning/E095_online_core_v1.py')
spec=importlib.util.spec_from_file_location('e095_unit',p);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
a=mod.OnlineAgent('full',28901)
deltas=[
 (2,-2,0,0,0),(0,2,-2,0,0),(0,0,2,-2,0),(0,0,0,2,-2)]
acts=[101,102,103,104]
for idx,delta in zip(acts,deltas):a.memory.forward[idx][delta]=3
scene={'now':(12,0,0,18,14),'controls':[(idx,idx,56) for idx in acts]}
choice=a.astar_plan(scene,(16,0,0,18,10))
assert choice is not None
idx,hyp=choice
assert idx==104,(idx,hyp)
assert hyp['lookahead']==8,hyp
print('E095_ASTAR_PREREQUISITE_TEST_PASSED',{'chosen':idx,'lookahead':hyp['lookahead'],'predicted_delta':hyp['expected']},flush=True)
PY
echo E095_UNITS_OK