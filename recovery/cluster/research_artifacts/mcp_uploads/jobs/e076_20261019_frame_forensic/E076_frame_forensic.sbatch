#!/bin/bash
#SBATCH --job-name=E076_vc33_frames
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
"$PY" - <<'PY'
from pathlib import Path
from collections import Counter
import hashlib,json
import numpy as np
from PIL import Image,ImageDraw
base=Path('/home-mscluster/astrauss/e075_one_game_runs')
dest=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e076_20261019_frame_forensic')
dest.mkdir(parents=True,exist_ok=True)
colors=[(0,0,0),(0,116,217),(255,65,54),(46,204,64),(255,220,0),(170,170,170),(240,18,190),(255,133,27),(127,219,255),(135,12,37),(255,255,255),(110,110,110),(40,70,155),(0,170,170),(200,100,80),(210,210,180)]
for seed,run in [(28901,'E075_VC33_71743'),(28902,'E075_VC33_71744_seed28902')]:
 folder=base/run
 info=json.loads((folder/'E075_REPORT.json').read_text())
 row=next(x for x in info['rows'] if x['mode']=='repeat')
 file=folder/'repeat_frames.npz'
 assert hashlib.sha256(file.read_bytes()).hexdigest()==row['frames_sha256']
 with np.load(file) as pack:z=pack['frames']
 trace=[json.loads(t) for t in (folder/'repeat.jsonl').read_text().splitlines()]
 indices=[0,5,17,18,42,89,92,93,110,120,145,len(z)-1] if seed==28901 else [0,5,6,7,42,89,91,92,110,125,145,len(z)-1]
 # indices are transition indices; frame after native action N lies at N minus in-trace reset overhead
 triggers=[(i,x['action_number'],int(x['native_level_reward'])) for i,x in enumerate(trace) if x['native_level_reward']]
 print('SEED',seed,'FRAME_COUNT',len(z),'PROGRESS_FRAME_INDICES',triggers,flush=True)
 tiles=[];summary=[]
 for k in indices:
  a=np.asarray(z[k],dtype=np.uint8)
  c=Counter(int(v) for v in a.ravel())
  im=Image.new('RGB',(64,64))
  im.putdata([colors[int(v)] for v in a.ravel()])
  im=im.resize((320,320),Image.Resampling.NEAREST)
  tile=Image.new('RGB',(340,352),(34,34,34));tile.paste(im,(10,22))
  draw=ImageDraw.Draw(tile)
  draw.text((12,5),f'seed{seed} frame idx {k}',fill='white')
  tiles.append(tile)
  summary.append({'index':k,'colours':dict(sorted(c.items())),
    'row_nonbackground':[(int(i),int(sum(a[i]!=0))) for i in range(64) if int(sum(a[i]!=0))>0][:12]})
 sheet=Image.new('RGB',(4*340,3*352),(30,30,30))
 for k,t in enumerate(tiles):sheet.paste(t,((k%4)*340,(k//4)*352))
 path=dest/f'E076_vc33_seed{seed}_observed_frames.png'
 if path.exists():raise FileExistsError(path)
 sheet.save(path,optimize=True)
 print('OBSERVED_FRAME_SHEET',path,'bytes',path.stat().st_size,'sha256',hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)
 (dest/f'E076_vc33_seed{seed}_frame_histogram.json').write_text(json.dumps(summary,indent=2))
 print('SELECTED_FRAME_COUNTS',json.dumps(summary),flush=True)
PY