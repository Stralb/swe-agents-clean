#!/usr/bin/env python3
"""Read-only comparison of archived SCREEN65 before-SARIF candidates."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib, json, os, sqlite3, sys, zipfile

ROOT = Path.home() / "research_artifacts"
DB = ROOT / "ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ARCHIVE = ROOT / "ARNO_CODEQL_EXPORT_20261019/05_SCREEN65_EVIDENCE.zip"
OUT = ROOT / "mcp_uploads/jobs/arno_20261029_sarif_crosscheck_v1/REPORT.json"

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def signatures(raw):
    obj=json.loads(raw)
    runs=obj.get("runs",[])
    complete=Counter()
    spatial=Counter()
    rules=Counter()
    features=[]
    for run in runs:
        driver=run.get("tool",{}).get("driver",{})
        features.append({
            "tool_name":driver.get("name"),
            "tool_version":driver.get("version"),
            "num_registered_rules":len(driver.get("rules",[])),
            "invocations":len(run.get("invocations",[])),
            "execution_successful": [i.get("executionSuccessful") for i in run.get("invocations",[])],
        })
        for result in run.get("results",[]):
            rule=result.get("ruleId","")
            pl=result.get("locations", [{}])[0].get("physicalLocation",{})
            uri=pl.get("artifactLocation",{}).get("uri","")
            reg=pl.get("region",{})
            line=reg.get("startLine")
            col=reg.get("startColumn")
            message=result.get("message",{}).get("text","")
            rules[rule]+=1
            spatial[(rule,uri,line,col)]+=1
            complete[(rule,uri,line,col,message)]+=1
    return {"features":features,"results":sum(rules.values()),"rules":rules,"spatial":spatial,"complete":complete}

def hash_counter(c):
    serial=json.dumps(sorted([{"sig":list(k) if isinstance(k,tuple) else k,"n":v} for k,v in c.items()],key=lambda x:str(x["sig"])),sort_keys=True,ensure_ascii=False,default=str).encode("utf8")
    return digest(serial)

def main():
    if not DB.is_file() or not ARCHIVE.is_file():
        raise RuntimeError("Required frozen source not available")
    c=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
    c.execute("PRAGMA query_only=ON")
    rows=c.execute("SELECT case_id,wave,zip_member_path,original_bytes,sha256,comparability_status FROM arno_screen65_before_sarif_candidates_20261029 ORDER BY case_id,wave").fetchall()
    c.close()
    bycase={}
    with zipfile.ZipFile(ARCHIVE,"r") as z:
        names=set(z.namelist())
        for case_id,wave,member,original_bytes,expected,old_status in rows:
            if member not in names:
                raise RuntimeError("Missing frozen member: "+member)
            raw=z.read(member)
            if len(raw)!=original_bytes or digest(raw)!=expected:
                raise RuntimeError("Frozen hash/length mismatch case "+str(case_id)+" "+wave)
            parsed=signatures(raw)
            bycase.setdefault(case_id,{})[wave]={
                "sha256":digest(raw),"bytes":len(raw),"result_count":parsed["results"],
                "rules":sorted(parsed["rules"].items()),
                "features":parsed["features"],
                "complete_hash":hash_counter(parsed["complete"]),
                "spatial_hash":hash_counter(parsed["spatial"]),
                "_spatial":parsed["spatial"],"_complete":parsed["complete"]
            }
        available_case_archives={str(cid):[n for n in names if n.endswith("/CASE_%05d.zip"%cid) or n.endswith("CASE_%05d.zip"%cid)] for cid in bycase}
    result=[]
    for case_id, versions in sorted(bycase.items()):
        a=versions["SCREEN65_FIRST"]
        b=versions["SCREEN65_SECOND"]
        shared=sum((a["_spatial"] & b["_spatial"]).values())
        total_first=sum(a["_spatial"].values())
        total_second=sum(b["_spatial"].values())
        result.append({
            "case_id":case_id,
            "same_result_count":total_first==total_second,
            "same_rules":a["rules"]==b["rules"],
            "same_primary_locations":a["spatial_hash"]==b["spatial_hash"],
            "same_primary_location_and_message":a["complete_hash"]==b["complete_hash"],
            "shared_primary_location_count":shared,
            "first_count":total_first,"second_count":total_second,
            "first_sha256":a["sha256"],"second_sha256":b["sha256"],
            "first_run_metadata":a["features"],"second_run_metadata":b["features"],
            "nearby_case_snapshot_members":available_case_archives[str(case_id)],
        })
    report={
        "status":"READ_ONLY_SCREEN65_TWO_WAVE_COMPARISON",
        "date_utc":datetime.now(timezone.utc).isoformat(),
        "source_archive":str(ARCHIVE),
        "case_count":len(result),"candidate_count":len(rows),
        "all_archive_hashes_verified":True,
        "identical_result_counts":sum(x["same_result_count"] for x in result),
        "identical_rule_counts":sum(x["same_rules"] for x in result),
        "identical_primary_locations":sum(x["same_primary_locations"] for x in result),
        "identical_primary_location_and_message":sum(x["same_primary_location_and_message"] for x in result),
        "case_comparisons":result,
        "critical_limit":"Comparing two earlier SCREEN65 wave SARIFs does not establish equivalence to OWP14 historical base repository or scanner configuration. Never promote these files to exact OWP baselines based on this report."
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    if OUT.exists():
        raise RuntimeError("Refusing overwrite of existing report")
    with OUT.open("x",encoding="utf8") as f:
        json.dump(report,f,indent=2,sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k!="case_comparisons"},sort_keys=True))
if __name__=="__main__":
    main()
