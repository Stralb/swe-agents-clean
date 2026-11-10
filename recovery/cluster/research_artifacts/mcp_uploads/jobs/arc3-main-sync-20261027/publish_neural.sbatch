#!/bin/bash
#SBATCH --job-name=arc3-publish-neural
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=3G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/publish-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/publish-%j.err
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027
set -euo pipefail
export GIT_TERMINAL_PROMPT=0
export GIT_LFS_SKIP_SMUDGE=1
SRC=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
WORK=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/neural_publication_20261027_76640
mkdir -p evidence
if [ -e "$WORK" ]; then echo "Refusing to overwrite existing worktree"; exit 3; fi
echo 'STAGE: clone current main'
if ! timeout 60 git clone --quiet --depth 1 --branch main https://github.com/Stralb/arc-agi-3-rl-research.git "$WORK"; then
 echo 'CLONE_FAILED: no accessible upstream or network'
 exit 10
fi
python3 - "$SRC" "$WORK" <<'PY'
import os,sys,json,hashlib,shutil
from pathlib import Path
src=Path(sys.argv[1]);repo=Path(sys.argv[2])
files=[
 'src/dqn_v1/exploration.py','src/dqn_v1/prior.py',
 'tests/test_adapter.py','tests/test_bridge.py','tests/test_learners.py',
 'tests/test_lifecycle.py','tests/test_run.py','tests/test_synthetic.py',
 'requirements.txt'
]
assets=sorted((src/'assets/dqn_v1/checkpoints').glob('*.pt'))
assert len(assets)==5, 'Expected five historical cross-fold weights'
files += [str(x.relative_to(src)) for x in assets]
log={'copied':[],'same':[],'conflicts':[],'missing':[]}
for rel in files:
 f=src/rel;dest=repo/'neural_coursework'/rel
 if not f.is_file():log['missing'].append(rel);continue
 raw=f.read_bytes()
 if dest.is_file():
  if dest.read_bytes()==raw:log['same'].append(rel)
  else:log['conflicts'].append(rel)
  continue
 dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
 log['copied'].append({'path':'neural_coursework/'+rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
readme=repo/'neural_coursework/README.md'
if not readme.exists():
 readme.write_text('''# ARC-AGI-3 neural coursework source

This directory preserves the original Wits cluster source files for **Random,
Double DQN and PPO** baseline learners, plus the separately selected **structured
DQN V1** implementation. The code is preserved as researched; missing later
evaluation artifacts are not regenerated.

## Source layout

- `src/adapter.py`, `bridge.py`, `learner.py`, `run.py`: native ARC
  action/observation translation, random reference, runner and checkpoints.
- `src/dqn.py`: online/target Double DQN with masked legal-action selection,
  replay, gradient updates and target synchronization.
- `src/ppo.py`: factorized actor/critic PPO, stored old log-probabilities,
  legal-action masks, GAE and clipped policy updates.
- `src/dqn_v1/`: original selected DQN value learner, dueling network,
  structured exploration, frozen effect representation and cross-fold weights.
- `assets/dqn_v1/checkpoints/`: five existing **historical** 2026 public
  cross-fold effect-model checkpoints copied byte-for-byte from the Wits
  research directory. SHA-256 hashes are available in the export manifest.
- `tests/`: original Wits learner, adapter, lifecycle, DQN V1 and runner tests.

## Reproduction notes

The baseline hyperparameters in `src/config.py` are explicitly marked
**provisional** in the source and are not evidence that every published
experiment used those exact settings. The selected DQN V1 loads a frozen
cross-fold effect prior; its performance and pretraining costs must not be
attributed solely to online DQN. It is a distinct development protocol from
the later four-game coursework outcome table.

The existing `kaggle/learner_agent.py` is a research integration scaffold,
not proof of a fully evaluated Kaggle neural submission. Exact historical
DQN/PPO I1/I2 coursework source, rollout histories and scorer receipts are
not established by this directory alone. Do not describe the files as a
verified reproduction of the later seven-arm study.

For a basic import smoke test, install `requirements.txt` dependencies,
then from this directory run:

```sh
python3 -m pytest -q tests/test_adapter.py tests/test_learners.py tests/test_dqn_v1.py
```

The source files were copied from
`/home-mscluster/astrauss/RL-ARC-AGI-3-Project` on 2026-10-27; existing
repository files were not overwritten during this sync.
''')
 log['copied'].append({'path':'neural_coursework/README.md','bytes':readme.stat().st_size})
(repo/'neural_coursework/SYNC_PROVENANCE.json').write_text(json.dumps(log,indent=2))
if log['conflicts'] or log['missing']:
 print('SOURCE_CONFLICT_OR_MISSING',json.dumps(log),flush=True)
 raise SystemExit(4)
print('SYNC_PLAN',json.dumps(log),flush=True)
PY
cd "$WORK"
python3 -m compileall -q neural_coursework/src neural_coursework/tests
git config user.name 'ARC research team'
git config user.email '97600416+Stralb@users.noreply.github.com'
git add neural_coursework
echo 'STAGED:'
git diff --cached --stat
if git diff --cached --quiet; then echo 'NO_CHANGES'; exit 0; fi
git commit --quiet -m 'Publish original Wits neural coursework DQN/PPO dependencies and cross-fold priors'
echo "CREATED_COMMIT $(git rev-parse HEAD)"
if timeout 55 git push --porcelain origin HEAD:main > /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/evidence/push_result.txt 2>&1; then
 echo 'PUSH_MAIN_SUCCEEDED'
else
 echo 'PUSH_MAIN_FAILED'
 sed -E 's#https?://[^/@ ]+@#https://REDACTED@#g' /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/evidence/push_result.txt | tail -12
 exit 12
fi
