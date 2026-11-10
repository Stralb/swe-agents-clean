#!/usr/bin/env python3
"""Prepare independent 50-root labeling worksheet from the existing Wits research data."""
import sqlite3,random,json,csv,zipfile,hashlib
from pathlib import Path
R=Path.home()/"research_artifacts"
db=sqlite3.connect("file:"+str(R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite")+"?mode=ro",uri=True)
db.row_factory=sqlite3.Row
rng=random.Random(20261031)
chosen=[];used=set()
for cls,n in [("H",6),("T",19),("M",25)]:
 rows=[dict(x) for x in db.execute("SELECT root_id,case_id,original_row_json FROM arno_d7_final_roots_342 WHERE final_route=?",(cls,))]
 rng.shuffle(rows);count=0
 for r in rows:
  if r["case_id"] in used:continue
  chosen.append(r);used.add(r["case_id"]);count+=1
  if count==n:break
 assert count==n,(cls,count)
rng.shuffle(chosen)
assert len(chosen)==50
out=R/"mcp_uploads/jobs/arno_sample_50_20261031_v3/BLIND_WORKSHEET"
out.mkdir(parents=True,exist_ok=False)
def write(name,header,items):
 with (out/name).open("w",encoding="utf-8-sig",newline="") as file:
  w=csv.DictWriter(file,fieldnames=header)
  w.writeheader()
  for item in items:
   row={}
   for k in header:
    v=item.get(k,"")
    if isinstance(v,str) and v.startswith(("=","+","-","@")):v="'"+v
    row[k]=v
   w.writerow(row)
review=[];evidence=[]
for i,r in enumerate(chosen,1):
 review_id="D7-REVIEW-%03d"%i
 case=db.execute("""SELECT c.id,rs.full_name,iss.title issue_title,iss.body issue_body,iss.url issue_url,iss.created_at issue_date,
 pr.title pr_title,pr.body pr_body,pr.url pr_url,pr.created_at pr_date,pr.base_sha,pr.head_sha
 FROM cases c JOIN repos rs ON rs.id=c.repo_id JOIN issues iss ON iss.id=c.issue_id
 JOIN pull_requests pr ON pr.id=c.pr_id WHERE c.id=?""",(r["case_id"],)).fetchone()
 original=json.loads(r["original_row_json"])
 issue_body=case["issue_body"] or ""
 pr_body=case["pr_body"] or ""
 change=original.get("root_summary","")
 pc_ids=original.get("pc_ids","")
 scan=db.execute("SELECT scanner,rule_id,severity,file_path,line,description FROM scanner_findings WHERE case_id=? ORDER BY id",(r["case_id"],)).fetchall()
 for j,f in enumerate(scan,1):
  evidence.append({"review_id":review_id,"evidence_kind":"CASE_LEVEL_SCANNER","sequence":j,"rule_id":f["rule_id"],
  "scanner":f["scanner"],"severity":f["severity"],"file_path":f["file_path"],"line":f["line"],"text":f["description"],
  "scope_note":"CASE_LEVEL_NOT_PROVEN_ROOT_SPECIFIC"})
 review.append({"review_id":review_id,"case_id":r["case_id"],"root_reference":r["root_id"],
 "repository":case["full_name"],"issue_url":case["issue_url"],"issue_title":case["issue_title"],
 "issue_body":issue_body,"issue_date":case["issue_date"],"pr_url":case["pr_url"],
 "pr_title":case["pr_title"],"pr_body":pr_body,"pr_date":case["pr_date"],
 "pr_base_commit":case["base_sha"],"pr_head_commit":case["head_sha"],
 "root_implementation_summary":change,"root_member_change_ids":pc_ids,
 "scanner_warning_count_case_level":len(scan),
 "YOUR_ROUTE_H_T_M_U":"","YOUR_TIER_IF_M":"","YOUR_CHRONOLOGY_YES_NO_UNCLEAR":"",
 "YOUR_EVIDENCE_COMPLETE_YES_NO_UNCLEAR":"","YOUR_HUMAN_DIRECTIVE_YES_NO_UNCLEAR":"",
 "YOUR_TOOLCHAIN_AUTOMATION_YES_NO_UNCLEAR":"","YOUR_DIRECT_REUSE_YES_NO_UNCLEAR":"",
 "YOUR_REPOSITORY_PRECEDENT_YES_NO_UNCLEAR":"","YOUR_PRECHANGE_GUIDANCE_YES_NO_UNCLEAR":"",
 "YOUR_CONTEXTUAL_PLAUSIBILITY_YES_NO_UNCLEAR":"",
 "YOUR_CONFIDENCE_HIGH_MEDIUM_LOW":"","YOUR_EVIDENCE_LINKS":"","YOUR_JUSTIFICATION":"",
 "YOUR_MISSING_MATERIAL":"","YOUR_REVIEW_DATE":"","YOUR_REVIEWER_ID":""})
write("01_BLINDED_REVIEW_50.csv",list(review[0]),review)
write("02_SCANNER_EVIDENCE.csv",["review_id","evidence_kind","sequence","rule_id","scanner","severity","file_path","line","text","scope_note"],evidence)
summary={
 "n_root_decisions":len(review),"n_distinct_cases":len(used),"seed":20261031,
 "selection":"stratified reference route, six H, 19 T, 25 M, reshuffled",
 "original_route_or_tier_in_csv":False,
 "original_rationale_or_adjudication_in_csv":False,
 "issue_pr_from_live_wits_db":True,
 "warning_scope":"case-level, may include different root decisions",
 "exact_producing_diff":"root_implementation_summary, not always complete original diff",
 "use":"independent single-human blinded re-review, no code execution",
 "source_sha256":hashlib.sha256((out/"01_BLINDED_REVIEW_50.csv").read_bytes()).hexdigest()}
(out/"03_AUDIT_MANIFEST.json").write_text(json.dumps(summary,indent=2))
(out/"04_README.txt").write_text("Write your labels ONLY into the YOUR_ columns. Read the separate codebook first. Do not open the reference classifications or the original database table during labeling. Issue and PR information may postdate the implementation; check chronology. Scanner warnings are scanner evidence, not proof of exploitability. A source root summary is not a substitute for the full patch. Reference labels are intentionally absent. This is a single-human validation, not independent human-human reliability.")
with zipfile.ZipFile(out/"D7_BLIND_SAMPLE_50.zip","w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for file in out.iterdir():
  if file.suffix in (".csv",".json",".txt"):z.write(file,file.name)
print(json.dumps({"status":"CREATED","zip_size":(out/"D7_BLIND_SAMPLE_50.zip").stat().st_size,
"cases":len(review),"distinct_cases":len(used),"scanner_rows":len(evidence)},indent=2))
