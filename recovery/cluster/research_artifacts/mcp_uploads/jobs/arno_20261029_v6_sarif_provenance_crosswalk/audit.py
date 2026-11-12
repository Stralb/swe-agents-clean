#!/usr/bin/env python3
"""Read-only source-identity crosswalk for historical Screen65 before and OWP14 after SARIF.
No experiment mutation and no raw paths, secrets, trace text, or warning messages emitted.
"""
from pathlib import Path
from collections import defaultdict,Counter
import json,sqlite3,zlib,zipfile,hashlib,re
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
SCREEN=R/"ARNO_CODEQL_EXPORT_20261019/05_SCREEN65_EVIDENCE.zip"
OUT=R/"mcp_uploads/jobs/arno_20261029_v6_sarif_provenance_crosswalk/REPORT.json"
def h(v):
 if isinstance(v,str):v=v.encode()
 return hashlib.sha256(v).hexdigest()
def valid_sha(s):
 return isinstance(s,str) and bool(re.fullmatch(r'[0-9a-fA-F]{40,64}',s))
def inspect_sarif(raw):
 o=json.loads(raw);runs=o.get("runs",[])
 out={"sarif_version":o.get("version"),"run_count":len(runs),"tools":[],
 "revision_shas":[],"original_uri_base_ids_present":[],"has_invocations":False,
 "invocation_parameter_keys":[],"run_property_keys":[],"version_provenance_fields":[]}
 commits=set()
 for run in runs:
  dr=run.get("tool",{}).get("driver",{})
  out["tools"].append({"name":dr.get("name"),"version":dr.get("semanticVersion") or dr.get("version")})
  for rec in run.get("versionControlProvenance",[]):
   revision=rec.get("revisionId")
   if valid_sha(revision):commits.add(revision.lower())
   out["version_provenance_fields"].append(sorted(rec.keys()))
  oids=run.get("originalUriBaseIds") or {}
  out["original_uri_base_ids_present"].extend(sorted(oids))
  inv=run.get("invocations",[])
  if inv:out["has_invocations"]=True
  for i in inv:
   out["invocation_parameter_keys"].extend(sorted(i.get("properties",{}).keys()))
  out["run_property_keys"].extend(sorted((run.get("properties") or {}).keys()))
 out["revision_shas"]=sorted(commits)
 out["tools"]=list({(x["name"],x["version"]):x for x in out["tools"]}.values())
 out["original_uri_base_ids_present"]=sorted(set(out["original_uri_base_ids_present"]))
 out["invocation_parameter_keys"]=sorted(set(out["invocation_parameter_keys"]))
 out["run_property_keys"]=sorted(set(out["run_property_keys"]))
 return out
conn=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
conn.execute("PRAGMA query_only=ON")
before=conn.execute("SELECT case_id,wave,zip_member_path,sha256 FROM arno_screen65_before_sarif_candidates_20261029 ORDER BY case_id,wave").fetchall()
after=conn.execute("SELECT case_id,arm,original_result_path,source_snapshot_type,codeql_version,result_sha256,original_result_zlib FROM arno_rq3_owp14_run_scans ORDER BY case_id,arm").fetchall()
assert len(before)==28 and len(after)==40
case_records=defaultdict(lambda:{"before":{},"after":{}})
with zipfile.ZipFile(SCREEN) as z:
 for case,wave,path,sha in before:
  raw=z.read(path);assert h(raw)==sha
  case_records[case]["before"][wave]=inspect_sarif(raw)
for case,arm,path,snapshot,version,result_sha,packed in after:
 raw=zlib.decompress(packed)
 assert h(raw)==result_sha
 obj=json.loads(raw)
 # Inspect original RESULT metadata field presence without disclosing arbitrary text.
 def fields(v):
  return sorted(v.keys()) if isinstance(v,dict) else []
 info={"root_field_keys":fields(obj),"nested_dict_keys":{
  key:fields(value) for key,value in obj.items() if isinstance(value,dict)
 },"sha_like_value_field_names":[]}
 def search_sha(prefix,v,depth=0):
  if depth>3:return
  if isinstance(v,dict):
   for key,val in v.items():
    if isinstance(val,str) and valid_sha(val):
     info["sha_like_value_field_names"].append(prefix+str(key))
    elif isinstance(val,dict):search_sha(prefix+str(key)+".",val,depth+1)
 search_sha("",obj)
 path_s=path[:-11]+"after.sarif"
 sarif_path=R/path_s
 assert sarif_path.is_file(),path_s
 sarif=inspect_sarif(sarif_path.read_bytes())
 assert any(str(version)==str(tool.get("version")) for tool in sarif["tools"] if tool.get("version")),(case,arm,"version mismatch")
 case_records[case]["after"][arm]={"source_snapshot_type":snapshot,
   "declared_codeql_version":version,"sarif":sarif,"result_metadata":info}
summary={"cases_with_both_before_waves":0,"cases_with_explicit_before_revision":0,
 "cases_with_explicit_after_revision":0,"cases_with_explicit_revision_matching_any":0,
 "cases_all_arms_codeql_version_match_before":0,"arms_with_result_metadata_sha_fields":0,
 "arms_total":len(after)}
rows=[]
for case,record in sorted(case_records.items()):
 b=record["before"];a=record["after"]
 assert set(b)=={"SCREEN65_FIRST","SCREEN65_SECOND"}
 summary["cases_with_both_before_waves"]+=1
 before_commits=set().union(*(set(x["revision_shas"]) for x in b.values()))
 after_commits=set().union(*(set(x["sarif"]["revision_shas"]) for x in a.values()))
 if before_commits:summary["cases_with_explicit_before_revision"]+=1
 if after_commits:summary["cases_with_explicit_after_revision"]+=1
 if before_commits & after_commits:summary["cases_with_explicit_revision_matching_any"]+=1
 before_versions={t["version"] for x in b.values() for t in x["tools"]}
 after_versions={t["version"] for x in a.values() for t in x["sarif"]["tools"]}
 if before_versions==after_versions and before_versions:summary["cases_all_arms_codeql_version_match_before"]+=1
 for arm,row in a.items():
  if row["result_metadata"]["sha_like_value_field_names"]:summary["arms_with_result_metadata_sha_fields"]+=1
 rows.append({"case_id":case,"arms":sorted(a),
  "source_snapshot_classes":sorted(set(x["source_snapshot_type"] for x in a.values())),
  "before_tool_versions":sorted(before_versions),"after_tool_versions":sorted(after_versions),
  "version_match":before_versions==after_versions,
  "before_explicit_git_revision_count":len(before_commits),
  "after_explicit_git_revision_count":len(after_commits),
  "overlapping_revision_sha_count":len(before_commits&after_commits),
  "before_sarif_vcs_fields":sorted({f for x in b.values() for kk in x["version_provenance_fields"] for f in kk}),
  "after_sarif_vcs_fields":sorted({f for x in a.values() for kk in x["sarif"]["version_provenance_fields"] for f in kk}),
  "after_RESULT_sha_value_field_names":{arm:row["result_metadata"]["sha_like_value_field_names"] for arm,row in a.items()},
  "result_metadata_field_keys_by_arm":{arm:row["result_metadata"]["root_field_keys"] for arm,row in a.items()},
  "source_commit_equivalence":"NOT_VERIFIED",
  "screen65_baseline_owp14_interchangeability":"NOT_VERIFIED"})
report={"status":"OWP14_SCREEN65_SARIF_PROVENANCE_CROSSWALK_COMPLETE","summary":summary,
"case_records":rows,"scope":"14 cases, 28 historical before SARIF + 40 OWP14 after SARIF",
"limits":["Matching scanner version and normalized warnings do not establish source commit identity.",
"Only standard SARIF versionControlProvenance.revisionId recognized; absent metadata is not negative evidence.",
"Original experiment result JSON field names are inventoried, not blindly interpreted as source git commits.",
"No SARIF or experimental results altered or embedded."]}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(report,f,indent=2)
print(json.dumps({"status":report["status"],"summary":summary,"report":str(OUT)},indent=2))
