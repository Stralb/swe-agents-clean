#!/bin/bash
#SBATCH --job-name=arc3-srcverify
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:02:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/srcverify-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/srcverify-%j.err
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import os,json,re,hashlib
base=Path('/home-mscluster/astrauss')
names=['e078_course_recovery','RL-ARC-AGI-3-Project','arc26','arc_rl_final_e012','arc_rl_mechanics_killtest']
pattern=re.compile(r'(?i)(ppo|dqn|actor|critic|mask|log_prob|learning.rate|discount|gamma|optimizer\.step|gradient|rollout|config|source|train)')
out={'source_candidates':[],'config_candidates':[],'implementation_snippets':[]}
for name in names:
 root=base/name
 if not root.is_dir():continue
 count=0
 for here,dirs,files in os.walk(root):
  dirs[:]=[d for d in dirs if d not in ('.git','.venv','venv','__pycache__','node_modules','recordings','checkpoints','runs') and len(Path(here).relative_to(root).parts)<4]
  for fname in files:
   f=Path(here)/fname
   if f.suffix not in ('.py','.json','.toml','.yaml','.md','.sh'):continue
   try:size=f.stat().st_size
   except OSError:continue
   if size>500000 or count>=1100:continue
   count+=1
   rel=str(f.relative_to(root))
   if pattern.search(rel):
    out['source_candidates'].append({'project':name,'path':rel,'bytes':size})
   if f.suffix in ('.py','.json','.yaml','.toml') and (pattern.search(rel) or 'agent' in rel.lower() or 'runner' in rel.lower()):
    try:txt=f.read_text(errors='replace')
    except OSError:continue
    lines=txt.splitlines()
    matched=[(i+1,l[:190]) for i,l in enumerate(lines) if re.search(r'(?i)(log_prob|masked_fill|mask_logits|logits|ratio|optimizer.step|gamma\s*=|lr\s*=|learning_rate|discount\s*=|Adam\(|network|class.*DQN|class.*PPO)',l)]
    if matched:
     out['implementation_snippets'].append({'project':name,'path':rel,'sha256':hashlib.sha256(txt.encode()).hexdigest(),'lines':matched[:35]})
   if count>=1100:break
out['implementation_snippets'].sort(key=lambda q:(-len(q['lines']),q['project']))
Path('out/gpu/source_verification_index.json').write_text(json.dumps(out,indent=2))
print('SOURCE_VERIFICATION',len(out['source_candidates']),len(out['implementation_snippets']))
print('TOP',json.dumps(out['implementation_snippets'][:12])[:14000])
PY
