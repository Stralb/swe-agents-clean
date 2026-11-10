#!/bin/bash
#SBATCH --job-name=arc3-publish-e012
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:03:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/publish-e012-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/publish-e012-%j.err
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027
set -euo pipefail
export GIT_TERMINAL_PROMPT=0
SRC=/home-mscluster/astrauss/arc_rl_final_e012
WORK=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/dqn_component_publication_20261027
if [ -e "$WORK" ]; then echo 'Destination already exists: no overwrite';exit 4;fi
timeout 60 git clone --quiet --depth 1 --branch main https://github.com/Stralb/arc-agi-3-rl-research.git "$WORK"
python3 - "$SRC" "$WORK" <<'PY'
import sys,shutil,hashlib,json
from pathlib import Path
src=Path(sys.argv[1]);repo=Path(sys.argv[2]);dest=repo/'neural_coursework/earlier_dqn_component_study'
allow=['src/arc_e012','tests/test_core.py','configs/e012.json','README.md','PROVENANCE.md','EXPERIMENTS.md','DECISIONS.md','RUNBOOK.md','VALIDATION.md','scripts/preflight.py','scripts/smoke.py','scripts/env.sh','scripts/worker_loop.sh','results/ABLATION_RESULTS.json','results/LOCK_IN.json','results/REPORT.md','results/EXPERIMENTS.md']
files=[]
for rel in allow:
 p=src/rel
 if p.is_file():files.append(p)
 elif p.is_dir():
  files.extend(x for x in sorted(p.rglob('*')) if x.is_file() and x.suffix in {'.py','.json','.md','.txt','.sh'})
assert len(files)>=10,'missing original project files'
manifest={'project_root':str(src),'source_git_ref':'original historical study, not primary coursework four-game runner','files':[]}
for f in files:
 rel=f.relative_to(src);t=dest/rel
 raw=f.read_bytes()
 if t.is_file():assert t.read_bytes()==raw,str(rel)
 else:
  t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(raw)
 manifest['files'].append({'path':str(rel),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
(dest/'ORIGIN_AND_SCOPE.md').write_text('''# Original earlier DQN component study

This directory contains the **actual archived** Wits DQN experiment source,
configuration, component ablations and tests, transferred without modifying
its historical experimental results. The development comparison evaluated
75 game-seed runs per arm with a 600-action upper budget. The four original
ablation arms isolate D14 structured exploration and the dueling head.
This is a distinct protocol from the later DQN/PPO four-game 256-action panel;
these results must not be pooled or described as that panel's chronological
second improvement.

Main neural source is in ../src/; the primary Double DQN/PPO baseline and
selected DQN V1 are separate from this historical component test.
The original 600-action records are preserved under results/ and any
experiment-specific supplementary dependencies must be checked before
claiming end-to-end native SDK replay.
''')
(dest/'SHA256_SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
print('E012_FILES',len(files),'SIZE',sum(x.stat().st_size for x in files))
print('EXAMPLES',[str(x.relative_to(src)) for x in files[:15]])
PY
cd "$WORK"
python3 -m compileall -q neural_coursework/earlier_dqn_component_study/src
git config user.name 'ARC research team'
git config user.email '97600416+Stralb@users.noreply.github.com'
git add neural_coursework/earlier_dqn_component_study
git diff --cached --stat
git commit --quiet -m 'Preserve original Wits DQN component-study source tests and ablations'
echo "COMMIT $(git rev-parse HEAD)"
if timeout 45 git push --porcelain origin HEAD:main >/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/evidence/push_e012_result.txt 2>&1;then echo 'PUSH_MAIN_OK';else echo 'PUSH_MAIN_FAILED';tail -8 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/evidence/push_e012_result.txt;exit 12;fi
