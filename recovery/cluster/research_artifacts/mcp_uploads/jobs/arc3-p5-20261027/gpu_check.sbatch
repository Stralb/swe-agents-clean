#!/bin/bash
#SBATCH --job-name=arc3-gpu-check
#SBATCH --partition=biggpu
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:06:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/gpu-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/gpu-%j.err
set -euo pipefail
mkdir -p out/gpu
python3 - <<'PY'
import os,sys,json,hashlib,subprocess,importlib.util
from pathlib import Path
b=Path('/home-mscluster/astrauss')
out=Path('out/gpu')
d={'host':os.uname().nodename,'python':sys.version,'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'source_heads':{},'project_roots':{},'torch':{},'records':{}}
for name in ('RL-ARC-AGI-3-Project','arc26','arc_rl_final_e012','e078_course_recovery'):
 p=b/name
 if p.is_dir():
  try: d['project_roots'][name]=[x.name for x in p.iterdir()][:80]
  except OSError as e:d['project_roots'][name]=str(e)
for rel in ('arc_rl_final_e012/src/arc_e012/qnet.py','arc_rl_final_e012/src/arc_e012/agent.py','arc_rl_final_e012/src/arc_e012/replay.py','arc_rl_final_e012/tests/test_core.py','arc_rl_final_e012/configs/e012.json'):
 p=b/rel
 if not p.is_file():continue
 data=p.read_bytes()
 d['source_heads'][rel]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'first3000':data.decode('utf8','replace')[:3000]}
for root in sorted((b/'e078_course_recovery').glob('E078_native_vc33_160_seed*')):
 for p in sorted(root.glob('*/*record.json'))[:8]:
  try:
   x=json.loads(p.read_text()); d['records'][str(p.relative_to(b))]={'type':type(x).__name__,'keys':list(x)[:35] if isinstance(x,dict) else [],'preview':str(x)[:500]}
  except Exception as e:d['records'][str(p.relative_to(b))]={'error':str(e)}
try:
 import torch
 d['torch']={'version':torch.__version__,'cuda_available':torch.cuda.is_available(),'gpu_count':torch.cuda.device_count(),'gpu_name':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
 if torch.cuda.is_available():
  # Genuine native GPU autograd smoke, NOT historical algorithm rerun.
  x=torch.tensor([[1.,2.],[3.,4.]],device='cuda')
  net=torch.nn.Linear(2,2).to('cuda')
  opt=torch.optim.Adam(net.parameters(),lr=1e-3)
  before=net.weight.detach().clone()
  loss=(net(x)**2).mean();loss.backward();grad=net.weight.grad.detach().norm().item();opt.step()
  d['torch']['gpu_autograd_smoke']={'loss':loss.item(),'gradient_l2':grad,'parameter_delta_l2':(net.weight.detach()-before).norm().item()}
except Exception as e:d['torch']={'error':repr(e)}
out.joinpath('gpu_preflight_and_e012_sources.json').write_text(json.dumps(d,indent=2))
print('GPU_PREFLIGHT',json.dumps(d['torch']))
print('PROJECT_ROOTS',json.dumps({k:v[:20] if isinstance(v,list) else v for k,v in d['project_roots'].items()}))
print('E012_SOURCE',json.dumps({k:{'sha256':v['sha256'],'bytes':v['bytes']} for k,v in d['source_heads'].items()}))
print('E078_RECORDS',len(d['records']))
PY
