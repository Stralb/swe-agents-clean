#!/usr/bin/env python3
"""Guarded append-only archive patch inventory:
235 frozen original patch ZIP members; embed only previously missing, unflagged patch bytes.
Never alter frozen patch/scanner tables or Hugging Face. --apply requires preflight.
"""
import argparse,hashlib,json,os,re,sqlite3,sys,zipfile,zlib
from pathlib import Path
from collections import Counter
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ARCH=R/"ARNO_CODEQL_EXPORT_20261019/02_ALL_GENERATED_PATCHES.zip"
DIR=R/"mcp_uploads/jobs/arno_v6_20261030_235_patch_append_safe_v2"
T="arno_oct19_patch_archive_member_inventory_20261030"
SOURCE="arno_codeql_oct19_original:02_ALL_GENERATED_PATCHES.zip"
AUDIT="arno_oct19_patch235_append_audit_20261030"
ZIP_SHA="1495e6797aec65d912ac3bc77b893cf79561f471749f78d6807fecbc619e0049"
RISK=re.compile(r"(?i)(?:-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16}|xox[baprs]-\d{8,}|(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*['\"][^'\"\n]{8,})")
def ck(ok,msg):
 if not ok:raise RuntimeError(msg)
def hash_path(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def sha(x):return hashlib.sha256(x).hexdigest()
def phase(s):
 s=s.lower()
 if "owp14_user12_o" in s:return "OWP14_O_AUTHENTICATED"
 if "owp14_user14_w" in s:return "OWP14_W_AUTHENTICATED"
 if "owp14_user14_p" in s:return "OWP14_P_AUTHENTICATED"
 if "screen65" in s:return "EARLIER_SCREEN65_NOT_OWP14"
 return "OTHER_EXPERIMENT_PHASE_UNVERIFIED"
def discover(con):
 ck(ARCH.exists(),"Original patch archive missing")
 ck(hash_path(ARCH)==ZIP_SHA,"Original archived ZIP SHA256 changed")
 archive_source=con.execute("SELECT source_sha256,verification FROM arno_sources WHERE source_key=?",(SOURCE,)).fetchone()
 ck(archive_source and archive_source[0]==ZIP_SHA,"Original source ref does not match")
 known_owp=set(x[0] for x in con.execute("SELECT patch_sha256 FROM arno_rq3_owp14_verified_patch_bytes"))
 known_other=set(x[0] for x in con.execute("SELECT patch_sha256 FROM arno_recovered_agent_patch_bytes"))
 ck(len(known_owp)==40 and len(known_other)==91 and not (known_owp&known_other),"Existing patch proof unexpected")
 case_ids=set(x[0] for x in con.execute("SELECT id FROM cases"))
 items=[];payloads={};seen=set()
 with zipfile.ZipFile(ARCH) as z:
  for member in z.infolist():
   if member.is_dir() or not member.filename.lower().endswith((".patch",".diff")):continue
   p=member.filename
   ck(p not in seen,"Duplicate path in original ZIP")
   seen.add(p)
   b=z.read(member);h=sha(b)
   ck(len(b)==member.file_size,"Original member length changed")
   match=re.search(r"CASE[_-]?(\d{4,5})(?!\d)",p,re.I)
   label=int(match.group(1)) if match else None
   matched_owp=h in known_owp;matched_other=h in known_other
   flag=bool(RISK.search(b.decode("utf-8","replace")))
   action=("EXISTING_OWP14_VERIFIED_BYTES" if matched_owp else
     "EXISTING_OTHER_AGENT_RECOVERED_BYTES" if matched_other else
     "HELD_METADATA_ONLY_POTENTIAL_SENSITIVE" if flag else "NOVEL_BYTES_TO_EMBED")
   item={"member":p,"sha256":h,"original_bytes":len(b),"case_id":label if label in case_ids else None,
    "case_label":label,"phase_from_path":phase(p),"storage_action":action,
    "potential_sensitive_pattern":flag}
   items.append(item)
   if action=="NOVEL_BYTES_TO_EMBED":payloads[p]=b
 ck(len(items)==235 and len({r["sha256"] for r in items})==235,"Wrong frozen archive count")
 cnt=Counter(x["storage_action"] for x in items)
 ck(cnt["EXISTING_OWP14_VERIFIED_BYTES"]==40,"Not all original OWP14 hashes present")
 ck(cnt["EXISTING_OTHER_AGENT_RECOVERED_BYTES"]==65,"Other 91 agent hash overlap changed")
 ck(cnt["NOVEL_BYTES_TO_EMBED"]+cnt["HELD_METADATA_ONLY_POTENTIAL_SENSITIVE"]==130,"Novel patch count discrepancy")
 ck(cnt["HELD_METADATA_ONLY_POTENTIAL_SENSITIVE"]==2,"Novel sensitive risk count changed")
 ck(cnt["NOVEL_BYTES_TO_EMBED"]==128,"Unexpected novel safe count")
 ck(sum(x["potential_sensitive_pattern"] for x in items)==4,"Risk screen outcome changed")
 ck(not any(re.search(r"(?:CASE[_-]?0*8461[_-]O|O[_-]CASE[_-]?0*8461|CASE[_-]?0*15151[_-]O|O[_-]CASE[_-]?0*15151)\.patch$",x["member"],re.I) for x in items),"Known missing O patch unexpectedly present")
 manifest_bytes=json.dumps(items,sort_keys=True,separators=(",",":")).encode()
 return items,payloads,cnt,sha(manifest_bytes)
def main():
 p=argparse.ArgumentParser();p.add_argument("--apply",action="store_true");args=p.parse_args()
 con=sqlite3.connect(str(DB) if args.apply else "file:"+str(DB)+"?mode=ro",uri=not args.apply,timeout=90)
 try:
  con.execute("PRAGMA foreign_keys=ON")
  if not args.apply:con.execute("PRAGMA query_only=ON")
  ck(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",(T,)).fetchone()[0]==0,"Patch inventory already exists; no overwrite")
  ck(con.execute("SELECT COUNT(*) FROM arno_sources WHERE source_key=?",(AUDIT,)).fetchone()[0]==0,"Source audit already exists; no overwrite")
  ck(con.execute("SELECT COUNT(*) FROM arno_d7_final_roots_342").fetchone()[0]==342,"Master D7 changed")
  ck(con.execute("SELECT COUNT(*) FROM arno_generated_patches").fetchone()[0]==40,"Original normalized patches changed")
  items,payloads,cnt,digest=discover(con)
  report={"status":"PATCH_ARCHIVE_235_IMPORT_PREFLIGHT_OK","archive_sha256":ZIP_SHA,
   "archive_member_count":235,"archive_bytes_total_original":sum(x["original_bytes"] for x in items),
   "manifest_sha256":digest,"storage_actions":dict(cnt),
   "existing_original_owp14_40_not_duplicated":True,
   "existing_other_recovered_65_not_duplicated":True,
   "private_archive_original_binary_not_embedded":True,
   "individual_novel_patch_blobs_to_embed":128,
   "potentially_sensitive_novel_patches_metadata_only":2,
   "all_235_paths_and_hashes_registered":True,
   "original_missing_owp_O_patches_still_absent":["CASE_08461_O.patch","CASE_15151_O.patch"],
   "historical_phase_classification_from_path_not_authentication":True,
   "unsafe_to_interpret_scanner_silence_as_vulnerability_elimination":True}
  DIR.mkdir(parents=True,exist_ok=True)
  if not args.apply:
   (DIR/"PREFLIGHT.json").write_text(json.dumps(report,indent=2))
   print(json.dumps(report,indent=2));return
  pref=json.loads((DIR/"PREFLIGHT.json").read_text())
  ck(pref["manifest_sha256"]==digest and pref["archive_sha256"]==ZIP_SHA,"Source changed since read-only preflight")
  con.execute("BEGIN IMMEDIATE")
  proof_bytes=(DIR/"PREFLIGHT.json").read_bytes()
  con.execute("""INSERT INTO arno_sources
     (source_key,source_kind,label,source_locator,source_sha256,embedded_encoding,embedded_bytes,verification,notes)
     VALUES(?,?,?,?,?,?,?,?,?)""",
    (AUDIT,"DERIVED_ORIGINAL_ARCHIVE_PATCH_MEMBER_AUDIT",
     "2026-10-30 individual 235 patch archive-member SHA256 and storage inventory",
     str(DIR/"PREFLIGHT.json"),sha(proof_bytes),
     "json/utf-8",proof_bytes,
     "ARCHIVE_SHA256_VERIFIED_235_ORIGINAL_PATCH_MEMBERS_40_PLUS_65_EXISTING_AND_128_NEW_SCRUBBED",
     "Two flagged novel patches metadata-only pending sensitive-content review. Phase derived from archive path."))
  con.execute("""CREATE TABLE arno_oct19_patch_archive_member_inventory_20261030(
    original_member_path TEXT PRIMARY KEY,
    archive_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    audit_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
    case_label INTEGER, case_id INTEGER REFERENCES cases(id),
    path_phase TEXT NOT NULL,
    original_patch_sha256 TEXT NOT NULL UNIQUE,
    original_patch_bytes INTEGER NOT NULL,
    original_patch_zlib BLOB,
    storage_action TEXT NOT NULL,
    sensitive_pattern_flag INTEGER NOT NULL CHECK(sensitive_pattern_flag IN (0,1)),
    provenance_claim TEXT NOT NULL DEFAULT 'FROZEN_ZIP_MEMBER_SHA_AND_PATH_ONLY',
    CHECK ((storage_action='NOVEL_BYTES_TO_EMBED' AND original_patch_zlib IS NOT NULL)
        OR (storage_action!='NOVEL_BYTES_TO_EMBED' AND original_patch_zlib IS NULL))
  )""")
  for row in items:
   p=row["member"];act=row["storage_action"]
   payload=zlib.compress(payloads[p],9) if act=="NOVEL_BYTES_TO_EMBED" else None
   if payload is not None:
    ck(sha(zlib.decompress(payload))==row["sha256"],"Compressed original patch proof failed "+p)
   con.execute("INSERT INTO "+T+" (original_member_path,archive_source_key,audit_source_key,case_label,case_id,path_phase,original_patch_sha256,original_patch_bytes,original_patch_zlib,storage_action,sensitive_pattern_flag) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
     (p,SOURCE,AUDIT,row["case_label"],row["case_id"],row["phase_from_path"],
      row["sha256"],row["original_bytes"],payload,act,int(row["potential_sensitive_pattern"])))
  ck(con.execute("SELECT COUNT(*) FROM "+T).fetchone()[0]==235,"Partial inventory insert")
  ck(con.execute("SELECT COUNT(*) FROM "+T+" WHERE original_patch_zlib IS NOT NULL").fetchone()[0]==128,"Wrong embedded patch count")
  ck(not con.execute("PRAGMA foreign_key_check("+T+")").fetchone(),"New patch table foreign keys fail")
  con.commit()
  report["status"]="PATCH_ARCHIVE_235_APPEND_IMPORT_COMPLETE"
  (DIR/"LIVE_REPORT.json").write_text(json.dumps(report,indent=2))
  print(json.dumps(report,indent=2))
 finally:con.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("PATCH_235_APPEND_ABORTED "+repr(e),file=sys.stderr,flush=True)
  sys.exit(1)
