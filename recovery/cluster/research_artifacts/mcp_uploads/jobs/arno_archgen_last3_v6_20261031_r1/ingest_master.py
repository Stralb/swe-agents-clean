from pathlib import Path
from collections import Counter
import datetime,hashlib,json,sqlite3,zlib
ROOT=Path.home()/"research_artifacts"
D=ROOT/"mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1"
MASTER=ROOT/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
HIST=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
FROZEN=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
cases={
 "03581":{"id":3581,"run":"RPL7_RUN_887FBD20CB75","folder":"results_03581_v2","baseline":82,"p1_after":84,"p1_new":2,"source_files":397},
 "08152":{"id":8152,"run":"RPL7_RUN_23E9AAB8295A","folder":"results_08152","baseline":4,"p1_after":5,"p1_new":1,"source_files":85},
 "12344":{"id":12344,"run":"RPL7_RUN_E0EDE434153B","folder":"results_12344","baseline":758,"p1_after":763,"p1_new":5,"source_files":10341}
}
def sha(b):return hashlib.sha256(b).hexdigest()
def verified(p,expected=None):
 assert p.is_file(),("Missing",str(p))
 raw=p.read_bytes()
 if expected:assert sha(raw)==expected,("SHA mismatch",str(p),sha(raw),expected)
 return raw
def signature(raw):
 counter=Counter();results=[]
 for item in json.loads(raw).get("runs",[]):
  assert item.get("tool",{}).get("driver",{}).get("name")=="CodeQL"
  for e in item.get("results",[]):
   loc=(e.get("locations") or [{}])[0].get("physicalLocation",{})
   region=loc.get("region",{})
   key=(e.get("ruleId",""),loc.get("artifactLocation",{}).get("uri","").replace("\\","/"),
       " ".join((e.get("message",{}).get("text") or "").split()))
   counter[key]+=1
   results.append((key,region.get("startLine"),region.get("startColumn"),e.get("level"),
     json.dumps(e,ensure_ascii=False,separators=(",",":"))))
 return counter,results
pack=[]
for case,c in cases.items():
 folder=D/c["folder"]
 info=json.loads(verified(folder/"RESULT.json"))
 receipt_raw=verified(folder/("RECEIPT_ARCHGEN_"+case+"_R1.json"),info["receipt_sha256"])
 receipt=json.loads(receipt_raw)
 prompt_raw=verified(folder/("IMPLEMENTATION_PROMPT_ARCHGEN_"+case+"_R1.md"),info["prompt_sha256"])
 patch_raw=verified(folder/("PATCH_ARCHGEN_"+case+"_R1.patch"),info["patch_sha256"])
 before_dir=BASE/("CASE_"+case);p1_dir=HIST/("CASE_"+case)/c["run"]
 bm=json.loads(verified(before_dir/"RESULT.json"))
 hm=json.loads(verified(p1_dir/"RESULT.json"))
 assert info["run_id"]==receipt["run_id"]=="ARCHGEN_"+case+"_R1"
 assert receipt["case_id"]==case
 assert receipt["patch_sha256"]==info["patch_sha256"]
 assert receipt["self_prompt_sha256"]==info["prompt_sha256"]
 assert info["status"]=="CODEQL_SCAN_COMPLETE" and info["suite"]==SUITE
 assert info["codeql_version"]==hm["codeql_version"]=="2.25.6"
 assert info["original_patch_modified"] is False
 assert all(info["checks"][name]["exit"]==0 for name in ["version","apply_check","apply","create","analyze"])
 assert info["source_file_count"]==bm["sanitized_repo_files"]==c["source_files"]
 assert info["source_kind"]==bm["source_kind"]==hm["source_kind"]
 assert info["source_tree_sha256"]==bm["sanitized_repo_sha256"]
 assert info["source_zip_sha256"]==bm["input_zip_sha256"]
 assert info["baseline_total"]==bm["result_count"]==c["baseline"]
 assert info["historical_p1_total"]==hm["after_total"]==c["p1_after"]
 assert info["historical_p1_new"]==hm["new_conservative_line_agnostic"]==c["p1_new"]
 before=verified(before_dir/"baseline.sarif",bm["sarif_sha256"])
 historical=verified(p1_dir/"after.sarif",hm["after_sarif_sha256"])
 after=verified(folder/"after.sarif",info["after_sarif_sha256"])
 bc,br=signature(before);hc,hr=signature(historical);ac,ar=signature(after)
 assert len(br)==c["baseline"] and len(hr)==c["p1_after"] and len(ar)==info["after_total"]
 historical_delta=hc-bc;current_delta=ac-bc
 assert sum(historical_delta.values())==c["p1_new"]
 assert sum(current_delta.values())==info["new_vs_baseline"]
 assert sum((historical_delta&current_delta).values())==info["historical_p1_remaining"]
 original=FROZEN/(c["run"]+".zip")
 assert original.is_file() and original.stat().st_size>0
 assert sha(original.read_bytes())==info["source_zip_sha256"]
 pack.append(dict(case=case,c=c,folder=folder,info=info,receipt=receipt,receipt_raw=receipt_raw,
                  prompt_raw=prompt_raw,patch_raw=patch_raw,after_raw=after,
                  baseline=bc,historical_delta=historical_delta,after_rows=ar,source=original))
print("ALL_THREE_VERIFIED_BEFORE_DB_WRITE",[(x["case"],x["info"]["new_vs_baseline"]) for x in pack],flush=True)

con=sqlite3.connect(str(MASTER),timeout=120,isolation_level=None)
con.execute("PRAGMA foreign_keys=ON")
con.execute("PRAGMA busy_timeout=120000")
before={
 "runs":con.execute("SELECT COUNT(*) FROM arno_experiment_runs").fetchone()[0],
 "scans":con.execute("SELECT COUNT(*) FROM arno_experiment_scans").fetchone()[0],
 "patches":con.execute("SELECT COUNT(*) FROM arno_generated_patches").fetchone()[0],
 "chat_metrics":con.execute("SELECT COUNT(*) FROM arno_chat_codeql_metrics").fetchone()[0]}
assert before["chat_metrics"]==23,("Unexpected pre-existing experiment count",before)
added={"runs":0,"scans":0,"patches":0,"metrics":0,"artifacts":0,"findings":0}
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def artifact(cursor,x,role,p,raw=None,external=False):
 rid=x["info"]["run_id"];cid=x["c"]["id"]
 if external:
  assert p.is_file()
  expected=x["info"]["source_zip_sha256"];content=None;size=p.stat().st_size
  codec="EXTERNAL_ONLY";status="FROZEN_SHA_VERIFIED"
 else:
  if raw is None:raw=verified(p)
  expected=sha(raw);size=len(raw)
  content=zlib.compress(raw,6);codec="zlib";status="ORIGINAL_BYTES_HASH_VERIFIED_EMBEDDED"
 assert p.is_relative_to(ROOT)
 loc=str(p.relative_to(ROOT))
 cursor.execute("""INSERT INTO arno_chat_evidence_objects
    (artifact_id,run_id,case_id,role,source_locator,sha256,original_bytes,compression,content_zlib,verification_status)
    VALUES (?,?,?,?,?,?,?,?,?,?)""",
   (rid+"::"+role,rid,cid,role,loc,expected,size,codec,content,status))
 added["artifacts"]+=1
try:
 con.execute("BEGIN IMMEDIATE")
 cursor=con.cursor()
 for x in pack:
  c=x["c"];case=x["case"];info=x["info"];rid=info["run_id"];cid=c["id"];folder=x["folder"]
  assert cursor.execute("SELECT id FROM cases WHERE id=?",(cid,)).fetchone() is not None
  assert cursor.execute("SELECT run_id FROM arno_experiment_runs WHERE run_id=?",(rid,)).fetchone() is None
  metadata=dict(info,chat_ingest_batch="ARCHGEN_LAST_THREE_20261031",
   functional_verification="NOT_INDEPENDENTLY_COMPLETED",
   agent_reported_generation_status=x["receipt"].get("generation_status"),
   source_note="Previously studied case; not a held-out test; one agent conversation across three cases")
  cursor.execute("""INSERT INTO arno_experiment_runs
   (run_id,case_id,root_id,experiment_family,treatment,prompt_blob,run_metadata_json,status)
   VALUES (?,?,?,?,?,?,?,?)""",
   (rid,cid,None,"OCT2026_ARCHITECTURAL_GENERATION","GENERAL_ARCHITECTURE",x["prompt_raw"],
    json.dumps(metadata,sort_keys=True),"CODEQL_SCAN_COMPLETE_FUNCTIONAL_NOT_VERIFIED"))
  added["runs"]+=1
  p=folder/("PATCH_ARCHGEN_"+case+"_R1.patch")
  cursor.execute("""INSERT INTO arno_generated_patches
   (patch_id,run_id,content_sha256,patch_blob,patch_uri,authenticity_status,notes)
   VALUES (?,?,?,?,?,?,?)""",
   (rid+"::PATCH",rid,info["patch_sha256"],x["patch_raw"],str(p.relative_to(ROOT)),
    "FIRST_DELIVERY_SHA256_VERIFIED_GENERATOR_NOT_INDEPENDENTLY_AUTHENTICATED",
    "Original agent-returned patch, unchanged, no remediation after scanner output"))
  added["patches"]+=1
  cursor.execute("""INSERT INTO arno_experiment_scans
   (scan_id,run_id,scanner,scanner_version,rule_id,raw_result_blob,result_json,execution_verified)
   VALUES (?,?,?,?,?,?,?,?)""",
   (rid+"::CODEQL",rid,"CodeQL","2.25.6",None,x["after_raw"],json.dumps(metadata,sort_keys=True),1))
  added["scans"]+=1
  cursor.execute("""INSERT INTO arno_chat_codeql_metrics
   (run_id,case_id,case_label,method,source_kind,source_tree_sha256,source_zip_sha256,
    baseline_total,after_total,new_vs_baseline,historical_p1_new,historical_p1_remaining,
    codeql_version,codeql_suite,sarif_sha256,patch_sha256,receipt_status,functional_status,
    provenance_status,result_metadata_json)
   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
   (rid,cid,case,"GENERAL_ARCHITECTURE",info["source_kind"],
    info["source_tree_sha256"],info["source_zip_sha256"],c["baseline"],info["after_total"],
    info["new_vs_baseline"],c["p1_new"],info["historical_p1_remaining"],"2.25.6",SUITE,
    info["after_sarif_sha256"],info["patch_sha256"],"PRESENT_VERIFIED",
    "NOT_INDEPENDENTLY_VERIFIED",
    "FIRST_DELIVERY_PATCH_SHA_VERIFIED; SCANNER_EXECUTED; PARTIAL_FUNCTIONALITY",
    json.dumps(metadata,sort_keys=True)))
  added["metrics"]+=1
  artifact(cursor,x,"after_sarif",folder/"after.sarif",x["after_raw"])
  artifact(cursor,x,"result_json",folder/"RESULT.json")
  artifact(cursor,x,"warning_delta_json",folder/"warning_delta.json")
  artifact(cursor,x,"patch",p,x["patch_raw"])
  artifact(cursor,x,"agent_receipt",folder/("RECEIPT_ARCHGEN_"+case+"_R1.json"),x["receipt_raw"])
  artifact(cursor,x,"self_written_prompt",folder/("IMPLEMENTATION_PROMPT_ARCHGEN_"+case+"_R1.md"),x["prompt_raw"])
  artifact(cursor,x,"source_zip_external",x["source"],external=True)
  for log in ["version.log","apply.log","apply_check.log","create.log","analyze.log"]:
   f=folder/log
   if f.is_file():artifact(cursor,x,"log_"+log,f)
  remaining=x["baseline"].copy();hist=x["historical_delta"].copy();number_new=0;number_match=0
  for i,(key,line,column,level,raw_json) in enumerate(x["after_rows"]):
   is_new=0
   if remaining[key]>0:remaining[key]-=1
   else:is_new=1
   match=int(bool(is_new and hist[key]>0))
   if match:hist[key]-=1
   number_new+=is_new;number_match+=match
   signature=sha(json.dumps(key,separators=(",",":"),ensure_ascii=False).encode("utf8"))
   cursor.execute("""INSERT INTO arno_chat_codeql_findings
      (finding_id,run_id,case_id,result_index,rule_id,file_path,line,column,level,message,
       signature_sha256,new_vs_baseline,matches_historical_p1,raw_result_json)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (rid+":"+str(i).zfill(6),rid,cid,i,key[0],key[1],line,column,level,key[2],
       signature,is_new,match,raw_json))
   added["findings"]+=1
  assert number_new==info["new_vs_baseline"] and number_match==info["historical_p1_remaining"]
  got=cursor.execute("SELECT COUNT(*), COALESCE(SUM(new_vs_baseline),0) FROM arno_chat_codeql_findings WHERE run_id=?",(rid,)).fetchone()
  assert got==(info["after_total"],info["new_vs_baseline"])
 assert cursor.execute("SELECT COUNT(*) FROM arno_chat_codeql_metrics").fetchone()[0]==26
 manifest=[{"case":x["case"],"patch":x["info"]["patch_sha256"],"sarif":x["info"]["after_sarif_sha256"],"receipt":x["info"]["receipt_sha256"],"prompt":x["info"]["prompt_sha256"]} for x in pack]
 cursor.execute("""INSERT INTO arno_chat_ingest_ledger
   (batch_id,ingested_utc,source_manifest_sha256,completed_runs,patch_count,sarif_count,finding_count,
    missing_receipts_json,preexisting_counts_json,notes)
   VALUES (?,?,?,?,?,?,?,?,?,?)""",
   ("ARNO_ARCHGEN_LAST_THREE_20261031_R1",now,sha(json.dumps(manifest,sort_keys=True).encode()),
    3,3,3,added["findings"],"[]",json.dumps(before),
    "Three final original-seven GASP runs; raw CodeQL SARIF, raw patches, prompts and receipts embedded; functional acceptance incomplete."))
 con.commit()
except BaseException:
 con.rollback()
 raise
finally:con.close()
report={"status":"COMMITTED_VERIFIED","created_at_utc":now,"master_path":str(MASTER),
   "before":before,"new_rows":added,
   "cases":{x["case"]:{key:x["info"][key] for key in
     ("run_id","status","source_kind","baseline_total","after_total","new_vs_baseline","historical_p1_new","historical_p1_remaining","patch_sha256","prompt_sha256","receipt_sha256","after_sarif_sha256")}
     for x in pack}}
dest=D/"MASTER_INGEST_RESULT.json"
assert not dest.exists()
dest.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2),flush=True)
