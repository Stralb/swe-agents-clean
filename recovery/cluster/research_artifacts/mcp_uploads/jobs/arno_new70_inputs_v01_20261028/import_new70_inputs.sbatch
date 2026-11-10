#!/bin/bash
#SBATCH --job-name=arno_new70_inputs
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
python3 - <<'PY'
import csv,datetime,hashlib,io,json,sqlite3,zlib
from pathlib import Path
root=Path.home()/"research_artifacts"
source_dir=root/"new70_frozen_methodology_20260829T091932Z"
master=root/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
out=root/"mcp_uploads/jobs/arno_new70_inputs_v01_20261028"
out.mkdir(parents=True,exist_ok=True)
paths={
"new70_case_mapping":source_dir/"90_LOCKED_FOR_LATER/case_mapping_FULL_NEW70.csv",
"new70_blind_issue_source":source_dir/"01_ISSUE_PASS1_BLIND/Blind_Issue_Source_NEW70.csv",
"new70_blind_pr_source":source_dir/"02_PR_PASS1_BLIND/Blind_PR_Source_NEW70.csv",
"new70_stage4b_evidence_index":source_dir/"03_STAGE4B_BLIND/stage4b_blind_evaluation_index_NEW70.csv"
}
report={"stage":"NEW70 source-input integration, not final classifications","status":"STARTED","source_paths":{k:str(v) for k,v in paths.items()}}
try:
    contents={k:p.read_bytes() for k,p in paths.items()}
    def rows(name):
      return list(csv.DictReader(io.StringIO(contents[name].decode("utf-8-sig"))))
    sets={name:rows(name) for name in paths}
    mapping={int(r["case_id"]):r for r in sets["new70_case_mapping"]}
    issues={int(r["Case ID"]):r for r in sets["new70_blind_issue_source"]}
    prs={int(r["Case ID"]):r for r in sets["new70_blind_pr_source"]}
    stage4={int(r["Case ID"]):r for r in sets["new70_stage4b_evidence_index"]}
    if not (len(mapping)==len(issues)==len(prs)==len(stage4)==70 and
            set(mapping)==set(issues)==set(prs)==set(stage4)):
       raise ValueError("Cohort mismatch across 4 source files")
    for case,r in mapping.items():
      if int(r["pr_id"])!=int(stage4[case]["PR ID"]):raise ValueError("PR mismatch "+str(case))
      if str(r["review_number"])!=str(issues[case]["Review #"]) or str(r["review_number"])!=str(prs[case]["Review #"]):
        raise ValueError("Review no. mismatch "+str(case))
    con=sqlite3.connect(str(master),timeout=45)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=45000")
    if con.execute("SELECT COUNT(*) FROM arno_classifications").fetchone()[0]!=122:raise ValueError("First cohort was modified")
    if con.execute("SELECT COUNT(*) FROM arno_excluded_cases").fetchone()[0]!=16:raise ValueError("Exclusion ledger not committed")
    missing=set(mapping)-{r[0] for r in con.execute("SELECT id FROM cases")}
    if missing:raise ValueError("NEW70 case IDs absent from baseline: "+str(sorted(missing)))
    overlap=set(mapping)&{r[0] for r in con.execute("SELECT case_id FROM arno_classifications")}
    if overlap:raise ValueError("NEW70 and FIRST122 overlap: "+str(sorted(overlap)))
    promoted={r[0] for r in con.execute("SELECT DISTINCT case_id FROM scanner_findings WHERE introduced=1")}
    if len(set(mapping)&promoted)!=60:raise ValueError("Expected 60 promoted NEW70")
    con.execute("BEGIN IMMEDIATE")
    con.executescript("""
CREATE TABLE arno_new70_source_inputs(
 case_id INTEGER PRIMARY KEY REFERENCES cases(id),
 pr_id INTEGER NOT NULL REFERENCES pull_requests(id),
 review_number INTEGER NOT NULL UNIQUE,
 issue_title TEXT, issue_body TEXT, pr_title TEXT, pr_body TEXT,
 case_mapping_json TEXT NOT NULL,
 blind_issue_source_json TEXT NOT NULL,
 blind_pr_source_json TEXT NOT NULL,
 stage4b_index_json TEXT NOT NULL,
 stage4b_evidence_filename TEXT,
 stage4b_evidence_completeness TEXT,
 raw_promoted_finding_eligible INTEGER NOT NULL CHECK(raw_promoted_finding_eligible IN (0,1)),
 classification_import_status TEXT NOT NULL DEFAULT 'SOURCE_ONLY',
 source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
);
""")
    for name,raw in contents.items():
      sha=hashlib.sha256(raw).hexdigest()
      con.execute("INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)",(
        name,"frozen_new70_input",name,str(paths[name]),sha,
        "zlib/bytes",zlib.compress(raw,9),"SOURCE_FILE_VERIFIED",
        "This is raw/frozen input, not final classification output"
      ))
    for case,r in mapping.items():
      ix=stage4[case]
      con.execute("""INSERT INTO arno_new70_source_inputs
       (case_id,pr_id,review_number,issue_title,issue_body,pr_title,pr_body,case_mapping_json,
       blind_issue_source_json,blind_pr_source_json,stage4b_index_json,
       stage4b_evidence_filename,stage4b_evidence_completeness,raw_promoted_finding_eligible,
       classification_import_status,source_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
        case,int(r["pr_id"]),int(r["review_number"]),r["issue_title"],r["issue_body"],r["pr_title"],r["pr_body"],
        json.dumps(r,ensure_ascii=False,sort_keys=True),
        json.dumps(issues[case],ensure_ascii=False,sort_keys=True),
        json.dumps(prs[case],ensure_ascii=False,sort_keys=True),
        json.dumps(ix,ensure_ascii=False,sort_keys=True),
        ix["Blind Evidence File"],ix["Stage4B Evidence Completeness"],int(case in promoted),
        "SOURCE_ONLY","new70_case_mapping"))
      con.execute("INSERT INTO arno_cohort_membership VALUES(?,?,?,?)",(case,"new70_historical_frozen","HISTORICAL_NEW70","new70_case_mapping"))
      if case not in promoted:
        con.execute("INSERT INTO arno_cohort_membership VALUES(?,?,?,?)",(case,"new70_unpromoted_low_confidence10","UNPROMOTED_SEMGREP_AUDIT","new70_case_mapping"))
    con.execute("UPDATE arno_stage_ledger SET status='partial', detail='70 frozen source inputs and Stage4B index integrated; original final 70 classification labels not yet located',last_updated_utc=? WHERE stage_number=3",
                (datetime.datetime.now(datetime.timezone.utc).isoformat(),))
    con.commit()
    report["counts"]={
      "new70_source_rows":con.execute("SELECT COUNT(*) FROM arno_new70_source_inputs").fetchone()[0],
      "new70_promoted":con.execute("SELECT SUM(raw_promoted_finding_eligible) FROM arno_new70_source_inputs").fetchone()[0],
      "new70_nonpromoted":con.execute("SELECT COUNT(*) FROM arno_new70_source_inputs WHERE raw_promoted_finding_eligible=0").fetchone()[0],
      "first122_unchanged":con.execute("SELECT COUNT(*) FROM arno_classifications").fetchone()[0],
      "excluded16_unchanged":con.execute("SELECT COUNT(*) FROM arno_excluded_cases").fetchone()[0]
    }
    report["embedded_source_sha256"]={key:hashlib.sha256(zlib.decompress(con.execute("SELECT embedded_bytes FROM arno_sources WHERE source_key=?",(key,)).fetchone()[0])).hexdigest() for key in paths}
    report["expected_source_sha256"]={key:hashlib.sha256(raw).hexdigest() for key,raw in contents.items()}
    report["fast_fk_check"]=len(con.execute("PRAGMA foreign_key_check(arno_new70_source_inputs)").fetchall())
    con.close()
    if report["counts"]!={"new70_source_rows":70,"new70_promoted":60,"new70_nonpromoted":10,
                          "first122_unchanged":122,"excluded16_unchanged":16}:
      raise ValueError("Unexpected post-import counts")
    if report["embedded_source_sha256"]!=report["expected_source_sha256"] or report["fast_fk_check"]!=0:
      raise ValueError("Source integrity check failed")
    report["status"]="COMPLETE"
except Exception as e:
    report["status"]="FAILED";report["error"]=type(e).__name__+": "+str(e)
    raise
finally:
    (out/"NEW70_SOURCE_IMPORT_REPORT.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
PY