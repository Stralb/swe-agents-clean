#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
GAMES="${1:-}"
BUDGET="${2:-600}"
SEEDS="${3:-5209,5623,6043}"
mkdir -p results/baseline_compare
IFS=',' read -r -a seed_arr <<< "$SEEDS"
for seed in "${seed_arr[@]}"; do
  extra=()
  if [[ -n "$GAMES" ]]; then extra+=(--games "$GAMES"); fi
  python scripts/run_framework_local.py --agent dqn_v0 --seed "$seed" --max-actions "$BUDGET" "${extra[@]}" \
    --out "results/baseline_compare/dqn_v0_s${seed}.json"
  python scripts/run_framework_local.py --agent dqn_v1 --seed "$seed" --max-actions "$BUDGET" "${extra[@]}" \
    --out "results/baseline_compare/dqn_v1_s${seed}.json"
done
python - <<'PY'
import glob, json
from collections import defaultdict
rows=[]
for p in sorted(glob.glob('results/baseline_compare/dqn_v*_s*.json')):
    d=json.load(open(p)); rows.append(d)
print('\n=== DQN BASELINE COMPARISON ===')
for agent in ('dqn_v0','dqn_v1'):
    rr=[r for r in rows if r['agent']==agent]
    if not rr: continue
    print(f"{agent}: seeds={len(rr)} mean_sdk_score={sum(r['sdk_score'] for r in rr)/len(rr):.6f} "
          f"mean_levels={sum(r['total_levels_completed'] for r in rr)/len(rr):.3f} "
          f"mean_actions={sum(r['total_actions'] for r in rr)/len(rr):.1f} "
          f"mean_wall_s={sum(r['wall_s'] for r in rr)/len(rr):.1f}")
by=defaultdict(lambda: defaultdict(list))
for r in rows:
    for g in r['per_game']:
        by[g['game']][r['agent']].append(g['levels_completed'])
print('\nPer-game mean levels (V1-V0 nonzero only):')
for game in sorted(by):
    if 'dqn_v0' not in by[game] or 'dqn_v1' not in by[game]: continue
    a=sum(by[game]['dqn_v0'])/len(by[game]['dqn_v0']); b=sum(by[game]['dqn_v1'])/len(by[game]['dqn_v1'])
    if a != b: print(f"{game}: V0={a:.3f} V1={b:.3f} delta={b-a:+.3f}")
PY
