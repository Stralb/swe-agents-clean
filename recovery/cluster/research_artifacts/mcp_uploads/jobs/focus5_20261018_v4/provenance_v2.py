#!/usr/bin/env python3
"""GitHub REST timeline chronology; read-only public issue metadata; no source generation."""
import os,json,hashlib,sqlite3,time,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
OUT=R/("focus5_provenance_job"+os.environ["SLURM_JOB_ID"]);OUT.mkdir(exist_ok=False)
DATA=Path.home()/"new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.full3809-continuation.db"
db=sqlite3.connect("file:"+str(DATA)+"?mode=ro",uri=True)
db.row_factory=sqlite3.Row;db.execute("PRAGMA query_only=ON")
rows=db.execute("""SELECT c.id cid,r.full_name repo,i.number issue_no,i.body corpus_body,i.updated_at updated,p.created_at pr_created
FROM cases c JOIN repos r ON r.id=c.repo_id JOIN issues i ON i.id=c.issue_id JOIN pull_requests p ON p.id=c.pr_id
WHERE c.id IN (668,3581,6104,8152,22223) ORDER BY c.id""").fetchall();db.close()
def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"WitsCausalIssueAudit/1.0","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"})
 with urllib.request.urlopen(req,timeout=35) as f:
  raw=f.read(12*1024*1024)
  if len(raw)>11*1024*1024:raise RuntimeError("response_limit")
  return json.loads(raw)
def dt(v):return datetime.fromisoformat(v.replace("Z","+00:00"))
def sha(v):return hashlib.sha256(v.encode()).hexdigest()
results=[]
for case in rows:
 cid=case["cid"];repo=case["repo"];issue_no=case["issue_no"];old=case["corpus_body"] or ""
 pr=dt(case["pr_created"])
 report={"case_id":cid,"repo":repo,"issue_no":issue_no,"pr_created":case["pr_created"],
         "corpus_body_sha256":sha(old),"corpus_body_chars":len(old),"state":"START","edited_events":[]}
 try:
  current=get("https://api.github.com/repos/%s/issues/%s"%(repo,issue_no))
  latest=current.get("body") or ""
  report["live_body_sha256"]=sha(latest);report["corpus_equals_live"]=(old==latest)
  all_events=[]
  for page in range(1,11):
   events=get("https://api.github.com/repos/%s/issues/%s/timeline?per_page=100&page=%d"%(repo,issue_no,page))
   if not isinstance(events,list):raise ValueError("timeline_not_list")
   all_events += events
   if len(events)<100:break
  else:raise RuntimeError("timeline_pagination_limit")
  edits=[]
  for event in all_events:
   if event.get("event")!="edited":continue
   changes=event.get("changes") or {}
   if "body" not in changes:continue
   bodychange=changes.get("body")
   oldbody=bodychange.get("from") if isinstance(bodychange,dict) else None
   item={"timestamp":event.get("created_at"),"body_old_present":isinstance(oldbody,str),
      "body_old":oldbody,
      "changes_keys":sorted(changes.keys())}
   edits.append(item)
  report["timeline_events"]=len(all_events)
  report["edit_events"]=len(edits)
  report["edit_after_pr"]=sum(bool(e["timestamp"] and dt(e["timestamp"])>pr) for e in edits)
  report["edited_events"]=[{k:v for k,v in e.items() if k!="body_old"} for e in edits]
  reconstructed=latest
  can_reconstruct=True
  for e in sorted(edits,key=lambda e:e["timestamp"] or "",reverse=True):
   if e["timestamp"] and dt(e["timestamp"])>pr:
    if e["body_old_present"]:reconstructed=e["body_old"]
    else:can_reconstruct=False
  report["reconstruction_complete"]=can_reconstruct
  if can_reconstruct:
   report["reconstructed_prepr_body_sha256"]=sha(reconstructed)
   report["reconstructed_prepr_body_chars"]=len(reconstructed)
   report["original_O_body_prepr_match"]=(old==reconstructed)
   report["state"]="CORPUS_PREPR_BODY_CONFIRMED_BY_TIMELINE" if old==reconstructed else "CORPUS_BODY_DIFFERS_FROM_RECONSTRUCTED_PREPR"
   (OUT/("CASE_%05d_PREPR_ISSUE.txt"%cid)).write_text(reconstructed)
  else:report["state"]="PREPR_ISSUE_BODY_UNRESOLVED_EDITS"
 except Exception as e:
  report["state"]="PROVENANCE_BLOCKED";report["reason"]=repr(e)[:650]
 (OUT/("CASE_%05d_RESULT.json"%cid)).write_text(json.dumps(report,indent=2)+"\n")
 results.append(report)
 print("PROVENANCE",cid,report["state"],report.get("edit_after_pr"),flush=True)
 time.sleep(1)
(OUT/"SUMMARY.json").write_text(json.dumps({"cases":results,"total":len(results),"limitations":["Public API timelines may omit historical edit payloads or older events","Event timestamps must be interpreted relative to historical PR creation; issue updated_at alone is not proof of an edited body","A GitHub public issue may have been removed or migrated; blocked is not disproven"],"no_generated_code":True},indent=2)+"\n")
print("PROVENANCE_DONE",OUT)
