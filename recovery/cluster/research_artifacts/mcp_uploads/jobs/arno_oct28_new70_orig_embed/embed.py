#!/usr/bin/env python3
"""Preserve exact original NEW70 Step1/Step2/Step3 bytes in ARNO master, without altering frozen rows.
--apply requires a separately verified full SQLite snapshot. Dry-run is read-only.
"""
import argparse,sqlite3,json,hashlib,zipfile,csv,io,sys
from pathlib import Path
from collections import Counter
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
BASE="mcp_uploads/jobs/arno_two_delta_master_import_"
REL="/expanded/inputs/"
SNAP=R/"ARNO_MASTER_DB/snapshots/ARNO_RESEARCH_MASTER_PRE_OCT28_RQ3_NORMALIZATION.sqlite"
REPORT=Path(str(SNAP)+".json")
OUT=R/"mcp_uploads/jobs/arno_oct28_new70_orig_embed"
FILES=[
 ("Step1_NEW70_FINAL.zip","480c671a873e0fe823cae8977b3dc66a2559813869a1cbf7aea2f4cf9a4243fa",37617),
 ("NEW70_Phase6_Step2_Mapping_FINAL_v1.0.zip","2c344f6ae577e2edb10392c2d40a25dc7ffdfd29c8a05068c4f1f87cd156b2ab",239428),
 ("NEW70_Phase6_Producing_Changes_FINAL_v1.0.csv","a7f2a5416d07c5321974ec24ce7360864a4fe769d0deeddc3a264c026eef9cb7",105577)]
def check(ok,msg):
 if not ok:raise ValueError(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def zrows(raw):
 return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
def archive_member(raw,suffix):
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  assert z.testzip() is None
  hits=[x for x in z.namelist() if x.endswith(suffix)]
  check(len(hits)==1,"Archive member ambiguous: "+suffix)
  return z.read(hits[0])
def source():
 items=[]
 for name,expected,size in FILES:
  a=R/(BASE+"v02_20261028"+REL+name)
  b=R/(BASE+"v03_20261028"+REL+name)
  check(a.is_file() and b.is_file(),"Both archived copies must exist: "+name)
  x=a.read_bytes();y=b.read_bytes()
  check(x==y,"Mismatch between original copies: "+name)
  check(len(x)==size and sha(x)==expected,"Checksum mismatch: "+name)
  if name.endswith(".zip"):
   with zipfile.ZipFile(io.BytesIO(x)) as z:check(z.testzip() is None,"ZIP CRC failure: "+name)
  items.append({"name":name,"bytes":x,"sha256":expected,"path":str(a.relative_to(R)),"duplicate":str(b.relative_to(R))})
 return items
def verify(c,items):
 m={x["name"]:x["bytes"] for x in items}
 a=zrows(archive_member(m[FILES[0][0]],"Step1_Canonical_Findings_NEW70_FINAL.csv"))
 b=zrows(archive_member(m[FILES[1][0]],"NEW70_Phase6_Step2_Finding_Changes_FINAL_v1.0.csv"))
 p=zrows(archive_member(m[FILES[1][0]],"NEW70_Phase6_Producing_Changes_FINAL_v1.0.csv"))
 u=zrows(archive_member(m[FILES[1][0]],"NEW70_Phase6_UNRESOLVED_v1.0.csv"))
 x=zrows(m[FILES[2][0]])
 ids=lambda rows,field:{r[field].strip() for r in rows}
 q1=ids(a,"Canonical Finding ID")
 q2=ids(b,"Canonical Finding ID")
 qp=ids(p,"Producing Change ID")
 qx=ids(x,"Producing Change ID")
 qu=ids(u,"Canonical Finding ID")
 check(len(a)==len(b)==len(q1)==len(q2)==237,"Final finding ID cardinality")
 check(len(p)==len(x)==len(qp)==len(qx)==133,"PC ID cardinality")
 check(len(u)==len(qu)==61,"Unresolved cardinality")
 check(q1==q2,"Final Step1/Step2 finding identities differ")
 check(qp==qx,"Final Step2 internal/external producing changes differ")
 check(qu.issubset(q1),"Unresolved findings are outside Step1 final corpus")
 db_f={r[0] for r in c.execute("SELECT canonical_finding_id FROM arno_new70_final_findings")}
 db_p={r[0] for r in c.execute("SELECT producing_change_id FROM arno_new70_final_producing_changes")}
 db_u={r[0] for r in c.execute("SELECT canonical_finding_id FROM arno_new70_final_unresolved")}
 check(db_f==q1,"Live 237 finding keys disagree with original files")
 check(db_p==qp,"Live 133 producing-change keys disagree")
 check(db_u==qu,"Live 61 unresolved keys disagree")
 existing=c.execute("SELECT COUNT(*) FROM arno_sources WHERE source_key LIKE 'new70_original_oct28:%'").fetchone()[0]
 check(existing==0,"Source files already embedded, do not overwrite")
 return {"final_findings":237,"final_mapping_rows":237,"final_pcs":133,"unresolved":61,
         "all_original_keys_match_live_db":True,"both_original_copies_sha256_equal":True}
def main():
 pa=argparse.ArgumentParser();pa.add_argument("--apply",action="store_true")
 args=pa.parse_args()
 items=source()
 if args.apply:
  check(SNAP.is_file() and REPORT.is_file(),"Verified full master snapshot not available")
  backup=json.loads(REPORT.read_text())
  check(backup.get("status")=="VERIFIED" and backup.get("quick_check")=="ok" and backup.get("snapshot")==str(SNAP),"Backup verification report invalid")
 c=sqlite3.connect(str(DB) if args.apply else "file:"+str(DB)+"?mode=ro",uri=not args.apply,timeout=90)
 try:
  c.execute("PRAGMA foreign_keys=ON")
  if not args.apply:c.execute("PRAGMA query_only=ON")
  counts=verify(c,items)
  if args.apply:
   c.execute("BEGIN IMMEDIATE");verify(c,items)
   for item in items:
    c.execute("""INSERT INTO arno_sources
      (source_key,source_kind,label,source_locator,source_sha256,embedded_encoding,
       embedded_bytes,verification,notes) VALUES(?,?,?,?,?,?,?,?,?)""",
       ("new70_original_oct28:"+item["name"],"frozen_original_source_file",item["name"],
        str(R/item["path"]),item["sha256"],"raw/original-file",item["bytes"],
        "VERIFIED_TWO_INDEPENDENT_ARCHIVE_COPIES_SHA256_CRC_ROW_KEYS",
        "Second identical source: "+item["duplicate"]+"; original bytes retained. No frozen rows changed."))
   check(c.execute("SELECT COUNT(*) FROM arno_sources WHERE source_key LIKE 'new70_original_oct28:%'").fetchone()[0]==3,"Three source rows missing")
   c.commit()
  result={"status":"NEW70_ORIGINALS_EMBEDDED_AND_VERIFIED" if args.apply else "NEW70_ORIGINALS_DRY_RUN_PASS",
          "original_file_sha256":{x["name"]:x["sha256"] for x in items},**counts,
          "database_modified":bool(args.apply),"huggingface_modified":False}
  dest=OUT/("IMPORT_REPORT.json" if args.apply else "PREFLIGHT_REPORT.json")
  if dest.exists():raise RuntimeError("Report already exists; refusing overwrite")
  dest.write_text(json.dumps(result,indent=2))
  print(json.dumps(result,indent=2))
 finally:c.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("NEW70 SOURCE PRESERVATION ERROR: "+str(e),file=sys.stderr)
  sys.exit(1)
