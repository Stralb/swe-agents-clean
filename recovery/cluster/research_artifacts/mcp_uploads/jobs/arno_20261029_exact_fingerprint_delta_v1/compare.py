#!/usr/bin/env python3
"""Reproduce frozen SCREEN65 strong/weak alert matcher for 40 archived OWP after-SARIFs.
Uses before-SARIF candidates only, never calls them original OWP14 baselines.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,sqlite3,zipfile

R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ZIP=R/"ARNO_CODEQL_EXPORT_20261019/05_SCREEN65_EVIDENCE.zip"
OUT=R/"mcp_uploads/jobs/arno_20261029_exact_fingerprint_delta_v1/REPORT.json"

def rows(raw):
    data=json.loads(raw)
    result=[]
    for run in data.get("runs",[]):
        for it in run.get("results",[]):
            loc=(it.get("locations") or [{}])[0].get("physicalLocation",{})
            result.append({
                "rule":it.get("ruleId",""),
                "path":loc.get("artifactLocation",{}).get("uri",""),
                "line":loc.get("region",{}).get("startLine"),
                "message":it.get("message",{}).get("text",""),
                "fingerprints":it.get("partialFingerprints") or {}
            })
    return result

def match_key(v,method):
    if method=="strong":
        return (v["rule"],v["path"],v["fingerprints"].get("primaryLocationLineHash") or v["message"],v["fingerprints"].get("primaryLocationStartColumnFingerprint") or "")
    return (v["rule"],v["path"],v["message"])

def new_findings(before,after,method):
    counted=Counter(map(lambda v:match_key(v,method),before))
    added=[]
    for v in after:
        k=match_key(v,method)
        if counted[k]:counted[k]-=1
        else:added.append(v)
    return added

def main():
    conn=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=120)
    conn.execute("PRAGMA query_only=ON")
    before_refs=conn.execute("SELECT case_id,wave,zip_member_path,sha256 FROM arno_screen65_before_sarif_candidates_20261029").fetchall()
    after_refs=conn.execute("""
       SELECT r.case_id,r.treatment,s.raw_result_blob,s.rule_id,
              h.new_strong_count,h.new_conservative_count,h.target_new_strong,r.run_metadata_json
       FROM arno_experiment_runs r
       JOIN arno_experiment_scans s ON s.run_id=r.run_id
       JOIN arno_rq3_owp14_run_scans h ON h.case_id=r.case_id AND h.arm=r.treatment
       ORDER BY r.case_id,r.treatment
    """).fetchall()
    conn.close()
    before={}
    with zipfile.ZipFile(ZIP,"r") as z:
        for cid,wave,member,expected in before_refs:
            blob=z.read(member)
            if hashlib.sha256(blob).hexdigest()!=expected:
                raise RuntimeError("Frozen before SARIF digest mismatch")
            before.setdefault(cid,{})[wave]=rows(blob)
    results=[]
    for cid,arm,blob,rule,expected_strong,expected_weak,expected_target,metadata_raw in after_refs:
        metadata=json.loads(metadata_raw)
        if hashlib.sha256(blob).hexdigest()!=metadata.get("sarif_sha256"):
            raise RuntimeError("Frozen after SARIF digest mismatch")
        after=rows(blob)
        versions={}
        for wave,pre in before[cid].items():
            x=new_findings(pre,after,"strong")
            y=new_findings(pre,after,"weak")
            versions[wave]={
                "strong_count":len(x),
                "weak_count":len(y),
                "target_strong_count":sum(v["rule"]==rule for v in x),
                "target_weak_count":sum(v["rule"]==rule for v in y),
            }
        first=versions["SCREEN65_FIRST"]
        results.append({
            "case_id":cid,"arm":arm,"target_rule":rule,
            "recorded_strong":expected_strong,"recorded_weak":expected_weak,
            "recorded_target_strong":expected_target,
            "identical_across_baseline_waves":versions["SCREEN65_FIRST"]==versions["SCREEN65_SECOND"],
            "strong_match":first["strong_count"]==expected_strong,
            "weak_match":first["weak_count"]==expected_weak,
            "target_strong_match":first["target_strong_count"]==expected_target,
            "reconstructed":versions,
        })
    out={
        "status":"FROZEN_SCREEN65_FINGERPRINT_MATCHER_APPLIED_TO_OWP_ARCHIVES",
        "utc":datetime.now(timezone.utc).isoformat(),
        "runs":len(results),
        "same_across_earlier_baseline_waves":sum(x["identical_across_baseline_waves"] for x in results),
        "strong_count_matches":sum(x["strong_match"] for x in results),
        "weak_count_matches":sum(x["weak_match"] for x in results),
        "target_strong_matches":sum(x["target_strong_match"] for x in results),
        "differences":[x for x in results if not x["strong_match"] or not x["target_strong_match"]],
        "per_run":results,
        "method_source":"mcp_uploads/jobs/screen65_second_20261018_v1/full_codeql.sbatch, original compare() strong/weak implementation",
        "limit":"The earlier SCREEN65 before-SARIF artifacts are source-tree and scanner-suite-linked, but still not original OWP14 baseline files. Matching is a retrospective cross-wave sensitivity, not independent function/security validation."
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("x") as f:json.dump(out,f,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k not in ("per_run","differences")},sort_keys=True))
if __name__=="__main__":main()
