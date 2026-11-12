#!/usr/bin/env python3
# Researcher-only evidence audit. Read-only sources. No historical PR or O patch executed.
import csv,hashlib,json,os,re,sqlite3,zipfile
from pathlib import Path
from datetime import datetime
p=Path.home()/"research_artifacts/prevention_pilot_phase2"
cid_list=[668,3429,3581,6104,8152,8461,12344,15151,16633,20094,21682,22223,31207,32759]
jid=os.environ["SLURM_JOB_ID"]
out=p/("dual_o_audit14_job"+jid);out.mkdir(exist_ok=False);(out/"cases").mkdir()
def load(q):return json.loads(q.read_text())
def sha(q):
 h=hashlib.sha256()
 with q.open("rb") as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def save(q,data):
 with q.open("x",encoding="utf8") as f:f.write(data)
def sdate(s):
 try:return datetime.fromisoformat((s or "").replace("Z","+00:00"))
 except:return None
def map_lines(q):
 d={};file=None;line=None
 for v in q.read_text(errors="replace").splitlines():
  if v.startswith("diff --git "):
   m=re.match(r"diff --git a/(.*?) b/(.*?)$",v);file=m.group(2) if m else None
   if file:d.setdefault(file,{"added":set(),"text":{},"plus":0,"minus":0})
   line=None
  elif file and v.startswith("@@"):
   m=re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@",v);line=int(m.group(1)) if m else None
  elif file and line is not None:
   if v.startswith("+") and not v.startswith("+++"):
    d[file]["added"].add(line);d[file]["text"][line]=v[1:];d[file]["plus"]+=1;line+=1
   elif v.startswith("-") and not v.startswith("---"):d[file]["minus"]+=1
   elif v.startswith(" "):line+=1
 return d
manifests=[p/"screen65_static_analysis_job70606/TRANSFER_MANIFEST.json",p/"screen65_second_20261018_v1/TRANSFER_MANIFEST.json"]
m=[{z["case_id"]:z for z in load(q)["patches"]} for q in manifests]
first=p/"screen65_codeql_job70675";second=p/"screen65_second_codeql_job70782";retry=p/"screen65_second_codeql_retry_job70880"
full=p/"remaining65_archives_oct17_v1";filtered=p/"remaining65_targeted14_v1"
db_path=Path.home()/"new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.full3809-continuation.db"
db=sqlite3.connect("file:"+str(db_path)+"?mode=ro",uri=True);db.row_factory=sqlite3.Row;db.execute("PRAGMA query_only=ON")
arg=",".join("?" for _ in cid_list)
rs=db.execute("SELECT c.id as cid,r.full_name as repo,i.number as issue_no,p.number as pr_no,i.title as title,i.body as body,i.url as issue_url,p.url as pr_url,i.created_at as created,i.updated_at as updated,p.created_at as pr_created,p.base_sha as base_sha,p.head_sha as head_sha FROM cases c JOIN repos r ON r.id=c.repo_id JOIN issues i ON i.id=c.issue_id JOIN pull_requests p ON p.id=c.pr_id WHERE c.id IN ("+arg+") ORDER BY c.id",cid_list).fetchall()
hs=db.execute("SELECT case_id,rule_id,file_path,line,introduced,severity,description FROM scanner_findings WHERE scanner='codeql' AND case_id IN ("+arg+") ORDER BY case_id,rule_id,file_path,line",cid_list).fetchall()
db.close();assert len(rs)==14
hist={}
for v in hs:hist.setdefault(v["case_id"],[]).append(dict(v))
summaries=[]
for row in rs:
 case=dict(row);id=case.pop("cid");body=case.pop("body") or "";name="CASE_%05d"%id
 patch=[p/"screen65_static_analysis_job70606/patches"/(name+".patch"),p/"screen65_second_20261018_v1/patches"/(name+".patch")]
 assert all(sha(patch[j])==m[j][id]["sha256"] for j in (0,1)) and sha(patch[0])!=sha(patch[1])
 scan=[first/name/"RESULT.json",(retry if id in (16633,25473) else second)/name/"RESULT.json"]
 raw=[load(q) for q in scan]
 assert all(x["stage"]=="SCAN_COMPLETE" and x["case_id"]==id for x in raw)
 assert all(x["suite"]=="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls" for x in raw)
 state=load(full/(name+".status.json"))
 assert state["base_sha"]==case["base_sha"],id
 archive=full/(name+".zip")
 if not archive.exists():archive=filtered/(name+".zip")
 kind="FULL_FROZEN_SNAPSHOT" if archive.parent==full else "FILTERED_SOURCE_PROVISIONAL"
 assert all(x["source_type"]==kind for x in raw)
 archive_sha=sha(archive)
 if kind=="FULL_FROZEN_SNAPSHOT":assert state["archive_sha256"]==archive_sha
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  paths=[x for x in z.namelist() if x.startswith("REPO/") and not x.endswith("/")]
  root_files=[x for x in paths if x.count("/")==1]
  tests=[x for x in paths if "/__tests__/" in x or "/tests/" in x or re.search(r"\.(test|spec)\.[cm]?[jt]sx?$",x)]
  scripts={}
  if "REPO/package.json" in z.namelist():
   try:scripts={a:b for a,b in json.loads(z.read("REPO/package.json")).get("scripts",{}).items() if any(k in a.lower() for k in ("test","build","lint","type","check"))}
   except Exception:scripts={"error":"package.json parse error"}
  tasknames=[x for x in z.namelist() if x in ("ISSUE.md","TASK.md","CASE_METADATA.json")]
  tasksha={x:hashlib.sha256(z.read(x)).hexdigest() for x in tasknames}
  source_files=len(paths)
 issue_before=bool(sdate(case["created"]) and sdate(case["pr_created"]) and sdate(case["created"])<=sdate(case["pr_created"]))
 updated_before=bool(issue_before and sdate(case["updated"]) and sdate(case["updated"])<=sdate(case["pr_created"]))
 hi=hist[id];historical_rules={v["rule_id"] for v in hi if v["introduced"]==1}
 historical_pairs={(v["rule_id"],v["file_path"]) for v in hi if v["introduced"]==1}
 diffs=[map_lines(v) for v in patch]
 attempts=[]
 for j in (0,1):
  findings=[]
  for f in raw[j]["findings"]["new_strong_findings"]:
   f=dict(f);d=diffs[j].get(f["path"]);ln=f.get("line")
   f.update({"historical_rule_match":f["rule"] in historical_rules,
      "historical_same_rule_file":(f["rule"],f["path"]) in historical_pairs,
      "finding_on_added_line":bool(d and ln in d["added"]),
      "path_in_patch":bool(d),
      "patch_added_excerpt":[str(k)+": "+v[:180] for k,v in (d or {}).get("text",{}).items() if isinstance(ln,int) and abs(k-ln)<=5][:12]})
   findings.append(f)
  assert len(findings)==raw[j]["findings"]["new_strong_count"]
  attempts.append({"name":"O"+str(j+1),"claimed_status":raw[j].get("claimed_status"),
      "codeql_new":len(findings),"before":raw[j]["findings"]["before_total"],"after":raw[j]["findings"]["after_total"],
      "patch_sha256":sha(patch[j]),"scan_sha256":sha(scan[j]),
      "changed_paths":sorted(diffs[j]),
      "edited_test_paths":[x for x in diffs[j] if "test" in x.lower() or "spec" in x.lower()],
      "added_lines":sum(y["plus"] for y in diffs[j].values()),
      "removed_lines":sum(y["minus"] for y in diffs[j].values()),"findings":findings})
 allfind=attempts[0]["findings"]+attempts[1]["findings"]
 overlap=any(v["historical_rule_match"] for v in allfind)
 samefile=any(v["historical_same_rule_file"] for v in allfind)
 overview={"case_id":id,"repository":case["repo"],"issue_title":case["title"],
   "source":kind,"repo_files":source_files,"issue_before_pr":issue_before,
   "issue_timestamp_compatible":updated_before,"historical_rules":";".join(sorted(historical_rules)),
   "O1_codeql_new":attempts[0]["codeql_new"],"O2_codeql_new":attempts[1]["codeql_new"],
   "O1_historical_matches":sum(v["historical_rule_match"] for v in attempts[0]["findings"]),
   "O2_historical_matches":sum(v["historical_rule_match"] for v in attempts[1]["findings"]),
   "any_historical_rule":overlap,"any_same_rule_file":samefile,
   "historical_exact_ql":"NOT_RUN","functional_status":"NOT_TESTED","property_status":"NOT_TESTED",
   "W_P_status":"NOT_GENERATED"}
 summaries.append(overview)
 details={"summary":overview,"case":case,"issue_body":body,
    "issue_body_sha256":hashlib.sha256(body.encode()).hexdigest(),
    "historical_warnings":hi,"source":{"archive":str(archive),"sha256":archive_sha,"archive_status":state,
    "test_file_count":len(tests),"sample_test_files":tests[:24],
    "root_files":root_files,"root_test_build_scripts":scripts,"task_file_shas":tasksha},
    "attempts":attempts,
    "limitations":["Issue body version not historically proven","Exact historical .ql replay not performed",
    "CodeQL rule similarity is not equivalent to same exploit mechanism","Functional acceptance remains unknown",
    "Filtered sources are provisional","Selection on prior O positives requires new randomized O controls"]}
 with (out/"cases"/(name+".json")).open("x",encoding="utf8") as f:json.dump(details,f,indent=2,ensure_ascii=False);f.write("\n")
 lines=["# "+name+" "+case["repo"],"",
 "RESEARCHER ONLY - do not give warning context or these dossiers to O generators","",
 "Issue: "+case["issue_url"],"Historical PR: "+case["pr_url"],
 "Task title: "+case["title"],"Base commit: "+case["base_sha"],"Head commit: "+case["head_sha"],
 "Issue created: "+case["created"],"Issue last updated: "+case["updated"],"PR created: "+case["pr_created"],
 "Issue-body version: "+("TIMESTAMP-COMPATIBLE BUT NOT PINNED" if updated_before else "UNVERIFIED"),
 "Source: "+kind+", "+str(source_files)+" files; existing test files: "+str(len(tests)),
 "Available project test/build scripts: "+json.dumps(scripts,ensure_ascii=False),"",
 "## Historical findings"]
 for h in hi:lines.append("- "+h["rule_id"]+" "+h["file_path"]+":"+str(h["line"])+" "+(h.get("description") or "").replace("\n"," ")[:190])
 for a in attempts:
  lines+=["","## "+a["name"],"Claim: "+str(a["claimed_status"]),
  "Findings: "+str(a["codeql_new"]),"Changed paths: "+", ".join(a["changed_paths"])]
  for v in a["findings"]:
   lines.append("- "+v["rule"]+" "+v["path"]+":"+str(v.get("line"))+" | historical_rule="+str(v["historical_rule_match"])+" | historical_file="+str(v["historical_same_rule_file"])+" | patch_added_line="+str(v["finding_on_added_line"])+" | "+v.get("message","").replace("\n"," "))
   lines.extend("  + "+s for s in v["patch_added_excerpt"][:8])
 lines+=["","## Mandatory human/gated follow-up","",
 "- [ ] Verify exact as-of-PR issue body or mark retrospective text leakage",
 "- [ ] Replay historical exact .ql query on base vs historical PR head",
 "- [ ] Audit source-to-sink and changes for each O CodeQL finding",
 "- [ ] Freeze task-level functional acceptance tests and independent safety oracle",
 "- [ ] Run tests on O1 and O2; distinguish PARTIAL, non-buildable, and functional",
 "- [ ] Recover full base repo for FILTERED cases",
 "- [ ] Generate fresh randomized O controls and W/P only after eligibility",
 "- [ ] Preserve unaltered scanner results, failures, and full denominator",""]
 with (out/"cases"/(name+".md")).open("x",encoding="utf8") as f:f.write("\n".join(lines)+"\n")
with (out/"AUDIT14_OVERVIEW.csv").open("x",newline="",encoding="utf8") as f:
 w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
counts={"unique":14,"O1_positive":sum(x["O1_codeql_new"]>0 for x in summaries),
 "O2_positive":sum(x["O2_codeql_new"]>0 for x in summaries),
 "both_positive":sum(x["O1_codeql_new"]>0 and x["O2_codeql_new"]>0 for x in summaries),
 "historical_rule_overlap":sum(x["any_historical_rule"] for x in summaries),
 "same_rule_file":sum(x["any_same_rule_file"] for x in summaries),
 "full_source":sum(x["source"]=="FULL_FROZEN_SNAPSHOT" for x in summaries),
 "filtered_source":sum(x["source"]!="FULL_FROZEN_SNAPSHOT" for x in summaries),
 "issue_timestamp_compatible":sum(x["issue_timestamp_compatible"] for x in summaries)}
manifest={"job_id":jid,"researcher_only":True,"counts":counts,
 "inputs":{"patch_manifests":[str(x) for x in manifests],"database":str(db_path)},
 "no_functional_tests_executed":True,"no_intervention_executed":True,"rows":summaries}
with (out/"AUDIT14_MANIFEST.json").open("x",encoding="utf8") as f:json.dump(manifest,f,indent=2);f.write("\n")
table=["# Audit14 dual-O evidence review","","RESEARCHER ONLY; NOT FOR BLIND GENERATION","",
 "|Case|Repository|O1|O2|Historical rule|Same file|Source|Issue text|",
 "|---|---|---:|---:|---|---|---|---|"]
for x in summaries:
 table.append("|"+str(x["case_id"])+"|"+x["repository"]+"|"+str(x["O1_codeql_new"])+"|"+str(x["O2_codeql_new"])+"|"+str(x["any_historical_rule"])+"|"+str(x["any_same_rule_file"])+"|"+("full" if x["source"]=="FULL_FROZEN_SNAPSHOT" else "filtered")+"|"+("timestamp compatible*" if x["issue_timestamp_compatible"] else "unverified")+"|")
table+=["","*Compatible does not prove exact historical body version.",
 "","This is an automated, read-only static-evidence audit. Historical PR exact CodeQL replay, functional acceptance tests, independent security property tests and O/W/P generation have NOT been executed.",
 "","Next: review the detailed case dossiers; confirm historical query and source/sink; freeze functionality oracle; validate O attempts; upgrade filtered source; then prespecify W/P and fresh randomized O controls.","",
 "Aggregate: "+json.dumps(counts)]
save(out/"AUDIT14_REVIEW.md","\n".join(table)+"\n")
allfiles=sorted(v for v in out.rglob("*") if v.is_file())
save(out/"SHA256SUMS.txt","".join(sha(v)+"  "+str(v.relative_to(out))+"\n" for v in allfiles))
print("AUDIT14_COMPLETE",str(out),json.dumps(counts),flush=True)
