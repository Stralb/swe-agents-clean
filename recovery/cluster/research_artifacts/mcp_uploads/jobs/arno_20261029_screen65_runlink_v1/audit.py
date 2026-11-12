#!/usr/bin/env python3
"""Read-only audit of two SCREEN65 scan-run RESULT records per OWP case."""
from pathlib import Path
from datetime import datetime,timezone
import json,sqlite3

R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
SCANBASE=R/"prevention_pilot_phase2"
REPORT=R/"mcp_uploads/jobs/arno_20261029_screen65_runlink_v1/REPORT.json"
PREV=R/"mcp_uploads/jobs/arno_20261029_sarif_crosscheck_v1/REPORT.json"
EXPECTED_SUITE="codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"

def main():
    prev=json.loads(PREV.read_text())
    bycid={x["case_id"]:x for x in prev["case_comparisons"]}
    con=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
    con.execute("PRAGMA query_only=ON")
    expected={
        r[0]:(r[1],r[2]) for r in con.execute(
            "SELECT e.case_id,e.repo_member_count,p.source_type FROM arno_owp14_input_repo_equivalence_20261029 e "
            "JOIN arno_owp14_original_input_packet_inventory_20261029 p ON p.case_id=e.case_id AND p.arm='O' ORDER BY e.case_id"
        )
    }
    con.close()
    results=[]
    waves=[("SCREEN65_FIRST","screen65_codeql_job70675"),("SCREEN65_SECOND","screen65_second_codeql_job70782")]
    for cid, (expected_files,expected_type) in sorted(expected.items()):
        row={"case_id":cid,"expected_repo_files":expected_files,"expected_source_type":expected_type,"waves":[]}
        for label, job in waves:
            source=SCANBASE/job/("CASE_%05d"%cid)/"RESULT.json"
            entry={"wave":label,"file_found":source.is_file()}
            if source.is_file():
                obj=json.loads(source.read_text())
                checks=obj.get("checks",{})
                rc={k:(v.get("rc") if isinstance(v,dict) else None) for k,v in checks.items()}
                before_count=obj.get("findings",{}).get("before_total")
                expected_sarif=bycid[cid]["first_count" if label=="SCREEN65_FIRST" else "second_count"]
                entry.update({
                    "case_id_matches":obj.get("case_id")==cid,
                    "source_type_matches":obj.get("source_type")==expected_type,
                    "source_files_match":obj.get("source_files")==expected_files,
                    "suite_matches_expected":obj.get("suite")==EXPECTED_SUITE,
                    "stage_complete":obj.get("stage")=="SCAN_COMPLETE",
                    "before_database_success":rc.get("database_before")==0,
                    "before_analysis_success":rc.get("analyze_before")==0,
                    "after_database_success":rc.get("database_after")==0,
                    "after_analysis_success":rc.get("analyze_after")==0,
                    "result_before_count_matches_archived_sarif":before_count==expected_sarif,
                    "before_result_count":before_count,
                })
            row["waves"].append(entry)
        results.append(row)
    predicates=["file_found","case_id_matches","source_type_matches","source_files_match","suite_matches_expected","stage_complete","before_database_success","before_analysis_success","after_database_success","after_analysis_success","result_before_count_matches_archived_sarif"]
    flat=[w for x in results for w in x["waves"]]
    summary={k:sum(bool(w.get(k)) for w in flat) for k in predicates}
    out={
        "status":"SCREEN65_SCAN_RUN_METADATA_CROSSCHECK",
        "utc":datetime.now(timezone.utc).isoformat(),
        "cases":len(results),
        "scan_runs":len(flat),
        "checks_passed_counts":summary,
        "per_case":results,
        "limit":"Equal case packet content, scanner suite, source_file counts, successful runs and scanner outputs do not alone establish the exact source snapshot used for each prior SARIF; no original OWP14 baseline identity is assumed."
    }
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    with REPORT.open("x") as f:json.dump(out,f,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k!="per_case"},sort_keys=True))
if __name__=="__main__":main()
