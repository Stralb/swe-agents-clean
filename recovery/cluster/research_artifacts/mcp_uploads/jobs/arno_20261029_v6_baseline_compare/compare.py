#!/usr/bin/env python3
"""Read-only compare historical Screen65 before-SARIF finding signatures, no prompt or source text exported."""
import sqlite3,json,zipfile,hashlib
from pathlib import Path
from collections import Counter
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ZIP=R/"ARNO_CODEQL_EXPORT_20261019/05_SCREEN65_EVIDENCE.zip"
OUT=R/"mcp_uploads/jobs/arno_20261029_v6_baseline_compare/REPORT.json"
def digest(b):return hashlib.sha256(b).hexdigest()
db=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
db.execute("PRAGMA query_only=ON")
rows=db.execute("SELECT case_id,wave,zip_member_path,sha256,result_count FROM arno_screen65_before_sarif_candidates_20261029").fetchall()
assert len(rows)==28
cases={}
with zipfile.ZipFile(ZIP) as z:
 for case,wave,path,expected,n in rows:
  raw=z.read(path)
  assert digest(raw)==expected
  sarif=json.loads(raw)
  features=[]
  for run in sarif.get("runs",[]):
   for finding in run.get("results",[]):
    msg=finding.get("message",{}).get("text","")
    features.append((finding.get("ruleId",""),finding.get("kind",""),finding.get("level",""),digest(msg.encode())[:16]))
  assert len(features)==n
  cases.setdefault(case,{})[wave]={"count":n,"sha256":expected,
    "rules":Counter(t[0] for t in features),"findings":Counter(features)}
out=[]
for case,waves in sorted(cases.items()):
 a=waves["SCREEN65_FIRST"];b=waves["SCREEN65_SECOND"]
 out.append({"case_id":case,"first_findings":a["count"],"second_findings":b["count"],
  "same_raw_sarif":a["sha256"]==b["sha256"],
  "same_rule_multiset":a["rules"]==b["rules"],
  "same_normalized_findings":a["findings"]==b["findings"],
  "shared_normalized_finding_count":sum((a["findings"]&b["findings"]).values()),
  "source_commit_equivalence":"NOT_VERIFIED"})
summary={"cases":len(out),"identical_raw_files":sum(row["same_raw_sarif"] for row in out),
 "same_rule_multisets":sum(row["same_rule_multiset"] for row in out),
 "same_normalized_findings":sum(row["same_normalized_findings"] for row in out)}
result={"status":"READ_ONLY_SCREEN65_COMPARISON_COMPLETE","summary":summary,"cases":out,
 "method":"Multisets of (ruleId,kind,level,hashed message text). Paths and line numbers omitted.",
 "limitation":"Not evidence that Screen65 baselines are the exact later OWP14 baselines; source commit and scan configuration equivalence remain unverified."}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(result,f,indent=2)
print(json.dumps({"status":result["status"],"summary":summary},indent=2))
