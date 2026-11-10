#!/bin/bash
#SBATCH --job-name=E084_causal_contact_sheet
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,numpy as np
from PIL import Image,ImageDraw
ROOT=Path('/home-mscluster/astrauss/e084_single_game_causal/E084_vc33_71855')
STORE=ROOT/'E084_CONTROLS_FRAMES.npz'
PALETTE=[
(0,0,0),(0,116,217),(255,65,54),(46,204,64),(255,220,0),
(170,170,170),(240,18,190),(255,133,27),(127,219,255),
(135,12,37),(255,255,255),(110,110,110),(40,70,155),
(0,170,170),(200,100,80),(210,210,180)]
prefix=[(12,56),(16,56),(24,56),(28,56),(34,56),(38,56),(46,56),(50,56)]
with np.load(STORE) as d:
 base=d['action_1318']
 assert len(base)==4
 sheet=Image.new('RGB',(3*685,3*365),(28,28,28))
 for i,(x,y) in enumerate(prefix+[('neutral',0)]):
  idx=6+y*64+x if x!='neutral' else 1318
  z=d['action_'+str(idx)]
  f=z[0]
  b=base[0]
  delta=(f!=b)
  def render(arr):
   im=Image.fromarray(np.asarray(arr,dtype=np.uint8),mode='P')
   p=[]
   for col in PALETTE:p.extend(col)
   im.putpalette(p+[0]*(768-len(p)))
   return im.convert('RGB').resize((320,320),Image.Resampling.NEAREST)
  tile=Image.new('RGB',(685,365),(38,38,38))
  original=render(b);after=render(f)
  diff=np.asarray(after,dtype=np.uint8).copy()
  expanded=np.repeat(np.repeat(delta,5,axis=0),5,axis=1)
  diff[expanded]=[255,0,255]
  tile.paste(original,(10,37));tile.paste(Image.fromarray(diff),(350,37))
  draw=ImageDraw.Draw(tile)
  title='E084 vc33 neutral' if x=='neutral' else f'E084 click({x},{y})'
  draw.text((10,8),title+' | causal px '+str(int(delta.sum())),fill='white')
  draw.text((10,22),'Neutral next frame',fill='white');draw.text((350,22),'Click next (causal difference MAGENTA)',fill='white')
  sheet.paste(tile,((i%3)*685,(i//3)*365))
dest=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e084_20261019_bottom_controls/E084_visual_control_effects.png')
if dest.exists():raise FileExistsError(dest)
sheet.save(dest,optimize=True)
print('E084_CAUSAL_SHEET_CREATED',dest,'bytes',dest.stat().st_size,
 'sha256',hashlib.sha256(dest.read_bytes()).hexdigest(),flush=True)
PY