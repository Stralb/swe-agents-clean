#!/bin/bash
#SBATCH --job-name=case21942baseQA
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:15:00
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
from pathlib import Path
import hashlib,subprocess,os,tarfile,urllib.request,pathlib,shutil,json,tempfile
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
O=R/("case21942_p1_base_qa_job"+os.environ["SLURM_JOB_ID"]);O.mkdir()
TMP=Path(tempfile.mkdtemp(prefix="case21942_bQA_",dir=os.environ.get("SLURM_TMPDIR") or "/tmp"))
URL="https://codeload.github.com/Soul-Brews-Studio/arra-oracle-skills-cli/tar.gz/639150316e6f14cdc78e7dba8c6263504895b2e1"
with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"WitsResearch"}),timeout=150) as f,(TMP/"base.tar.gz").open("xb") as t:shutil.copyfileobj(f,t)
archive=TMP/"base.tar.gz";assert hashlib.sha256(archive.read_bytes()).hexdigest()=="e9ad762c91e49756f0ace64ccb3678af8711d2c304b5d110f2871f994bad6aec"
root=TMP/"base";root.mkdir()
with tarfile.open(archive) as t:
 for m in t:
  parts=pathlib.PurePosixPath(m.name).parts
  if len(parts)<2:continue
  rel=pathlib.PurePosixPath(*parts[1:])
  assert ".." not in rel.parts and not rel.is_absolute()
  path=root.joinpath(*rel.parts)
  if m.isdir():path.mkdir(parents=True,exist_ok=True)
  elif m.isfile():
   path.parent.mkdir(parents=True,exist_ok=True)
   with t.extractfile(m) as f,path.open("xb") as o:shutil.copyfileobj(f,o)
  elif m.issym():
   assert not pathlib.PurePosixPath(m.linkname).is_absolute()
   path.parent.mkdir(parents=True,exist_ok=True);os.symlink(m.linkname,path)
  else:raise Exception('Unsupported')
results={}
for name,command in [
 ("install",[str(Path.home()/".bun/bin/bun"),"install","--ignore-scripts","--frozen-lockfile"]),
 ("focused",[str(Path.home()/".bun/bin/bun"),"test","__tests__/codex-plugin.test.ts"]),
 ("full",[str(Path.home()/".bun/bin/bun"),"test","__tests__/"]),
 ("typecheck",[str(Path.home()/".bun/bin/bun"),"x","tsc","--noEmit"])
]:
 with (O/(name+".log")).open("x") as out:
  p=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,cwd=root,timeout=420)
 results[name]={"exit":p.returncode,"log":name+".log"}
 print("RESULT",name,p.returncode,flush=True)
(O/"RESULT.json").write_text(json.dumps(results,indent=2))
PY
