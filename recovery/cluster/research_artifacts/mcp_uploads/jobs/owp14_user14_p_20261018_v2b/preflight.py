#!/usr/bin/env python3
"""P-arm ZIP transfer verification and safe isolated git-apply preflight."""
from pathlib import Path, PurePosixPath
import os, re, csv, json, zipfile, base64, hashlib, tempfile, subprocess
ROOT=Path.home()/"research_artifacts"
PILOT=ROOT/"prevention_pilot_phase2"
OUT=PILOT/("owp14_user14_p_preflight_job"+os.environ["SLURM_JOB_ID"])
OUT.mkdir(parents=True,exist_ok=False)
INPUT=ROOT/"mcp_uploads/owp14_user_p14_20261018_transfer_v1"
enc="".join((INPUT/("chunk_%02d.txt"%i)).read_text("ascii").replace("\n","") for i in range(1,5))
raw=base64.b64decode(enc,validate=True)
sha=hashlib.sha256(raw).hexdigest()
assert len(raw)==34311 and sha=="ccae9ab03303e91d2231e1291766d4cb47159981053fc84a4182c5eba4851f67"
(OUT/"ALL_CASES_PATCHES_ORIGINAL.zip").write_bytes(raw)
PACK=PILOT/"owp14_allcases_packets_job71014"
with (PACK/"PACKET_INDEX.csv").open(newline="") as f:
 expected={(int(x["case_id"]),x["arm"]):x for x in csv.DictReader(f)}
ids={668,3429,3581,6104,8152,8461,12344,15151,16633,20094,21682,22223,31207,32759}
def sha_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(2*1024*1024),b""): h.update(b)
 return h.hexdigest()
def extract(zip_path,repo):
 files=0;bytes_total=0
 with zipfile.ZipFile(zip_path) as z:
  assert z.testzip() is None
  for e in z.infolist():
   if e.is_dir() or not e.filename.startswith("REPO/"):continue
   path=PurePosixPath(e.filename)
   assert len(path.parts)>1 and path.parts[0]=="REPO"
   assert ".." not in path.parts and ".git" not in path.parts
   assert ((e.external_attr>>16)&0o170000) not in (0o120000,0o060000)
   files+=1;bytes_total+=e.file_size
   assert files<=30000 and bytes_total<=2*1024**3
   dest=repo.joinpath(*path.parts[1:]);dest.parent.mkdir(parents=True,exist_ok=True)
   dest.write_bytes(z.read(e))
 return files
with zipfile.ZipFile(OUT/"ALL_CASES_PATCHES_ORIGINAL.zip") as z:
 assert z.testzip() is None
 names=z.namelist()
 assert len(names)==14 and len(set(names))==14
 assert {int(re.fullmatch(r"CASE_(\d{5})_P\.patch",n).group(1)) for n in names}==ids
 outcomes={}
 for name in sorted(names):
  cid=int(name.split("_")[1])
  rec={"case_id":cid,"arm":"P","filename":name,"stage":"START"}
  work=OUT/("CASE_%05d"%cid);work.mkdir()
  try:
   data=z.read(name)
   assert 100<len(data)<1000000 and data.startswith(b"diff --git a/")
   assert b"\x00" not in data and b"\r" not in data
   paths=re.findall(rb"^diff --git a/([^\n]+) b/([^\n]+)$",data,re.M)
   assert paths and b"new file mode 120000" not in data and b"old mode 120000" not in data
   for a,b in paths:
    for p in (a,b):
     seg=PurePosixPath(p.decode("utf-8"))
     assert not seg.is_absolute() and ".." not in seg.parts
     assert ".git" not in seg.parts and ".github" not in seg.parts
   patch=work/name;patch.write_bytes(data)
   rec.update({"original_patch_sha256":hashlib.sha256(data).hexdigest(),
    "original_patch_bytes":len(data),"changed_paths":[b.decode("utf8") for a,b in paths]})
   source=PACK/("CASE_%05d_P.zip"%cid)
   assert sha_file(source)==expected[(cid,"P")]["sha256"]
   rec["frozen_input_sha256"]=expected[(cid,"P")]["sha256"]
   rec["source_type"]=expected[(cid,"P")]["source_type"]
   scratch=PILOT/"owp14_user14_p_preflight_scratch";scratch.mkdir(exist_ok=True)
   with tempfile.TemporaryDirectory(prefix="CASE_%05d_"%cid,dir=scratch) as temp:
    repo=Path(temp)/"repo";repo.mkdir()
    rec["source_files"]=extract(source,repo)
    for label,command in [("applycheck",["git","apply","--check",str(patch)]),
                           ("apply",["git","apply",str(patch)])]:
     pr=subprocess.run(command,cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
       text=True,timeout=240,env={"HOME":str(work),"PATH":os.environ.get("PATH","/usr/bin:/bin"),
       "GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null","GIT_TERMINAL_PROMPT":"0"})
     (work/(label+".log")).write_text(pr.stdout)
     rec[label+"_returncode"]=pr.returncode
     if pr.returncode:break
    rec["patch_applied"]=rec.get("apply_returncode")==0
    rec["stage"]="APPLIED_IN_ISOLATED_COPY" if rec["patch_applied"] else "APPLY_FAILED"
  except Exception as e:
   rec["patch_applied"]=False;rec["stage"]="PREFLIGHT_ERROR";rec["error"]=repr(e)
  outcomes[str(cid)]=rec
  (work/"RESULT.json").write_text(json.dumps(rec,indent=2)+"\n")
  (OUT/"SUMMARY.json").write_text(json.dumps({"stage":"IN_PROGRESS","received":14,
      "verified_archive_sha256":sha,"cases":outcomes},indent=2)+"\n")
  print("PREFLIGHT_P",cid,rec["stage"],flush=True)
(OUT/"SUMMARY.json").write_text(json.dumps({"stage":"COMPLETE","received":14,
 "verified_archive_sha256":sha,"case_count_applied":sum(bool(v["patch_applied"]) for v in outcomes.values()),
 "cases":outcomes},indent=2)+"\n")
print("PREFLIGHT_COMPLETE",OUT,flush=True)
