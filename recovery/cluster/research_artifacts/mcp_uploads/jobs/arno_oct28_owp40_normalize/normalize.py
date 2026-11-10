#!/usr/bin/env python3
"""Exact-source O/W/P14 normalized experiment migration.
--check read-only; --apply requires verified master backup. Never infer missing runs.
"""
import argparse,sqlite3,hashlib,zlib,zipfile,json,sys,os
from pathlib import Path
from collections import Counter
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ARC=R/"ARNO_CODEQL_EXPORT_20261019/03_CODEQL_SARIF_AND_SCANS.zip"
ARC_SHA="4896827bb45257527f7816731d2b541b9dd5c8d8d00cb8755868b6083491b2cb"
SNAP=R/"ARNO_MASTER_DB/snapshots/ARNO_RESEARCH_MASTER_PRE_OCT28_RQ3_NORMALIZATION.sqlite"
SNAP_REPORT=Path(str(SNAP)+".json")
REPORT_DIR=R/"mcp_uploads/jobs/arno_oct28_owp40_normalize"
COUNTS={"O":12,"W":14,"P":14}
def digest(b):return hashlib.sha256(b).hexdigest()
def file_sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
def gather():
 db=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=90)
 db.execute("PRAGMA query_only=ON")
 rs=db.execute("""SELECT case_id,arm,scan_state,source_snapshot_type,codeql_version,
 historical_target_rule,new_strong_count,new_conservative_count,target_new_strong,
 patch_sha256,functional_status,baseline_codeql_version_match,original_result_path,
 result_sha256,original_result_zlib,frozen_summary_row_json,patch_bytes_match_status
 FROM arno_rq3_owp14_run_scans ORDER BY case_id,arm""").fetchall()
 pt={(r[0],r[1]):r for r in db.execute("""SELECT case_id,arm,original_filename,patch_sha256,
 original_patch_bytes,patch_zlib,patch_header_present,verification_status
 FROM arno_rq3_owp14_verified_patch_bytes""")}
 assert len(rs)==len(pt)==40, (len(rs),len(pt))
 assert Counter(r[1] for r in rs)==COUNTS
 assert file_sha(ARC)==ARC_SHA
 rows=[]
 with zipfile.ZipFile(ARC) as z:
  for r in rs:
   (case,arm,state,snapshot,version,rule,n_strong,n_con,target,p_sha,func,bmatch,
    result_path,result_sha,result_z,summary,match)=r
   assert state=="SCAN_COMPLETE",(case,arm,state)
   assert match=="ORIGINAL_PATCH_BYTES_SHA256_MATCH_SCANNER_RESULT",(case,arm,match)
   p=pt[(case,arm)]
   assert p[3]==p_sha and p[6]==1 and p[7]=="EXACT_SHA256_MATCH_TO_SCANNER_RESULT",(case,arm)
   patch=zlib.decompress(p[5])
   assert len(patch)==p[4] and digest(patch)==p_sha,(case,arm,"patch_sha")
   result_raw=zlib.decompress(result_z)
   assert digest(result_raw)==result_sha,(case,arm,"original-result-sha")
   json.loads(result_raw)
   assert result_path.endswith("/RESULT.json"),result_path
   sarif_rel=result_path[:-11]+"after.sarif"
   sarif_path=R/sarif_rel
   assert sarif_path.is_file(),sarif_path
   sarif=sarif_path.read_bytes()
   zip_member="03_CODEQL_SARIF_AND_SCANS/"+sarif_rel
   assert sarif==z.read(zip_member),(case,arm,"archive to cluster SARIF mismatch")
   doc=json.loads(sarif)
   assert doc.get("version")=="2.1.0",(case,arm,"SARIF version")
   token="OWP14_CASE"+str(case).zfill(5)+"_"+arm
   meta={"origin":"Wits 14-case O/W/P original archive","run_kind":"ARCHIVED_SCANNER_ARM",
         "arm":arm,"case_id":case,"snapshot_type":snapshot,"scan_state":state,
         "codeql_version":version,"original_result_path":result_path,
         "original_result_sha256":result_sha,"archive_sha256":ARC_SHA,
         "sarif_original_path":sarif_rel,"sarif_sha256":digest(sarif),
         "patch_source_filename":p[2],"patch_sha256":p_sha,"functional_status":func,
         "baseline_codeql_version_match":bmatch,"new_strong_count":n_strong,
         "new_conservative_count":n_con,"target_new_strong":target,
         "source_evidence_table":"arno_rq3_owp14_run_scans",
         "interpretation_limits":"Archived scanner output, not an independently rerun scan, verified agent trajectory, confirmed vulnerability, or functional equivalence."}
   rows.append({"token":token,"case":case,"arm":arm,"rule":rule,"version":version,
                "patch":patch,"patch_sha":p_sha,"sarif":sarif,"sarif_sha":digest(sarif),
                "metadata":json.dumps(meta,sort_keys=True)})
 db.close()
 return rows
def guard(db,rows):
 for t,field in [("arno_experiment_runs","run_id"),("arno_generated_patches","patch_id"),("arno_experiment_scans","scan_id")]:
  names=[r["token"] if t=="arno_experiment_runs" else r["token"]+("_PATCH" if t=="arno_generated_patches" else "_CODEQL_AFTER") for r in rows]
  q="SELECT COUNT(*) FROM "+t+" WHERE "+field+" IN ("+",".join("?" for _ in names)+")"
  count=db.execute(q,names).fetchone()[0]
  if count:raise ValueError("Target "+t+" already contains "+str(count)+" run keys; refusing overwrite")
 for r in rows:
  if db.execute("SELECT 1 FROM cases WHERE id=?",(r["case"],)).fetchone() is None:
   raise ValueError("Unknown case id "+str(r["case"]))
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("--apply",action="store_true")
 args=parser.parse_args()
 rows=gather()
 rd=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
 rd.execute("PRAGMA query_only=ON")
 guard(rd,rows);rd.close()
 qa={"rows":len(rows),"counts":dict(Counter(r["arm"] for r in rows)),
     "patch_bytes_sha_verified":40,"sarif_bytes_equal_archive":40,
     "archive_sha256":ARC_SHA,"example_scan_sha256":rows[0]["sarif_sha"],
     "destination":"arno_experiment_runs + arno_generated_patches + arno_experiment_scans",
     "execution_verified_field":0,"prompt_blobs_inferred":False,
     "source_db_modified":False}
 if not args.apply:
  path=REPORT_DIR/"DRY_RUN_REPORT.json"
  if path.exists(): raise RuntimeError("Dry-run report exists; refusing overwrite")
  path.write_text(json.dumps(qa,indent=2))
  print(json.dumps({"status":"DRY_RUN_PASS","report":str(path),**qa},indent=2))
  return
 if not SNAP.exists() or not SNAP_REPORT.exists():
  raise ValueError("Verified full master backup missing; no write allowed")
 sr=json.loads(SNAP_REPORT.read_text())
 if sr.get("status")!="VERIFIED" or sr.get("quick_check")!="ok" or str(SNAP)!=sr.get("snapshot") or sr.get("sha256")!=file_sha(SNAP):
  raise ValueError("Backup verification failed")
 if sr.get("table_counts",{}).get("arno_experiment_runs")!=0 or sr.get("table_counts",{}).get("arno_experiment_scans")!=0:
  raise ValueError("Backup had unexpected existing experiment rows")
 c=sqlite3.connect(str(DB),timeout=120)
 c.execute("PRAGMA foreign_keys=ON")
 try:
  c.execute("BEGIN IMMEDIATE")
  guard(c,rows)
  for r in rows:
   t=r["token"]
   c.execute("INSERT INTO arno_experiment_runs (run_id,case_id,root_id,experiment_family,treatment,prompt_blob,run_metadata_json,status) VALUES(?,?,NULL,?,?,NULL,?,?)",
     (t,r["case"],"RQ3_OWP14_ARCHIVED_SCAN_ARM",r["arm"],r["metadata"],"ORIGINAL_ARCHIVED_PATCH_AND_SCANNER_RESULT_NOT_REEXECUTED"))
   c.execute("INSERT INTO arno_generated_patches (patch_id,run_id,content_sha256,patch_blob,patch_uri,authenticity_status,notes) VALUES(?,?,?,?,?,?,?)",
     (t+"_PATCH",t,r["patch_sha"],r["patch"],None,"ARCHIVED_PATCH_SHA256_VERIFIED_AGENT_ORIGIN_UNVERIFIED",
      "Exact original source bytes and primary source in arno_rq3_owp14_verified_patch_bytes. Functional equivalence not proven."))
   c.execute("INSERT INTO arno_experiment_scans (scan_id,run_id,scanner,scanner_version,rule_id,raw_result_blob,result_json,execution_verified) VALUES(?,?,?,?,?,?,?,0)",
     (t+"_CODEQL_AFTER",t,"CodeQL",r["version"],r["rule"],r["sarif"],r["metadata"]))
  if any(c.execute("SELECT COUNT(*) FROM "+t+" WHERE "+f+" LIKE 'OWP14_CASE%'").fetchone()[0]!=40
      for t,f in [("arno_experiment_runs","run_id"),("arno_generated_patches","patch_id"),("arno_experiment_scans","scan_id")]):
   raise RuntimeError("Pre-commit 40-row check failed")
  if c.execute("PRAGMA foreign_key_check").fetchone():raise RuntimeError("FK failure")
  c.commit()
 except BaseException:
  c.rollback()
  raise
 finally:c.close()
 qa["source_db_modified"]=True
 qa["backup_snapshot_sha256"]=sr["sha256"]
 qa["status"]="IMPORT_COMPLETE"
 p=REPORT_DIR/"IMPORT_REPORT.json"
 if p.exists():raise RuntimeError("Import report exists; data committed, manually inspect")
 p.write_text(json.dumps(qa,indent=2))
 print(json.dumps(qa,indent=2))
if __name__=="__main__":
 try: main()
 except Exception as e:
  print("OWP40 ERROR: "+str(e),file=sys.stderr)
  sys.exit(1)
