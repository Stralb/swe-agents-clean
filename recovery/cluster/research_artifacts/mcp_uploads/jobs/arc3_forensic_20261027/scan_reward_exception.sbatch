#!/bin/bash
#SBATCH --job-name=arc3-win-scan
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:03:00
set -euo pipefail
umask 077
python3 - <<'PY'
from pathlib import Path
import collections,json
root=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_coursework_completion_20261027/records')
d=[json.loads(p.read_text()) for p in sorted(root.glob('*.json'))]
print('ORIGINAL_RUN_RECORDS',len(d))
g=collections.defaultdict(lambda:{'n':0,'wins':0,'positive_rewards':0,'game_overs':0,'nullerrors':0,'commits':set(),'sdk_actions_equal':0,'scorecard_present':0})
for x in d:
 s=x['study'];key=(s['algorithm'],s['arm']);v=g[key]
 v['n']+=1
 v['wins']+=int(x['diagnostics']['wins'])
 v['positive_rewards']+=int(x['diagnostics']['rewarded_transitions'])
 v['game_overs']+=int(x['diagnostics']['game_overs'])
 v['nullerrors']+=int(x.get('error') is None)
 v['commits'].add(x['identity']['code_commit'])
 v['sdk_actions_equal']+=int(x['counters']['scorer_actions']==x['counters']['sdk_total_actions'])
 v['scorecard_present']+=int(x['official_score'] is not None)
for key,v in sorted(g.items()):
 v['commits']=sorted(v['commits'])
 print(key,v,flush=True)
print('WIN_EXCEPTION_AUDIT_DONE',flush=True)
PY