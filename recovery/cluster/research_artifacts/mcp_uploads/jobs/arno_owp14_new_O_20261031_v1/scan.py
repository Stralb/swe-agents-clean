#!/usr/bin/env python3
"""New O-arm October 31 generation scanner. Independent from historical O records."""
import base64,zlib,zipfile,hashlib,subprocess,os,json,re,time,shutil,traceback,collections,tempfile
from pathlib import Path,PurePosixPath
ROOT=Path.home()/"research_artifacts"
PACK=ROOT/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
OUT=ROOT/"mcp_uploads/jobs/arno_owp14_new_O_20261031_v1/output"
OUT.mkdir(parents=True,exist_ok=True)
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CASES=json.loads("{\"15151\":{\"source_sha256\":\"25317a7d85f2208b372f69c746de2b6bb08f616b8c552a4b360fbd0b19af5270\",\"patch_sha256\":\"7a74407b3c3c61b7b6b650b3fb2cb9e09e9b21b72a8e4363420bcc1000d644eb\",\"target_rule\":\"js/log-injection\",\"payload\":\"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\"},\"08461\":{\"source_sha256\":\"cf604dce142adf1ddeda24d54f17944e6bdb3969d8a3e0b70febc0599e92d5a5\",\"patch_sha256\":\"23d93f3aab67d42a00c3eb4406b2e6645d777ca3f8829c21e26ac82e739ce7a1\",\"target_rule\":\"js/incomplete-multi-character-sanitization\",\"payload\":\"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\"}}")
def sha(x):return hashlib.sha256(x).hexdigest()
def filehash(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def run(cmd,cwd,log,timeout=1800):
 env=os.environ.copy()
 for k in list(env):
  if any(s in k.upper() for s in ("API_KEY","TOKEN","SECRET","PASSWORD","PRIVATE_KEY","GITHUB_","HF_","AWS_","OPENAI_","WANDB_","SSH_","AZURE_")):env.pop(k,None)
 env["GIT_CONFIG_NOSYSTEM"]="1";env["GIT_CONFIG_GLOBAL"]="/dev/null";env["GIT_TERMINAL_PROMPT"]="0"
 env["PATH"]=str(Path.home()/"tools/codeql")+":"+env.get("PATH","/usr/bin:/bin")
 start=time.monotonic()
 try:
  with open(log,"w") as f:
   p=subprocess.run([str(c) for c in cmd],cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  return dict(rc=p.returncode,seconds=round(time.monotonic()-start,2),log=str(log.name))
 except Exception as e:
  Path(log).write_text(repr(e)+"\n")
  return dict(rc=124 if isinstance(e,subprocess.TimeoutExpired) else 127,error=str(e),log=str(log.name))
def extract(z,repo):
 count=0;total=0;seen=set()
 for f in z.infolist():
  if f.is_dir() or not f.filename.startswith("REPO/"):continue
  parts=PurePosixPath(f.filename).parts
  assert len(parts)>1 and parts[0]=="REPO" and ".." not in parts and ".git" not in parts
  assert not (f.external_attr>>16)&0o170000 in [0o120000,0o060000]
  assert parts not in seen;seen.add(parts)
  count+=1;total+=f.file_size
  assert count<=30000 and total<=2*1024**3
  dst=repo.joinpath(*parts[1:]);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(z.read(f))
 return count,total
def parse(sarif):
 d=json.loads(Path(sarif).read_text())
 vers=[r.get("tool",{}).get("driver",{}).get("semanticVersion","") for r in d.get("runs",[])]
 alerts=[]
 for r in d.get("runs",[]):
  for e in r.get("results",[]):
   p=(e.get("locations") or [{}])[0].get("physicalLocation",{})
   ff=e.get("partialFingerprints") or {}
   alerts.append(dict(rule=e.get("ruleId",""),path=p.get("artifactLocation",{}).get("uri","").replace("\\","/").removeprefix("file://"),
     line=p.get("region",{}).get("startLine"),message=e.get("message",{}).get("text",""),
     fp=ff.get("primaryLocationLineHash",""),col=ff.get("primaryLocationStartColumnFingerprint","")))
 return vers,alerts
def delta(before,after,conservative=False):
 def key(x):
  if conservative:return (x["rule"],x["path"],x["message"].strip().replace("\n"," "))
  return (x["rule"],x["path"],x["fp"] or x["message"],x["col"] or (x["line"] if not x["fp"] else ""))
 before_set=collections.Counter(key(x) for x in before);added=[]
 for x in after:
  k=key(x)
  if before_set[k]:before_set[k]-=1
  else:added.append(x)
 return added
summary={"status":"RUNNING","generation_model":"GPT-6 current assistant 2026-10-31, NEW IMPLEMENTATION NOT BLIND OR HISTORICAL O","input_policy":"FROZEN_ISSUE_MD_AND_REPO_ONLY","codeql_suite":SUITE,"cases":{},"db_ingested":False}
(OUT/"SUMMARY.json").write_text(json.dumps(summary,indent=2))
for case,meta in CASES.items():
 case_dir=OUT/("CASE_"+case);case_dir.mkdir(exist_ok=True)
 record={"case_id":int(case),"arm":"O","experimental_generation":"RERUN_20261031_R1_GPT6","source_sha256":meta["source_sha256"],"patch_sha256":meta["patch_sha256"],"historical_target_rule":meta["target_rule"],"functional_status":"NOT_INDEPENDENTLY_VERIFIED","checks":{}}
 summary["cases"][case]=record
 try:
  src=PACK/("CASE_"+case+"_O.zip")
  assert filehash(src)==meta["source_sha256"],"FROZEN_ZIP_SHA_MISMATCH"
  patch=zlib.decompress(base64.b64decode(meta["payload"]))
  assert sha(patch)==meta["patch_sha256"],"PATCH_SHA_MISMATCH"
  assert patch.startswith(b"diff --git a/"),"INVALID_PATCH"
  patchfile=case_dir/("CASE_"+case+"_O_RERUN_20261031_R1.patch");patchfile.write_bytes(patch)
  with zipfile.ZipFile(src) as z:
   assert z.testzip() is None and "ISSUE.md" in z.namelist()
   record["source_files"],record["source_uncompressed_bytes"]=extract(z,case_dir/"repo")
  repo=case_dir/"repo"
  record["checks"]["git_apply_check"]=run(["git","apply","--check",patchfile],repo,case_dir/"apply_check.log",120)
  assert record["checks"]["git_apply_check"]["rc"]==0,"APPLY_CHECK_FAILED"
  record["checks"]["git_apply"]=run(["git","apply",patchfile],repo,case_dir/"apply.log",120)
  assert record["checks"]["git_apply"]["rc"]==0,"APPLY_FAILED"
  codeql_ver=run([CODEQL,"version"],repo,case_dir/"codeql_version.log",120)
  record["checks"]["codeql_version"]=codeql_ver
  assert codeql_ver["rc"]==0,"CODEQL_NOT_PRESENT"
  curr=re.search(r"\b2\.\d+\.\d+\b",(case_dir/"codeql_version.log").read_text())
  assert curr,"UNKNOWN_CODEQL_VERSION"
  record["codeql_version"]=curr.group(0)
  before=ROOT/"prevention_pilot_phase2/screen65_codeql_job70675"/("CASE_"+case)/"before.sarif"
  assert before.exists(),"ORIGINAL_BASELINE_MISSING"
  base_versions,base_alerts=parse(before)
  if base_versions and all(x==record["codeql_version"] for x in base_versions):
   record["baseline_mode"]="ARCHIVED_SCREEN65_FIRST_SAME_VERSION"
   record["baseline_sarif_sha256"]=filehash(before)
   shutil.copyfile(before,case_dir/"before.sarif")
  else:
   record["baseline_mode"]="NEW_PAIRED_SAME_VERSION"
   with zipfile.ZipFile(src) as z:extract(z,case_dir/"repo_before")
   db=case_dir/"codeql_db_before"
   record["checks"]["db_before"]=run([CODEQL,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(case_dir/"repo_before"),"--threads=4","--ram=24000"],case_dir/"repo_before",case_dir/"db_before.log",3600)
   assert record["checks"]["db_before"]["rc"]==0,"DB_BEFORE_FAILED"
   before=case_dir/"before.sarif"
   record["checks"]["analyze_before"]=run([CODEQL,"database","analyze",db,SUITE,"--format=sarif-latest","--output",before,"--threads=4","--ram=24000"],case_dir/"repo_before",case_dir/"analyze_before.log",3600)
   assert record["checks"]["analyze_before"]["rc"]==0,"ANALYZE_BEFORE_FAILED"
   base_versions,base_alerts=parse(before)
   record["baseline_sarif_sha256"]=filehash(before)
  db=case_dir/"codeql_db_after"
  record["checks"]["db_after"]=run([CODEQL,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(repo),"--threads=4","--ram=24000"],repo,case_dir/"db_after.log",3600)
  assert record["checks"]["db_after"]["rc"]==0,"DB_AFTER_FAILED"
  sarif=case_dir/"after.sarif"
  record["checks"]["analyze_after"]=run([CODEQL,"database","analyze",db,SUITE,"--format=sarif-latest","--output",sarif,"--threads=4","--ram=24000"],repo,case_dir/"analyze_after.log",3600)
  assert record["checks"]["analyze_after"]["rc"]==0,"ANALYZE_AFTER_FAILED"
  after_versions,after=parse(sarif)
  assert after_versions==base_versions or (set(after_versions)==set(base_versions)=={record["codeql_version"]}),"SCAN_VERSION_MISMATCH"
  new_strong=delta(base_alerts,after);new_conservative=delta(base_alerts,after,True)
  record.update(status="CODEQL_PASS",baseline_total=len(base_alerts),after_total=len(after),new_strong=len(new_strong),new_conservative=len(new_conservative),
       historical_target_new_strong=sum(x["rule"]==meta["target_rule"] for x in new_strong),after_sarif_sha256=filehash(sarif),
       new_strong_by_rule=dict(collections.Counter(x["rule"] for x in new_strong)),
       new_conservative_by_rule=dict(collections.Counter(x["rule"] for x in new_conservative)))
  (case_dir/"warning_delta.json").write_text(json.dumps(dict(new_strong=new_strong,new_conservative=new_conservative),indent=2))
 except Exception as e:
  record["status"]="FAILED";record["error"]=repr(e);record["traceback"]=traceback.format_exc()
 (case_dir/"RESULT.json").write_text(json.dumps(record,indent=2)+"\n")
 (OUT/"SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
 print("CASE",case,record.get("status"),record.get("error",""),flush=True)
summary["status"]="COMPLETED" if all(x["status"]=="CODEQL_PASS" for x in summary["cases"].values()) else "PARTIAL"
(OUT/"SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
print("SUMMARY",summary["status"],flush=True)
