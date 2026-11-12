#!/usr/bin/env python3
"""Offline runner for seven-case issue-only information-ablation screen."""
from pathlib import Path, PurePosixPath
import argparse, subprocess, zipfile, tempfile, shutil, json, hashlib, sys, datetime
ROOT=Path(__file__).resolve().parent.parent
CASES=("03429","03581","08152","12344","22223","31207","32759")
ARMS=("H1","H2","H3")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,cwd=None):
 x=subprocess.run([str(i) for i in args],cwd=cwd,capture_output=True,text=True)
 if x.returncode:raise RuntimeError("Command failed: "+str(args)+"\n"+x.stderr+"\n"+x.stdout[-1000:])
 return x.stdout
def taskdir(case,arm):
 assert case in CASES and arm in ARMS
 return ROOT/"WORKSPACE"/("CASE_"+case+"_"+arm+"_r01")
def source(case):return ROOT/"CASES"/case/("CASE_"+case+"_O_FROZEN.zip")
def issue(case):return (ROOT/"CASES"/case/"ISSUE_ORIGINAL.md").read_bytes()
def addon(case,arm):return (ROOT/"CASES"/case/("ADD_"+arm+".txt")).read_bytes()
def materialize(case,arm):
 dest=taskdir(case,arm)
 if dest.exists():raise RuntimeError("Refusing overwrite "+str(dest))
 dest.mkdir(parents=True)
 repo=dest/"WORK";repo.mkdir()
 with zipfile.ZipFile(source(case)) as z:
  for name in z.namelist():
   if not name.startswith("REPO/") or name.endswith("/"):continue
   bits=PurePosixPath(name).parts
   if len(bits)<2 or ".." in bits or bits[0]!="REPO":raise RuntimeError("Unsafe ZIP member "+name)
   p=repo.joinpath(*bits[1:]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
 combined=issue(case).rstrip()+b"\n\n"+addon(case,arm).rstrip()+b"\n"
 (dest/"TASK_ISSUE.md").write_bytes(combined)
 (dest/"RUN_NOTE.txt").write_text("ONLY change files under WORK/. The task is TASK_ISSUE.md in this directory. No scanner feedback. See case ACCEPTANCE.md.\n")
 run(["git","init","-q"],cwd=repo)
 run(["git","add","-A"],cwd=repo)
 run(["git","-c","user.name=Frozen baseline","-c","user.email=baseline@example.invalid","-c","commit.gpgsign=false","commit","-q","-m","Frozen input"],cwd=repo)
 m={"case":case,"arm":arm,"source_archive_sha256":sha(source(case)),"original_issue_sha256":hashlib.sha256(issue(case)).hexdigest(),"addon_sha256":hashlib.sha256(addon(case,arm)).hexdigest(),"combined_issue_sha256":hashlib.sha256(combined).hexdigest(),"case_task_path":str(dest.relative_to(ROOT)),"functional_status":"NOT_YET_EVALUATED","codeql_status":"NOT_RUN"}
 (dest/"INPUT_MANIFEST.json").write_text(json.dumps(m,indent=2)+"\n")
 print("PREPARED",dest,"=> TASK_ISSUE.md and WORK/")
def export(case,arm):
 dest=taskdir(case,arm);repo=dest/"WORK"
 if not (repo/".git").exists():raise RuntimeError("Run prepare first")
 run(["git","add","-A"],cwd=repo)
 patch=run(["git","diff","--cached","--binary","--no-ext-diff","HEAD"],cwd=repo)
 if not patch.strip():raise RuntimeError("Empty patch: required implementation not produced")
 out=ROOT/"OUTPUT";(out/"patches").mkdir(parents=True,exist_ok=True)
 pname="CASE_"+case+"_"+arm+"_r01.patch";p=out/"patches"/pname;p.write_bytes(patch.encode())
 with tempfile.TemporaryDirectory(prefix="ablation_check_") as d:
  target=Path(d)
  with zipfile.ZipFile(source(case)) as z:
   for name in z.namelist():
    if name.startswith("REPO/") and not name.endswith("/"):
     parts=PurePosixPath(name).parts
     q=target.joinpath(*parts[1:]);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(z.read(name))
  run(["git","apply","--check",str(p.resolve())],cwd=target)
 changed=run(["git","diff","--cached","--name-only","HEAD"],cwd=repo).strip().splitlines()
 m=json.loads((dest/"INPUT_MANIFEST.json").read_text())
 m.update({"patch_file":str(p.relative_to(ROOT)),"patch_sha256":sha(p),"patch_bytes":p.stat().st_size,"modified_files":changed,"codeql_status":"NOT_RUN","functional_status":"REQUIRES_INDEPENDENT_VALIDATION"})
 (out/("CASE_"+case+"_"+arm+"_r01.json")).write_text(json.dumps(m,indent=2)+"\n")
 print("EXPORTED",p,"patch_bytes",p.stat().st_size,"changed",len(changed))
def pack(allow_partial):
 output=ROOT/"OUTPUT";found=[];missing=[]
 for case in CASES:
  for arm in ARMS:
   tag="CASE_"+case+"_"+arm+"_r01"
   patch=output/"patches"/(tag+".patch")
   log=output/"runlogs"/(tag+"_runlog.txt")
   meta=output/(tag+".json")
   if not patch.is_file() or not meta.is_file() or not log.is_file():
    missing.append({"task":tag,"patch":patch.is_file(),"runlog":log.is_file(),"metadata":meta.is_file()})
   else:
    x=json.loads(meta.read_text())
    assert x["patch_sha256"]==sha(patch)
    found.append(x)
 if missing and not allow_partial:
  print(json.dumps({"ready":len(found),"missing":missing},indent=2))
  raise RuntimeError("Incomplete: finish all 21 patches + real runlogs, or pass --allow-partial and label the submission PARTIAL")
 submission=ROOT/"ALL_7_CASE_MININFO_PATCHES_FOR_WITS.zip"
 with zipfile.ZipFile(submission,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
  for item in found:
   tag="CASE_"+item["case"]+"_"+item["arm"]+"_r01"
   for p in [output/"patches"/(tag+".patch"), output/"runlogs"/(tag+"_runlog.txt"),output/(tag+".json")]:
    z.write(p,p.relative_to(output).as_posix())
  z.writestr("RUN_MANIFEST.json",json.dumps({"study":"Seven case, 3 add-only levels per case, screening without CodeQL feedback","expected_runs":21,"included_runs":len(found),"missing":missing,"complete":not bool(missing),"results":found},indent=2)+"\n")
 print("DONE",submission,"included",len(found),"/21; SHA256",sha(submission))
def main():
 p=argparse.ArgumentParser()
 p.add_argument("action",choices=["prepare","export","pack","status","prepare-all"])
 p.add_argument("--case",choices=CASES)
 p.add_argument("--arm",choices=ARMS)
 p.add_argument("--allow-partial",action="store_true")
 a=p.parse_args()
 if a.action=="prepare-all":
  for case in CASES:
   for arm in ARMS:materialize(case,arm)
 elif a.action in ("prepare","export"):
  if not a.case or not a.arm:p.error("Required --case and --arm")
  (materialize if a.action=="prepare" else export)(a.case,a.arm)
 elif a.action=="status":
  for c in CASES:
   for arm in ARMS:
    tag="CASE_"+c+"_"+arm+"_r01"
    print(tag, "patch" if (ROOT/"OUTPUT"/"patches"/(tag+".patch")).exists() else "MISSING", "log" if (ROOT/"OUTPUT"/"runlogs"/(tag+"_runlog.txt")).exists() else "NOLOG")
 elif a.action=="pack":pack(a.allow_partial)
if __name__=="__main__":main()
