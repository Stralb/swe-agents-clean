#!/usr/bin/env python3
"""Read-only audit of all 235 original patch archive members versus live SQLite BLOB hashes.
No patch data, source code, prompts, secrets or input ZIPs copied into report.
"""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import sqlite3,zipfile,io,json,hashlib,re
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ZIP=R/"ARNO_CODEQL_EXPORT_20261019/02_ALL_GENERATED_PATCHES.zip"
OUT=R/"mcp_uploads/jobs/arno_v6_20261030_full_patch_archive_vs_master/REPORT.json"
EXPECTED="1495e6797aec65d912ac3bc77b893cf79561f471749f78d6807fecbc619e0049"
def sha(b):return hashlib.sha256(b).hexdigest()
def verify_zip():
 h=hashlib.sha256()
 with ZIP.open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 assert h.hexdigest()==EXPECTED,"Original ZIP sha mismatch"
def phase(s):
 s=s.lower()
 if "owp14_user12_o" in s:return "OWP14_O"
 if "owp14_user14_w" in s:return "OWP14_W"
 if "owp14_user14_p" in s:return "OWP14_P"
 if "screen65" in s:return "SCREEN65_OTHER"
 return "OTHER_EARLIER_OR_UNCLASSIFIED"
def case_of(s):
 m=re.search(r"CASE[_-]?(\d{4,5})(?!\d)",s,re.I)
 return int(m.group(1)) if m else None
def risk(b):
 s=b.decode("utf-8","replace")
 # Conservative detection only. False positives possible. No matched text emitted.
 return bool(re.search(r"(?i)(?:-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16}|xox[baprs]-\d{8,}|(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*['\"][^'\"\n]{8,})",s))
def main():
 verify_zip()
 db=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
 db.execute("PRAGMA query_only=ON")
 record=db.execute("SELECT source_sha256 FROM arno_sources WHERE source_key='arno_codeql_oct19_original:02_ALL_GENERATED_PATCHES.zip'").fetchone()
 assert record and record[0]==EXPECTED
 forty={(case,arm):h for case,arm,h in db.execute("SELECT case_id,arm,patch_sha256 FROM arno_rq3_owp14_verified_patch_bytes")}
 agent=set(x[0] for x in db.execute("SELECT patch_sha256 FROM arno_recovered_agent_patch_bytes"))
 generic=set(x[0] for x in db.execute("SELECT content_sha256 FROM arno_generated_patches WHERE content_sha256 IS NOT NULL"))
 assert len(forty)==40 and len(agent)==91 and len(generic)==40
 known_by_sha=defaultdict(list)
 for (case,arm),h in forty.items():known_by_sha[h].append(f"{case}:{arm}")
 entries=[];inside_archives=[];seen=set()
 with zipfile.ZipFile(ZIP) as z:
  for info in z.infolist():
   if info.is_dir():continue
   if info.filename.lower().endswith(".zip"):
    with zipfile.ZipFile(io.BytesIO(z.read(info))) as nested:
     patches=[i.filename for i in nested.infolist() if i.filename.lower().endswith((".patch",".diff"))]
     inside_archives.append({"nested_archive":info.filename,"patch_members":len(patches),
       "missing_08461_O_candidate":any(re.search(r"(?:CASE[_-]?0*8461[_-]O|O[_-]CASE[_-]?0*8461)\.patch$",x,re.I) for x in patches),
       "missing_15151_O_candidate":any(re.search(r"(?:CASE[_-]?0*15151[_-]O|O[_-]CASE[_-]?0*15151)\.patch$",x,re.I) for x in patches)})
   if not info.filename.lower().endswith((".patch",".diff")):continue
   raw=z.read(info)
   h=sha(raw)
   assert len(raw)==info.file_size
   assert info.filename not in seen
   seen.add(info.filename)
   m=known_by_sha.get(h,[])
   entries.append({"source_archive_member_path":info.filename,
     "sha256":h,"bytes":len(raw),"path_category":phase(info.filename),
     "case_label_from_path":case_of(info.filename),
     "matches_authenticated_owp":m,
     "matches_other_91_recovered_agent_patches":h in agent,
     "matches_generic_40":h in generic,
     "potential_sensitive_token_pattern":risk(raw)})
 assert len(entries)==235
 matches=[x for x in entries if x["matches_authenticated_owp"]]
 assert len(matches)==40,"Archive does not contain all 40 authenticated patches"
 assert len({match for row in matches for match in row["matches_authenticated_owp"]})==40
 results={
 "status":"ORIGINAL_PATCH_ARCHIVE_VS_MASTER_HASH_AUDIT_COMPLETE",
 "verified_at_utc":datetime.now(timezone.utc).isoformat(),
 "original_zip_sha256":EXPECTED,
 "original_archive_patch_members":len(entries),
 "unique_original_archive_patch_hashes":len({x["sha256"] for x in entries}),
 "original_archive_uncompressed_patch_bytes":sum(x["bytes"] for x in entries),
 "existing_owp14_exact_sha_matches":sum(bool(x["matches_authenticated_owp"]) for x in entries),
 "existing_other_recovered_agent_exact_sha_matches":sum(x["matches_other_91_recovered_agent_patches"] for x in entries),
 "existing_generic_normalized_exact_sha_matches":sum(x["matches_generic_40"] for x in entries),
 "not_sha_present_in_owp_or_recovered_agent":sum(not x["matches_authenticated_owp"] and not x["matches_other_91_recovered_agent_patches"] for x in entries),
 "path_category_counts":dict(Counter(x["path_category"] for x in entries)),
 "flagged_possible_sensitive_pattern_count":sum(x["potential_sensitive_token_pattern"] for x in entries),
 "missing_o_arm_named_patch":False,
 "nested_archives":inside_archives,
 "archive_members":entries,
 "limitations":["Case-name similarity across different experimental stages does not authenticate OWP14 treatment outputs.",
 "Potential-sensitive-token pattern detection is heuristic, not a full security review.",
 "The original 235 patch archive member bytes were NOT written to the master by this read-only audit.",
 "Existing 91 other agent patch blobs are distinct SHA from the 40 authenticated OWP14 blobs."]
 }
 assert all(not n["missing_08461_O_candidate"] and not n["missing_15151_O_candidate"] for n in inside_archives)
 OUT.parent.mkdir(parents=True,exist_ok=True)
 with OUT.open("x") as f:json.dump(results,f,indent=2)
 print(json.dumps({k:v for k,v in results.items() if k not in ("archive_members","nested_archives")},indent=2))
 print("REPORT",OUT,flush=True)
if __name__=="__main__":
 main()
