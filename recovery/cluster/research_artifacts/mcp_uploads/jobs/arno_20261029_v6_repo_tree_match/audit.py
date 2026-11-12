#!/usr/bin/env python3
"""Read-only equality test for original O/W/P packet REPO/ trees. No extraction or source disclosure."""
from pathlib import Path
from collections import Counter
import zipfile,sqlite3,json,re,hashlib
R=Path.home()/"research_artifacts"
D=R/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
O=R/"mcp_uploads/jobs/arno_20261029_v6_repo_tree_match/REPORT.json"
C=sqlite3.connect("file:"+str(R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite")+"?mode=ro",uri=True)
C.execute("PRAGMA query_only=ON")
rows=C.execute("SELECT case_id,arm,original_filename FROM arno_owp14_original_input_packet_inventory_20261029").fetchall()
assert len(rows)==42
def filehash(z,info):
 h=hashlib.sha256()
 with z.open(info) as f:
  for data in iter(lambda:f.read(4*1024*1024),b""):h.update(data)
 return h.hexdigest()
def members(path):
 repo={};issues=[];instructions=[]
 with zipfile.ZipFile(path) as z:
  for i in z.infolist():
   if i.is_dir():continue
   n=i.filename.replace("\\","/")
   match=re.search(r"(?:^|/)REPO/(.+)$",n,re.I)
   if match:
    key=match.group(1)
    if ".." in key.split("/") or key in repo:raise RuntimeError("Invalid REPO member")
    repo[key]=(i.file_size,filehash(z,i))
   elif re.search(r"(?:^|/)ISSUE\.md$",n,re.I):issues.append(filehash(z,i))
   elif re.search(r"(?:^|/)RUN_INSTRUCTIONS\.md$",n,re.I):instructions.append(filehash(z,i))
 assert repo,"Empty REPO"
 h=hashlib.sha256()
 for name,(size,sha) in sorted(repo.items()):
  h.update(name.encode()+b"\x00"+str(size).encode()+b"\x00"+sha.encode()+b"\n")
 return {"entries":repo,"fingerprint":h.hexdigest(),"issues":issues,"instructions":instructions,
         "files":len(repo),"bytes":sum(x[0] for x in repo.values())}
cases={}
for case,arm,name in rows:cases.setdefault(case,{})[arm]=members(D/name)
out=[]
for case,arms in sorted(cases.items()):
 assert set(arms)=={"O","W","P"}
 a,b,c=[arms[k] for k in "OWP"]
 same=a["entries"]==b["entries"]==c["entries"]
 out.append({"case_id":case,"same_repo_tree_contents_all_arms":same,
  "source_tree_sha256":a["fingerprint"] if same else None,
  "repo_files_by_arm":{k:v["files"] for k,v in arms.items()},
  "repo_bytes_by_arm":{k:v["bytes"] for k,v in arms.items()},
  "issue_present_by_arm":{k:bool(v["issues"]) for k,v in arms.items()},
  "distinct_issue_file_hashes":len(set(y for v in arms.values() for y in v["issues"])),
  "historical_git_revision_match":"NOT_VERIFIED"})
summary={"cases":len(out),"arms":len(rows),"identical_repository_content_cases":sum(x["same_repo_tree_contents_all_arms"] for x in out),
"nonidentical_repository_content_cases":sum(not x["same_repo_tree_contents_all_arms"] for x in out),
"cases_with_issue_in_all_arms":sum(all(x["issue_present_by_arm"].values()) for x in out),
"issue_distinct_hash_count_distribution":dict(Counter(x["distinct_issue_file_hashes"] for x in out))}
report={"status":"REPO_TREE_INPUT_EQUALITY_AUDIT_COMPLETE","summary":summary,"per_case":out,
"method":"Uncompressed ZIP REPO member paths and SHA256, no extraction.",
"limit":"Equal source trees among treatment arms do not prove PR-time revision or historical issue text."}
O.parent.mkdir(parents=True,exist_ok=True)
with O.open("x") as f:json.dump(report,f,indent=2)
print(json.dumps(summary,indent=2))
