#!/usr/bin/env python3
import sqlite3,io,zipfile,hashlib,json,zlib
from pathlib import Path
root=Path.home()/"research_artifacts"
jobs=root/"mcp_uploads/jobs"
v1=jobs/"arno_unified_evidence_20261031_v1/output/ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
out=jobs/"arno_peer_review_recovery_20261101/proof";out.mkdir(parents=True,exist_ok=True)
db=out/"ARCHIVE_ONLY_150_SHA256_VERIFIED.sqlite";manifest=out/"PROOF_MANIFEST.json"
assert not db.exists() and not manifest.exists()
s=sqlite3.connect("file:"+str(v1)+"?mode=ro",uri=True);d=sqlite3.connect(db)
d.execute("CREATE TABLE archive_only_patch(archive TEXT,member TEXT,case_id TEXT,sha256 TEXT,bytes INTEGER,compressed_blob BLOB,verified INTEGER,PRIMARY KEY(archive,member))")
d.execute("CREATE TABLE zip_inspection(path TEXT PRIMARY KEY,sha256 TEXT,bytes INTEGER,members INTEGER,prompt_candidates TEXT)")
h=lambda b:hashlib.sha256(b).hexdigest()
rows=s.execute("SELECT archive_name,member_path,case_id,sha256,original_bytes FROM arno_archive_vault_members WHERE role='PATCH' AND indexed_in_master=0 ORDER BY archive_name,member_path").fetchall()
assert len(rows)==150
archives=sorted(set(x[0] for x in rows))
for name in archives:
 key="archive:"+name
 meta=s.execute("SELECT expected_sha256,original_bytes,segment_count FROM arno_archive_vault_objects WHERE object_key=?",(key,)).fetchone()
 assert meta,key
 parts=s.execute("SELECT sequence,bytes,content_sha256 FROM arno_archive_vault_chunks WHERE object_key=? ORDER BY sequence",(key,)).fetchall()
 assert len(parts)==meta[2]
 for index,(seq,raw,dig) in enumerate(parts):assert seq==index and h(raw)==dig,key
 original=b"".join(x[1] for x in parts)
 assert h(original)==meta[0] and len(original)==meta[1],key
 with zipfile.ZipFile(io.BytesIO(original)) as z:
  for archive,member,case,expected,n in rows:
   if archive!=name:continue
   raw=z.read(member)
   assert h(raw)==expected and len(raw)==n,member
   d.execute("INSERT INTO archive_only_patch VALUES(?,?,?,?,?,?,1)",(archive,member,case,expected,n,sqlite3.Binary(zlib.compress(raw,6))))
 print("PROVED",name,flush=True)
s.close()
pkg=jobs/"arno_ac6_v6_20261030"
for file in [pkg/"ARNO_A_C_ALL12_EVIDENCE_INPUT.zip",pkg/"ARNO_AC6_V6_CODEQL_EVIDENCE_FINAL_V6E.zip",jobs/"arno_v6_20261030_case22223_three_pilots/ARNO_22223_THREE_READY_UPLOAD_PILOTS_20261030.zip"]:
 if not file.exists():continue
 with zipfile.ZipFile(file) as z:
  names=z.namelist()
  possible=[name for name in names if "prompt" in name.lower() or "issue" in name.lower()]
  dig=h(file.read_bytes())
  d.execute("INSERT INTO zip_inspection VALUES(?,?,?,?,?)",(str(file.relative_to(root)),dig,file.stat().st_size,len(names),json.dumps(possible[:80])))
  print("ZIP",file.name,dig,len(names),"prompt candidates:",possible[:25],flush=True)
d.commit();assert d.execute("SELECT count(*) FROM archive_only_patch").fetchone()[0]==150
assert d.execute("PRAGMA quick_check").fetchone()[0]=="ok";d.close()
report={"status":"PASS","verified_patch_members":150,"archive_names":archives,"sqlite_sha256":h(db.read_bytes()),"sqlite_bytes":db.stat().st_size}
manifest.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
