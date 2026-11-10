#!/bin/bash
#SBATCH --job-name=arc3compcompare
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:07:00
set -euo pipefail
python3 - <<'PY'
import json,re
from pathlib import Path
base=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3_public_rl_survey_20261026/source_archive')
names=[
'ashvinsingh__ash-s-arc-agi-3-agent',
'projectforty2__forge-arc-agi-3-agent',
'vyankteshdwivedi__arc-agi-3-hybrid-solver-bfs-cnn-heuristics',
'nihilisticneuralnet__0-46-arc-agi-3-persistent-memory-bfs-arc-solver',
'marynaborovska__hybrid-search-and-learn-agent-0-35-lb',
'rauffauzanrambe__trigger-aware-bfs-for-game-simulation-score-0-35',
]
terms=re.compile(r'\b(class\s+\w+|def\s+(?:choose_action|pick_action|next_action|decide|plan|select_action|_choose|_select|_act|act|advance|_rank|_score|score_actions|_build_candidates|_find_path|_bfs|_observe|observe)|epsilon|reward|checkpoint|action_effect|effect_memory|repeat|memo|novelty|progress|regression|source|game_source|load_game|world_model|graph|astar|bfs|a_star|exploration|scan|prune|frontier)\b',re.I)
for name in names:
    path=base/name
    texts=[]
    for f in path.iterdir():
        if f.suffix not in ('.py','.ipynb','.txt'):continue
        t=f.read_text(errors='replace')
        if f.suffix=='.ipynb':
            x=json.loads(t)
            t='\n'.join(''.join(c.get('source',[])) for c in x.get('cells',[]))
        texts.append(t)
    lines='\n'.join(texts).splitlines()
    hits=[(i+1,l.strip()[:130]) for i,l in enumerate(lines) if terms.search(l) and not re.search('^\s*(#|//|\*)',l)]
    classes=[(i,l.strip()[:170]) for i,l in enumerate(lines,1) if re.match('^\s*class\s+\w+',l)]
    funcs=[(i,l.strip()[:150]) for i,l in enumerate(lines,1) if re.match('^\s*def\s+',l)]
    print('\n===',name,'LINES',len(lines),'HITS',len(hits),'===',flush=True)
    print('CLASS_AND_FUNCTIONS')
    for i,line in (classes+funcs)[:80]:
        print(i,line)
    print('SAMPLE_KEY_MATCHES')
    for i,l in hits[:65]:print(i,l)
    print('END_ITEM',flush=True)
PY