#!/bin/bash
#SBATCH --job-name=case21942G
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --time=01:00:00
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
from pathlib import Path
import os, hashlib, json, subprocess, tempfile, tarfile, pathlib, shutil, urllib.request, time, re, zipfile
JOB=os.environ["SLURM_JOB_ID"]
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2"
OUT=ROOT/("case21942_GW_G_eval_job"+JOB)
OUT.mkdir(exist_ok=True)
STAGE=Path.home()/"research_artifacts/mcp_uploads/jobs/c21942-final-GW-20261017-v1"
SOURCE="https://codeload.github.com/Soul-Brews-Studio/arra-oracle-skills-cli/tar.gz/639150316e6f14cdc78e7dba8c6263504895b2e1"
EXPECTED_SOURCE="e9ad762c91e49756f0ace64ccb3678af8711d2c304b5d110f2871f994bad6aec"
EXPECTED_PATCH="a9817c6b554545044a7212caf78b597ba9de25fba32351b21a4161ebc06ff99f"
RULE="js/insecure-temporary-file"
RESULT={"case_id":21942,"arm":"G","codeql_rule":RULE,"state":"STARTED","evaluations":[]}
def save():(OUT/"RESULT.json").write_text(json.dumps(RESULT,indent=2,ensure_ascii=False)+"\n")
def sha(f):
 h=hashlib.sha256()
 with Path(f).open("rb") as fi:
  for b in iter(lambda:fi.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def run(name,args,cwd,timeout=1200):
 log=OUT/(name+".log")
 item={"name":name,"cmd":list(map(str,args)),"status":None,"log":log.name}
 try:
  with log.open("x") as f:
   p=subprocess.run(list(map(str,args)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  item["status"]=p.returncode
 except Exception as err:
  item["error"]=repr(err)[:500]
 RESULT["evaluations"].append(item);save()
 print("STEP",name,item.get("status"),flush=True)
 return item.get("status")==0
def download(url,path):
 for attempt in range(3):
  try:
   request=urllib.request.Request(url,headers={"User-Agent":"Wits-Research-Case21942-G"})
   with urllib.request.urlopen(request,timeout=120) as f,path.open("xb") as o:
    n=0
    while True:
     b=f.read(1048576)
     if not b:break
     n+=len(b)
     if n>50_000_000:raise ValueError("Archive too big")
     o.write(b)
   return
  except Exception:
   path.unlink(missing_ok=True)
   if attempt==2:raise
   time.sleep(5)
def unpack(path,target):
 target.mkdir()
 with tarfile.open(path,"r:gz") as tar:
  for member in tar:
   a=pathlib.PurePosixPath(member.name).parts
   if len(a)<2:continue
   rel=pathlib.PurePosixPath(*a[1:])
   if ".." in rel.parts or rel.is_absolute() or chr(92) in str(rel):raise ValueError("Unsafe path")
   dest=target.joinpath(*rel.parts)
   if member.isdir():dest.mkdir(parents=True,exist_ok=True)
   elif member.isfile():
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tar.extractfile(member) as fi,dest.open("xb") as fo:shutil.copyfileobj(fi,fo)
   elif member.issym():
    assert not pathlib.PurePosixPath(member.linkname).is_absolute()
    assert os.path.commonpath([str(target.resolve()),str((dest.parent/member.linkname).resolve())])==str(target.resolve())
    dest.parent.mkdir(parents=True,exist_ok=True)
    os.symlink(member.linkname,dest)
   else:raise ValueError("Unsupported source member")
def scan(label,repo,query,workspace):
 db=workspace/("codeql_"+label)
 sarif=OUT/(label+".sarif")
 if not run(label+"_create",[codeql,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(repo),"--threads=4","--ram=14500"],repo,2400):return None
 if not run(label+"_analyze",[codeql,"database","analyze",db,query,"--format=sarif-latest","--output="+str(sarif),"--threads=4","--ram=14500"],repo,1200):return None
 doc=json.loads(sarif.read_text())
 hits=[]
 for rr in doc.get("runs",[]):
  for e in rr.get("results",[]):
   if e.get("ruleId")!=RULE:continue
   loc=(e.get("locations") or [{}])[0].get("physicalLocation",{})
   fp=e.get("partialFingerprints",{})
   hits.append({"file":loc.get("artifactLocation",{}).get("uri",""),"line":loc.get("region",{}).get("startLine"),
   "fingerprint":fp.get("primaryLocationLineHash"),"column":fp.get("primaryLocationStartColumnFingerprint")})
 return hits
def delta(old,new):
 oldset={(a["file"],a["fingerprint"],a["column"]) for a in old}
 return [a for a in new if (a["file"],a["fingerprint"],a["column"]) not in oldset]
save()
try:
 scratch=Path(tempfile.mkdtemp(prefix="case21942G_"+JOB+"_",dir=os.environ.get("SLURM_TMPDIR") or "/tmp"))
 patch=OUT/"CASE21942_G.patch"
 for i in range(2):
  if not run("write_patch_"+str(i),["python3",STAGE/("armG_p"+str(i)+".py"),patch],OUT,30):raise RuntimeError("patch reconstruction")
 RESULT["patch_sha256"]=sha(patch)
 assert RESULT["patch_sha256"]==EXPECTED_PATCH,"Patch bytes do not match upload"
 tarball=scratch/"base.tar.gz"
 download(SOURCE,tarball)
 assert sha(tarball)==EXPECTED_SOURCE,"Source mismatch"
 base=scratch/"base";unpack(tarball,base)
 treated=scratch/"treated";shutil.copytree(base,treated,symlinks=True)
 RESULT["applies"]=run("git_apply_check",["git","apply","--check",patch],treated,80)
 if not RESULT["applies"]:raise RuntimeError("Patch does not apply")
 assert run("git_apply",["git","apply",patch],treated,80)
 original=patch.read_text()
 RESULT["changed_files"]=re.findall(r"^\+\+\+ b/(\S+)",original,re.M)
 codeql=str(Path.home()/"tools/codeql/codeql")
 query=Path.home()/".codeql/packages/codeql/javascript-queries/2.3.11/Security/CWE-377/InsecureTemporaryFile.ql"
 assert query.is_file() and ("@id "+RULE) in query.read_text()
 RESULT["query_sha256"]=sha(query)
 before=scan("base",base,query,scratch)
 after=scan("G",treated,query,scratch)
 RESULT["base_count"]=len(before) if before is not None else None
 RESULT["G_count"]=len(after) if after is not None else None
 if before is None or after is None:raise RuntimeError("CodeQL failed")
 introduced=delta(before,after)
 RESULT["G_new_findings"]=introduced
 modified=set(RESULT["changed_files"])
 RESULT["new_in_changed_files"]=[x for x in introduced if x["file"] in modified or any(x["file"].endswith("/"+k) for k in modified)]
 RESULT["base_finding_locations"]=before
 RESULT["G_finding_locations"]=after
 save()
 bun=str(Path.home()/".bun/bin/bun")
 RESULT["frozen_install"]=run("bun_install",[bun,"install","--ignore-scripts","--frozen-lockfile"],treated,420)
 if RESULT["frozen_install"]:
  RESULT["focused_tests"]=run("codex_focused_tests",[bun,"test","__tests__/codex-plugin.test.ts"],treated,500)
  RESULT["full_suite"]=run("full_bun_suite",[bun,"test","__tests__/"],treated,900)
  RESULT["typecheck"]=run("typecheck",[bun,"x","tsc","--noEmit"],treated,400)
 RESULT["state"]="COMPLETE"
 save()
 print("FINAL",json.dumps({k:RESULT.get(k) for k in ["applies","base_count","G_count","G_new_findings","new_in_changed_files","focused_tests","full_suite","typecheck"]}),flush=True)
except Exception as e:
 RESULT["state"]="ERROR";RESULT["error"]=repr(e)[:1200];save()
 print("ERROR",repr(e),flush=True)
finally:
 try:
  bundle=OUT/"CASE21942_G_EVIDENCE.zip"
  with zipfile.ZipFile(bundle,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
   for file in sorted(OUT.glob("*")):
    if file.is_file() and file!=bundle:z.write(file,file.name)
  print("BUNDLE",str(bundle),"HASH",sha(bundle),flush=True)
 except Exception as e:print("BUNDLE_ERROR",repr(e),flush=True)
PY
