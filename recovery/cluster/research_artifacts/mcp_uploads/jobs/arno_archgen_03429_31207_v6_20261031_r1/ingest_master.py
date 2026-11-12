"""Append two verified ARCHGEN runs to the existing research master, transactionally."""
from pathlib import Path
from collections import Counter
import datetime,hashlib,json,sqlite3,zlib,zipfile

ROOT=Path.home()/"research_artifacts"
DIR=ROOT/"mcp_uploads/jobs/arno_archgen_03429_31207_v6_20261031_r1"
UPLOAD=ROOT/"mcp_uploads/archgen_03429_31207_uploaded_20261031"
MASTER=ROOT/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
P1=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
SOURCE=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
CFG={
"03429":{"id":3429,"run":"RPL7_RUN_6F9E2CE56C8C","patch":"5b8e0ab4063788f2c6a5efe52b355511192515f434adbdc23c0457a16f4f5f97","receipt":"43f4698c07c1e49361da6a43bc97fd5f3384f7ccaea8bbbce0cf67b2bc8484aa","prompt":"6589cb81c5c5ac4f045b9da0517d5c090b6e804d4fd881024b52ab1fc4ca469c","baseline":42,"historical":40,"p1_new":1,"after":39,"new":0,"source_files":241},
"31207":{"id":31207,"run":"RPL7_RUN_18A6F0AE41E9","patch":"970ea6a8e84d3191ec16fe9cbeef94d659e0c951ed32866e45d67b25cc1f71db","receipt":"bbc0b763dd1256a84713b753b10703416a625df8c8900623de357cfd4ab71d91","prompt":"e8b5c45823c0cf991615b5beac83a2eb640d80f7b91dc845a5211e52da1736df","baseline":60,"historical":61,"p1_new":1,"after":61,"new":1,"source_files":15499}
}
def sha(b):return hashlib.sha256(b).hexdigest()
def verified(p,expected=None):
 assert p.is_file(),("Missing",str(p))
 data=p.read_bytes()
 if expected:assert sha(data)==expected,("SHA mismatch",str(p),sha(data),expected)
 return data
def sig_data(raw):
 data=[];counter=Counter()
 for run in json.loads(raw).get("runs",[]):
  assert run.get("tool",{}).get("driver",{}).get("name")=="CodeQL"
  for result in run.get("results",[]):
   loc=(result.get("locations") or [{}])[0].get("physicalLocation",{})
   region=loc.get("region",{})
   key=(result.get("ruleId",""),loc.get("artifactLocation",{}).get("uri","").replace("\\","/")," ".join((result.get("message",{}).get("text") or "").split()))
   counter[key]+=1
   data.append((key,region.get("startLine"),region.get("startColumn"),result.get("level"),json.dumps(result,separators=(",",":"),ensure_ascii=False)))
 return counter,data

prepared=[]
for case,c in CFG.items():
 directory=DIR/("results_"+case)
 bdir=BASE/("CASE_"+case)
 hdir=P1/("CASE_"+case)/c["run"]
 bm=json.loads(verified(bdir/"RESULT.json"));hm=json.loads(verified(hdir/"RESULT.json"))
 result=json.loads(verified(directory/"RESULT.json"))
 assert result["run_id"]=="ARCHGEN_"+case+"_R1" and result["status"]=="CODEQL_SCAN_COMPLETE"
 assert result["source_kind"]==bm["source_kind"]=="FILTERED_SOURCE_PROVISIONAL"
 assert result["codeql_suite"]==bm["suite"]==hm["suite"]==SUITE
 assert result["codeql_version"]==hm["codeql_version"]=="2.25.6"
 assert result["source_zip_sha256"]==bm["input_zip_sha256"]
 assert result["source_tree_sha256"]==bm["sanitized_repo_sha256"]
 assert result["source_files"]==bm["sanitized_repo_files"]==c["source_files"]
 assert result["baseline_total"]==bm["result_count"]==c["baseline"]
 assert result["historical_p1_total"]==hm["after_total"]==c["historical"]
 assert result["historical_p1_new"]==hm["new_conservative_line_agnostic"]==c["p1_new"]
 assert result["after_total"]==c["after"] and result["new_vs_baseline"]==c["new"]
 assert result["patch_sha256"]==c["patch"]
 assert all(result["checks"].get(k)==0 for k in ("codeql_version","apply_check","apply","database_create","analyze"))
 patch=verified(directory/("PATCH_ARCHGEN_"+case+"_R1.patch"),c["patch"])
 prompt_path=UPLOAD/("IMPLEMENTATION_PROMPT_ARCHGEN_"+case+"_R1.md")
 receipt_path=UPLOAD/("RECEIPT_ARCHGEN_"+case+"_R1.json")
 prompt=verified(prompt_path,c["prompt"]);receipt=verified(receipt_path,c["receipt"])
 agent=json.loads(receipt)
 assert agent["run_id"]==result["run_id"]
 assert agent["patch_sha256"]==c["patch"] and agent["self_prompt_sha256"]==c["prompt"]
 assert str(agent["case_id"])==case
 b_raw=verified(bdir/"baseline.sarif",bm["sarif_sha256"])
 p_raw=verified(hdir/"after.sarif",hm["after_sarif_sha256"])
 a_raw=verified(directory/"after.sarif",result["after_sarif_sha256"])
 bc,brows=sig_data(b_raw);pc,prows=sig_data(p_raw);ac,arows=sig_data(a_raw)
 historical_delta=pc-bc;actual_delta=ac-bc
 assert len(brows)==c["baseline"] and len(prows)==c["historical"] and len(arows)==c["after"]
 assert sum(historical_delta.values())==c["p1_new"]
 assert sum(actual_delta.values())==c["new"]
 assert sum((historical_delta&actual_delta).values())==result["historical_p1_remaining"]
 verified(SOURCE/(c["run"]+".zip"),bm["input_zip_sha256"]) if c["source_files"]<1000 else None
 prepared.append(dict(case=case,cfg=c,result=result,agent=agent,bdir=bdir,hdir=hdir,dir=directory,
  patch=patch,prompt=prompt,receipt=receipt,prompt_path=prompt_path,receipt_path=receipt_path,
  after=a_raw,after_rows=arows,baseline_counter=bc,historical_delta=historical_delta,source=SOURCE/(c["run"]+".zip")))
print("PRECHECK_PASSED",[(x["case"],x["result"]["new_vs_baseline"]) for x in prepared],flush=True)

con=sqlite3.connect(str(MASTER),timeout=120,isolation_level=None)
con.execute("PRAGMA busy_timeout=120000")
con.execute("PRAGMA foreign_keys=ON")
counts={"runs":0,"patches":0,"scans":0,"metrics":0,"artifacts":0,"findings":0,"pending_updated":0}
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def add_artifact(cur,obj,role,path,data=None,hash_expected=None,external=False):
 rid=obj["result"]["run_id"];cid=obj["cfg"]["id"]
 if external:
  assert path.is_file()
  assert hash_expected
  size=path.stat().st_size
  actual_hash=hash_expected
  content=None;codec="EXTERNAL_ONLY";verify="V6_FROZEN_SOURCE_SHA_VERIFIED"
 else:
  if data is None:data=verified(path,hash_expected)
  actual_hash=sha(data);size=len(data)
  if hash_expected:assert actual_hash==hash_expected
  content=zlib.compress(data,6);codec="zlib";verify="ORIGINAL_BYTES_SHA_VERIFIED_EMBEDDED"
 assert path.is_relative_to(ROOT)
 uri=str(path.relative_to(ROOT))
 identifier=rid+"::"+role
 cur.execute("""INSERT INTO arno_chat_evidence_objects
   (artifact_id,run_id,case_id,role,source_locator,sha256,original_bytes,compression,content_zlib,verification_status)
   VALUES(?,?,?,?,?,?,?,?,?,?)""",(identifier,rid,cid,role,uri,actual_hash,size,codec,content,verify))
 counts["artifacts"]+=1

try:
 con.execute("BEGIN IMMEDIATE")
 db=con.cursor()
 for r in prepared:
  c=r["cfg"];case=r["case"];result=r["result"];rid=result["run_id"];cid=c["id"]
  assert db.execute("SELECT 1 FROM cases WHERE id=?",(cid,)).fetchone()
  assert not db.execute("SELECT 1 FROM arno_experiment_runs WHERE run_id=?",(rid,)).fetchone()
  metadata=dict(result,receipt_status="PRESENT_SHA_VERIFIED",prompt_sha256=c["prompt"],receipt_sha256=c["receipt"],
    chat_ingest="ARCHGEN_TWO_MORE_CASES_20261031",functional_status="NOT_FULLY_VERIFIED",
    methodological_qualification="Previously studied cases; filtered provisional source snapshots; single chat")
  db.execute("""INSERT INTO arno_experiment_runs
   (run_id,case_id,root_id,experiment_family,treatment,prompt_blob,run_metadata_json,status)
   VALUES (?,?,?,?,?,?,?,?)""",
   (rid,cid,None,"OCT2026_ARCHITECTURAL_GENERATION","GENERAL_ARCHITECTURE",r["prompt"],
    json.dumps(metadata,sort_keys=True),"CODEQL_SCAN_COMPLETE_FUNCTIONAL_NOT_VERIFIED"))
  counts["runs"]+=1
  db.execute("""INSERT INTO arno_generated_patches
   (patch_id,run_id,content_sha256,patch_blob,patch_uri,authenticity_status,notes)
   VALUES (?,?,?,?,?,?,?)""",(rid+"::PATCH",rid,c["patch"],r["patch"],
      str((r["dir"]/("PATCH_ARCHGEN_"+case+"_R1.patch")).relative_to(ROOT)),
      "USER_RETURNED_SHA_VERIFIED_AGENT_ORIGIN_NOT_INDEPENDENTLY_ATTESTED",
      "Original first-delivered patch, unchanged; scanner succeeded without patch edits"))
  counts["patches"]+=1
  db.execute("""INSERT INTO arno_experiment_scans
   (scan_id,run_id,scanner,scanner_version,rule_id,raw_result_blob,result_json,execution_verified)
   VALUES (?,?,?,?,?,?,?,?)""",
   (rid+"::CODEQL",rid,"CodeQL","2.25.6",None,r["after"],json.dumps(metadata,sort_keys=True),1))
  counts["scans"]+=1
  db.execute("""INSERT INTO arno_chat_codeql_metrics
   (run_id,case_id,case_label,method,source_kind,source_tree_sha256,source_zip_sha256,
    baseline_total,after_total,new_vs_baseline,historical_p1_new,historical_p1_remaining,
    codeql_version,codeql_suite,sarif_sha256,patch_sha256,receipt_status,functional_status,
    provenance_status,result_metadata_json)
   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
   (rid,cid,case,"GENERAL_ARCHITECTURE","FILTERED_SOURCE_PROVISIONAL",
    result["source_tree_sha256"],result["source_zip_sha256"],c["baseline"],c["after"],c["new"],c["p1_new"],
    result["historical_p1_remaining"],"2.25.6",SUITE,result["after_sarif_sha256"],
    c["patch"],"PRESENT_VERIFIED","NOT_FULLY_VERIFIED",
    "ALL_UPLOADS_AND_SARIF_SHA256_VERIFIED; EXPERIMENTAL_FUNCTIONALITY_NOT_PROVEN",
    json.dumps(metadata,sort_keys=True)))
  counts["metrics"]+=1
  add_artifact(db,r,"after_sarif",r["dir"]/"after.sarif",r["after"],result["after_sarif_sha256"])
  add_artifact(db,r,"result_json",r["dir"]/"RESULT.json")
  add_artifact(db,r,"warning_delta_json",r["dir"]/"warning_delta.json")
  add_artifact(db,r,"patch",r["dir"]/("PATCH_ARCHGEN_"+case+"_R1.patch"),r["patch"],c["patch"])
  add_artifact(db,r,"agent_receipt",r["receipt_path"],r["receipt"],c["receipt"])
  add_artifact(db,r,"self_written_prompt",r["prompt_path"],r["prompt"],c["prompt"])
  add_artifact(db,r,"source_zip_external",r["source"],hash_expected=result["source_zip_sha256"],external=True)
  for log in ["version.log","apply_check.log","apply.log","create.log","analyze.log"]:
   path=r["dir"]/log
   if path.is_file():add_artifact(db,r,"log_"+log,path)
  remaining=r["baseline_counter"].copy();hist=r["historical_delta"].copy();observed_new=0;matched=0
  for index,(key,line,column,level,raw_json) in enumerate(r["after_rows"]):
   new=0
   if remaining[key]>0:remaining[key]-=1
   else:new=1
   is_historical=int(bool(new and hist[key]>0))
   if is_historical:hist[key]-=1
   observed_new+=new;matched+=is_historical
   db.execute("""INSERT INTO arno_chat_codeql_findings
    (finding_id,run_id,case_id,result_index,rule_id,file_path,line,column,level,message,signature_sha256,
     new_vs_baseline,matches_historical_p1,raw_result_json)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (rid+":"+str(index).zfill(6),rid,cid,index,key[0],key[1],line,column,level,key[2],
     sha(json.dumps(key,separators=(",",":"),ensure_ascii=False).encode()),new,is_historical,raw_json))
   counts["findings"]+=1
  assert observed_new==c["new"] and matched==result["historical_p1_remaining"]
  got=db.execute("SELECT COUNT(*),COALESCE(SUM(new_vs_baseline),0) FROM arno_chat_codeql_findings WHERE run_id=?",(rid,)).fetchone()
  assert got==(c["after"],c["new"])
  db.execute("""UPDATE arno_chat_pending_runs
    SET status='CODEQL_SCAN_COMPLETE_FUNCTIONALITY_NOT_VERIFIED',
        missing_artifacts_json='[]',
        notes='Complete prompt/receipt/patch/SARIF imported; V6 scan verified; runtime functionality not fully validated'
    WHERE run_id=? AND status='AWAITING_AGENT_OUTPUTS'""",(rid,))
  assert db.rowcount==1,("Missing expected pending run",rid)
  counts["pending_updated"]+=1
 batch="ARNO_ARCHGEN_TWO_MORE_20261031_R1"
 manifest=[{"run_id":r["result"]["run_id"],"patch":r["cfg"]["patch"],"prompt":r["cfg"]["prompt"],
            "receipt":r["cfg"]["receipt"],"sarif":r["result"]["after_sarif_sha256"]} for r in prepared]
 db.execute("""INSERT INTO arno_chat_ingest_ledger
    (batch_id,ingested_utc,source_manifest_sha256,completed_runs,patch_count,sarif_count,finding_count,
    missing_receipts_json,preexisting_counts_json,notes)
    VALUES(?,?,?,?,?,?,?,?,?,?)""",
   (batch,now,sha(json.dumps(manifest,sort_keys=True).encode()),2,2,2,counts["findings"],
    "[]",json.dumps({"previously_loaded_runs":21}),
    "Transactional append to master; both pending cases marked scanned. No Hugging Face changes."))
 assert db.execute("SELECT COUNT(*) FROM arno_chat_codeql_metrics").fetchone()[0]==23
 assert db.execute("SELECT COUNT(*) FROM arno_chat_pending_runs WHERE status='AWAITING_AGENT_OUTPUTS'").fetchone()[0]==0
 con.commit()
except BaseException:
 con.rollback()
 raise
finally:con.close()

summary={"status":"COMMITTED_VERIFIED","ingested_utc":now,"master_path":str(MASTER),
 "new_rows":counts,"cases":{r["case"]:{"baseline":r["cfg"]["baseline"],
          "historical_new":r["cfg"]["p1_new"],"after":r["cfg"]["after"],"new":r["cfg"]["new"],
          "patch_sha256":r["cfg"]["patch"],"receipt_sha256":r["cfg"]["receipt"],
          "prompt_sha256":r["cfg"]["prompt"],"sarif_sha256":r["result"]["after_sarif_sha256"]} for r in prepared}}
destination=DIR/"MASTER_INGEST_RESULT.json"
assert not destination.exists()
destination.write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary,indent=2),flush=True)
