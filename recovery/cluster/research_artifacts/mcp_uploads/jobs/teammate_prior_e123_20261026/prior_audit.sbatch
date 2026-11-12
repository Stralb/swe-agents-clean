#!/bin/bash
#SBATCH --job-name=e123prioraudit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:06:00
set -euo pipefail
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
PEER=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo SOURCE_CHECKSUM
sha256sum "$PEER/src/dqn_v1/prior.py" "$PEER/src/dqn_v1/exploration.py" "$PEER/assets/dqn_v1/checkpoints/E-onehotcnn__T-stack2__A-vector__U-effect__f0__s11.pt"
export PYTHONPATH="$PEER"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PY" - <<'PY'
from pathlib import Path
import numpy as np,torch
from src.dqn_v1.prior import SelectedEffectModel,random_prior
p=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project/assets/dqn_v1/checkpoints/E-onehotcnn__T-stack2__A-vector__U-effect__f0__s11.pt')
ck=torch.load(p,map_location='cpu',weights_only=True)
print('CHECKPOINT_KEYS',list(ck)[:20],flush=True)
m=SelectedEffectModel();m.load_state_dict(ck['state_dict'],strict=True);m.eval()
r=random_prior(torch.device('cpu'))
x=torch.zeros((1,64,64),dtype=torch.int64)
with torch.no_grad():
  g,s=m.temporal(x,x,torch.zeros((1,4,64,64),dtype=torch.long),torch.zeros((1,4),dtype=torch.bool))
  a=torch.tensor([[1.,-1.,-1.],[2.,-1.,-1.],[6.,0.5,0.5],[6.,0.25,0.75]],dtype=torch.float32)
  scores,c=m.action(g.expand(len(a),-1),s.expand(len(a),-1,-1,-1),a)
  print('SMOKE_TENSORS',tuple(g.shape),tuple(s.shape),tuple(scores.shape),'VALUES',scores.tolist(),flush=True)
  g2,s2=r.temporal(x,x,torch.zeros((1,4,64,64),dtype=torch.long),torch.zeros((1,4),dtype=torch.bool))
  vals,_=r.action(g2.expand(len(a),-1),s2.expand(len(a),-1,-1,-1),a)
  print('RANDOM_WEIGHTS_SMOKE',vals.tolist(),flush=True)
print('PEER_PRIOR_AUDIT_OK')
PY