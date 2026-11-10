#!/usr/bin/env python3
"""Immutable analysis package of six-case paired A/C results, not the master research DB."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,sqlite3
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_ac6_v6_20261030"
SRC=D/"results_v6c";OUT=D/"summary_v6e"
CASES=("03429","03581","08152","12344","31207","32759")
ARMS=("MECHANISM","PROSPECTIVE_BUILD")
def dig(b):return hashlib.sha256(b).hexdigest()
assert not OUT.exists(),"Refuse to overwrite results summary"
OUT.mkdir(parents=True,mode=0o700)
rows=[];findings=[];census=[]
for case in CASES:
 pair=[]
 for arm in ARMS:
  p=SRC/("CASE_"+case)/arm/"RESULT.json"
  assert p.is_file(),"Missing "+str(p)
  d=json.loads(p.read_text())
  assert d["case_id"]==case and d["arm"]==arm
  pair.append(d)
  row={
   "case_id":case,"arm":arm,"run_id":d.get("run_id"),"status":d["status"],
   "source_kind":d.get("source_kind"),"source_zip_sha256":d.get("source_zip_sha256"),
   "repo_tree_sha256":d.get("repo_tree_sha256"),
   "original_p1_new":d.get("original_p1_new"),"baseline_total":d.get("baseline_total"),
   "after_total":d.get("after_total"),"new_warnings":d.get("new_conservative_line_agnostic"),
   "historical_p1_new_keys_retained":d.get("historical_p1_new_keys_retained"),
   "historical_p1_new_keys_avoided":d.get("historical_p1_new_keys_avoided"),
   "new_by_rule":json.dumps(d.get("new_by_rule",{}),sort_keys=True),
   "functional_status":d.get("functional_status"),"agent_generation_status":d.get("agent_generation_status"),
   "patch_sha256":d.get("patch_sha256"),"receipt_sha256":d.get("receipt_sha256"),
   "after_sarif_sha256":d.get("after_sarif_sha256"),
   "error_type":d.get("error_type"),"error_message":d.get("error_message"),
   "result_json_sha256":dig(p.read_bytes()),
   "result_json_path":str(p.relative_to(R)),
   "sarif_path":str((p.parent/"after.sarif").relative_to(R)) if (p.parent/"after.sarif").exists() else None
  }
  rows.append(row)
  for f in d.get("new_findings",[]):
   findings.append({"case_id":case,"arm":arm,"rule":f.get("rule"),"file":f.get("file"),
    "line":f.get("line"),"message":f.get("message"),"count":f.get("count")})
 assert len(pair)==2
 census.append({"case_id":case,"original_p1_new":pair[0].get("original_p1_new"),
  "A_new":pair[0].get("new_conservative_line_agnostic"),
  "C_new":pair[1].get("new_conservative_line_agnostic"),
  "A_status":pair[0]["status"],"C_status":pair[1]["status"],
  "A_generation":pair[0].get("agent_generation_status"),
  "C_generation":pair[1].get("agent_generation_status")})
record={"created_utc":datetime.now(timezone.utc).isoformat(),
 "method":"Common frozen baseline; CodeQL javascript-security-extended suite; stable key=(rule,path,message); new=after-baseline multiset",
 "limitations":["CodeQL findings are not confirmed vulnerabilities","No general functional correctness evidence for this cohort",
  "Some frozen sources are filtered provisional snapshots","One run per case/arm","Windows-specific behavior not natively tested"],
 "runs":rows,"findings":findings,"case_matrix":census,
 "all_scans_complete":all(x["status"]=="CODEQL_SCAN_COMPLETE" for x in rows)}
(OUT/"RESULTS.json").write_text(json.dumps(record,indent=2))
with (OUT/"RUNS.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with (OUT/"CASE_MATRIX.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(census[0]));w.writeheader();w.writerows(census)
connection=sqlite3.connect(OUT/"AC_SIX_CASE_RESULTS.sqlite")
connection.execute("PRAGMA journal_mode=DELETE")
connection.execute("""CREATE TABLE runs (case_id TEXT NOT NULL,arm TEXT NOT NULL,
 run_id TEXT,status TEXT,source_kind TEXT,original_p1_new INTEGER,baseline_total INTEGER,
 after_total INTEGER,new_warnings INTEGER,historical_p1_new_keys_avoided INTEGER,
 patch_sha256 TEXT,receipt_sha256 TEXT,after_sarif_sha256 TEXT,agent_generation_status TEXT,
 functional_status TEXT,result_json_path TEXT,PRIMARY KEY(case_id,arm))""")
connection.executemany("""INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
 [tuple(x.get(k) for k in ("case_id","arm","run_id","status","source_kind","original_p1_new",
  "baseline_total","after_total","new_warnings","historical_p1_new_keys_avoided","patch_sha256",
  "receipt_sha256","after_sarif_sha256","agent_generation_status","functional_status","result_json_path"))
 for x in rows])
connection.execute("""CREATE TABLE findings (case_id TEXT,arm TEXT,rule TEXT,file TEXT,
 line INTEGER,message TEXT,count INTEGER)""")
connection.executemany("INSERT INTO findings VALUES (?,?,?,?,?,?,?)",
 [tuple(x.get(k) for k in ("case_id","arm","rule","file","line","message","count")) for x in findings])
connection.commit();connection.close()
print(json.dumps({"ready":True,"all_scans_complete":record["all_scans_complete"],"matrix":census,
 "results_path":str(OUT)},indent=2),flush=True)
