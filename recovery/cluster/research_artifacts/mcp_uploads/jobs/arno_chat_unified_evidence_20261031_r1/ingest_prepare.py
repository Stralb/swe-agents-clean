# Audited input inventory and scanner signature verification; no DB writes.
from pathlib import Path
from collections import Counter
import hashlib,json
ROOT=Path.home()/"research_artifacts"
MASTER=ROOT/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
STAGE=ROOT/"mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1"
BASE=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
HIST=ROOT/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
INPUT=ROOT/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"
VERSION="2.25.6"
CASES={
 "03429":"RPL7_RUN_6F9E2CE56C8C",
 "03581":"RPL7_RUN_887FBD20CB75",
 "08152":"RPL7_RUN_23E9AAB8295A",
 "12344":"RPL7_RUN_E0EDE434153B",
 "22223":"RPL7_RUN_3D0780CD09D2",
 "31207":"RPL7_RUN_18A6F0AE41E9",
 "32759":"RPL7_RUN_C24121FB6FE5"}
VARIANTS=[
 ("03581","SCGG","SCGG_03581_P1","arno_scgg_03581_v6_20261030_r1/results","PATCH_SCGG_03581_P1.patch","RECEIPT_SCGG_03581_P1.json",None),
 ("08152","SCGG","SCGG_08152_R1","arno_scgg_replication_08152_12344_20261030_r1/results_08152","PATCH_SCGG_08152_R1.patch","RECEIPT_SCGG_08152_R1.json",None),
 ("12344","SCGG","SCGG_12344_R1","arno_scgg_replication_08152_12344_20261030_r1/results_12344","PATCH_SCGG_12344_R1.patch","RECEIPT_SCGG_12344_R1.json",None),
 ("12344","SELF_PROMPT","SPSCGG_12344_R1","arno_spss_12344_v6_20261030_r1/results","PATCH_SPSCGG_12344_R1.patch","RECEIPT_SPSCGG_12344_R1.json","IMPLEMENTATION_PROMPT_SPSCGG_12344_R1.md"),
 ("12344","ARCHITECTURE_CONSTRAINED","ARCHSPSCGG_12344_R1","arno_archsps_12344_v6_20261030_r1/results","PATCH_ARCHSPSCGG_12344_R1.patch","RECEIPT_ARCHSPSCGG_12344_R1.json","IMPLEMENTATION_PROMPT_ARCHSPSCGG_12344_R1.md"),
 ("22223","GENERAL_ARCHITECTURE","ARCHGEN_22223_R1","arno_archgen_22223_32759_v6_20261030_r1/results_22223","PATCH_ARCHGEN_22223_R1.patch",None,"IMPLEMENTATION_PROMPT_ARCHGEN_22223_R1.md"),
 ("32759","GENERAL_ARCHITECTURE","ARCHGEN_32759_R1","arno_archgen_22223_32759_v6_20261030_r1/results_32759","PATCH_ARCHGEN_32759_R1.patch","RECEIPT_ARCHGEN_32759_R1.json","IMPLEMENTATION_PROMPT_ARCHGEN_32759_R1.md")]
PENDING=[("03429","ARCHGEN_03429_R1"),("31207","ARCHGEN_31207_R1")]
def sha(b):return hashlib.sha256(b).hexdigest()
def filebytes(p,expect=None):
 assert p.is_file(),("Missing source",str(p))
 b=p.read_bytes()
 if expect:assert sha(b)==expect,("SHA mismatch",str(p),sha(b),expect)
 return b
def info(p):return json.loads(filebytes(p).decode())
def results_from_sarif(raw):
 result=[]
 for segment in json.loads(raw).get("runs",[]):
  assert segment.get("tool",{}).get("driver",{}).get("name")=="CodeQL"
  for obj in segment.get("results",[]):
   loc=(obj.get("locations") or [{}])[0].get("physicalLocation",{})
   region=loc.get("region",{})
   key=(obj.get("ruleId",""),loc.get("artifactLocation",{}).get("uri","").replace("\\","/"),
        " ".join((obj.get("message",{}).get("text") or obj.get("message",{}).get("markdown") or "").split()))
   result.append((key,region.get("startLine"),region.get("startColumn"),obj.get("level"),json.dumps(obj,separators=(",",":"),ensure_ascii=False)))
 return result
def counts(items):return Counter(row[0] for row in items)
RUNS=[];BASELINES={}
for case,source_run in CASES.items():
 bdir=BASE/("CASE_"+case);bm=info(bdir/"RESULT.json")
 assert bm["case_id"]==case and bm["model_run_id_p1"]==source_run
 assert bm["status"]=="BASELINE_CODEQL_COMPLETE" and bm["suite"]==SUITE and bm["codeql_version_expected"]==VERSION
 assert bm["source_kind"] in ("FULL_FROZEN_SNAPSHOT","FILTERED_SOURCE_PROVISIONAL")
 source=INPUT/(source_run+".zip")
 filebytes(source,bm["input_zip_sha256"])
 sarif_file=bdir/"baseline.sarif";sarif=filebytes(sarif_file,bm["sarif_sha256"])
 rows=results_from_sarif(sarif)
 assert len(rows)==bm["result_count"],("baseline SARIF result mismatch",case)
 baseline=dict(case=case,case_int=int(case),method="FROZEN_BASELINE",id="CHAT_BASELINE_"+case,meta=bm,
   dir=bdir,sarif_path=sarif_file,sarif=sarif,rows=rows,
   patch=None,receipt=None,prompt=None,source=source,
   source_sha=bm["input_zip_sha256"],tree=bm["sanitized_repo_sha256"],
   source_kind=bm["source_kind"],new=0,functional="NOT_TESTED")
 BASELINES[case]=baseline;RUNS.append(baseline)
 hdir=HIST/("CASE_"+case)/source_run;hm=info(hdir/"RESULT.json")
 assert hm["run_id"]==source_run and hm["case_id"]==case
 assert hm["status"]=="CODEQL_SCAN_COMPLETE" and hm["codeql_version"]==VERSION and hm["suite"]==SUITE
 assert hm["source_kind"]==bm["source_kind"] and hm["sanitized_repo_tree_sha256"]==bm["sanitized_repo_sha256"]
 patch=hdir/("PATCH_"+source_run+".patch");receipt=hdir/("RECEIPT_"+source_run+".json")
 filebytes(patch,hm["patch_sha256"]);filebytes(receipt,hm["receipt_sha256"])
 after=hdir/"after.sarif";s=filebytes(after,hm["after_sarif_sha256"]);rs=results_from_sarif(s)
 delta=counts(rs)-counts(rows);new=sum(delta.values())
 assert len(rs)==hm["after_total"] and new==hm["new_conservative_line_agnostic"],("P1 mismatch",case,new)
 RUNS.append(dict(case=case,case_int=int(case),method="HISTORICAL_P1",id=source_run,meta=hm,
   dir=hdir,sarif_path=after,sarif=s,rows=rs,patch=patch,receipt=receipt,prompt=None,source=source,
   source_sha=bm["input_zip_sha256"],tree=bm["sanitized_repo_sha256"],
   source_kind=bm["source_kind"],new=new,functional=hm.get("functional_status","NOT_TESTED")))
for case,method,rid,sub,patch_name,receipt_name,prompt_name in VARIANTS:
 base=BASELINES[case];dir=ROOT/"mcp_uploads/jobs"/sub;meta=info(dir/"RESULT.json")
 assert meta["run_id"]==rid and meta["status"]=="CODEQL_SCAN_COMPLETE" and meta["suite"]==SUITE
 assert meta["source_kind"]==base["source_kind"] and meta["source_tree_sha256"]==base["tree"]
 assert meta["source_zip_sha256"]==base["source_sha"] and meta["source_files"]==base["meta"]["sanitized_repo_files"]
 assert meta.get("codeql_version",VERSION)==VERSION
 patch=dir/patch_name;filebytes(patch,meta["patch_sha256"])
 receipt=dir/receipt_name if receipt_name else None
 if receipt:filebytes(receipt,meta["receipt_sha256"])
 else:assert meta.get("receipt_status")=="MISSING"
 prompt=dir/prompt_name if prompt_name else None
 if prompt:filebytes(prompt,meta.get("prompt_sha256") or meta.get("implementation_prompt_sha256"))
 after=dir/"after.sarif";raw=filebytes(after,meta["after_sarif_sha256"])
 rows=results_from_sarif(raw);new=sum((counts(rows)-counts(base["rows"])).values())
 assert len(rows)==meta["after_total"] and new==meta["new_vs_baseline"],("Intervention mismatch",rid,new)
 RUNS.append(dict(case=case,case_int=int(case),method=method,id=rid,meta=meta,
   dir=dir,sarif_path=after,sarif=raw,rows=rows,patch=patch,receipt=receipt,prompt=prompt,
   source=base["source"],source_sha=base["source_sha"],tree=base["tree"],
   source_kind=base["source_kind"],new=new,functional=meta.get("functional_status","NOT_VERIFIED")))
assert len(RUNS)==21 and len({r["id"] for r in RUNS})==21
hist={r["case"]:r for r in RUNS if r["method"]=="HISTORICAL_P1"}
for r in RUNS:
 base=BASELINES[r["case"]]
 r["historical_new"]=hist[r["case"]]["new"]
 r["p1_delta"]=counts(hist[r["case"]]["rows"])-counts(base["rows"])
 r["historical_remaining"]=None if r["method"] in ("FROZEN_BASELINE","HISTORICAL_P1") else sum((r["p1_delta"]&(counts(r["rows"])-counts(base["rows"]))).values())
stats={
 "completed_runs":len(RUNS),"case_count":len(BASELINES),"historical_p1_runs":7,"baseline_runs":7,
 "intervention_runs":len(VARIANTS),"patches":sum(bool(r["patch"]) for r in RUNS),
 "sarif":len(RUNS),"receipts":sum(bool(r["receipt"]) for r in RUNS),
 "self_written_prompts":sum(bool(r["prompt"]) for r in RUNS),
 "individual_scanner_findings":sum(len(r["rows"]) for r in RUNS),
 "pending_cases":[x[0] for x in PENDING],"known_missing_receipts":["ARCHGEN_22223_R1"],
 "case_summary":{cid:[dict(run_id=r["id"],method=r["method"],after=len(r["rows"]),new=r["new"])
                      for r in RUNS if r["case"]==cid] for cid in CASES}}
STAGE.mkdir(parents=True,exist_ok=True)
print("INPUTS_VERIFIED",json.dumps({k:v for k,v in stats.items() if k!="case_summary"},sort_keys=True),flush=True)
