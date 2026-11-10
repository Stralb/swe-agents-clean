#!/usr/bin/env python3
"""Read-only O/W/P ISSUE.md to mined GitHub issue-text comparison.
No issue text, prompt content, source code, or credentials emitted.
Comparisons against miner DB do NOT establish exact historical PR-time wording.
"""
import sqlite3,zipfile,re,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from collections import Counter
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
PACK=R/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
OUT=R/"mcp_uploads/jobs/arno_v6_20261030_owp14_issue_text_comparison/REPORT.json"
def norm(s):
 return re.sub(r"\s+"," ",str(s or "").casefold()).strip()
def datestamp(s):
 if not s:return None
 try:
  d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
  return d.timestamp() if d.tzinfo else d.replace(tzinfo=timezone.utc).timestamp()
 except (TypeError,ValueError):return None
c=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
c.execute("PRAGMA query_only=ON")
rows=c.execute("""SELECT c.id,i.title,i.body,i.created_at,i.updated_at,p.created_at
FROM arno_owp14_input_repo_equivalence_20261029 r
JOIN cases c ON c.id=r.case_id
JOIN issues i ON i.id=c.issue_id
JOIN pull_requests p ON p.id=c.pr_id ORDER BY c.id""").fetchall()
assert len(rows)==14
items=[]
for case,title,body,created,updated,pr_created in rows:
 issue_title=norm(title);issue_body=norm(body)
 per={}
 for arm in "OWP":
  path=PACK/f"CASE_{case:05d}_{arm}.zip"
  with zipfile.ZipFile(path) as z:
   hits=[i for i in z.infolist() if not i.is_dir() and re.search(r"(?:^|/)ISSUE\.md$",i.filename,re.I)]
   assert len(hits)==1,(case,arm,"missing or duplicate ISSUE.md")
   original=z.read(hits[0])
  md=original.decode("utf-8","replace")
  txt=norm(md)
  per[arm]={"issue_md_sha256":hashlib.sha256(original).hexdigest(),
   "issue_md_chars":len(md),
   "mined_issue_title_verbatim_present":len(issue_title)>=8 and issue_title in txt,
   "mined_issue_body_verbatim_present":len(issue_body)>=40 and issue_body in txt,
   "mined_issue_body_exact_after_whitespace_normalization":len(issue_body)>=40 and issue_body==txt}
 a=datestamp(updated);b=datestamp(pr_created)
 items.append({"case_id":case,
  "mined_issue_title_present":len(issue_title)>0,
  "mined_issue_body_present":len(issue_body)>0,
  "mined_issue_body_chars":len(body or ""),
  "mined_issue_updated_after_pr_opening":a>b if a is not None and b is not None else None,
  "issue_created_at_present":bool(created),
  "pr_created_at_present":bool(pr_created),
  "arms":per,
  "historical_pr_time_body_verified":False})
summary={"cases":len(items),
  "cases_with_mined_issue_body":sum(x["mined_issue_body_present"] for x in items),
  "cases_with_mined_issue_title":sum(x["mined_issue_title_present"] for x in items),
  "cases_with_mined_issue_updated_after_pr_opening":sum(x["mined_issue_updated_after_pr_opening"] is True for x in items),
  "cases_with_unknown_issue_update_chronology":sum(x["mined_issue_updated_after_pr_opening"] is None for x in items),
  "title_verbatim_matches_by_arm":{a:sum(x["arms"][a]["mined_issue_title_verbatim_present"] for x in items) for a in "OWP"},
  "body_verbatim_matches_by_arm":{a:sum(x["arms"][a]["mined_issue_body_verbatim_present"] for x in items) for a in "OWP"},
  "full_body_whitespace_normalized_exact_matches_by_arm":{a:sum(x["arms"][a]["mined_issue_body_exact_after_whitespace_normalization"] for x in items) for a in "OWP"},
  "historical_pr_time_body_verifications":0}
report={"status":"OWP14_ISSUE_TEXT_VS_MINER_METADATA_AUDIT_COMPLETE",
 "utc":datetime.now(timezone.utc).isoformat(),
 "summary":summary,"cases":items,
 "method":"Case-linked raw ZIP ISSUE.md decoded; casefolded whitespace-normalized containment checked against miner issues.title/body. No raw text exposed.",
 "limitations":[
  "The miner issues.body is not a proven historical PR-time version, especially where issues.updated_at exceeds PR opening time.",
  "Containment or exact match is only a linkage to available miner text, not independent proof of historical original issue wording.",
  "The frozen packet index marks historical issue wording unverified for all 42 inputs.",
  "Original agent execution, output patches and functional equivalence require separate evidence."
 ]}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(report,f,indent=2)
print(json.dumps({"status":report["status"],"summary":summary,"case_flags":[{"case_id":x["case_id"],"issue_edited_after_pr":x["mined_issue_updated_after_pr_opening"],"O_contains_mined_body":x["arms"]["O"]["mined_issue_body_verbatim_present"]} for x in items]},indent=2))
