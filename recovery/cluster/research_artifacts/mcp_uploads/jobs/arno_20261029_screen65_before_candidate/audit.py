#!/usr/bin/env python3
"""Read-only Screen65 baseline candidate and agent trace-reference audit;
--apply registers source-linked candidate SARIF metadata in ARNO master.
No SARIF or trace bodies emitted or embedded.
"""
import json,zipfile,re,hashlib,sqlite3,sys,argparse
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
ZIP=R/"ARNO_CODEQL_EXPORT_20261019/05_SCREEN65_EVIDENCE.zip"
TRACE=R/"ARNO_CODEQL_EXPORT_20261019/07_AGENT_PROMPTS_AND_TRACES.zip"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=R/"mcp_uploads/jobs/arno_20261029_screen65_before_candidate"
CASES=["00668","03429","03581","06104","08152","08461","12344","15151","16633","20094","21682","22223","31207","32759"]
BASE_KEY="arno_codeql_oct19_original:05_SCREEN65_EVIDENCE.zip"
TABLE="arno_screen65_before_sarif_candidates_20261029"
def req(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def get_versions(s):
 versions=[]
 for run in s.get("runs",[]):
  driver=run.get("tool",{}).get("driver",{})
  v=driver.get("semanticVersion") or driver.get("version")
  if v:versions.append(str(v)[:90])
 return sorted(set(versions))
def fetch():
 refs=[]
 with zipfile.ZipFile(ZIP) as z:
  for entry in z.infolist():
   n=entry.filename
   if not n.endswith("/before.sarif"):continue
   hit=re.search(r"/CASE_(\d{5})/before\.sarif$",n)
   if not hit:continue
   case=hit.group(1)
   if case not in CASES:continue
   if "screen65_codeql_job70675" not in n and "screen65_second_codeql_job70782" not in n:
    continue
   data=z.read(entry)
   sarif=json.loads(data)
   req(sarif.get("version")=="2.1.0","Unexpected SARIF version for "+n)
   wave="SCREEN65_FIRST" if "screen65_codeql_job70675" in n else "SCREEN65_SECOND"
   refs.append({"case_id":int(case),"case_label":case,"wave":wave,"zip_member_path":n,
     "byte_count":len(data),"sha256":sha(data),"sarif_version":sarif.get("version"),
     "tool_versions":get_versions(sarif),
     "scanner_run_count":len(sarif.get("runs",[])),
     "result_count":sum(len(run.get("results",[])) for run in sarif.get("runs",[])),
     "comparability_status":"EARLIER_SCREEN65_BASELINE_CANDIDATE_NOT_MATCHED_TO_OWP14_SOURCE_COMMIT"})
 req(len(refs)==28,"Unexpected 14-case baseline file count: "+str(len(refs)))
 for case in CASES:
  rows=[r for r in refs if r["case_label"]==case]
  req(len(rows)==2 and {r["wave"] for r in rows}=={"SCREEN65_FIRST","SCREEN65_SECOND"},"Missing Screen65 wave "+case)
 seen=Counter();scanned=0;skip_size=0
 with zipfile.ZipFile(TRACE) as z:
  for m in z.infolist():
   if not m.filename.lower().endswith((".log",".out",".err",".json",".jsonl",".txt",".md")):continue
   if m.file_size>2_000_000:
    skip_size+=1;continue
   try:s=z.read(m).decode("utf-8",errors="ignore").upper()
   except Exception:continue
   scanned+=1
   for case in CASES:
    if "CASE_"+case in s:
     seen[case]+=1
 return refs,{"archive_members_screened":scanned,"large_log_members_not_read":skip_size,
  "case_explicit_token_log_member_hits":dict(seen),
  "note":"Text mention counts do not establish full original agent execution or case-authentic prompt lineage."}
def main():
 pa=argparse.ArgumentParser();pa.add_argument("--apply",action="store_true")
 args=pa.parse_args()
 conn=sqlite3.connect(str(DB) if args.apply else "file:"+str(DB)+"?mode=ro",uri=not args.apply,timeout=90)
 try:
  if not args.apply:conn.execute("PRAGMA query_only=ON")
  conn.execute("PRAGMA foreign_keys=ON")
  req(conn.execute("SELECT COUNT(*) FROM arno_experiment_runs").fetchone()[0]==40,"40 archived scan run census regressed")
  b=conn.execute("SELECT source_sha256 FROM arno_sources WHERE source_key=?",(BASE_KEY,)).fetchone()
  req(b is not None and b[0]=="cf12a89f95d59ca3634d5792d29d14e74480765bf5e8ce96ab1311efd90c7054","Frozen ZIP source provenance mismatch")
  req(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(TABLE,)).fetchone()[0]==0,"Already indexed")
  rows,traces=fetch()
  report={"status":"EARLIER_SCREEN65_BASELINE_CANDIDATES_VERIFIED","date_utc":datetime.now(timezone.utc).isoformat(),
  "archive_source_key":BASE_KEY,"owp_case_count":14,"candidate_before_sarif_files":28,
  "candidates":rows,"original_agent_trace_reference_scan":traces,
  "scientific_limitation":"Screen65 before SARIF is not an OWP14 exact baseline without repository commit, scanner configuration, and source-snapshot equivalence verification."}
  raw=json.dumps(report,indent=2,sort_keys=True).encode()+b"\n"
  OUT.mkdir(parents=True,exist_ok=True)
  if not args.apply:
   with (OUT/"PREFLIGHT.json").open("xb") as f:f.write(raw)
   print(json.dumps({"status":"PREFLIGHT_PASS","before_sarif_candidates":28,"trace_log_members":traces["archive_members_screened"],"trace_case_hits":traces["case_explicit_token_log_member_hits"]},indent=2));return
  conn.execute("BEGIN IMMEDIATE")
  conn.execute("""CREATE TABLE arno_screen65_before_sarif_candidates_20261029 (
   case_id INTEGER NOT NULL REFERENCES cases(id),wave TEXT NOT NULL,zip_member_path TEXT NOT NULL UNIQUE,
   original_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,sarif_version TEXT NOT NULL,
   tool_versions_json TEXT NOT NULL,scanner_run_count INTEGER NOT NULL,result_count INTEGER NOT NULL,
   comparability_status TEXT NOT NULL,source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
   PRIMARY KEY(case_id,wave))""")
  conn.executemany("INSERT INTO "+TABLE+" VALUES(?,?,?,?,?,?,?,?,?,?,?)",[
   (r["case_id"],r["wave"],r["zip_member_path"],r["byte_count"],r["sha256"],r["sarif_version"],
    json.dumps(r["tool_versions"]),r["scanner_run_count"],r["result_count"],
    r["comparability_status"],BASE_KEY) for r in rows])
  req(conn.execute("SELECT COUNT(*) FROM "+TABLE).fetchone()[0]==28,"Count mismatch")
  req(not conn.execute("PRAGMA foreign_key_check("+TABLE+")").fetchone(),"FK conflict")
  conn.commit()
  with (OUT/"LIVE_REPORT.json").open("xb") as f:f.write(raw)
  print(json.dumps({"status":"CANDIDATES_INDEXED_NOT_ASSUMED_EQUIVALENT","cases":14,"files":28,"trace_screened":traces["archive_members_screened"]},indent=2))
 finally:conn.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("BEFORE_SARIF_CANDIDATE_AUDIT_FAILED "+repr(e),file=sys.stderr)
  sys.exit(1)
