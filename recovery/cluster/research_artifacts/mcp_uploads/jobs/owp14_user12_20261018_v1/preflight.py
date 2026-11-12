#!/usr/bin/env python3
"""Byte-verified transfer and read-only-to-source patch application preflight for 12 user O patches."""
import base64,csv,hashlib,json,os,re,subprocess,sys,tempfile,shutil,zipfile
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
ROOT=Path.home()/"research_artifacts"
PILOT=ROOT/"prevention_pilot_phase2"
JOB=os.environ["SLURM_JOB_ID"]
OUT=PILOT/("owp14_user12_o_preflight_job"+JOB)
OUT.mkdir(parents=True,exist_ok=False)
TRANSFER=ROOT/"mcp_uploads/owp14_20261018_transfer_v1"
archive_bytes=b""
chunks=[]
for i in range(1,7):
 f=TRANSFER/("chunk_%02d.txt"%i)
 s=f.read_text("ascii")
 part="".join(s.splitlines())
 assert len(part)<=12000 and all(c.isalnum() or c in "+/=" for c in part),(i,"INVALID_BASE64_CHUNK")
 chunks.append(part)
b64="".join(chunks)
archive_bytes=base64.b64decode(b64,validate=True)
transfer_sha=hashlib.sha256(archive_bytes).hexdigest()
assert len(archive_bytes)==51838,("archive bytes",len(archive_bytes))
assert transfer_sha=="a9b6965de4d246d1b7a6765e71ac50d3f578440d6678f53bedea4d1f84aaf85f",("zip sha",transfer_sha)
incoming=OUT/"all_case_patches_original.zip";incoming.write_bytes(archive_bytes)
SOURCE=PILOT/"owp14_allcases_packets_job71014"
with (SOURCE/"PACKET_INDEX.csv").open(newline="") as f:
 inputs={(int(r["case_id"]),r["arm"]):r for r in csv.DictReader(f)}
expected_cases={668,3429,3581,6104,8152,12344,16633,20094,21682,22223,31207,32759}
def filehash(p):
 h=hashlib.sha256()
 with p.open("rb") as fd:
  for chunk in iter(lambda:fd.read(2*1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def git_command(args,cwd,output,timeout=300):
 env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),
   "HOME":str(output.parent),"GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null",
   "GIT_OPTIONAL_LOCKS":"0","GIT_TERMINAL_PROMPT":"0","LC_ALL":"C","LANG":"C"}
 try:
  p=subprocess.run(["git",*args],cwd=cwd,env=env,timeout=timeout,
      stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors="replace")
  output.write_text(p.stdout)
  return p.returncode
 except Exception as exc:
  output.write_text("ERROR "+repr(exc))
  return 124 if isinstance(exc,subprocess.TimeoutExpired) else 127
def extract_to_repo(archive,repo):
 count=0;total=0
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  assert "ISSUE.md" in z.namelist()
  for member in z.infolist():
   name=member.filename
   if not name.startswith("REPO/") or member.is_dir():continue
   rel=PurePosixPath(name)
   assert len(rel.parts)>1 and rel.parts[0]=="REPO"
   assert ".." not in rel.parts and ".git" not in rel.parts
   assert (member.external_attr>>16)&0o170000 not in [0o120000,0o060000]
   count+=1;total+=member.file_size
   assert count<=30000 and total<2*1024**3,(count,total)
   p=repo.joinpath(*rel.parts[1:]);p.parent.mkdir(parents=True,exist_ok=True)
   p.write_bytes(z.read(member))
 return count,total
data={}
with zipfile.ZipFile(incoming) as userzip:
 assert userzip.testzip() is None
 names=userzip.namelist()
 assert len(names)==12 and len(set(names))==12
 cases=[]
 for name in names:
  match=re.fullmatch(r"CASE_(\d{5})_O\.patch",name)
  assert match,("BAD_PATCH_FILENAME",name)
  cases.append(int(match.group(1)))
 assert set(cases)==expected_cases,(sorted(cases),sorted(expected_cases))
 for name in names:
  cid=int(name.split("_")[1])
  rec={"case_id":cid,"arm":"O","filename":name,"stage":"PREFLIGHT_STARTED"}
  caseout=OUT/("CASE_%05d"%cid);caseout.mkdir()
  patch=userzip.read(name)
  assert len(patch)>100 and len(patch)<1000000 and patch.startswith(b"diff --git a/"),("INVALID_PATCH",name)
  assert b"\x00" not in patch and b"\r" not in patch
  matches=re.findall(rb"^diff --git a/([^\n]+) b/([^\n]+)$",patch,re.M)
  assert matches,("NO_DIFF_HEADERS",name)
  for left,right in matches:
   for item in (left,right):
    path=PurePosixPath(item.decode("utf-8"))
    assert not path.is_absolute() and ".." not in path.parts
    assert ".git" not in path.parts and ".github" not in path.parts
  assert b"new file mode 120000" not in patch and b"old mode 120000" not in patch
  pfile=caseout/name;pfile.write_bytes(patch)
  rec.update({"original_patch_sha256":hashlib.sha256(patch).hexdigest(),
      "original_patch_bytes":len(patch),
      "changed_paths":[r.decode("utf-8") for _,r in matches],
      "diff_file_count":len(matches)})
  source=SOURCE/("CASE_%05d_O.zip"%cid)
  expected=inputs[(cid,"O")]
  assert source.exists() and filehash(source)==expected["sha256"],("FROZEN_SOURCE_HASH_MISMATCH",cid)
  rec["frozen_input_sha256"]=expected["sha256"]
  rec["source_type"]=expected["source_type"]
  scratchroot=PILOT/"owp14_user12_preflight_scratch"
  scratchroot.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(prefix="CASE_%05d_"%cid,dir=scratchroot) as tmp:
   repo=Path(tmp)/"repo";repo.mkdir()
   try:
    count,nbytes=extract_to_repo(source,repo)
    rec["source_files"]=count;rec["source_bytes"]=nbytes
    code=git_command(["apply","--check",str(pfile)],repo,caseout/"git_apply_check.log")
    rec["git_apply_check_returncode"]=code
    rec["patch_applies"]=code==0
    if code==0:
     apply=git_command(["apply",str(pfile)],repo,caseout/"git_apply.log")
     rec["git_apply_returncode"]=apply
     rec["patch_applied"]=apply==0
     if apply==0:
      rec["stage"]="APPLIED_IN_ISOLATED_COPY"
     else:rec["stage"]="APPLY_FAILED"
    else:rec["stage"]="APPLY_CHECK_FAILED"
   except Exception as exc:
    rec["stage"]="PREFLIGHT_ERROR";rec["error"]=repr(exc)
  (caseout/"RESULT.json").write_text(json.dumps(rec,indent=2)+"\n")
  data[str(cid)]=rec
  (OUT/"SUMMARY.json").write_text(json.dumps({"stage":"IN_PROGRESS",
      "received":len(names),"verified_archive_sha256":transfer_sha,
      "cases":data},indent=2)+"\n")
  print("PREFLIGHT",cid,rec["stage"],rec.get("git_apply_check_returncode"),rec["source_type"],flush=True)
(OUT/"SUMMARY.json").write_text(json.dumps({"stage":"COMPLETE",
  "received":len(names),"verified_archive_sha256":transfer_sha,
  "case_count_applied":sum(bool(v.get("patch_applied")) for v in data.values()),
  "case_count_apply_failed":sum(v["stage"]=="APPLY_CHECK_FAILED" for v in data.values()),
  "cases":data},indent=2)+"\n")
print("PREFLIGHT_COMPLETE",OUT,flush=True)
