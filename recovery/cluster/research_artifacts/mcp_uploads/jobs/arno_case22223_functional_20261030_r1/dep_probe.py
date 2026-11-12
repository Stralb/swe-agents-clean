#!/usr/bin/env python3
"""Isolated frozen-repo package-manager dependency probe; ignore lifecycle scripts."""
from pathlib import Path
import os,json,subprocess,zipfile,tempfile,shutil,stat,time
R=Path.home()/"research_artifacts"
OUT=R/"mcp_uploads/jobs/arno_case22223_functional_20261030_r1"
Z=R/"mcp_uploads/jobs/arno_v6_20261030_case22223_three_pilots/ready/ARNO_22223_A_MECHANISM_UPLOAD.zip"
NODE=Path.home()/"tools/node/bin/node"
PNPM=Path.home()/".cache/node/corepack/v1/pnpm/10.20.0/bin/pnpm.cjs"
B_PATCH=R/"mcp_uploads/jobs/arno_case22223_three_arm_eval_20261030_r1/results2/B/PATCH.patch"
data={"probe":"B dependency availability","pnpm_bin_exists":PNPM.exists(),"commands":[]}
def run(cmd,repo,timeout):
 start=time.monotonic()
 try:
  p=subprocess.run(list(map(str,cmd)),cwd=repo,capture_output=True,text=True,timeout=timeout,
   env={**os.environ,"PATH":str(NODE.parent)+":"+os.environ.get("PATH",""),"CI":"true","COREPACK_ENABLE_NETWORK":"0","COREPACK_ENABLE_PROJECT_SPEC":"0"})
  out={"cmd":" ".join(map(str,cmd)),"exit":p.returncode,"seconds":round(time.monotonic()-start,2),"stdout":p.stdout[-5000:],"stderr":p.stderr[-5000:]}
 except Exception as e:out={"cmd":" ".join(map(str,cmd)),"error":repr(e)}
 data["commands"].append(out)
 return out
with tempfile.TemporaryDirectory(prefix="arno_22223_depcheck_") as td:
 repo=Path(td)/"repo";repo.mkdir()
 with zipfile.ZipFile(Z) as z:
  for i in z.infolist():
   if i.is_dir() or not i.filename.startswith("REPO/"):continue
   rel=i.filename[5:];p=Path(rel)
   assert not p.is_absolute() and ".." not in p.parts and "\\" not in rel and (i.external_attr>>16)&0o170000!=stat.S_IFLNK
   target=repo/rel;target.parent.mkdir(parents=True,exist_ok=True)
   with z.open(i) as src,target.open("wb") as dest:shutil.copyfileobj(src,dest)
 data["patch_apply"]=run(["git","apply",B_PATCH],repo,20)
 if data["patch_apply"].get("exit")==0 and PNPM.exists():
  run([NODE,PNPM,"--version"],repo,30)
  run([NODE,PNPM,"install","--offline","--frozen-lockfile","--ignore-scripts","--config.manage-package-manager-versions=false"],repo,240)
(OUT/"DEP_PROBE.json").write_text(json.dumps(data,indent=2))
print(json.dumps(data,indent=2),flush=True)
