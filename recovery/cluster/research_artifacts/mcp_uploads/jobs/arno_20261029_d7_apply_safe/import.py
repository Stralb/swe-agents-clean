#!/usr/bin/env python3
"""D7 final 342 source integration into persistent master. Read-only by default.
Exact-user-source SHA mandatory; no reconstructed roots, no HF writes.
"""
from pathlib import Path
from collections import Counter
import argparse,csv,io,hashlib,json,sqlite3,sys
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
SOURCE=R/"mcp_uploads/arno_master_20261028/D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv"
SNAP=R/"ARNO_MASTER_DB/snapshots/ARNO_RESEARCH_MASTER_PRE_OCT28_RQ3_NORMALIZATION.sqlite"
REPORT=Path(str(SNAP)+".json")
EXPECTED="be316e7eb5708d4cf5ac71baafaf82f84fbe15fbb44deb651ac76712d24083b4"
KEY="d7_final_342_user_csv_be316e7e_20261028"
TABLE="arno_d7_final_roots_342"
OUT=R/"mcp_uploads/jobs/arno_oct28_d7_import_prepared"
def check(cond,text):
 if not cond:raise ValueError(text)
def load():
 check(SOURCE.is_file(),"Original D7 CSV not available at authorized upload path")
 raw=SOURCE.read_bytes()
 check(hashlib.sha256(raw).hexdigest()==EXPECTED,"Full original D7 CSV SHA256 mismatch")
 rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
 check(len(rows)==342,"Not 342 rows")
 check(len({x["root_id"] for x in rows})==342,"Duplicate root IDs")
 check(Counter(x["final_route"] for x in rows)=={"M":233,"H":6,"T":103},"Incorrect route census")
 links={}
 for x in rows:
  pcs=[q.strip() for q in x["pc_ids"].split("|") if q.strip()]
  check(len(pcs)==int(x["pc_count"]),"PC count mismatch for "+x["root_id"])
  for pc in pcs:
   check(pc not in links,"Repeated PC in D7 source: "+pc)
   links[pc]=x["root_id"]
 check(len(links)==455,"Incorrect producing-change count")
 return raw,rows,links
def lineage(conn,rows,links):
 frozen=dict(conn.execute("SELECT root_id,case_id FROM arno_root_decisions"))
 check(len(frozen)==342 and set(frozen)=={x["root_id"] for x in rows},"C6 frozen root IDs disagree with D7")
 for x in rows:check(frozen[x["root_id"]]==int(x["case_id"]),"Case ID conflict: "+x["root_id"])
 original=dict(conn.execute("SELECT producing_change_id,root_id FROM arno_pc_root_lineage"))
 check(len(original)==455 and original==links,"455 producing-change lineage conflicts")
 ms={r[0]:(r[1],r[2],r[3]) for r in conn.execute("SELECT root_id,case_id,final_tier,d7_cohort FROM arno_d7_final_M_roots_233")}
 m={x["root_id"]:x for x in rows if x["final_route"]=="M"}
 check(len(ms)==len(m)==233 and set(ms)==set(m),"M233 identity conflict")
 for k,x in m.items():
  check(ms[k]==(int(x["case_id"]),x["final_tier"],x["d7_m_cohort"]),"M233 coding changed: "+k)
def main():
 pa=argparse.ArgumentParser()
 pa.add_argument("--apply",action="store_true")
 args=pa.parse_args()
 raw,rows,links=load()
 if args.apply:
  check(SNAP.exists() and REPORT.exists(),"Verified master backup absent")
  rep=json.loads(REPORT.read_text())
  check(rep.get("status")=="VERIFIED" and rep.get("quick_check")=="ok" and rep.get("snapshot")==str(SNAP),"Master backup invalid")
 db=sqlite3.connect(str(DB) if args.apply else "file:"+str(DB)+"?mode=ro",uri=not args.apply,timeout=120)
 try:
  db.execute("PRAGMA foreign_keys=ON")
  if not args.apply:db.execute("PRAGMA query_only=ON")
  lineage(db,rows,links)
  has_table=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(TABLE,)).fetchone()
  has_src=db.execute("SELECT 1 FROM arno_sources WHERE source_key=?",(KEY,)).fetchone()
  check(not has_table and not has_src,"Prior final-D7 import already exists: refusing overwrite")
  summary={"mode":"DRY_RUN_PASS" if not args.apply else "LIVE_IMPORT_PASS",
    "source_sha256":EXPECTED,"source_bytes":len(raw),"roots":342,
    "producing_changes":455,"old_M233_consistent":True,"routes":dict(Counter(x["final_route"] for x in rows))}
  if args.apply:
   db.execute("BEGIN IMMEDIATE")
   lineage(db,rows,links)
   db.execute("""INSERT INTO arno_sources(source_key,source_kind,label,source_locator,source_sha256,
      embedded_encoding,embedded_bytes,verification,notes) VALUES(?,?,?,?,?,?,?,?,?)""",
      (KEY,"user_supplied_original_csv","D7 final original 342-root census",
       str(SOURCE),EXPECTED,"raw/utf-8-sig;csv",raw,"EXACT_SHA256_VERIFIED",
       "Preserved original bytes; independent final D7 labels; no modification of frozen C6 or D7 M233."))
   db.execute("""CREATE TABLE arno_d7_final_roots_342 (
      root_id TEXT PRIMARY KEY REFERENCES arno_root_decisions(root_id),
      case_id INTEGER NOT NULL REFERENCES cases(id),repository TEXT NOT NULL,
      pc_count INTEGER NOT NULL,final_route TEXT NOT NULL CHECK(final_route IN ('M','H','T')),
      final_tier TEXT NOT NULL,d7_cohort TEXT NOT NULL,final_route_confidence TEXT NOT NULL,
      final_explanation_confidence TEXT,chronology_status TEXT NOT NULL,
      evidence_complete TEXT NOT NULL,evidence_ids TEXT,
      adjudication_rationale TEXT NOT NULL,original_row_json TEXT NOT NULL,
      source_key TEXT NOT NULL REFERENCES arno_sources(source_key))""")
   db.executemany("""INSERT INTO arno_d7_final_roots_342
    (root_id,case_id,repository,pc_count,final_route,final_tier,d7_cohort,
    final_route_confidence,final_explanation_confidence,chronology_status,
    evidence_complete,evidence_ids,adjudication_rationale,original_row_json,source_key)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",[
      (x["root_id"],int(x["case_id"]),x["repository"],int(x["pc_count"]),x["final_route"],
       x["final_tier"],x["d7_m_cohort"],x["final_route_confidence"],x["final_explanation_confidence"],
       x["final_chronology_ok"],x["final_evidence_complete"],x["final_evidence_ids"],
       x["adjudication_rationale"],json.dumps(x,sort_keys=True,ensure_ascii=False),KEY)
       for x in rows])
   check(db.execute("SELECT count(*) FROM arno_d7_final_roots_342").fetchone()[0]==342,"Post-write D7 count")
   check(db.execute("SELECT count(*) FROM arno_d7_final_roots_342 WHERE final_route!='M'").fetchone()[0]==109,"Post-write H/T count")
   check(not db.execute("PRAGMA foreign_key_check(arno_d7_final_roots_342)").fetchone(),"Final D7 table FK conflict")
   db.commit()
  print(json.dumps(summary,indent=2))
 finally:db.close()
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("D7 SOURCE INTEGRITY ERROR: "+str(e),file=sys.stderr)
  sys.exit(1)
