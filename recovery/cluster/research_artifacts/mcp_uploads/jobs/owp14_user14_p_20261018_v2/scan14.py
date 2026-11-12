#!/usr/bin/env python3
"""Independent CodeQL scan of user-submitted 14 P patches, with frozen prepatch SARIF controls."""
from pathlib import Path,PurePosixPath
from collections import Counter,defaultdict
import os,re,json,zipfile,hashlib,subprocess,tempfile,shutil,time,csv,traceback
ROOT=Path.home()/"research_artifacts"/"prevention_pilot_phase2"
PRE=ROOT/"owp14_user14_p_preflight_job71200"
PACK=ROOT/"owp14_allcases_packets_job71014"
OUT=ROOT/("owp14_user14_p_codeql_job"+os.environ["SLURM_JOB_ID"])
OUT.mkdir(parents=True,exist_ok=False)
CQ=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
assert CQ.exists()
pre=json.loads((PRE/"SUMMARY.json").read_text())
assert pre["stage"]=="COMPLETE" and pre["received"]==14
index={}
with (ROOT/"owp14_target_specific_index_job71021/TARGET_SPECIFIC_INDEX_CORRECTED.csv").open(newline="") as f:
 for rec in csv.DictReader(f):index[int(rec["case_id"])]=rec
assert len(index)==14
def fhash(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(2*1024*1024),b""):h.update(b)
 return h.hexdigest()
def safe_env():
 env=dict(os.environ)
 for k in list(env):
  if any(x in k.upper() for x in ("TOKEN","SECRET","PASSWORD","API_KEY","PRIVATE_KEY",
     "OPENAI_","GITHUB_","AWS_","HF_","WANDB_","SLACK_","SSH_","AZURE_")):
   env.pop(k,None)
 env["HOME"]=str(Path.home())
 env["PATH"]=str(Path.home()/"tools/codeql")+":"+str(Path.home()/"tools/node/bin")+":"+env.get("PATH","/usr/bin:/bin")
 env.update({"CI":"1","GIT_TERMINAL_PROMPT":"0","GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null",
   "HUSKY":"0","PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD":"1","PUPPETEER_SKIP_DOWNLOAD":"1"})
 return env
ENV=safe_env()
def invoke(rec,logtag,cmd,cwd,timeout):
 t=time.monotonic(); log=Path(rec["_out"])/(logtag+".log")
 try:
  with log.open("w") as f:
   pr=subprocess.run([str(x) for x in cmd],cwd=cwd,env=ENV,
       stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  code=pr.returncode
 except subprocess.TimeoutExpired:code=124
 except Exception as exc:
  code=127;log.write_text("EXCEPTION "+repr(exc)+"\n")
 rec["checks"][logtag]={"rc":code,"seconds":round(time.monotonic()-t,2),"log":logtag+".log"}
 save(rec)
 return code
def save(rec):
 out=Path(rec["_out"])
 obj={k:v for k,v in rec.items() if k!="_out"}
 (out/"RESULT.json").write_text(json.dumps(obj,indent=2)+"\n")
def extract(source,repo):
 n=0;bytes_total=0
 with zipfile.ZipFile(source) as z:
  assert z.testzip() is None
  assert "ISSUE.md" in z.namelist()
  for f in z.infolist():
   if f.is_dir() or not f.filename.startswith("REPO/"):continue
   pp=PurePosixPath(f.filename)
   assert len(pp.parts)>1 and pp.parts[0]=="REPO"
   assert ".." not in pp.parts and ".git" not in pp.parts
   n+=1;bytes_total+=f.file_size
   assert n<=30000 and bytes_total<=2*1024**3
   path=repo.joinpath(*pp.parts[1:]);path.parent.mkdir(parents=True,exist_ok=True)
   path.write_bytes(z.read(f))
 return n
def results(sarif):
 d=json.loads(Path(sarif).read_text())
 version=d["runs"][0]["tool"]["driver"].get("semanticVersion","")
 alerts=[]
 for run in d.get("runs",[]):
  for item in run.get("results",[]):
   loc=(item.get("locations") or [{}])[0].get("physicalLocation",{})
   artifact=loc.get("artifactLocation",{})
   uri=artifact.get("uri","").replace("\\","/")
   uri=uri.removeprefix("file://")
   line=loc.get("region",{}).get("startLine")
   msg=item.get("message",{}).get("text","")
   fp=item.get("partialFingerprints") or {}
   alerts.append({"rule":item.get("ruleId",""),"path":uri,"line":line,
     "message":msg,"primaryLocationLineHash":fp.get("primaryLocationLineHash",""),
     "primaryLocationStartColumnFingerprint":fp.get("primaryLocationStartColumnFingerprint","")})
 return version,alerts
def findings_new(old,new,key):
 tally=Counter(key(x) for x in old)
 a=[]
 for v in new:
  k=key(v)
  if tally[k]:tally[k]-=1
  else:a.append(v)
 return a
def strongkey(v):
 return (v["rule"],v["path"],v["primaryLocationLineHash"] or v["message"],
    v["primaryLocationStartColumnFingerprint"] or (v["line"] if not v["primaryLocationLineHash"] else ""))
def weakkey(v):
 return (v["rule"],v["path"],v["message"].replace("\n"," ").strip())
def added_lines_from_patch(b):
 ret=defaultdict(set);cur=None;line=None
 for raw in b.decode("utf8","replace").splitlines():
  m=re.match(r"diff --git a/(.*?) b/(.*)",raw)
  if m:cur=m.group(2);line=None;continue
  h=re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@",raw)
  if h:line=int(h.group(1));continue
  if line is None or cur is None:continue
  if raw.startswith("+++ ") or raw.startswith("--- "):continue
  if raw.startswith("+"):ret[cur].add(line);line+=1
  elif raw.startswith("-"):pass
  elif raw.startswith(" "):line+=1
  elif raw.startswith("\\ No newline"):pass
  else:line=None
 return ret
scanver=subprocess.run([str(CQ),"version"],env=ENV,stdout=subprocess.PIPE,
  stderr=subprocess.STDOUT,text=True,timeout=100).stdout
(OUT/"CODEQL_VERSION.txt").write_text(scanver)
match=re.search(r"\b(2\.\d+\.\d+)\b",scanver)
assert match,("CANNOT_FIND_CODEQL_VERSION",scanver)
CLI_VERSION=match.group(1)
all_cases=pre["cases"]
order=sorted((int(x) for x in all_cases),key=lambda cid:(all_cases[str(cid)]["source_bytes"],cid))
(OUT/"PLAN.json").write_text(json.dumps({"case_order":order,"codeql_version":CLI_VERSION,
 "suite":SUITE,"stages":"CodeQL database after, analyze after, baseline reuse only when CodeQL versions match, otherwise new paired baseline",
 "historical_issue_body_provenance":"UNVERIFIED","functional_tests_performed":False},indent=2)+"\n")
summary={"stage":"IN_PROGRESS","codeql_version":CLI_VERSION,"suite":SUITE,
 "paired_version_required":True,"case_count":14,"completed":0,"cases":{}}
def write_summary(): (OUT/"SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
write_summary()
for cid in order:
 old=all_cases[str(cid)]
 if not old.get("patch_applied"):
  summary["cases"][str(cid)]={"case_id":cid,"arm":"P","stage":"SKIPPED_PATCH_NOT_APPLIED","preflight_stage":old.get("stage"),"source_type":old.get("source_type"),"functional_status":"NOT_VALIDATED"}
  summary["completed"]=len(summary["cases"])
  write_summary()
  print("SCAN",cid,"SKIPPED_PATCH_NOT_APPLIED",flush=True)
  continue
 prev=ROOT/"screen65_codeql_job70675"/("CASE_%05d"%cid)/"before.sarif"
 caseout=OUT/("CASE_%05d"%cid);caseout.mkdir()
 rec={"case_id":cid,"arm":"P","stage":"INIT","source_type":old["source_type"],
   "patch_sha256":old["original_patch_sha256"],"frozen_source_sha256":old["frozen_input_sha256"],
   "target_rule":index[cid]["target_rule"],"target_recurred_previous_O":index[cid]["any_O_target_warning"],
   "current_codeql_version":CLI_VERSION,"suite":SUITE,"checks":{},
   "functional_status":"NOT_VALIDATED","baseline_version_match":None,
   "_out":str(caseout)}
 tmp=None
 try:
  inputzip=PACK/("CASE_%05d_P.zip"%cid)
  userpatch=PRE/("CASE_%05d"%cid)/old["filename"]
  assert fhash(inputzip)==old["frozen_input_sha256"]
  assert fhash(userpatch)==old["original_patch_sha256"]
  assert prev.is_file()
  baseline_version,baseline_alerts=results(prev)
  rec["archived_baseline_codeql_version"]=baseline_version
  scratchroot=ROOT/"owp14_user12_scanner_scratch"
  scratchroot.mkdir(exist_ok=True)
  stat=os.statvfs(scratchroot)
  assert stat.f_bavail*stat.f_frsize>12*1024**3,"NOT_ENOUGH_SCRATCH"
  tmp=Path(tempfile.mkdtemp(prefix="CASE_%05d_"%cid,dir=scratchroot))
  repo=tmp/"repo";repo.mkdir()
  rec["files_extracted"]=extract(inputzip,repo)
  rec["stage"]="PATCH_APPLY";save(rec)
  if invoke(rec,"applycheck",["git","apply","--check",userpatch],repo,180):
   raise RuntimeError("APPLY_CHECK_FAILED")
  if invoke(rec,"apply",["git","apply",userpatch],repo,180):
   raise RuntimeError("APPLY_FAILED")
  if baseline_version==CLI_VERSION:
   baseline=prev
   rec["baseline_version_match"]=True
   rec["baseline_mode"]="archived_FROZEN_base_compatible_CodeQL_version"
  else:
   rec["baseline_version_match"]=False
   rec["baseline_mode"]="rerun_baseline_same_current_version"
   base=tmp/"base";base.mkdir()
   extract(inputzip,base)
   dbbase=tmp/"db_before"
   if invoke(rec,"db_before",[CQ,"database","create",dbbase,"--language=javascript-typescript",
      "--build-mode=none","--source-root="+str(base),"--threads=4","--ram=24000"],base,2700):
    raise RuntimeError("BASE_DATABASE_FAILED")
   baseline=caseout/"before_newversion.sarif"
   if invoke(rec,"scan_before",[CQ,"database","analyze",dbbase,SUITE,
      "--format=sarif-latest","--output",baseline,"--threads=4","--ram=24000"],base,3600):
    raise RuntimeError("BASE_ANALYZE_FAILED")
   baseline_version,baseline_alerts=results(baseline)
   assert baseline_version==CLI_VERSION,(baseline_version,CLI_VERSION)
  rec["baseline_sarif_sha256"]=fhash(baseline)
  rec["stage"]="CODEQL_DB_AFTER";save(rec)
  dbafter=tmp/"db_after"
  if invoke(rec,"db_after",[CQ,"database","create",dbafter,"--language=javascript-typescript",
    "--build-mode=none","--source-root="+str(repo),"--threads=4","--ram=24000"],repo,3300):
   raise RuntimeError("CODEQL_DATABASE_FAILED")
  rec["stage"]="CODEQL_ANALYZE_AFTER";save(rec)
  sarif=caseout/"after.sarif"
  if invoke(rec,"scan_after",[CQ,"database","analyze",dbafter,SUITE,
    "--format=sarif-latest","--output",sarif,"--threads=4","--ram=24000"],repo,3800):
   raise RuntimeError("CODEQL_ANALYZE_FAILED")
  version,after_alerts=results(sarif)
  assert version==baseline_version==CLI_VERSION,(version,baseline_version,CLI_VERSION)
  strong=findings_new(baseline_alerts,after_alerts,strongkey)
  conservative=findings_new(baseline_alerts,after_alerts,weakkey)
  added=added_lines_from_patch(userpatch.read_bytes())
  def format_alert(v):
   return {"rule":v["rule"],"path":v["path"],"line":v["line"],
     "message":v["message"][:440],
     "on_added_line":isinstance(v["line"],int) and v["line"] in added.get(v["path"],set()),
     "historical_target_rule":v["rule"]==rec["target_rule"]}
  rec["codeql_before_total"]=len(baseline_alerts)
  rec["codeql_after_total"]=len(after_alerts)
  rec["new_strong_total"]=len(strong)
  rec["new_conservative_total"]=len(conservative)
  rec["new_strong_by_rule"]=dict(Counter(v["rule"] for v in strong))
  rec["new_conservative_by_rule"]=dict(Counter(v["rule"] for v in conservative))
  rec["new_strong_target_rule"]=sum(v["rule"]==rec["target_rule"] for v in strong)
  rec["new_conservative_target_rule"]=sum(v["rule"]==rec["target_rule"] for v in conservative)
  rec["new_strong_on_added_line"]=sum(format_alert(v)["on_added_line"] for v in strong)
  rec["new_strong_alerts"]=[format_alert(v) for v in strong]
  rec["new_conservative_alerts"]=[format_alert(v) for v in conservative]
  rec["stage"]="SCAN_COMPLETE"
 except Exception as err:
  rec["stage"]="SCAN_FAILED";rec["error"]=repr(err)
  (caseout/"error_traceback.txt").write_text(traceback.format_exc())
 finally:
  save(rec)
  summary["cases"][str(cid)]={k:v for k,v in rec.items() if k not in ["_out","new_strong_alerts","new_conservative_alerts"]}
  summary["completed"]=len(summary["cases"])
  write_summary()
  if tmp:shutil.rmtree(tmp,ignore_errors=True)
  print("SCAN",cid,rec["stage"],"new_strong",rec.get("new_strong_total"),
      "new_conservative",rec.get("new_conservative_total"),
      "new_target",rec.get("new_strong_target_rule"),
      "elapsed",round(sum(x["seconds"] for x in rec["checks"].values()),1),flush=True)
summary["stage"]="COMPLETE"
summary["scans_complete"]=sum(v["stage"]=="SCAN_COMPLETE" for v in summary["cases"].values())
summary["scans_failed"]=sum(v["stage"]=="SCAN_FAILED" for v in summary["cases"].values())
write_summary()
print("ALL_SCANS_DONE",summary["scans_complete"],"FAILED",summary["scans_failed"],OUT,flush=True)
