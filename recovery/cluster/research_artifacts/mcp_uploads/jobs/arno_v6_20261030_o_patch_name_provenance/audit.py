#!/usr/bin/env python3
"""Compare original archived patch-member SHA256 with the 40 authenticated O/W/P patch hashes.
No patch contents exported and no database or archive modified.
"""
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime,timezone
import zipfile,sqlite3,hashlib,json,re,csv,io
R=Path.home()/"research_artifacts"
ARCH=R/"ARNO_CODEQL_EXPORT_20261019/02_ALL_GENERATED_PATCHES.zip"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=R/"mcp_uploads/jobs/arno_v6_20261030_o_patch_name_provenance/REPORT.json"
con=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
con.execute("PRAGMA query_only=ON")
known=con.execute("SELECT case_id,arm,patch_sha256 FROM arno_rq3_owp14_verified_patch_bytes").fetchall()
assert len(known)==40
known_by_sha=defaultdict(list)
for case,arm,sha in known:known_by_sha[sha].append((case,arm))
case_ids={case for case,_,sha in known}|{8461,15151}
def cases_in(name):
 return [case for case in case_ids if re.search(r"CASE[_-]?0*"+str(case)+r"(?![0-9])",name,re.I)]
found=defaultdict(list);known_matches=[]
with zipfile.ZipFile(ARCH) as z:
 patch_count=0
 for info in z.infolist():
  if info.is_dir() or not info.filename.lower().endswith((".patch",".diff")):continue
  patch_count+=1
  data=z.read(info);digest=hashlib.sha256(data).hexdigest()
  matches=known_by_sha.get(digest,[])
  labels=cases_in(info.filename)
  rec={"original_zip_member_path":info.filename,"basename":Path(info.filename).name,
       "original_bytes":len(data),"sha256":digest,
       "verified_owp14_patch_cases_and_arms":[{"case_id":case,"arm":arm} for case,arm in matches]}
  for case in labels:found[case].append(rec)
  if matches:known_matches.append(rec)
 source_idx=[m for m in z.infolist() if Path(m.filename).name=="RESULTS_INDEX_ORIGINAL.csv"]
 assert len(source_idx)==1
 rdr=csv.DictReader(io.StringIO(z.read(source_idx[0]).decode("utf-8-sig","replace")))
 idx={int(re.search(r"[0-9]+",r["case_id"]).group()):{"status":r["status"],
     "filename":r["filename"]} for r in rdr if re.search(r"[0-9]+",r["case_id"] or "")}
target={}
for case in [8461,15151]:
 originals=found[case]
 record=idx.get(case)
 target[str(case)]={"original_index":record,
 "archive_case_named_patch_candidates":originals,
 "index_filename_exact_member_match":sum(Path(x["original_zip_member_path"]).name==record["filename"] for x in originals) if record else 0,
 "matching_authenticated_known_owp14_patch_count":sum(bool(x["verified_owp14_patch_cases_and_arms"]) for x in originals)}
summary={
 "all_zip_patch_members":patch_count,
 "authenticated_owp14_patch_hashes":len(known),
 "archive_members_matching_authenticated_owp14_patch_SHA256":len(known_matches),
 "distinct_known_owp14_cases_and_arms_matched":len({(x["case_id"],x["arm"]) for member in known_matches for x in member["verified_owp14_patch_cases_and_arms"]}),
 "matching_authenticated_O":sum(any(m["arm"]=="O" for m in x["verified_owp14_patch_cases_and_arms"]) for x in known_matches),
 "matching_authenticated_W":sum(any(m["arm"]=="W" for m in x["verified_owp14_patch_cases_and_arms"]) for x in known_matches),
 "matching_authenticated_P":sum(any(m["arm"]=="P" for m in x["verified_owp14_patch_cases_and_arms"]) for x in known_matches)}
report={"status":"O_PATCH_CASE_LEVEL_INDEX_VS_OWP14_HASH_AUDIT_COMPLETE",
 "timestamp_utc":datetime.now(timezone.utc).isoformat(),
 "summary":summary,"missing_cases":target,
 "known_patch_hash_matches":known_matches,
 "limits":["Original RESULTS_INDEX_ORIGINAL.csv describes a case-level patch output; it may predate the later OWP14 experiment.",
 "A CASE_08461.patch basename is not automatically the same as O_CASE_08461.patch or CASE_08461_O.patch.",
 "Do not classify candidates as recovered original O-arm without exact arm and original pipeline linkage.",
 "No patch bytes or source code exported."]}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(report,f,indent=2)
print(json.dumps({"status":report["status"],"summary":summary,"case_index_status":{c:x["original_index"] for c,x in target.items()},
 "target_archive_candidates":{c:[{"path":x["original_zip_member_path"],"bytes":x["original_bytes"],"sha256":x["sha256"]} for x in t["archive_case_named_patch_candidates"]] for c,t in target.items()},
 "report":str(OUT)},indent=2))
