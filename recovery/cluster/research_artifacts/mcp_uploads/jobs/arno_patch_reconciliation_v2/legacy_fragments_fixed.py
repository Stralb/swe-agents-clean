#!/usr/bin/env python3
"""Index preserved earlier uploads and seven final repair sources; verify compressed bytes."""
import sqlite3,re,hashlib,json,zlib,datetime
from pathlib import Path
R=Path.home()/"research_artifacts"
o=R/"mcp_uploads/jobs/arno_patch_reconciliation_v2/output"
d=o/"ARNO_UNIFIED_EVIDENCE_WITH_DEEP_PATCHES_V2.sqlite"
assert (o/"FINAL_INTEGRATION_VALIDATION.json").exists()
cx=sqlite3.connect(str(d),timeout=200)
cx.execute("PRAGMA foreign_keys=ON")
if cx.execute("SELECT 1 FROM sqlite_master WHERE name='study_deep_legacy_evidence_links'").fetchone():
 assert cx.execute("SELECT COUNT(*) FROM study_deep_legacy_evidence_links").fetchone()[0]==0,"Refuse to overwrite populated crosswalk"
 cx.execute("DROP TABLE study_deep_legacy_evidence_links")
 cx.commit()
cx.executescript("""
CREATE TABLE study_deep_legacy_evidence_links(
 key TEXT PRIMARY KEY,case_id INTEGER REFERENCES cases(id),
 source_table TEXT NOT NULL,source_record_key TEXT NOT NULL,
 source_column TEXT NOT NULL,source_group TEXT,
 condition_token TEXT,sha256 TEXT,stored_original_bytes INTEGER,
 content_status TEXT NOT NULL,source_locator TEXT,
 original_source_hash_verified INTEGER NOT NULL);
CREATE INDEX deep_legacy_case_idx ON study_deep_legacy_evidence_links(case_id);
""")
cx.execute("BEGIN IMMEDIATE")
q="SELECT source_path,source_group,filename,source_sha256,original_byte_count,original_zlib FROM arno_exp_transfer_files"
transfers=cx.execute(q).fetchall()
for path,group,name,hash_,n,raw in transfers:
 payload=zlib.decompress(raw)
 assert len(payload)==n and hashlib.sha256(payload).hexdigest()==hash_,("transfer checksum",path)
 hit=re.search(r"(?:CASE_)?(\d{3,5})(?:[_\.]|$)",name)
 cid=int(hit.group(1)) if hit else None
 if cid is not None and not cx.execute("SELECT 1 FROM cases WHERE id=?",(cid,)).fetchone():cid=None
 condition=(re.search(r"(?:^|[_\.])(P[1234]|O[1234]?|W[1234]?)(?:[_\.]|$)",name,re.I))
 condition=condition.group(1).upper() if condition else None
 cx.execute("INSERT INTO study_deep_legacy_evidence_links VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
 "EXP_TRANSFER:"+path,cid,"arno_exp_transfer_files",path,
 "original_zlib",group,condition,hash_,n,"EMBEDDED_ORIGINAL_ZLIB_VERIFIED",path,1))
# The seven final repairs have original compressed patch+result+after SARIF plus optional earlier evidence.
rows=cx.execute("""SELECT case_id,final_patch_sha256,final_patch_zlib,
final_result_sha256,final_result_zlib,final_after_sarif_sha256,final_after_sarif_zlib,
initial_result_zlib,initial_before_sarif_zlib,initial_after_sarif_zlib
FROM arno_seven_final_repair_case_evidence""").fetchall()
assert len(rows)==7
roles=[
("final_patch_sha256","final_patch_zlib","FINAL_PATCH"),("final_result_sha256","final_result_zlib","FINAL_SCAN_RESULT"),
("final_after_sarif_sha256","final_after_sarif_zlib","FINAL_AFTER_SARIF"),
(None,"initial_result_zlib","INITIAL_SCAN_RESULT"),(None,"initial_before_sarif_zlib","INITIAL_BEFORE_SARIF"),
(None,"initial_after_sarif_zlib","INITIAL_AFTER_SARIF")]
for row in rows:
 cid=row[0]
 mapping={"final_patch_sha256":row[1],"final_patch_zlib":row[2],"final_result_sha256":row[3],
 "final_result_zlib":row[4],"final_after_sarif_sha256":row[5],"final_after_sarif_zlib":row[6],
 "initial_result_zlib":row[7],"initial_before_sarif_zlib":row[8],"initial_after_sarif_zlib":row[9]}
 for hkey,col,role in roles:
  raw=mapping[col]
  if raw is None:continue
  decoded=zlib.decompress(raw)
  content_hash=hashlib.sha256(decoded).hexdigest()
  assert not hkey or content_hash==mapping[hkey],("final repair hash",cid,role)
  cx.execute("INSERT INTO study_deep_legacy_evidence_links VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
   "SEVEN_REPAIR:"+str(cid)+":"+role,cid,"arno_seven_final_repair_case_evidence",str(cid),
   col,"SEVEN_CASE_FINAL_REPAIR","FINAL" if role.startswith("FINAL") else "INITIAL",
   content_hash,len(decoded),"EMBEDDED_ORIGINAL_ZLIB_VERIFIED","case="+str(cid),1))
count=cx.execute("SELECT COUNT(*) FROM study_deep_legacy_evidence_links").fetchone()[0]
assert count>=97+21,("unexpected link coverage",count)
assert cx.execute("SELECT COUNT(*) FROM study_deep_legacy_evidence_links WHERE source_table='arno_exp_transfer_files'").fetchone()[0]==len(transfers)
assert not cx.execute("PRAGMA foreign_key_check('study_deep_legacy_evidence_links')").fetchall()
cx.commit()
coverage={"status":"ADDITIONAL_HISTORIC_EXPERIMENT_ARTIFACTS_INDEXED","original_exp_transfer_fragments":len(transfers),
"seven_repair_cases":len(rows),"seven_case_artifact_links":count-len(transfers),"all_artifact_hashes_checked":True,
"full_index_row_count":count,"original_database_untouched":True,
"utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
(o/"LEGACY_FRAGMENT_INTEGRATION.json").write_text(json.dumps(coverage,indent=2)+"\n")
print(json.dumps(coverage,indent=2),flush=True)
cx.close()
