#!/usr/bin/env python3
"""Retry JS/TS CodeQL on already verified and applied 15151 new O patch. New output directory."""
from pathlib import Path
import subprocess,os,json,time,hashlib,collections,traceback
ROOT=Path.home()/"research_artifacts"
ORIG=ROOT/"mcp_uploads/jobs/arno_owp14_new_O_20261031_v1/output/CASE_15151"
OUT=ROOT/"mcp_uploads/jobs/arno_owp14_new_O_20261031_v2/output/CASE_15151"
OUT.mkdir(parents=True,exist_ok=False)
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
record=dict(case_id=15151,arm="O",run_id="OWP14_NEW_O_15151_GPT6_20261031_R1",source_case_dir=str(ORIG),patch_sha256="7a74407b3c3c61b7b6b650b3fb2cb9e09e9b21b72a8e4363420bcc1000d644eb",source_sha256="25317a7d85f2208b372f69c746de2b6bb08f616b8c552a4b360fbd0b19af5270",functional_status="NOT_INDEPENDENTLY_VERIFIED",status="RUNNING",checks={})
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for x in iter(lambda:f.read(1024*1024),b""):h.update(x)
 return h.hexdigest()
def run(args,dir,log,timeout=2700):
 env=os.environ.copy()
 for k in list(env):
  if any(s in k.upper() for s in ("TOKEN","API_KEY","PASSWORD","PRIVATE_KEY","SECRET","GITHUB_","HF_","OPENAI_","AWS_","WANDB_","SSH_","AZURE_")):env.pop(k,None)
 env.update({"PATH":str(Path.home()/"tools/node/bin")+":"+str(Path.home()/"tools/codeql")+":"+env.get("PATH","/usr/bin:/bin"),"GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null","GIT_TERMINAL_PROMPT":"0","CI":"1"})
 t=time.monotonic()
 try:
  with open(OUT/log,"w") as f:
   p=subprocess.run([str(v) for v in args],cwd=dir,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  return dict(rc=p.returncode,seconds=round(time.monotonic()-t,2),log=log)
 except Exception as e:
  (OUT/log).write_text(repr(e));return dict(rc=124 if isinstance(e,subprocess.TimeoutExpired) else 127,log=log,error=repr(e))
def parse(path):
 d=json.loads(Path(path).read_text())
 out=[]
 for r in d.get("runs",[]):
  for item in r.get("results",[]):
   p=(item.get("locations") or [{}])[0].get("physicalLocation",{})
   fp=item.get("partialFingerprints") or {}
   out.append(dict(rule=item.get("ruleId",""),path=p.get("artifactLocation",{}).get("uri","").replace(chr(92),"/").removeprefix("file://"),line=p.get("region",{}).get("startLine"),
     msg=item.get("message",{}).get("text",""),fp=fp.get("primaryLocationLineHash",""),col=fp.get("primaryLocationStartColumnFingerprint","")))
 return out
def delta(before,after,weak=False):
 def key(x):
  if weak:return(x["rule"],x["path"],x["msg"].replace("\n"," ").strip())
  return(x["rule"],x["path"],x["fp"] or x["msg"],x["col"] or (x["line"] if not x["fp"] else ""))
 old=collections.Counter(key(x) for x in before)
 added=[]
 for v in after:
  k=key(v)
  if old[k]:old[k]-=1
  else:added.append(v)
 return added
try:
 assert sha(ORIG/"CASE_15151_O_RERUN_20261031_R1.patch")==record["patch_sha256"]
 assert (ORIG/"repo").is_dir() and (ORIG/"before.sarif").exists()
 record["checks"]["node"]=run([str(Path.home()/"tools/node/bin/node"),"--version"],ORIG/"repo","node_version.log",60)
 assert record["checks"]["node"]["rc"]==0
 db=OUT/"codeql_db"
 record["checks"]["create"]=run([CODEQL,"database","create",db,"--language=javascript-typescript","--build-mode=none","--source-root="+str(ORIG/"repo"),"--threads=4","--ram=24000"],ORIG/"repo","db_create.log",3600)
 assert record["checks"]["create"]["rc"]==0,"DB_CREATE_FAILED"
 record["checks"]["scan"]=run([CODEQL,"database","analyze",db,SUITE,"--format=sarif-latest","--output",OUT/"after.sarif","--threads=4","--ram=24000"],ORIG/"repo","analyze.log",3600)
 assert record["checks"]["scan"]["rc"]==0,"ANALYZE_FAILED"
 before=parse(ORIG/"before.sarif");after=parse(OUT/"after.sarif")
 strong=delta(before,after);cons=delta(before,after,True)
 record.update(status="CODEQL_PASS",baseline_total=len(before),after_total=len(after),new_strong=len(strong),new_conservative=len(cons),new_strong_by_rule=dict(collections.Counter(v["rule"] for v in strong)),historical_target_new_strong=sum(v["rule"]=="js/log-injection" for v in strong),after_sarif_sha256=sha(OUT/"after.sarif"),baseline_sarif_sha256=sha(ORIG/"before.sarif"),codeql_version="2.25.6",suite=SUITE,baseline_mode="ARCHIVED_SCREEN65_FIRST_SAME_VERSION")
 (OUT/"warning_delta.json").write_text(json.dumps(dict(new_strong=strong,new_conservative=cons),indent=2)+"\n")
except Exception as e:
 record["status"]="FAILED";record["error"]=repr(e);record["traceback"]=traceback.format_exc()
(OUT/"RESULT.json").write_text(json.dumps(record,indent=2)+"\n")
print(json.dumps(dict(status=record["status"],case=15151,checks=record["checks"],error=record.get("error")),indent=2),flush=True)
