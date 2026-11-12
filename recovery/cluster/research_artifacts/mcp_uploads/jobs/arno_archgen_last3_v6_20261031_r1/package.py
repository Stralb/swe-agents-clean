from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
from datetime import datetime,timezone
import hashlib,json
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1"
B=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results"
H=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results"
F=R/"mcp_uploads/jobs/arno_v6_20261030_p1p2p3_blinded_runs_v2/run_zips"
RUNS={"03581":("RPL7_RUN_887FBD20CB75","results_03581_v2",82,84,3),
      "08152":("RPL7_RUN_23E9AAB8295A","results_08152",4,5,1),
      "12344":("RPL7_RUN_E0EDE434153B","results_12344",758,763,5)}
def digest(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
 return h.hexdigest()
meta={};items={};sources={}
for cid,(run,folder,baseline,p1after,new) in RUNS.items():
 od=D/folder;bd=B/("CASE_"+cid);hd=H/("CASE_"+cid)/run
 r=json.loads((od/"RESULT.json").read_text())
 b=json.loads((bd/"RESULT.json").read_text())
 h=json.loads((hd/"RESULT.json").read_text())
 assert r["status"]=="CODEQL_SCAN_COMPLETE" and r["baseline_total"]==baseline and r["historical_p1_total"]==p1after and r["new_vs_baseline"]==new
 assert all(r["checks"][x]["exit"]==0 for x in ("version","apply_check","apply","create","analyze"))
 assert digest(od/"after.sarif")==r["after_sarif_sha256"]
 assert digest(bd/"baseline.sarif")==b["sarif_sha256"]
 assert digest(hd/"after.sarif")==h["after_sarif_sha256"]
 assert digest(od/f"PATCH_ARCHGEN_{cid}_R1.patch")==r["patch_sha256"]
 assert digest(od/f"IMPLEMENTATION_PROMPT_ARCHGEN_{cid}_R1.md")==r["prompt_sha256"]
 assert digest(od/f"RECEIPT_ARCHGEN_{cid}_R1.json")==r["receipt_sha256"]
 frozen=F/(run+".zip")
 assert digest(frozen)==r["source_zip_sha256"]
 sources[f"FROZEN_INPUT/{cid}/{run}.zip"]=frozen
 for base,folderpath,names in [
   (f"SCANNED_{cid}",od,["RESULT.json","warning_delta.json","after.sarif",f"PATCH_ARCHGEN_{cid}_R1.patch",
       f"IMPLEMENTATION_PROMPT_ARCHGEN_{cid}_R1.md",f"RECEIPT_ARCHGEN_{cid}_R1.json",
       "apply.log","apply_check.log","version.log","create.log","analyze.log"]),
   (f"BASELINE_{cid}",bd,["RESULT.json","baseline.sarif"]),
   (f"HISTORICAL_P1_{cid}",hd,["RESULT.json","after.sarif"])
 ]:
  for name in names:
   path=folderpath/name
   assert path.is_file(),path
   items[f"{base}/{name}"]=path
 meta[cid]={"run_id":r["run_id"],"source_kind":r["source_kind"],
    "baseline_total":baseline,"historical_p1_total":p1after,"historical_p1_new":r["historical_p1_new"],
    "after_total":r["after_total"],"new_vs_baseline":new,
    "rule_breakdown":r["new_by_rule"],"native_functionality":"NOT_VERIFIED",
    "prompt_sha256":r["prompt_sha256"],"patch_sha256":r["patch_sha256"],
    "receipt_sha256":r["receipt_sha256"],"after_sarif_sha256":r["after_sarif_sha256"],
    "source_zip_sha256":r["source_zip_sha256"]}
for filename in ["evaluate.py","evaluate_verified.py","evaluate_03581_v4.py",
                 "scan_08152.sbatch","scan_12344.sbatch","scan_03581_v4.sbatch",
                 "ingest_master.py","ingest_master.sbatch","MASTER_INGEST_RESULT.json"]:
 path=D/filename
 if path.exists():items["REPRODUCIBILITY/"+filename]=path
for filename in ["RESULT.json","create.log"]:
 path=D/"results_03581"/filename
 if path.exists():items["FAILED_INFRASTRUCTURE_03581/"+filename]=path
report={
 "experiment":"GASP general architecture, remaining original seven cases",
 "comparison":"CodeQL 2.25.6 javascript-security-extended, multiset of (ruleId,path,normalized message)",
 "generated_utc":datetime.now(timezone.utc).isoformat(),
 "new_runs":meta,"source_provenance":"Frozen original pre-patch ZIP, all SHA-256 checked",
 "limitations":["The cases were previously investigated and are not blinded held-outs",
                "Three cases were implemented in the same agent chat, allowing cross-case information leakage",
                "Static-analysis warning deltas do not prove real vulnerabilities or actual security fixes",
                "Native Windows BYOK tests, live Telegram tests, and complete commentary workflow tests are not verified",
                "03581 had earlier infrastructure retries; successful scan used the original unchanged patch",
                "12344 uses a FILTERED_SOURCE_PROVISIONAL snapshot"],
 "gasp_all_seven":[{"case":"03429","new":0,"historical_p1_new":1},
                  {"case":"03581","new":3,"historical_p1_new":2},
                  {"case":"08152","new":1,"historical_p1_new":1},
                  {"case":"12344","new":5,"historical_p1_new":5},
                  {"case":"22223","new":0,"historical_p1_new":3},
                  {"case":"31207","new":1,"historical_p1_new":1},
                  {"case":"32759","new":1,"historical_p1_new":2}]
}
summarypath=D/"ARCHGEN_LAST3_SUMMARY.json"
assert not summarypath.exists()
summarypath.write_text(json.dumps(report,indent=2)+"\n")
items["SUMMARY.json"]=summarypath
def make_zip(name,with_sources):
 dest=D/name;assert not dest.exists()
 all_files=dict(items)
 if with_sources:all_files.update(sources)
 manifest={"generated_utc":report["generated_utc"],"sha256_algorithm":"SHA256","files":{}}
 for k,path in sorted(all_files.items()):
  manifest["files"][k]={"bytes":path.stat().st_size,"sha256":digest(path)}
 with ZipFile(dest,"x",compression=ZIP_DEFLATED,compresslevel=7) as z:
  for k,path in sorted(all_files.items()):
   z.write(path,k,compress_type=ZIP_STORED if k.startswith("FROZEN_INPUT/") else ZIP_DEFLATED)
  z.writestr("MANIFEST.json",json.dumps(manifest,indent=2)+"\n")
  z.writestr("README.txt","CodeQL 2.25.6 independent scans, unchanged agent patches. Original source is included only in the FULL archive. Results are not proof of functional correctness. 03581 infrastructure failures preserved; successful scan in SCANNED_03581.\n")
 with ZipFile(dest) as z:assert z.testzip() is None
 return {"path":str(dest.relative_to(R)),"bytes":dest.stat().st_size,"sha256":digest(dest),"entries":len(all_files)+2}
a=make_zip("ARNO_ARCHGEN_LAST3_CODEQL_SCAN_EVIDENCE.zip",False)
b=make_zip("ARNO_ARCHGEN_LAST3_FULL_FROZEN_EVIDENCE.zip",True)
info={"status":"VERIFIED_PACKAGES","scan_only":a,"full_frozen":b}
(D/"PACKAGE_INFO.json").write_text(json.dumps(info,indent=2)+"\n")
print(json.dumps(info,indent=2),flush=True)
