#!/bin/bash
#SBATCH --job-name=E075_visual_bundle
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,zipfile
H=Path('/home-mscluster/astrauss')
A=H/'E075_ONE_GAME_CLUSTER_HANDOFF_20261019.zip'
V=H/'e075_one_game_runs'
P=H/'E075_TEAM_DEMO_WITH_VISUAL_20261019.zip'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(A)=='b7ac01cba62e3c3a380a1c50f1540f281905092d39e0cf0e4a45823de247f99a'
GIF1=V/'E075_VC33_repeat_seed28901_replay.gif'
GIF2=V/'E075_VC33_repeat_seed28902_replay.gif'
assert sha(GIF1)=='59632db3a6152878b19889e3efaa86a91dca67d7fefd69f81168ecb097c97604'
assert sha(GIF2)=='193c4a1d1ca79d8f3935fd8f5dd25e3c3d87bb86290477f9b296d128dfee2419'
if P.exists():raise FileExistsError('Not overwriting existing visual bundle')
with zipfile.ZipFile(P,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.writestr('START_HERE.txt',
  'E075 vc33 first native one-game demo.\n'
  'Unzip E075_ONE_GAME_CLUSTER_HANDOFF_20261019.zip for original source, checkpoints, frame traces and three-seed comparisons.\n'
  'GIFs are visualizations of the recorded real SDK frame arrays using a reference palette, with progress/click overlay; they are NOT independent gameplay replays or a native Kaggle submission.\n'
  'Event-terminated repeat reached 2 of 7 levels in all three fixed-development-game controller seeds. This policy is hand-designed and is NOT trained RL.\n'
  'See README.txt inside nested full evidence ZIP; tests and controls are documented there.\n')
 z.write(A,A.name)
 z.write(GIF1,'DEMO/E075_vc33_repeat_seed28901.gif')
 z.write(GIF2,'DEMO/E075_vc33_repeat_seed28902.gif')
with zipfile.ZipFile(P) as z:assert z.testzip() is None
print('E075_VISUAL_BUNDLE_READY',str(P),'bytes',P.stat().st_size,'sha256',sha(P),flush=True)
PY