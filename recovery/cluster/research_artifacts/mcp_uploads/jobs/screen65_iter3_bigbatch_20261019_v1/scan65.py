#!/usr/bin/env python3
"""Third-generation 65-case O-patch static analysis; frozen source, archived baseline, no repository code execution."""
import collections,csv,hashlib,json,os,re,subprocess,sys,tempfile,time,traceback,zipfile,shutil
from pathlib import Path,PurePosixPath
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2"
STAGE=ROOT/"screen65_iter3_staged_20261019_v2_bigbatch"
OLD=ROOT/"screen65_codeql_job70675"
BASE_META=ROOT/"screen65_codeql_summary_job70694/SCREEN65_CODEQL_RESULTS.csv"
OUT=ROOT/("screen65_iter3_codeql_job"+os.environ["SLURM_ARRAY_JOB_ID"])
OUT.mkdir(parents=True,exist_ok=True)
INDEX=int(os.environ["SLURM_ARRAY_TASK_ID"])
CQ=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
m=json.loads((STAGE/"MANIFEST.json").read_text())
assert m["status"]=="STAGED" and m["patch_count"]==65
case=m["patches"][INDEX];cid=case["case_id"]
caseout=OUT/("CASE_%05d"%cid);caseout.mkdir(exist_ok=False)
pr=(STAGE/"patches"/case["patch_filename"])
ref=OLD/("CASE_%05d"%cid)
historical={int(r["case_id"]):r for r in csv.DictReader(BASE_META.open(newline=""))}
rule_set=set(historical[cid]["historical_target_rules"].split(";"))-set([""])
full_source=ROOT/"remaining65_archives_oct17_v1"/("CASE_%05d.zip"%cid)
filtered_source=ROOT/"remaining65_targeted14_v1"/("CASE_%05d.zip"%cid)
source=full_source if full_source.exists() else filtered_source
source_type="FULL_FROZEN_SNAPSHOT" if source==full_source else "FILTERED_SOURCE_PROVISIONAL"
status={"case_id":cid,"iteration":3,"claimed_status":case["status"],
 "patch_sha256":case["patch_sha256"],"source_archive":str(source.relative_to(ROOT)),
 "source_type":source_type,"target_rules":sorted(rule_set),
 "stage":"STARTED","checks":{},"suite":SUITE,"codeql_expected":"2.25.6",
 "functional_acceptance":"NOT_EVALUATED","issue_version_asof_pr_verified":False}
def save(): (caseout/"RESULT.json").write_text(json.dumps(status,indent=2)+"\n")
def hashpath(p):
 h=hashlib.sha256()
 with p.open("rb") as fd:
  for b in iter(lambda:fd.read(2*1024*1024),b""):h.update(b)
 return h.hexdigest()
def execute(tag,cmd,cwd,timeout=4000):
 t=time.monotonic()
 try:
  with (caseout/(tag+".log")).open("w") as log:
   cp=subprocess.run([str(x) for x in cmd],cwd=cwd,env=env,
    stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
   rc=cp.returncode
 except subprocess.TimeoutExpired:rc=124
 except Exception as e:
  rc=127;(caseout/(tag+".log")).write_text("EXCEPTION: "+repr(e))
 status["checks"][tag]={"returncode":rc,"seconds":round(time.monotonic()-t,1)}
 save()
 return rc==0
def sarif(path):
 d=json.loads(path.read_text())
 versions={x.get("tool",{}).get("driver",{}).get("semanticVersion") for x in d["runs"]}
 assert versions=={"2.25.6"},("CODEQL_VERSION_MISMATCH",versions)
 ans=[]
 for run in d["runs"]:
  for x in run.get("results",[]):
   loc=(x.get("locations") or [{}])[0].get("physicalLocation",{})
   ans.append({"rule":x.get("ruleId",""),"path":loc.get("artifactLocation",{}).get("uri","").replace("\\","/"),
    "line":loc.get("region",{}).get("startLine"),"message":x.get("message",{}).get("text",""),
    "fingerprints":x.get("partialFingerprints") or {},
    "related_locations":x.get("relatedLocations",[])[:3],
    "code_flows":x.get("codeFlows",[])[:2]})
 return ans
def key(x,strong):
 f=x["fingerprints"]
 return (x["rule"],x["path"],f.get("primaryLocationLineHash") or x["message"],
    f.get("primaryLocationStartColumnFingerprint") or "") if strong else (
     x["rule"],x["path"],x["message"].strip().replace("\n"," "))
def difference(old,new,strong):
 freq=collections.Counter(key(x,strong) for x in old)
 result=[]
 for x in new:
  k=key(x,strong)
  if freq[k]>0:freq[k]-=1
  else:result.append(x)
 return result
def added_from_patch(b):
 tracks=collections.defaultdict(set)
 cur=None;line=None
 for raw in b.decode("utf-8","replace").splitlines():
  if raw.startswith("diff --git a/"):
   mt=re.match(r"diff --git a/(.*) b/(.*)",raw)
   cur=mt.group(2) if mt else None
   line=None;continue
  h=re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@",raw)
  if h:line=int(h.group(1));continue
  if line is None or cur is None:continue
  if raw.startswith("+++ ") or raw.startswith("--- "):continue
  if raw.startswith("+"):tracks[cur].add(line);line+=1
  elif raw.startswith(" "):line+=1
  elif raw.startswith("-"):continue
  elif raw.startswith("\\ No newline"):continue
  else:line=None
 return tracks
def fmt(x,added,changed):
 flows=[]
 for cf in x.get("code_flows") or []:
  for flow in (cf.get("threadFlows") or [])[:2]:
   locs=flow.get("locations") or []
   compressed=[]
   for y in locs[:50]:
    l=y.get("location",{})
    physical=l.get("physicalLocation",{})
    compressed.append({"path":physical.get("artifactLocation",{}).get("uri",""),
     "line":physical.get("region",{}).get("startLine"),
     "msg":l.get("message",{}).get("text","")[:170]})
   flows.append(compressed)
 return {"rule":x["rule"],"path":x["path"],"line":x["line"],"message":x["message"][:400],
  "on_added_line":isinstance(x["line"],int) and x["line"] in added.get(x["path"],set()),
  "in_changed_file":x["path"] in changed,"historical_rule_class":x["rule"] in rule_set,
  "source_to_sink":flows[:2],"related_locations":x.get("related_locations",[])}
# CLI only gets scanner binaries and local tools; credentials stripped.
env=dict(os.environ)
for name in list(env):
 if re.search("TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY|OPENAI_|GITHUB_|AWS_|HF_|WANDB_|SLACK_|SSH_|AZURE_",name,re.I):
  env.pop(name,None)
env["PATH"]=str(Path.home()/"tools/codeql")+":"+str(Path.home()/"tools/node/bin")+":/usr/bin:/bin"
env.update({"CI":"1","GIT_TERMINAL_PROMPT":"0","GIT_CONFIG_GLOBAL":"/dev/null",
 "GIT_CONFIG_NOSYSTEM":"1","GIT_OPTIONAL_LOCKS":"0","NODE_ENV":"production",
 "PUPPETEER_SKIP_BROWSER_DOWNLOAD":"1","PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD":"1"})
save()
tmp=None
try:
 assert source.exists() and ref.joinpath("before.sarif").exists() and ref.joinpath("RESULT.json").exists()
 prev=json.loads((ref/"RESULT.json").read_text())
 assert prev["stage"]=="SCAN_COMPLETE" and prev["suite"]==SUITE and prev["source_type"]==source_type
 assert hashpath(pr)==case["patch_sha256"]
 status["source_archive_sha256"]=hashpath(source)
 status["baseline_sarif_sha256"]=hashpath(ref/"before.sarif")
 before=sarif(ref/"before.sarif")
 # For this generation, use the SAME frozen archive and scanner version as the first 65-case screen.
 scratchparent=Path(os.environ.get("SLURM_TMPDIR") or str(ROOT/"screen65_iter3_scratch"))
 scratchparent.mkdir(parents=True,exist_ok=True)
 tmp=Path(tempfile.mkdtemp(prefix="case_%05d_"%cid,dir=scratchparent))
 repo=tmp/"repo";repo.mkdir()
 status["stage"]="SOURCE_EXTRACT"
 file_count=0;total_bytes=0
 with zipfile.ZipFile(source) as z:
  assert z.testzip() is None
  for item in z.infolist():
   if item.is_dir() or not item.filename.startswith("REPO/"):continue
   parts=PurePosixPath(item.filename).parts
   assert len(parts)>1 and parts[0]=="REPO" and ".." not in parts and ".git" not in parts
   file_count+=1;total_bytes+=item.file_size
   assert file_count<=80000 and total_bytes<=950*1024*1024 and item.file_size<=65*1024*1024
   target=repo.joinpath(*parts[1:])
   target.parent.mkdir(parents=True,exist_ok=True)
   target.write_bytes(z.read(item))
 status["source_file_count"]=file_count;status["source_uncompressed_bytes"]=total_bytes
 assert file_count==prev.get("source_files"),("BASELINE_FILE_COUNT_CHANGED",file_count,prev.get("source_files"))
 status["stage"]="PATCH_APPLY"
 if not execute("git_apply_check",["git","apply","--check",str(pr)],repo,180):
  raise RuntimeError("PATCH_DOES_NOT_APPLY")
 if not execute("git_apply",["git","apply",str(pr)],repo,180):
  raise RuntimeError("PATCH_APPLY_FAILED")
 status["stage"]="DATABASE_AFTER";save()
 if not execute("database_after",[CQ,"database","create",tmp/"db_after","--language=javascript-typescript",
    "--build-mode=none","--source-root="+str(repo),"--threads=3","--ram=11000"],repo,4500):
  raise RuntimeError("CODEQL_DB_FAILED")
 status["stage"]="SCAN_AFTER";save()
 if not execute("scan_after",[CQ,"database","analyze",tmp/"db_after",SUITE,
   "--format=sarif-latest","--output",caseout/"after.sarif","--threads=3","--ram=11000"],repo,4500):
  raise RuntimeError("CODEQL_SCAN_FAILED")
 after=sarif(caseout/"after.sarif")
 strong=difference(before,after,True)
 weak=difference(before,after,False)
 added=added_from_patch(pr.read_bytes())
 changed=set(case["changed_files"])
 ss=[fmt(x,added,changed) for x in strong]
 ww=[fmt(x,added,changed) for x in weak]
 status["findings"]={
 "before_total":len(before),"after_total":len(after),
 "new_strong_count":len(ss),"new_weak_count":len(ww),
 "new_on_added_line_count":sum(x["on_added_line"] for x in ss),
 "new_in_changed_file_count":sum(x["in_changed_file"] for x in ss),
 "historical_target_count":sum(x["historical_rule_class"] for x in ss),
 "historical_target_on_added_line":sum(x["historical_rule_class"] and x["on_added_line"] for x in ss),
 "new_by_rule_strong":dict(collections.Counter(x["rule"] for x in ss)),
 "new_by_rule_weak":dict(collections.Counter(x["rule"] for x in ww)),
 "new_strong_findings":ss,"new_weak_findings":ww}
 status["stage"]="SCAN_COMPLETE"
except BaseException as e:
 status["stage"]="FAILED"
 status["error"]=repr(e)[:1600]
 (caseout/"TRACEBACK.txt").write_text(traceback.format_exc()[-6000:])
finally:
 save()
 if tmp and tmp.exists():shutil.rmtree(tmp,ignore_errors=True)
 print("ITER3_CASE",cid,status["stage"],status.get("findings",{}).get("new_strong_count"),
  status.get("findings",{}).get("historical_target_count"),status.get("error",""),flush=True)
