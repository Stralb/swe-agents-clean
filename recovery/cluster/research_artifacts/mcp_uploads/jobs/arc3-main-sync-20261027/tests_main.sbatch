#!/bin/bash
#SBATCH --job-name=arc3-source-tests
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:04:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/source-tests-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/source-tests-%j.err
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027
set -uo pipefail
WORK=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/neural_publication_20261027_76640/neural_coursework
PYTHON=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
mkdir -p evidence
cd "$WORK"
echo 'RUNNING_CLUSTER_VENV_TESTS'
"$PYTHON" - <<'PY'
import sys,traceback,json,time
out={'python':sys.executable}
try:
 import torch,numpy
 out['torch']=torch.__version__;out['numpy']=numpy.__version__
 from src.dqn import DQN
 from src.ppo import PPO,evaluate_actions
 from src.dqn_v1.exploration import StructuredExplorer
 from src.dqn_v1.prior import load_prior
 from src.dqn_v1.learner import DQNV1
 from pathlib import Path
 out['imports']='PASS'
 model,fold,path=load_prior('ar25',Path('assets/dqn_v1'),torch.device('cpu'))
 out['prior']={'fold':fold,'path':str(path),'n_parameters':sum(p.numel() for p in model.parameters())}
 del model
except Exception as e:
 out['error']=repr(e);out['traceback']=traceback.format_exc()[-3000:]
open('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/evidence/runtime_smoke.json','w').write(json.dumps(out,indent=2))
print('RUNTIME_SMOKE',json.dumps(out))
PY
SMOKE=$?
timeout 125 "$PYTHON" -m pytest -q tests/test_adapter.py tests/test_learners.py tests/test_dqn_v1.py tests/test_bridge.py tests/test_lifecycle.py tests/test_run.py tests/test_synthetic.py > /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/evidence/pytest_neural_main.txt 2>&1
RC=$?
echo "PYTEST_EXIT $RC"
tail -55 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/evidence/pytest_neural_main.txt
echo "SMOKE_EXIT $SMOKE"
exit 0
