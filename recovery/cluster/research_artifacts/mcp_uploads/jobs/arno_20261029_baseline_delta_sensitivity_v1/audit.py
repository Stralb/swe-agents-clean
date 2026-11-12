#!/usr/bin/env python3
"""Read-only sensitivity: SCREEN65 before SARIFs versus 40 archived OWP after scans.
This is not a claim that SCREEN65 was the original OWP scan baseline.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,sqlite3,zipfile

R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
ZPATH=R/"ARNO_CODEQL_EXPORT_20261019/05_SCREEN65_EVIDENCE.zip"
OUT=R/"mcp_uploads/jobs/arno_20261029_baseline_delta_sensitivity_v1/REPORT.json"

def get_results(raw):
    obj=json.loads(raw)
    output=[]
    for run in obj.get("runs",[]):
        output.extend(run.get("results",[]))
    return output

def sig(result,mode):
    rule=result.get("ruleId") or ""
    p=(result.get("locations") or [{}])[0].get("physicalLocation",{})
    uri=p.get("artifactLocation",{}).get("uri","")
    reg=p.get("region",{})
    line=reg.get("startLine")
    col=reg.get("startColumn")
    msg=result.get("message",{}).get("text","")
    if mode=="strict":
        return (rule,uri,line,col,msg)
    if mode=="location":
        return (rule,uri,line,col)
    if mode=="path_message":
        return (rule,uri,msg)
    if mode=="path_rule":
        return (rule,uri)
    raise ValueError(mode)

def compare(before,after,mode):
    a=Counter(sig(x,mode) for x in before)
    b=Counter(sig(x,mode) for x in after)
    return b-a

def main():
    con=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=120)
    con.execute("PRAGMA query_only=ON")
    base=con.execute("SELECT case_id,wave,zip_member_path,sha256 FROM arno_screen65_before_sarif_candidates_20261029").fetchall()
    rows=con.execute("""
        SELECT r.case_id,r.treatment,s.raw_result_blob,s.rule_id,
               h.new_strong_count,h.target_new_strong,r.run_metadata_json
        FROM arno_experiment_runs r
        JOIN arno_experiment_scans s ON s.run_id=r.run_id
        JOIN arno_rq3_owp14_run_scans h
          ON h.case_id=r.case_id AND h.arm=r.treatment
        ORDER BY r.case_id,r.treatment
    """).fetchall()
    con.close()
    bs={}
    with zipfile.ZipFile(ZPATH,"r") as z:
        for cid,wave,member,expected_sha in base:
            raw=z.read(member)
            if hashlib.sha256(raw).hexdigest()!=expected_sha:
                raise RuntimeError("Baseline candidate digest mismatch "+str(cid)+wave)
            bs.setdefault(cid,{})[wave]=get_results(raw)
    if len(rows)!=40 or len(bs)!=14:
        raise RuntimeError("Unexpected frozen cohort size")

    details=[]
    for cid,arm,after_blob,target_rule,archived_total,archived_target,metadata_json in rows:
        metadata=json.loads(metadata_json)
        actual_sha=hashlib.sha256(after_blob).hexdigest()
        if metadata.get("sarif_sha256")!=actual_sha:
            raise RuntimeError("After SARIF hash mismatch "+str(cid)+" "+arm)
        after=get_results(after_blob)
        per={}
        for wave,before in bs[cid].items():
            types={}
            for mode in ("strict","location","path_message","path_rule"):
                delta=compare(before,after,mode)
                types[mode]={
                    "introduced_total":sum(delta.values()),
                    "introduced_target":sum(n for k,n in delta.items() if k[0]==target_rule),
                }
            per[wave]={"before_count":len(before),"after_count":len(after),"delta":types}
        same_wave=per["SCREEN65_FIRST"]==per["SCREEN65_SECOND"]
        strong=per["SCREEN65_FIRST"]["delta"]["strict"]
        details.append({
            "case_id":cid,"arm":arm,"target_rule":target_rule,
            "recorded_new_strong_count":archived_total,
            "recorded_target_new_strong":archived_target,
            "identical_reconstructed_deltas_across_earlier_waves":same_wave,
            "strict_total_matches_archived":strong["introduced_total"]==archived_total,
            "strict_target_matches_archived":strong["introduced_target"]==archived_target,
            "candidate_baseline_comparisons":per,
        })
    report={
        "status":"READ_ONLY_CANDIDATE_BASELINE_DELTA_SENSITIVITY",
        "date_utc":datetime.now(timezone.utc).isoformat(),
        "archived_owp_after_runs":len(details),
        "all_after_sarif_hashes_verified":True,
        "identical_candidate_wave_deltas":sum(x["identical_reconstructed_deltas_across_earlier_waves"] for x in details),
        "strict_total_match_count":sum(x["strict_total_matches_archived"] for x in details),
        "strict_target_match_count":sum(x["strict_target_matches_archived"] for x in details),
        "rows":details,
        "critical_limit":"These are retrospective alert-delta sensitivity calculations against SCREEN65 earlier before-SARIF candidates. They do not prove that these were original OWP14 baselines, that generated patches passed functional tests, or that alerts represent exploitable vulnerabilities."
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("x",encoding="utf8") as f:
        json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!="rows"},sort_keys=True))
if __name__=="__main__":main()
