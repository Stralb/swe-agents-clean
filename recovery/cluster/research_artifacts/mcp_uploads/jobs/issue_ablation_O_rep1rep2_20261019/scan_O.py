#!/usr/bin/env python3
from pathlib import Path,PurePosixPath
from collections import Counter
import hashlib,zipfile,json,subprocess,tempfile,shutil,os,traceback,time,sys
home=Path.home()/"research_artifacts"
source_dir=home/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
prior=home/"prevention_pilot_phase2/mininfo_3x4_scan_job71825"
inputs=home/"mcp_uploads/issue_ablation_O_rep1rep2_20261019"
output=home/("prevention_pilot_phase2/issue_ablation_O_scans_job"+os.environ.get("SLURM_JOB_ID","unknown"))
output.mkdir(parents=True,exist_ok=False)
scanner=Path.home()/"tools/codeql/codeql"
suite="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
cases={
"03429":{"zipsha":"a42f6b1db690ae6c5734cb7a3e66c179a62f02e3afb8fc55a389fbbbe63c04d0","baseline":42,"rep1":"d13e9d992a64403da943c806eb1e3ce50f48c719d074bfb3d8bf8683f223b16d","rep2":"afc597437cf0581c52da2da02a3254e2ebd5ab3744da71e1a404f4953428c60b"},
"03581":{"zipsha":"b223cc0f9cfb477c9f1d087bffc13d32ea34d1a125761a0fe65cc1038a38ae07","baseline":82,"rep1":"81cecfd53cc390d853bc5d6bb34935b6cbd3e8d0ec10e7388f7009642e3e2399","rep2":"514a9f8a8be2eabd905c00ed3e0b842ae37cae43a7e36033608fc6f9157af711"}}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert "2.25.6" in subprocess.check_output([str(scanner),"version"],text=True)
def run(label,cmd,cwd):
 start=time.monotonic()
 with (output/(label+".log")).open("w") as f:
  r=subprocess.run([str(x) for x in cmd],cwd=str(cwd),stdout=f,stderr=subprocess.STDOUT,timeout=2100)
 if r.returncode:raise RuntimeError(label+" rc="+str(r.returncode))
 return round(time.monotonic()-start,2)
def alerts(path):
 rows=[]
 for r in json.loads(path.read_text()).get("runs",[]):
  for x in r.get("results",[]):
   loc=(x.get("locations") or [{}])[0].get("physicalLocation",{})
   rows.append({"rule":x.get("ruleId",""),"path":loc.get("artifactLocation",{}).get("uri",""),"line":loc.get("region",{}).get("startLine"),"message":x.get("message",{}).get("text",""),"fp":x.get("partialFingerprints") or {}})
 return rows
def fresh(before,after,strong):
 def key(x):
  if strong:return (x["rule"],x["path"],x["fp"].get("primaryLocationLineHash") or x["message"],x["fp"].get("primaryLocationStartColumnFingerprint") or "")
  return (x["rule"],x["path"],x["message"])
 count=Counter(map(key,before))
 result=[]
 for x in after:
  k=key(x)
  if count[k]:count[k]-=1
  else:result.append({n:v for n,v in x.items() if n!="fp"})
 return result
scratch=Path(tempfile.mkdtemp(prefix="issueabl_o_",dir=os.environ.get("SLURM_TMPDIR") or "/tmp"))
results=[]
try:
 for case,spec in cases.items():
  zippath=source_dir/("CASE_"+case+"_O.zip")
  assert sha(zippath)==spec["zipsha"],"FROZEN_SOURCE_MISMATCH "+case
  base=prior/(case+"_baseline.sarif")
  assert base.is_file()
  before=alerts(base)
  assert len(before)==spec["baseline"],"BASELINE_DIFF "+case
  repo=scratch/(case+"_source");repo.mkdir()
  with zipfile.ZipFile(zippath) as z:
   names=[name for name in z.namelist() if name.startswith("REPO/") and not name.endswith("/")]
   for name in names:
    bits=PurePosixPath(name).parts
    assert len(bits)>1 and bits[0]=="REPO" and ".." not in bits
    p=repo.joinpath(*bits[1:]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
  for rep in (1,2):
   label=case+"_O_rep"+str(rep)
   rec={"case":case,"condition":"O","replicate":rep,"state":"START","source_sha256":spec["zipsha"],"baseline_count":len(before),"scanner_version":"2.25.6","suite":suite,"functional_status":"UNVERIFIED"}
   try:
    if case=="03429":
     patchdata=(inputs/("CASE_"+label+".patch.txt")).read_bytes()
    else:
     parts=[inputs/("CASE_"+label+".patch.part"+str(i)+".txt") for i in (0,1,2)]
     patchdata=b"".join(part.read_bytes() for part in parts)
    patch=output/(label+".patch");patch.write_bytes(patchdata)
    assert sha(patch)==spec["rep"+str(rep)],"PATCH_SHA256_MISMATCH"
    rec["patch_sha256"]=sha(patch)
    candidate=scratch/label;shutil.copytree(repo,candidate)
    rec["apply_check_seconds"]=run(label+"_apply_check",["git","apply","--check",patch],candidate)
    rec["apply_seconds"]=run(label+"_apply",["git","apply",patch],candidate)
    db=scratch/(label+"_db")
    rec["database_seconds"]=run(label+"_db",[scanner,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(candidate),"--threads=3","--ram=10000"],candidate)
    after_file=output/(label+"_after.sarif")
    rec["scan_seconds"]=run(label+"_scan",[scanner,"database","analyze",db,suite,"--format=sarif-latest","--output="+str(after_file),"--threads=3","--ram=10000"],candidate)
    after=alerts(after_file)
    strong=fresh(before,after,True);weak=fresh(before,after,False)
    rec.update(state="SCAN_COMPLETE",after_count=len(after),new_strong_count=len(strong),new_conservative_count=len(weak),new_strong=strong,new_conservative=weak)
   except Exception as e:
    rec.update(state="ERROR",error=repr(e),traceback=traceback.format_exc()[-2000:])
   results.append(rec)
   (output/(label+"_RESULT.json")).write_text(json.dumps(rec,indent=2)+"\n")
   (output/"SUMMARY.json").write_text(json.dumps(results,indent=2)+"\n")
   print(label,rec["state"],rec.get("new_strong_count"),rec.get("error",""),flush=True)
finally:
 shutil.rmtree(scratch,ignore_errors=True)
