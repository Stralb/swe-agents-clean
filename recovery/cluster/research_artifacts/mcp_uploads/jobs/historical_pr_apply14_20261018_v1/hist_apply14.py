#!/usr/bin/env python3
"""Dataset-pinned historical PR reconstruction and apply checks. No repo code executed."""
from pathlib import Path,PurePosixPath
from contextlib import ExitStack
from datetime import datetime
import os,sqlite3,json,zipfile,subprocess,hashlib,tempfile,re,csv
P=Path.home()/"research_artifacts/prevention_pilot_phase2"
IDs=[668,3429,3581,6104,8152,8461,12344,15151,16633,20094,21682,22223,31207,32759]
job=os.environ["SLURM_JOB_ID"]
out=P/("hist_pr_apply14_job"+job);out.mkdir(exist_ok=False)
db=Path.home()/"new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.full3809-continuation.db"
con=sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True,timeout=60)
con.execute("PRAGMA query_only=ON");con.row_factory=sqlite3.Row
q=",".join("?" for _ in IDs)
links=con.execute("SELECT c.id AS cid,p.id AS pr_id,p.base_sha AS base_sha,p.head_sha AS head_sha,p.number AS pr_no FROM cases c JOIN pull_requests p ON p.id=c.pr_id WHERE c.id IN ("+q+") ORDER BY c.id",IDs).fetchall()
assert len(links)==14
res=[]
for x in links:
 cid=x["cid"];name="CASE_%05d"%cid
 dir=out/name;dir.mkdir()
 files=con.execute("SELECT filename,status,patch,additions,deletions FROM pr_files WHERE pr_id=? ORDER BY id",(x["pr_id"],)).fetchall()
 status=json.loads((P/"remaining65_archives_oct17_v1"/(name+".status.json")).read_text())
 assert status["base_sha"]==x["base_sha"]
 full=P/"remaining65_archives_oct17_v1"/(name+".zip")
 source=full if full.is_file() else P/"remaining65_targeted14_v1"/(name+".zip")
 source_type="FULL" if full.is_file() else "FILTERED"
 assert source.is_file()
 problems=[]
 patch_parts=[]
 missing_patch=[]
 for f in files:
  filename=f["filename"];kind=f["status"];fragment=f["patch"]
  parts=PurePosixPath(filename).parts
  if not filename or PurePosixPath(filename).is_absolute() or ".." in parts:
   raise ValueError("Unsafe path "+str(filename))
  if kind not in ("added","modified","removed"):
   problems.append("UNSUPPORTED_STATUS:"+kind+":"+filename);continue
  if not fragment:
   missing_patch.append(filename);continue
  header="diff --git a/"+filename+" b/"+filename+"\n"
  if kind=="added":header+="new file mode 100644\n--- /dev/null\n+++ b/"+filename+"\n"
  elif kind=="removed":header+="deleted file mode 100644\n--- a/"+filename+"\n+++ /dev/null\n"
  else:header+="--- a/"+filename+"\n+++ b/"+filename+"\n"
  if not fragment.startswith("@@"):problems.append("HUNK_FORMAT_INVALID:"+filename)
  patch_parts.append(header+fragment.rstrip("\n")+"\n")
 patch_text="".join(patch_parts)
 with (dir/"DATASET_PR_RECONSTRUCTED.patch").open("x",encoding="utf-8") as f:f.write(patch_text)
 entry={"case_id":cid,"PR":x["pr_no"],"base_sha":x["base_sha"],"head_sha_recorded":x["head_sha"],
    "source_type":source_type,"pr_files":len(files),"text_hunks":len(patch_parts),
    "missing_pr_patch_file_paths":missing_patch,"format_issues":problems,
    "patch_sha256":hashlib.sha256(patch_text.encode()).hexdigest(),
    "status":"UNTESTED","patch_from":"DATASET_PR_FILES_NOT_LIVE_GITHUB"}
 try:
  with tempfile.TemporaryDirectory(prefix="base_",dir=dir) as scratch:
   tree=Path(scratch)/"repo";tree.mkdir()
   total=0;count=0
   with zipfile.ZipFile(source) as z:
    for f in z.infolist():
     if not f.filename.startswith("REPO/") or f.is_dir():continue
     parts=PurePosixPath(f.filename).parts
     if ".." in parts or f.filename.startswith("/"):raise ValueError("ZIP_TRAVERSAL")
     nameparts=parts[1:]
     if not nameparts:continue
     count+=1;total+=f.file_size
     if count>80000 or total>900*1024*1024:raise RuntimeError("SOURCE_LIMIT")
     path=tree.joinpath(*nameparts);path.parent.mkdir(parents=True,exist_ok=True)
     path.write_bytes(z.read(f.filename))
   entry["source_files"]=count
   missing=[]
   for f in files:
    if f["status"] in ("modified","removed") and not (tree/f["filename"]).exists():
     missing.append(f["filename"])
   entry["missing_changed_existing_files"]=missing
   if problems or missing_patch:
    entry["status"]="INCOMPLETE_DATASET_PR_PATCH"
   elif missing:
    entry["status"]="BASE_FILES_MISSING"
   else:
    cmd=["git","apply","--check","--whitespace=nowarn",str(dir/"DATASET_PR_RECONSTRUCTED.patch")]
    chk=subprocess.run(cmd,cwd=tree,capture_output=True,text=True,timeout=180)
    entry["git_apply_check_exit"]=chk.returncode
    entry["git_apply_check_output"]=(chk.stderr+"\n"+chk.stdout)[:2000]
    if chk.returncode:
     entry["status"]="GIT_APPLY_CONFLICT"
    else:
     actual=subprocess.run(["git","apply","--whitespace=nowarn",str(dir/"DATASET_PR_RECONSTRUCTED.patch")],
       cwd=tree,capture_output=True,text=True,timeout=180)
     entry["git_apply_exit"]=actual.returncode
     entry["git_apply_output"]=(actual.stderr+"\n"+actual.stdout)[:1000]
     entry["status"]="APPLIED" if actual.returncode==0 else "GIT_APPLY_FAILED"
 except Exception as e:
  entry["status"]="ERROR";entry["exception"]=repr(e)[:700]
 with (dir/"RESULT.json").open("x") as f:json.dump(entry,f,indent=2);f.write("\n")
 res.append(entry)
 print("HIST_PR",cid,entry["status"],"hunks",entry["text_hunks"],"missing",len(entry["missing_pr_patch_file_paths"]),flush=True)
con.close()
with (out/"HIST14_SUMMARY.csv").open("x",newline="") as f:
 cols=["case_id","PR","source_type","pr_files","text_hunks","status","git_apply_check_exit","git_apply_exit"]
 w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader();w.writerows(res)
with (out/"HIST14_MANIFEST.json").open("x") as f:json.dump({"job_id":job,"source_database":str(db),
 "READ_ONLY_HISTORICAL_DATA":True,"historical_codeql_replayed":False,
 "functional_tests_executed":False,"results":res},f,indent=2);f.write("\n")
print("HIST_PR_DONE",len(res),{k:sum(v["status"]==k for v in res) for k in sorted({v["status"] for v in res})},flush=True)
