#!/usr/bin/env python3
"""Append-only evidence ingestion of two NEW nonblind GPT-6 O-arm reruns. No original historic O changes."""
import sqlite3,json,zlib,hashlib,zipfile,collections,os,traceback
from pathlib import Path,PurePosixPath
ROOT=Path.home()/"research_artifacts"
DB=ROOT/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
OUT=ROOT/"mcp_uploads/jobs/arno_owp14_new_O_20261031_ingest_v1"
OUT.mkdir(parents=True,exist_ok=True)
DIR1=ROOT/"mcp_uploads/jobs/arno_owp14_new_O_20261031_v1/output"
DIR2=ROOT/"mcp_uploads/jobs/arno_owp14_new_O_20261031_v2/output"
IN=ROOT/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CASES={
 8461: dict(case="08461",code_dir=DIR1/"CASE_08461",result_dir=DIR1/"CASE_08461",source_sha="cf604dce142adf1ddeda24d54f17944e6bdb3969d8a3e0b70febc0599e92d5a5",patch_sha="23d93f3aab67d42a00c3eb4406b2e6645d777ca3f8829c21e26ac82e739ce7a1",target_rule="js/incomplete-multi-character-sanitization"),
 15151:dict(case="15151",code_dir=DIR1/"CASE_15151",result_dir=DIR2/"CASE_15151",source_sha="25317a7d85f2208b372f69c746de2b6bb08f616b8c552a4b360fbd0b19af5270",patch_sha="7a74407b3c3c61b7b6b650b3fb2cb9e09e9b21b72a8e4363420bcc1000d644eb",target_rule="js/log-injection")
}
def sha(data):return hashlib.sha256(data).hexdigest()
def filehash(path):return sha(Path(path).read_bytes())
def parse_results(data):
 obj=json.loads(data);result=[]
 for run in obj.get("runs",[]):
  for raw in run.get("results",[]):
   p=(raw.get("locations") or [{}])[0].get("physicalLocation",{})
   loc=p.get("artifactLocation",{}).get("uri","").replace(chr(92),"/").removeprefix("file://")
   fp=raw.get("partialFingerprints") or {}
   result.append(dict(raw=raw,rule=raw.get("ruleId",""),path=loc,line=p.get("region",{}).get("startLine"),
    column=p.get("region",{}).get("startColumn"),level=raw.get("level",""),
    msg=raw.get("message",{}).get("text",""),fp=fp.get("primaryLocationLineHash",""),col=fp.get("primaryLocationStartColumnFingerprint","")))
 return result
def strongkey(x):
 return (x["rule"],x["path"],x["fp"] or x["msg"],x["col"] or (x["line"] if not x["fp"] else ""))
def weakkey(x):
 return (x["rule"],x["path"],x["msg"].replace("\n"," ").strip())
def new_flags(before,after,key):
 counter=collections.Counter(key(x) for x in before);flags=[]
 for x in after:
  k=key(x)
  if counter[k]:
   counter[k]-=1;flags.append(0)
  else:flags.append(1)
 return flags
def treehash(z):
 h=hashlib.sha256();h.update(b"ARNO_FROZEN_REPO_TREE_V1\0")
 names=sorted(n for n in z.namelist() if n.startswith("REPO/") and not n.endswith("/"))
 for name in names:
  data=z.read(name)
  h.update(name[5:].encode()+b"\0"+sha(data).encode()+b"\0")
 return h.hexdigest()
audits=[]
prepared=[]
for cid,m in CASES.items():
 code=m["code_dir"];rs=m["result_dir"];c=m["case"]
 patch_path=code/("CASE_"+c+"_O_RERUN_20261031_R1.patch")
 patch=patch_path.read_bytes()
 assert sha(patch)==m["patch_sha"]
 src=IN/("CASE_"+c+"_O.zip");source_zip=src.read_bytes();assert sha(source_zip)==m["source_sha"]
 with zipfile.ZipFile(src) as z:
  assert z.testzip() is None
  instruction=z.read("RUN_INSTRUCTIONS.md")
  issue=z.read("ISSUE.md")
  src_tree=treehash(z)
 result=json.loads((rs/"RESULT.json").read_text())
 assert result["status"]=="CODEQL_PASS",result
 assert result["patch_sha256"]==m["patch_sha"] and result["source_sha256"]==m["source_sha"]
 assert result["checks"].get("analyze_after",result["checks"].get("scan"))["rc"]==0
 after_path=rs/"after.sarif";before_path=code/"before.sarif"
 after=after_path.read_bytes();before=before_path.read_bytes()
 assert sha(after)==result["after_sarif_sha256"] and sha(before)==result["baseline_sarif_sha256"]
 afr=parse_results(after);bfr=parse_results(before)
 flags=new_flags(bfr,afr,strongkey);wflags=new_flags(bfr,afr,weakkey)
 assert len(bfr)==result["baseline_total"] and len(afr)==result["after_total"]
 assert sum(flags)==result["new_strong"] and sum(wflags)==result["new_conservative"]
 assert sum(1 for x,flag in zip(afr,flags) if flag and x["rule"]==m["target_rule"])==result["historical_target_new_strong"]
 assert result["new_strong"]==0 and result["new_conservative"]==0,"Unexpected nonzero new finding; check reclassification"
 # Archived baseline and source used by this run are first-wave CodeQL 2.25.6.
 run_id=f"OWP14_NEW_O_{c}_GPT6_20261031_R1"
 prompt=b"RUN_INSTRUCTIONS.md (exact original bytes):\n"+instruction+b"\nISSUE.md (exact original bytes):\n"+issue+b"\n"
 metadata=dict(experiment_status="NEW_NONBLIND_RERUN_NOT_HISTORICAL_O",original_owp14_O_missing=True,
  historical_comparison_eligible=False,model="GPT-6 current ChatGPT assistant",model_temperature="NOT_EXPOSED",model_seed="NOT_EXPOSED",
  coding_context="Assistant knew historical O-arm results missing; implementation used frozen ISSUE and REPO; NOT blinded.",
  generation_date="2026-10-31",frozen_input_zip_sha256=m["source_sha"],tree_sha256_scheme="ARNO_FROZEN_REPO_TREE_V1",
  functional_status="NOT_INDEPENDENTLY_VERIFIED",local_syntax_parse="PASS_TYPESCRIPT_TRANSPILATION_ONLY",
  local_git_apply_to_fresh_copy="PASS",cluster_git_apply="PASS",scanner_version="2.25.6",scanner_suite=SUITE,
  scanner_baseline="SCREEN65_FIRST_SAME_VERSION",reported_new_strong=result["new_strong"],reported_new_conservative=result["new_conservative"],
  original_target_rule=m["target_rule"],before_target_rule_total=sum(x["rule"]==m["target_rule"] for x in bfr),
  after_target_rule_total=sum(x["rule"]==m["target_rule"] for x in afr),
  patched_source_file_count=len([x for x in patch.splitlines() if x.startswith(b"diff --git")]),
  first_codeql_attempt_environment_failure=cid==15151,
  evidence_not_to_merge_into_historical_12_triple_comparisons=True)
 prepared.append(dict(cid=cid,m=m,src=src,src_tree=src_tree,patch=patch,patch_path=patch_path,issue=issue,instruction=instruction,
  after=after,before=before,afr=afr,bfr=bfr,flags=flags,rs=rs,code=code,result=result,
  run_id=run_id,meta=metadata,prompt=prompt))
 audits.append(dict(run_id=run_id,case_id=cid,source_sha256=m["source_sha"],patch_sha256=m["patch_sha"],
  source_tree_sha256=src_tree,baseline_total=len(bfr),after_total=len(afr),new_strong=sum(flags),
  historical_target_new=0,before_target_rule_total=metadata["before_target_rule_total"],
  after_target_rule_total=metadata["after_target_rule_total"],status="PREVALIDATED_NO_DB_WRITE"))
(OUT/"PRECOMMIT_AUDIT.json").write_text(json.dumps(audits,indent=2)+"\n")
con=sqlite3.connect(str(DB),timeout=240)
try:
 con.execute("PRAGMA busy_timeout=240000")
 con.execute("PRAGMA foreign_keys=ON")
 assert con.execute("PRAGMA foreign_keys").fetchone()[0]==1
 for rec in prepared:
  assert con.execute("SELECT count(*) FROM cases WHERE id=?",(rec["cid"],)).fetchone()[0]==1
  assert con.execute("SELECT count(*) FROM arno_experiment_runs WHERE run_id=?",(rec["run_id"],)).fetchone()[0]==0,"RUN_ALREADY_EXISTS_NO_DUPLICATE_IMPORT"
 con.execute("BEGIN IMMEDIATE")
 con.execute("""CREATE TABLE IF NOT EXISTS arno_owp14_fresh_o_reruns_20261031(
 run_id TEXT PRIMARY KEY REFERENCES arno_experiment_runs(run_id),
 case_id INTEGER NOT NULL REFERENCES cases(id),
 frozen_packet_sha256 TEXT NOT NULL,
 patch_sha256 TEXT NOT NULL,
 after_sarif_sha256 TEXT NOT NULL,
 before_sarif_sha256 TEXT NOT NULL,
 historical_O_recovered INTEGER NOT NULL CHECK(historical_O_recovered=0),
 contributes_to_original_triple_count INTEGER NOT NULL CHECK(contributes_to_original_triple_count=0),
 source_model TEXT NOT NULL,
 provenance_status TEXT NOT NULL,
 functional_status TEXT NOT NULL,
 generation_date TEXT NOT NULL
 )""")
 def ev(rec,role,data,locator):
  if data is not None:
   payload=bytes(data);h=sha(payload);n=len(payload);comp="zlib";raw=zlib.compress(payload,9);v="NEW_RUN_ORIGINAL_BYTES_SHA256_VERIFIED"
  else:
   h=rec["m"]["source_sha"];n=rec["src"].stat().st_size;comp="EXTERNAL_ONLY";raw=None;v="EXTERNAL_FROZEN_INPUT_SHA256_VERIFIED_ORIGINAL_IN_VAULT"
  con.execute("""INSERT INTO arno_chat_evidence_objects(artifact_id,run_id,case_id,role,source_locator,sha256,original_bytes,compression,content_zlib,verification_status)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
   (rec["run_id"]+"::"+role,rec["run_id"],rec["cid"],role,str(locator.relative_to(ROOT)) if isinstance(locator,Path) and locator.is_relative_to(ROOT) else str(locator),h,n,comp,raw,v))
 for rec in prepared:
  run_id=rec["run_id"];cid=rec["cid"];meta=rec["meta"];m=rec["m"];result=rec["result"]
  con.execute("""INSERT INTO arno_experiment_runs(run_id,case_id,root_id,experiment_family,treatment,prompt_blob,run_metadata_json,status)
                 VALUES (?,?,NULL,?,?,?,?,?)""",(run_id,cid,"RQ3_OWP14_NEW_GENERATION_NONBLIND_20261031","O_NEW_RERUN_GPT6",rec["prompt"],json.dumps(meta,sort_keys=True),"SCANNED_NEW_EXPLORATORY_NONHISTORICAL_FUNCTIONAL_UNVERIFIED"))
  con.execute("""INSERT INTO arno_generated_patches(patch_id,run_id,content_sha256,patch_blob,patch_uri,authenticity_status,notes)
                 VALUES(?,?,?,?,?,?,?)""",(run_id+"::PATCH",run_id,m["patch_sha"],rec["patch"],str(rec["patch_path"].relative_to(ROOT)),"NEWLY_GENERATED_CURRENT_SESSION_SHA256_VERIFIED","NOT_HISTORICAL_O; NEW GPT6 generation 2026-10-31; functional acceptance not independently verified"))
  con.execute("""INSERT INTO arno_experiment_scans(scan_id,run_id,scanner,scanner_version,rule_id,raw_result_blob,result_json,execution_verified)
                 VALUES(?,?,?,?,?,?,?,1)""",(run_id+"::CODEQL_AFTER",run_id,"CodeQL",result["codeql_version"],m["target_rule"],rec["after"],json.dumps(result,sort_keys=True)))
  con.execute("""INSERT INTO arno_chat_codeql_metrics(run_id,case_id,case_label,method,source_kind,source_tree_sha256,source_zip_sha256,
                 baseline_total,after_total,new_vs_baseline,historical_p1_new,historical_p1_remaining,codeql_version,codeql_suite,sarif_sha256,
                 patch_sha256,receipt_status,functional_status,provenance_status,result_metadata_json)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
   (run_id,cid,"OWP14_CASE_"+m["case"]+"_O_RERUN","NEW_O_GPT6_NONBLIND_20261031","FULL_FROZEN_SNAPSHOT",rec["src_tree"],m["source_sha"],
    len(rec["bfr"]),len(rec["afr"]),sum(rec["flags"]),0,None,result["codeql_version"],SUITE,sha(rec["after"]),m["patch_sha"],
    "CURRENT_ASSISTANT_GENERATION_NOT_ORIGINAL_AGENT_RECEIPT","NOT_INDEPENDENTLY_VERIFIED","NEW_NONBLIND_NEVER_SUBSTITUTE_FOR_HISTORICAL_O",json.dumps(meta,sort_keys=True)))
  for i,(row,flag) in enumerate(zip(rec["afr"],rec["flags"])):
   signature={"rule":row["rule"],"path":row["path"],"line":row["line"],"fingerprint":row["fp"],"column_fingerprint":row["col"]}
   con.execute("""INSERT INTO arno_chat_codeql_findings(finding_id,run_id,case_id,result_index,rule_id,file_path,line,column,level,message,signature_sha256,new_vs_baseline,matches_historical_p1,raw_result_json)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (run_id+"::FINDING::"+str(i),run_id,cid,i,row["rule"],row["path"],row["line"],row["column"],row["level"],row["msg"],
     sha(json.dumps(signature,sort_keys=True).encode()),flag,0,json.dumps(row["raw"],sort_keys=True)))
  # Versioned raw evidence. Scan logs and full SARIF retained in normalized blob store.
  ev(rec,"patch",rec["patch"],rec["patch_path"])
  ev(rec,"after_sarif",rec["after"],rec["rs"]/"after.sarif")
  ev(rec,"baseline_sarif",rec["before"],rec["code"]/"before.sarif")
  ev(rec,"result_json",(rec["rs"]/"RESULT.json").read_bytes(),rec["rs"]/"RESULT.json")
  ev(rec,"original_issue",rec["issue"],rec["src"])
  ev(rec,"original_run_instructions",rec["instruction"],rec["src"])
  ev(rec,"source_zip_external",None,rec["src"])
  for role,folder,filename in [
    ("log_git_apply_check",rec["code"],"apply_check.log"),
    ("log_git_apply",rec["code"],"apply.log"),
    ("log_codeql_create",rec["rs"],"db_after.log" if cid==8461 else "db_create.log"),
    ("log_codeql_analyze",rec["rs"],"analyze_after.log" if cid==8461 else "analyze.log"),
    ("warning_delta_json",rec["rs"],"warning_delta.json")
   ]:
    f=folder/filename
    if f.is_file():ev(rec,role,f.read_bytes(),f)
  con.execute("""INSERT INTO arno_owp14_fresh_o_reruns_20261031(run_id,case_id,frozen_packet_sha256,patch_sha256,
        after_sarif_sha256,before_sarif_sha256,historical_O_recovered,contributes_to_original_triple_count,source_model,provenance_status,functional_status,generation_date)
        VALUES (?,?,?,?,?,?,0,0,?,?,?,?)""",
   (run_id,cid,m["source_sha"],m["patch_sha"],sha(rec["after"]),sha(rec["before"]),"GPT-6","NEW_NONBLIND_RERUN_NOT_HISTORICAL","NOT_INDEPENDENTLY_VERIFIED","2026-10-31"))
  n=con.execute("SELECT COUNT(*),SUM(new_vs_baseline) FROM arno_chat_codeql_findings WHERE run_id=?",(run_id,)).fetchone()
  assert n[0]==len(rec["afr"]) and int(n[1] or 0)==sum(rec["flags"])
 assert con.execute("PRAGMA foreign_key_check").fetchone() is None,"NEW_FOREIGN_KEY_VIOLATION"
 con.commit()
 for a in audits:a["status"]="COMMITTED_AND_VERIFIED"
except Exception:
 con.rollback()
 (OUT/"INGEST_ERROR.txt").write_text(traceback.format_exc())
 raise
finally:con.close()
audit=dict(status="COMMITTED_AND_VERIFIED",claims_scope="ONLY_NEW_NONBLIND_O_RERUNS; HISTORICAL_O_STILL_ABSENT",runs=audits,
  database=str(DB),date="2026-10-31",source_database_writes="APPEND_ONLY",previous_historical_triples=12,post_ingest_historical_triples=12)
(OUT/"FINAL_AUDIT.json").write_text(json.dumps(audit,indent=2)+"\n")
print(json.dumps(audit,indent=2))
