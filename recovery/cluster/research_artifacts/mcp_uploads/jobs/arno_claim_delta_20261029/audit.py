#!/usr/bin/env python3
"""Append-only 2026-10-29 claim supersession; old audits remain untouched."""
import sqlite3,json,hashlib,argparse,sys
from pathlib import Path
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
DIR=R/"mcp_uploads/jobs/arno_claim_delta_20261029"
ARCH=R/"mcp_uploads/jobs/arno_20261029_archive_provenance_audit/REPORT.json"
FINAL=R/"mcp_uploads/jobs/arno_20261029_terminal_integrity_audit/RESULT.json"
K="claim_delta_v1_20261029"
T="arno_claim_status_supersession_20261029"
CLAIMS=[
("RQ1_H_T_FULL","RQ1","SOURCE_RECOVERED","109 final H/T rows now stored with byte-exact D7 source","AI coding does not establish independent human adjudication"),
("RQ1_NEW70_237","RQ1","ORIGINAL_SOURCE_VERIFIED","237 final finding rows; original Step1/Step2 sources embedded","Scanner findings are not verified vulnerabilities"),
("RQ3_OWP","RQ3","PATCH_AND_SARIF_PROVENANCE_VERIFIED","40 original patch and scanner hashes linked; 12 complete triples","Original O-arm patches 08461/15151 absent; complete agent traces and functional equivalence unverified"),
("RQ3_REPAIR","RQ3","SCANNER_ONLY_REPAIR_CHAIN_VERIFIED","Seven final patch, SARIF and scan records linked; seven scanner-negative","Two repairs researcher-authored; functional equivalence and causal prevention unverified"),
("RQ2_PAIRED_SEMANTICS","RQ2","NINE_PVALUES_REPRODUCED_REVIEW_PROVENANCE_UNVERIFIED","Nine frozen primary p-values reproduced from C6 evidence","Independent human semantic annotation provenance not established"),
("RQ1_HUMAN","RQ1","HUMAN_ADJUDICATION_UNVERIFIED","Final D7 roots present","AI blind coding is not independent human adjudication"),
("RQ2_HUMAN_QC","RQ2","HUMAN_QC_UNVERIFIED","C5/C6 corrections retained","Independent human review identities not established"),
("RQ1_NON_M_ROOTS_20261028","RQ1","SOURCE_GAP_SUPERSEDED","Former RQ1 source gap resolved: H6 and T103 original rows imported","Independent human verification remains unverified"),
("RQ3_OWP_BEFORE_SARIF","RQ3","NOT_IN_THIS_ARCHIVE","40 OWP after SARIF, no before.sarif filenames in that archive","Original baseline scans may exist elsewhere"),
("RQ3_AGENT_TRAJECTORIES","RQ3","FULL_CASE_LINKAGE_UNVERIFIED","601 members in agent prompts/traces archive","Names and logs do not prove complete original per-case execution trajectories"),
]
def req(x,msg):
 if not x:raise ValueError(msg)
def run(apply):
 c=sqlite3.connect(str(DB) if apply else "file:"+str(DB)+"?mode=ro",uri=not apply,timeout=90)
 try:
  if not apply:c.execute("PRAGMA query_only=ON")
  c.execute("PRAGMA foreign_keys=ON")
  a=json.loads(ARCH.read_text());f=json.loads(FINAL.read_text())
  req(f["status"]=="MASTER_RECOVERY_VERIFIED","Final source audit invalid")
  for t,n in [("arno_d7_final_roots_342",342),("arno_experiment_runs",40),("arno_generated_patches",40),("arno_experiment_scans",40),("arno_new70_final_findings",237),("arno_seven_final_repair_case_evidence",7)]:
   req(c.execute("SELECT count(*) FROM "+t).fetchone()[0]==n,t+" count changed")
  req(c.execute("SELECT count(*) FROM arno_d7_final_roots_342 WHERE final_route!='M'").fetchone()[0]==109,"H/T count")
  req(c.execute("SELECT count(*) FROM arno_sources WHERE source_key LIKE 'new70_original_oct28:%'").fetchone()[0]==3,"NEW70 source bytes")
  req(c.execute("SELECT count(*) FROM arno_rq2_c6_reproduced_tests WHERE tolerance_status='PASS_MATCHES_FROZEN_P'").fetchone()[0]==9,"RQ2 pvalues")
  req(c.execute("SELECT count(*) FROM arno_seven_final_repair_case_evidence WHERE final_scan_completed=1 AND final_strong_new=0 AND final_conservative_new=0").fetchone()[0]==7,"Repairs")
  req(a["archives"]["03_CODEQL_SARIF_AND_SCANS.zip"]["after_name_count"]==40 and a["archives"]["03_CODEQL_SARIF_AND_SCANS.zip"]["before_name_count"]==0,"SARIF archive names changed")
  req(not a["specific_missing_o_patch"]["08461"] and not a["specific_missing_o_patch"]["15151"],"Missing O patch unexpectedly found; revise")
  req(c.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",(T,)).fetchone()[0]==0,"Audit table exists")
  req(c.execute("SELECT count(*) FROM arno_sources WHERE source_key=?",(K,)).fetchone()[0]==0,"Source already in master")
  orig={k:(status,rq) for k,rq,status in c.execute("SELECT claim_id,rq,audit_status FROM arno_rq_publication_claim_audit")}
  req(all(orig[k][0]=="REPORTED_NOT_REPRODUCED" for k in ["RQ1_H_T_FULL","RQ1_NEW70_237","RQ3_OWP","RQ3_REPAIR","RQ2_PAIRED_SEMANTICS","RQ1_HUMAN","RQ2_HUMAN_QC"]),"Historical statuses unexpected")
  report={"status":"CLAIM_SUPERSESSION_VERIFIED","utc":datetime.now(timezone.utc).isoformat(),
   "is_newer_than_20261028_audits":True,"historical_tables_unchanged":True,
   "original_archive_index":str(ARCH),"final_recovery_audit":str(FINAL),
   "claims":[{"claim_id":k,"rq":rq,"current_evidence_status":st,"evidence":ev,"caveat":lim} for k,rq,st,ev,lim in CLAIMS]}
  raw=(json.dumps(report,sort_keys=True,indent=2)+"\n").encode()
  DIR.mkdir(parents=True,exist_ok=True)
  if not apply:
   with (DIR/"PREFLIGHT.json").open("xb") as h:h.write(raw)
   print(json.dumps({"status":"PREFLIGHT_PASS","claims":len(CLAIMS),"sha256":hashlib.sha256(raw).hexdigest()},indent=2));return
  c.execute("BEGIN IMMEDIATE")
  c.execute("INSERT INTO arno_sources (source_key,source_kind,label,source_locator,source_sha256,embedded_encoding,embedded_bytes,verification,notes) VALUES(?,?,?,?,?,?,?,?,?)",(K,"GENERATED_AUDIT_SUPERSESSION","2026-10-29 claim status supersession",str(DIR/"LIVE_REPORT.json"),hashlib.sha256(raw).hexdigest(),"json/utf-8",raw,"VERIFIED_LIVE_MASTER_AND_ORIGINAL_ARCHIVE_METADATA","Historical claim audit remains unchanged; source is generated reconciliation, not original study artifact."))
  c.execute("CREATE TABLE "+T+" (claim_id TEXT PRIMARY KEY,rq TEXT NOT NULL,current_evidence_status TEXT NOT NULL,evidence TEXT NOT NULL,caveat TEXT NOT NULL,source_key TEXT NOT NULL REFERENCES arno_sources(source_key))")
  c.executemany("INSERT INTO "+T+" VALUES(?,?,?,?,?,?)",[(k,rq,st,ev,lim,K) for k,rq,st,ev,lim in CLAIMS])
  req(c.execute("SELECT COUNT(*) FROM "+T).fetchone()[0]==len(CLAIMS),"New table count")
  req(not c.execute("PRAGMA foreign_key_check("+T+")").fetchone(),"FK mismatch")
  c.commit()
  with (DIR/"LIVE_REPORT.json").open("xb") as h:h.write(raw)
  print(json.dumps({"status":"APPENDED_VERIFIED","claims":len(CLAIMS),"report_sha256":hashlib.sha256(raw).hexdigest()}))
 finally:c.close()
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--apply",action="store_true")
 try:run(p.parse_args().apply)
 except Exception as e:
  print("CLAIM_SUPERSESSION_ERROR "+str(e),file=sys.stderr);sys.exit(1)
