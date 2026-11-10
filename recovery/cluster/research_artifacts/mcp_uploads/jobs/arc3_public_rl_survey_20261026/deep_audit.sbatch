#!/bin/bash
#SBATCH --job-name=arc3rldeepaudit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
python3 - <<'PY'
import json,re
from pathlib import Path
base=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3_public_rl_survey_20261026/source_archive')
slugs=[
'rauffauzanrambe__arc-reinforcement-learning-for-agi',
'rauffauzanrambe__arc3-agi-reinforcement-agents',
'rauffauzanrambe__arc-agi-3-agent-running-training-v17',
'sinethembanani__dqn-agent',
'princemolakeng__psalm91-agent-dqn-region-clicks',
'thezetaproject__dqn-linalg-arc-agi-3',
'ipfilidzhade__ppo-improvement-2',
'iddrisabdulnasir__arc-agi-3-pamdp-baseline-active-epistemic-rl',
'thomasferraz__arc-agi-3-td-jepa-first-submission-5k-bfs',
'avikdas567__arc-agi-3-neural-world-models-for-spatial-pomdps',
'suneetsaini__arc-agi-3-dreamerv3-icm-agent',
'poonszesen__redpill-latent-imaginations-in-dream-rollouts',
'marynaborovska__hybrid-search-and-learn-agent-0-35-lb',
'nihilisticneuralnet__0-17-arc-agi-3-residual-cnn-state-graph',
'nihilisticneuralnet__0-46-arc-agi-3-persistent-memory-bfs-arc-solver',
'gourabr0y555__improved-bfs-curiosity-driven-cnn-fallback',
]
kw=r'(^\s*class\s+(?:DQN|PPO|.*Agent|.*Trainer|.*Critic|.*WorldModel|.*Learner)|optimizer\.step\(|\.backward\(|loss\s*=|loss:|train_step\(|\.learn\(|TD\(|q_target|target_q|bellman|actor_loss|critic_loss|value_loss|policy_loss|reward\s*=|reward:|RHAE|score[=:]|public score|leaderboard|LB\s+0\.\d+|PPO|DQN|learns|does not train|score 0\.[0-9]+|\[0\.[0-9]+\])'
for slug in slugs:
  folder=base/slug
  docs=[]
  for f in folder.glob('*'):
    if f.suffix not in ('.py','.ipynb','.txt'):continue
    raw=f.read_text(errors='replace')
    if f.suffix=='.ipynb':
      nb=json.loads(raw)
      raw='\n'.join(''.join(c.get('source',[])) for c in nb.get('cells',[]))
    docs.append(raw)
  code='\n'.join(docs)
  matches=[(i,x.strip()[:160]) for i,x in enumerate(code.splitlines(),1) if re.search(kw,x,re.I)]
  print('\n===== ',slug,' total',len(code),' line_count',len(code.splitlines()),'matches',len(matches),' =====',flush=True)
  for i,ln in matches[:42]:
    print(str(i)+': '+ln,flush=True)
  if len(matches)>42:print('... '+str(len(matches)-42)+' more matches',flush=True)
PY