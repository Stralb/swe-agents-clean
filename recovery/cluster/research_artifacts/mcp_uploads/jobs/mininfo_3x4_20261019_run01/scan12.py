#!/usr/bin/env python3
"""Paired source/patch CodeQL 2.25.6 scans for three cases x four prompt arms."""
from pathlib import Path,PurePosixPath
from collections import Counter
import os,json,hashlib,zipfile,subprocess,tempfile,shutil,traceback,time,re
home=Path.home()/"research_artifacts"
frozen=home/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
stage=home/"mcp_uploads/jobs/mininfo_3x4_20261019_run01"
out=home/("prevention_pilot_phase2/mininfo_3x4_scan_job"+os.environ.get("SLURM_JOB_ID","unknown"))
out.mkdir(parents=True,exist_ok=False)
codeql=Path.home()/"tools/codeql/codeql"
suite="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
hashes={
"03429":{"source":"a42f6b1db690ae6c5734cb7a3e66c179a62f02e3afb8fc55a389fbbbe63c04d0","patch":{"C0":"879e4dfc48ec3211b61da789b0875bc2686045696e94dbd0cea4f092860c5f6e","C1":"8d8b1154cbff0474093b7b3ce74c04a17e6f14ffa0522fd58fe7e0b5168fca59","C2":"3e13f794b269c754de2cbe5cbc0169f5ce61abafa6b3305192eb1f02e65b0566","C3":"b45d4af230578fa6f021f7a885826dc511defdf1c8e4af9511f4161baac2d759"},"parts":2},
"03581":{"source":"b223cc0f9cfb477c9f1d087bffc13d32ea34d1a125761a0fe65cc1038a38ae07","patch":{"C0":"e8784ebf8d94973d9aa0f88d82e0f6114503bdd8d8ce8a533f29d68fb2e4843c","C1":"556f7c57be39d8216fdd4ff9c026ee267376adb12b4fc57d5689df8a26e1f7c7","C2":"9ea3e32c77bc0c0fcb1ee28620bd0fb61c034dcd652f77a88fa0c0236e4e60d5","C3":"d53ebbe4dbf4f7a0aa7cb032400750ab1b576385ab519cddbe8f3cf91fe27cc8"},"parts":3},
"32759":{"source":"2dce5a0132cadb85b779cdb032e81b5aadc95bfafce391e8437916fb400399f2","patch":{"C0":"6f6e8a5e35b4f462ab46a335faff581ee1cb6c8967edef28ae4a64fb8b5c95c0","C1":"350119c3050cc8c5427a6d3b5ab2162c5388238082b7ccbd51e539bc0385aca2","C2":"363d2f088ce54325ac3a985fedbff7579828cb059b7ae6d6541b960f3044405a","C3":"2ce2f2a0d136d432316ce9d6a939102016d3c528879478b7fee2c33f19de9f1c"},"parts":1}}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
def cmd(label,args,cwd):
 t=time.monotonic()
 with (out/(label+".log")).open("w") as log:
  r=subprocess.run([str(x) for x in args],cwd=str(cwd),stdout=log,stderr=subprocess.STDOUT,timeout=2400)
 return {"rc":r.returncode,"seconds":round(time.monotonic()-t,2)}
def must(label,args,cwd):
 r=cmd(label,args,cwd)
 if r["rc"]:raise RuntimeError(label+" failed rc="+str(r["rc"]))
 return r
def alerts(path):
 rows=[]
 for run in json.loads(path.read_text()).get("runs",[]):
  for x in run.get("results",[]):
   loc=(x.get("locations") or [{}])[0].get("physicalLocation",{})
   rows.append({"rule":x.get("ruleId",""),"path":loc.get("artifactLocation",{}).get("uri",""),"line":loc.get("region",{}).get("startLine"),"message":x.get("message",{}).get("text",""),"fp":x.get("partialFingerprints") or {}})
 return rows
def diff_alerts(before,after,strong):
 def key(x):
  if strong:return (x["rule"],x["path"],x["fp"].get("primaryLocationLineHash") or x["message"],x["fp"].get("primaryLocationStartColumnFingerprint") or "")
  return (x["rule"],x["path"],x["message"])
 count=Counter(key(x) for x in before);added=[]
 for x in after:
  k=key(x)
  if count[k]:count[k]-=1
  else:added.append({a:b for a,b in x.items() if a!="fp"})
 return added
assert codeql.is_file()
assert "2.25.6" in subprocess.check_output([str(codeql),"version"],text=True)
scratch=Path(tempfile.mkdtemp(prefix="mininfo_",dir=os.environ.get("SLURM_TMPDIR") or "/tmp"))
records=[]
try:
 for case,spec in hashes.items():
  src=frozen/("CASE_"+case+"_O.zip")
  caseinfo={"case":case,"stage":"BASELINE_START","source_sha256":spec["source"],"codeql_version":"2.25.6","suite":suite}
  case_dir=scratch/case;case_dir.mkdir()
  root=case_dir/"baseline";root.mkdir()
  try:
   assert sha(src)==spec["source"],"SOURCE_ARCHIVE_HASH_MISMATCH"
   with zipfile.ZipFile(src) as z:
    names=[n for n in z.namelist() if n.startswith("REPO/") and not n.endswith("/")]
    assert len(names)>0
    for name in names:
     bits=PurePosixPath(name).parts
     assert len(bits)>1 and ".." not in bits and bits[0]=="REPO"
     target=root.joinpath(*bits[1:])
     assert not target.exists()
     target.parent.mkdir(parents=True,exist_ok=True)
     target.write_bytes(z.read(name))
   caseinfo["source_files"]=len(names)
   db=case_dir/"baseline_db"
   caseinfo["baseline_db"]=must(case+"_baseline_db",[codeql,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(root),"--threads=3","--ram=10000"],root)
   sarif=out/(case+"_baseline.sarif")
   caseinfo["baseline_scan"]=must(case+"_baseline_scan",[codeql,"database","analyze",db,suite,"--format=sarif-latest","--output="+str(sarif),"--threads=3","--ram=10000"],root)
   before=alerts(sarif)
   caseinfo.update(stage="BASELINE_COMPLETE",baseline_alert_count=len(before))
  except Exception as exc:
   caseinfo.update(stage="BASELINE_ERROR",error=repr(exc),traceback=traceback.format_exc()[-2300:])
   save(out/(case+"_BASELINE_RESULT.json"),caseinfo)
   for arm in "C0 C1 C2 C3".split():
    item={"case":case,"arm":arm,"stage":"NOT_RUN_BASELINE_ERROR","baseline_error":caseinfo.get("error")}
    records.append(item)
   save(out/"SUMMARY.json",records)
   print(case,"BASELINE_ERROR",flush=True)
   continue
  save(out/(case+"_BASELINE_RESULT.json"),caseinfo)
  print(case,"BASELINE_DONE",len(before),flush=True)
  for arm in "C0 C1 C2 C3".split():
   item={"case":case,"arm":arm,"stage":"START","source_sha256":spec["source"],"codeql_version":"2.25.6","suite":suite,"baseline_alert_count":len(before),"functional_status":"NOT_VALIDATED"}
   armroot=case_dir/arm
   try:
    armroot.mkdir()
    patch=out/("CASE_"+case+"_"+arm+"_r01.patch")
    for i in range(spec["parts"]):
     name="input_"+case+"_"+arm+"_"+str(i).zfill(2)+".py"
     must(case+"_"+arm+"_stage"+str(i),["python3",stage/name,patch],armroot)
    assert sha(patch)==spec["patch"][arm],"PATCH_SHA256_MISMATCH"
    assert patch.stat().st_size>50,"EMPTY_PATCH"
    item["patch_sha256"]=sha(patch)
    item["patch_bytes"]=patch.stat().st_size
    repo=armroot/"repo";shutil.copytree(root,repo)
    item["applycheck"]=must(case+"_"+arm+"_check",["git","apply","--check",patch],repo)
    item["apply"]=must(case+"_"+arm+"_apply",["git","apply",patch],repo)
    text=patch.read_text(errors="replace")
    item["modified_paths"]=list(dict.fromkeys(re.findall(r"(?m)^diff --git a/.*? b/(.*?)$",text)))
    item["modified_file_count"]=len(item["modified_paths"])
    db=armroot/"db"
    item["database"]=must(case+"_"+arm+"_db",[codeql,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(repo),"--threads=3","--ram=10000"],repo)
    afterfile=out/(case+"_"+arm+"_after.sarif")
    item["scan"]=must(case+"_"+arm+"_scan",[codeql,"database","analyze",db,suite,"--format=sarif-latest","--output="+str(afterfile),"--threads=3","--ram=10000"],repo)
    after=alerts(afterfile)
    strong=diff_alerts(before,after,True);conserv=diff_alerts(before,after,False)
    item.update(stage="SCAN_COMPLETE",after_alert_count=len(after),new_strong_count=len(strong),new_conservative_count=len(conserv),new_strong_by_rule=dict(Counter(x["rule"] for x in strong)),new_conservative_by_rule=dict(Counter(x["rule"] for x in conserv)),new_strong_alerts=strong,new_conservative_alerts=conserv)
   except Exception as exc:
    item.update(stage="ERROR",error=repr(exc),traceback=traceback.format_exc()[-2300:])
   save(out/(case+"_"+arm+"_RESULT.json"),item)
   records.append(item);save(out/"SUMMARY.json",records)
   print(case,arm,item["stage"],item.get("new_strong_count"),item.get("error",""),flush=True)
finally:
 shutil.rmtree(scratch,ignore_errors=True)
