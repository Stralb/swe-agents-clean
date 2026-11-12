#!/usr/bin/env python3
"""Fresh controlled baseline CodeQL scan over one sanitized RPL7 source input.
Source ZIP SHA verified against frozen manifest. This does not execute repository code.
Retains raw SARIF, original scanner logs, toolchain info and SHA256 provenance.
No writes to ARNO master, frozen source packages, HF, or historical archives.
"""
import argparse,hashlib,json,os,shutil,stat,subprocess,tempfile,time,zipfile,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.home()/"research_artifacts"
SRC=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2"
OUT=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
CODEQL=Path.home()/"tools/codeql/codeql"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CASES=("03429","03581","08152","12344","22223","31207","32759")
def digest(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
def ck(ok,why):
 if not ok:raise RuntimeError(why)
def call(args,log,timeout=14400):
 t=time.monotonic()
 with log.open("x",encoding="utf-8") as f:
  try:
   p=subprocess.run([str(x) for x in args],stdout=f,stderr=subprocess.STDOUT,check=False,timeout=timeout,
    env={**os.environ,"CODEQL_THREADS":"4"})
   return {"exit":p.returncode,"seconds":round(time.monotonic()-t,2),"log":log.name}
  except subprocess.TimeoutExpired:
   return {"exit":124,"seconds":round(time.monotonic()-t,2),"log":log.name,"timed_out":True}
def main(case):
 ck(case in CASES,"Unexpected case")
 manifest=json.loads((SRC/"MANIFEST.json").read_text())
 runs=[r for r in manifest["runs"] if r["case_id"]==case]
 ck(len(runs)==3 and {r["condition"] for r in runs}=={"P1","P2","P3"},"Cannot establish 3 treatment arms")
 p1=next(r for r in runs if r["condition"]=="P1")
 ck(len({r["repo_tree_sha256"] for r in runs})==1,"Source trees not identical")
 zippath=SRC/"run_zips"/(p1["run_id"]+".zip")
 ck(zippath.exists() and digest(zippath)==p1["sha256"],"Source ZIP hash invalid")
 caseout=OUT/("CASE_"+case)
 ck(not caseout.exists(),"Case output already exists: no overwrite")
 caseout.mkdir(parents=True)
 start=time.monotonic(); report={"case_id":case,"status":"PREPARING","model_run_id_p1":p1["run_id"],
 "input_zip_sha256":p1["sha256"],"sanitized_repo_sha256":p1["repo_tree_sha256"],
 "original_O_source_zip_sha256":p1["original_O_source_zip_sha256"],
 "source_kind":p1["source_kind"],"scanner":"CodeQL","suite":SUITE,
 "started_at_utc":datetime.now(timezone.utc).isoformat(),"codeql_version_expected":"2.25.6",
 "env_python":sys.executable,"hostname":os.uname().nodename,"checks":{}}
 scratch=Path(tempfile.mkdtemp(prefix="arno_rpl7_base_"+case+"_",dir=os.environ.get("TMPDIR","/tmp")))
 try:
  repo=scratch/"REPO";repo.mkdir()
  total=0
  with zipfile.ZipFile(zippath) as z:
   for info in z.infolist():
    name=info.filename
    if not name.startswith("REPO/") or name.endswith("/"):continue
    rel=name[len("REPO/"):]
    parts=Path(rel).parts
    ck(parts and not Path(rel).is_absolute() and ".." not in parts and "\\" not in rel,"Unsafe input source ZIP member")
    mode=(info.external_attr>>16)&0o170000
    ck(mode!=stat.S_IFLNK,"Zip symlink not allowed")
    target=repo.joinpath(*parts)
    target.parent.mkdir(parents=True,exist_ok=True)
    ck(not target.exists(),"Duplicate REPO member")
    with z.open(info) as f,target.open("xb") as g:shutil.copyfileobj(f,g)
    total+=1
  ck(total>0,"No REPO files")
  report["sanitized_repo_files"]=total
  version=call([CODEQL,"version"],caseout/"codeql_version.log",120)
  report["checks"]["version"]=version
  vtext=(caseout/"codeql_version.log").read_text(encoding="utf-8",errors="replace")
  ck(version["exit"]==0 and "release 2.25.6" in vtext,"CodeQL toolchain version mismatch")
  db=scratch/"codeql_db"
  report["checks"]["database_create"]=call([CODEQL,"database","create",db,"--language=javascript",
    "--source-root="+str(repo),"--threads=4","--ram=12000"],caseout/"codeql_create.log",10800)
  ck(report["checks"]["database_create"]["exit"]==0,"CodeQL baseline extraction failed")
  sarif=caseout/"baseline.sarif"
  report["checks"]["analysis"]=call([CODEQL,"database","analyze",db,SUITE,
    "--format=sarifv2.1.0","--output="+str(sarif),"--threads=4","--ram=12000"],caseout/"codeql_analyze.log",10800)
  ck(report["checks"]["analysis"]["exit"]==0 and sarif.exists(),"CodeQL baseline analysis failed")
  sarif_doc=json.loads(sarif.read_text(encoding="utf-8"))
  report["status"]="BASELINE_CODEQL_COMPLETE"
  report["sarif_sha256"]=digest(sarif)
  report["sarif_bytes"]=sarif.stat().st_size
  report["result_count"]=sum(len(run.get("results",[])) for run in sarif_doc.get("runs",[]))
 except Exception as exc:
  report["status"]="BASELINE_FAILED"
  report["error_type"]=type(exc).__name__
  report["error_message"]=str(exc)[:350]
 finally:
  report["duration_seconds"]=round(time.monotonic()-start,1)
  report["finished_at_utc"]=datetime.now(timezone.utc).isoformat()
  (caseout/"RESULT.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
  shutil.rmtree(scratch,ignore_errors=True)
 print(json.dumps({k:report.get(k) for k in ("case_id","status","result_count","sarif_sha256","error_message","duration_seconds")}),flush=True)
 if report["status"]!="BASELINE_CODEQL_COMPLETE":sys.exit(1)
if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("--case",required=True,choices=CASES)
 args=parser.parse_args();main(args.case)
