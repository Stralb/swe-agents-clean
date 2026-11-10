#!/bin/bash
#SBATCH --job-name=E075_replay_visual
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
"$PY" - <<'PY'
from pathlib import Path
import numpy as np,hashlib,json
from PIL import Image,ImageDraw
root=Path('/home-mscluster/astrauss/e075_one_game_runs')
palette=[
 (0,0,0),(0,116,217),(255,65,54),(46,204,64),
 (255,220,0),(170,170,170),(240,18,190),(255,133,27),
 (127,219,255),(135,12,37),(255,255,255),(110,110,110),
 (40,70,155),(0,170,170),(200,100,80),(210,210,180)]
lut=[]
for rgb in palette:lut.extend(rgb)
lut.extend([0]*(768-len(lut)))
for seed,directory in ((28901,'E075_VC33_71743'),(28902,'E075_VC33_71744_seed28902')):
 path=root/directory
 rep=json.loads((path/'E075_REPORT.json').read_text())
 mode=next(x for x in rep['rows'] if x['mode']=='repeat')
 src=path/'repeat_frames.npz'
 if hashlib.sha256(src.read_bytes()).hexdigest()!=mode['frames_sha256']:
  raise RuntimeError('Recorded native frames hash mismatch')
 with np.load(src,allow_pickle=False) as z:raw=z['frames']
 events=[json.loads(s) for s in (path/'repeat.jsonl').read_text().splitlines()]
 assert raw.ndim==3 and raw.shape[1:]==(64,64) and len(raw)==len(events)+1
 output=root/f'E075_VC33_repeat_seed{seed}_replay.gif'
 if output.exists():raise FileExistsError('Preserving existing recorded visualization '+str(output))
 imgs=[]
 for i,frm in enumerate(raw):
  im=Image.fromarray(frm.astype(np.uint8),mode='P');im.putpalette(lut)
  im=im.convert('RGB').resize((512,512),Image.Resampling.NEAREST)
  canvas=Image.new('RGB',(512,558),(17,17,17))
  canvas.paste(im,(0,46))
  draw=ImageDraw.Draw(canvas)
  event=events[i-1] if i else None
  progress=int(event['progress']) if event else 0
  xy=event.get('xy') if event else None
  draw.text((8,6),f"ARC-AGI-3 vc33 | development replay | seed {seed}",fill='white')
  draw.text((8,23),f"step {int(event['action_number']) if event else 0}   progress {progress}/7   click {xy if xy is not None else '-'}",fill='white')
  imgs.append(canvas)
  if event and event['native_level_reward']>0:
   imgs.extend([canvas.copy() for _ in range(7)])
 with open(output,'xb') as f:
  imgs[0].save(f,format='GIF',save_all=True,append_images=imgs[1:],duration=120,loop=0,optimize=True)
 print('E075_REPLAY_GIF',str(output),'bytes',output.stat().st_size,'frames',len(imgs),
       'sha256',hashlib.sha256(output.read_bytes()).hexdigest(),flush=True)
print('E075_RENDERED_REPLAY_DONE',flush=True)
PY