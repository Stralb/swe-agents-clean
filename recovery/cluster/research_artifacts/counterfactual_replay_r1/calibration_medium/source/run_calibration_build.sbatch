#!/bin/bash
#SBATCH --job-name=cf_cal_build
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/logs/%x_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/calibration_medium/logs/%x_%j.err

set -euo pipefail

ROOT="$HOME/research_artifacts/counterfactual_replay_r1/calibration_medium"
SRC="$ROOT/source"
OUT="$ROOT/generated"
SNAP="$ROOT/snapshots"
WORK="$ROOT/work"
LOGS="$ROOT/logs"

mkdir -p "$OUT" "$SNAP" "$WORK" "$LOGS"
rm -f "$OUT"/C???_INPUT.zip "$OUT/CALIBRATION_16_INPUTS.zip" "$OUT/CALIBRATION_GENERATION_PROMPT.txt" "$OUT/PUBLIC_CHAT_BLOCKS.csv"

python3 - "$SRC" "$SNAP" "$WORK" "$OUT" <<'PY_INNER_321'
import csv, hashlib, shutil, subprocess, sys, zipfile
from pathlib import Path
SRC=Path(sys.argv[1]); SNAP=Path(sys.argv[2]); WORK=Path(sys.argv[3]); OUT=Path(sys.argv[4])

def run(cmd,cwd=None,timeout=240):
    p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if p.returncode!=0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\nSTDOUT:\n{p.stdout[-3000:]}\nSTDERR:\n{p.stderr[-5000:]}")
    return p

def sha256(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

tasks=list(csv.DictReader(open(SRC/'TASK_MANIFEST.csv',encoding='utf-8')))
assign=list(csv.DictReader(open(SRC/'SECRET_ASSIGNMENT.csv',encoding='utf-8')))
repos={}
for t in tasks:
    repos.setdefault((t['repository'],t['repository_url']),set()).add(t['base_sha'])
archive_by_key={}
for (repo,url),shas in repos.items():
    slug=repo.replace('/','__'); w=WORK/slug
    if w.exists(): shutil.rmtree(w)
    w.mkdir(parents=True)
    run(['git','init','-q'],cwd=w)
    run(['git','remote','add','origin',url],cwd=w)
    for sha in sorted(shas):
        run(['git','fetch','--depth=1','origin',sha],cwd=w,timeout=300)
        got=run(['git','rev-parse','FETCH_HEAD'],cwd=w).stdout.strip()
        if got!=sha: raise RuntimeError(f'{repo} expected {sha} got {got}')
        ap=SNAP/f'{slug}__{sha[:12]}.tar.gz'
        with open(ap,'wb') as fh:
            p=subprocess.run(['git','archive','--format=tar.gz',f'--prefix={slug}-{sha[:8]}/',sha],cwd=w,stdout=fh,stderr=subprocess.PIPE,timeout=300)
        if p.returncode!=0: raise RuntimeError(p.stderr.decode(errors='replace'))
        archive_by_key[(repo,sha)]=ap
qc=[]
for a in assign:
    rid=a['run_id']; pair=a['pair_id']; role='positive' if a['role']=='P0' else 'negative'
    t=next(x for x in tasks if x['pair_id']==pair and x['role']==role)
    task=SRC/'tasks'/t['task_file']; archive=archive_by_key[(t['repository'],t['base_sha'])]
    zp=OUT/f'{rid}_INPUT.zip'
    with zipfile.ZipFile(zp,'w',compression=zipfile.ZIP_STORED) as z:
        z.write(archive,'repo.tar.gz'); z.write(task,'TASK.md'); z.writestr('RUN_ID.txt',rid+'\n')
    qc.append({'run_id':rid,'chat_block':a['chat_block'],'bytes':zp.stat().st_size,'sha256':sha256(zp)})
shutil.copy2(SRC/'CALIBRATION_GENERATION_PROMPT.txt',OUT/'CALIBRATION_GENERATION_PROMPT.txt')
shutil.copy2(SRC/'PUBLIC_CHAT_BLOCKS.csv',OUT/'PUBLIC_CHAT_BLOCKS.csv')
with open(OUT/'INPUT_QC.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(qc[0])); w.writeheader(); w.writerows(qc)
master=OUT/'CALIBRATION_16_INPUTS.zip'
with zipfile.ZipFile(master,'w',compression=zipfile.ZIP_STORED) as z:
    z.write(OUT/'CALIBRATION_GENERATION_PROMPT.txt','CALIBRATION_GENERATION_PROMPT.txt')
    z.write(OUT/'PUBLIC_CHAT_BLOCKS.csv','PUBLIC_CHAT_BLOCKS.csv')
    z.write(OUT/'INPUT_QC.csv','INPUT_QC.csv')
    for a in assign:
        p=OUT/f"{a['run_id']}_INPUT.zip"; z.write(p,p.name)
print('CALIBRATION_BUILD_STATUS=PASS')
print('RUN_INPUTS=16')
print('SNAPSHOTS='+str(len(archive_by_key)))
print('MASTER='+str(master))
print('MASTER_SHA256='+sha256(master))
for row in qc: print(row['run_id'],row['chat_block'],row['sha256'])
PY_INNER_321
