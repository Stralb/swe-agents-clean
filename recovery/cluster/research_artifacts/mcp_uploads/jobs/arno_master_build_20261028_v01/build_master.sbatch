#!/bin/bash
#SBATCH --job-name=arno_master_v01
#SBATCH --partition=stampede
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G

python3 - <<'PY'
import csv, datetime, hashlib, io, json, os, shutil, sqlite3, subprocess, sys, time, zlib
from pathlib import Path

start=time.time()
home=Path.home()
root=home/"research_artifacts"
input_dir=root/"mcp_uploads/arno_master_20261028"
report_dir=root/"mcp_uploads/jobs/arno_master_build_20261028_v01"
report_dir.mkdir(parents=True, exist_ok=True)
output_dir=root/"ARNO_MASTER_DB"
output_dir.mkdir(parents=True, exist_ok=True)
target=output_dir/"ARNO_RESEARCH_MASTER.sqlite"
partial=output_dir/"ARNO_RESEARCH_MASTER.sqlite.incomplete_v01"
source=home/"new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db"
report={"version":"0.1","created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_db":str(source),"master_path":str(target),"source_immutable":True,
        "operations":[],"errors":[],"status":"STARTING"}
def checkpoint(stage, extra=None):
    report["operations"].append({"stage":stage,"seconds":round(time.time()-start,1),"details":extra})
    (report_dir/"BUILD_REPORT.json").write_text(json.dumps(report,indent=2,default=str)+"\n")
    print(stage,json.dumps(extra,default=str)[:500] if extra is not None else "",flush=True)
try:
    if target.exists() or partial.exists():
        raise FileExistsError("Refusing to overwrite existing master or incomplete copy")
    paths=[input_dir/("first122_part_"+str(i).zfill(3)+".txt") for i in range(1,42)]
    absent=[str(p) for p in paths if not p.is_file()]
    if absent:raise FileNotFoundError("Missing uploaded classification segments: "+str(absent))
    text="".join(p.read_text(encoding="utf-8") for p in paths)
    source_csv_sha=hashlib.sha256(text.encode("utf-8")).hexdigest()
    reader=csv.DictReader(io.StringIO(text))
    rows=list(reader)
    if len(rows)!=122 or len({int(x["case_id"]) for x in rows})!=122:
        raise RuntimeError("Classification transfer failed 122-case uniqueness QC")
    required=["case_id","review_number","issue_purpose","risk_first_pass","risk_final","implementation_category_final",
              "issue_instruction_specificity","pr_purpose","issue_pr_goal_alignment","risk_qc_correction","implementation_category_qc"]
    if any(f not in reader.fieldnames for f in required):
        raise RuntimeError("Missing required classification columns")
    cids=[int(x["case_id"]) for x in rows]
    checkpoint("classifications_transfer_verified",{"rows":len(rows),"source_characters":len(text),
             "csv_sha256_normalized":source_csv_sha,"columns":len(reader.fieldnames)})
    if not source.is_file():raise FileNotFoundError(str(source))
    source_size=source.stat().st_size
    if source_size!=37283119104:raise RuntimeError("Unexpected mining DB size "+str(source_size))
    ro=sqlite3.connect("file:"+str(source)+"?mode=ro",uri=True,timeout=30)
    counts={"cases":ro.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
            "scanner_findings":ro.execute("SELECT COUNT(*) FROM scanner_findings").fetchone()[0],
            "raw_positive":ro.execute("SELECT COUNT(DISTINCT case_id) FROM scanner_findings WHERE introduced=1").fetchone()[0]}
    q="SELECT id FROM cases WHERE id IN ("+",".join("?" for _ in cids)+")"
    found={x[0] for x in ro.execute(q,cids)}
    ro.close()
    if counts["cases"]!=3809 or counts["raw_positive"]!=198 or set(cids)!=found:
        raise RuntimeError("Baseline/122 membership mismatch: "+str({"counts":counts,"missing":sorted(set(cids)-found)}))
    checkpoint("source_read_only_verified",{"bytes":source_size,**counts,"first122_id_matches":122})
    stat=os.statvfs(output_dir)
    available=stat.f_bavail*stat.f_frsize
    if available<source_size+1024*1024*1024:raise RuntimeError("Less than 1GB safety headroom for master copy")
    checkpoint("source_clone_started",{"free_bytes":available})
    subprocess.run(["cp","--reflink=auto","--sparse=auto",str(source),str(partial)],check=True,timeout=2100)
    if partial.stat().st_size!=source_size:raise RuntimeError("Incomplete cloned source database")
    checkpoint("source_clone_finished",{"elapsed_s":round(time.time()-start,1),"master_bytes_pre_import":partial.stat().st_size})
    c=sqlite3.connect(str(partial),timeout=90)
    c.execute("PRAGMA busy_timeout=90000")
    c.execute("PRAGMA journal_mode=DELETE")
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript("""
CREATE TABLE arno_sources(
  source_key TEXT PRIMARY KEY, source_kind TEXT NOT NULL, label TEXT NOT NULL, source_locator TEXT NOT NULL,
  source_sha256 TEXT, embedded_encoding TEXT, embedded_bytes BLOB, verification TEXT NOT NULL, notes TEXT
);
CREATE TABLE arno_stage_ledger(
 stage_number INTEGER PRIMARY KEY, stage_name TEXT UNIQUE NOT NULL,
 status TEXT NOT NULL, detail TEXT, last_updated_utc TEXT NOT NULL
);
CREATE TABLE arno_classifications(
 case_id INTEGER PRIMARY KEY REFERENCES cases(id), review_number INTEGER UNIQUE NOT NULL,
 issue_request_summary TEXT, issue_purpose TEXT, instruction_specificity TEXT, request_scope TEXT,
 pr_stated_goal_summary TEXT, pr_purpose TEXT, goal_alignment TEXT,
 implementation_summary TEXT, implementation_first_pass TEXT, implementation_correction TEXT, implementation_final TEXT,
 risk_first_pass TEXT, risk_correction TEXT, risk_final TEXT, risk_human_review TEXT,
 agent_tool TEXT, agent_provenance TEXT,
 original_row_json TEXT NOT NULL, imported_source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
 raw_row_sha256 TEXT NOT NULL
);
CREATE TABLE arno_annotation_events(
 event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 case_id INTEGER NOT NULL REFERENCES arno_classifications(case_id),
 dimension TEXT NOT NULL, event_stage TEXT NOT NULL, label_value TEXT,
 source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
 notes TEXT, UNIQUE(case_id,dimension,event_stage)
);
CREATE TABLE arno_mechanism_selection(
 decision_id TEXT PRIMARY KEY, case_id INTEGER REFERENCES cases(id),
 producing_change_id TEXT, choice_summary TEXT, evidence_json TEXT,
 evidence_source_key TEXT REFERENCES arno_sources(source_key), coding_status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE arno_root_decisions(
 root_id TEXT PRIMARY KEY, case_id INTEGER REFERENCES cases(id),
 mechanism_decision_id TEXT REFERENCES arno_mechanism_selection(decision_id),
 producing_change_ids_json TEXT, root_coding_json TEXT,
 evidence_source_key TEXT REFERENCES arno_sources(source_key), coding_status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE arno_experiment_runs(
 run_id TEXT PRIMARY KEY, case_id INTEGER REFERENCES cases(id),
 root_id TEXT REFERENCES arno_root_decisions(root_id), experiment_family TEXT NOT NULL,
 treatment TEXT, prompt_blob BLOB, run_metadata_json TEXT, status TEXT NOT NULL
);
CREATE TABLE arno_generated_patches(
 patch_id TEXT PRIMARY KEY, run_id TEXT REFERENCES arno_experiment_runs(run_id),
 content_sha256 TEXT, patch_blob BLOB, patch_uri TEXT, authenticity_status TEXT NOT NULL,
 notes TEXT
);
CREATE TABLE arno_experiment_scans(
 scan_id TEXT PRIMARY KEY, run_id TEXT REFERENCES arno_experiment_runs(run_id),
 scanner TEXT NOT NULL, scanner_version TEXT, rule_id TEXT,
 raw_result_blob BLOB, result_json TEXT, execution_verified INTEGER NOT NULL DEFAULT 0
);
CREATE VIEW arno_v_first122 AS SELECT c.id as case_id,c.status as miner_status,
 a.issue_purpose,a.instruction_specificity,a.request_scope,a.pr_purpose,
 a.goal_alignment,a.implementation_final,a.risk_final FROM cases c
 JOIN arno_classifications a ON a.case_id=c.id;
CREATE VIEW arno_v_raw_positive198 AS SELECT c.id AS case_id,COUNT(f.id) AS introduced_finding_rows
 FROM cases c JOIN scanner_findings f ON f.case_id=c.id
 WHERE f.introduced=1 GROUP BY c.id;
""")
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    compressed=zlib.compress(text.encode("utf-8"),9)
    c.execute("INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)",
              ("first122_normalized_csv","normalized_classification_csv",
               "First 122 case classifications with frozen first pass and QC",
               "ChatGPT conversation attachment: FIRST122_CLASSIFICATIONS_WITH_FIRSTPASS_AND_QC.csv",
               source_csv_sha,"zlib/utf8",compressed,"VERIFIED_122_ROWS_38_COLUMNS",
               "CSV is normalized from 18-sheet original workbook; embedded bytes represent normalized text, not the XLSX original."))
    c.execute("INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)",
              ("first122_original_xlsx","original_workbook",
               "issue_pr_manual_evaluation_master_122(1).xlsx",
               "ChatGPT project attachment /mnt/data/issue_pr_manual_evaluation_master_122(1).xlsx",
               "490ff135700e51f654ec9c1f1ebf6f50ee38bc874fa4c67dda9798bb26af1e2f",
               None,None,"SHA256_VERIFIED_LOCAL_NOT_EMBEDDED",
               "Original 18-sheet workbook retained outside cluster until byte-level transfer; annotations already embedded as normalized CSV."))
    c.execute("INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)",
              ("miner_aug29_snapshot","baseline_sqlite","Final scanner-complete miner snapshot",
               str(source),None,None,None,"CLONED_SOURCE_FROZEN",
               "Baseline file is also on private HuggingFace at final/full3809-scanner-complete-20260829; revision 145e38bf736d5475c736ce1c78f02b4ca54306e6."))
    for row in rows:
        get=lambda key:row.get(key) or None
        cid=int(row["case_id"])
        payload=json.dumps(row,sort_keys=True,ensure_ascii=False)
        rowhash=hashlib.sha256(payload.encode("utf-8")).hexdigest()
        c.execute("""INSERT INTO arno_classifications VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
            cid,int(row["review_number"]),get("issue_request_summary"),get("issue_purpose"),
            get("issue_instruction_specificity"),get("issue_request_scope"),
            get("pr_stated_goal_summary"),get("pr_purpose"),get("issue_pr_goal_alignment"),
            get("implementation_summary"),get("implementation_category_first_pass"),
            get("implementation_category_qc"),get("implementation_category_final"),
            get("risk_first_pass"),get("risk_qc_correction"),get("risk_final"),
            get("risk_human_review"),get("agent_tool"),get("agent_provenance"),
            payload,"first122_normalized_csv",rowhash
        ))
        for dimension,origin,corrected,final in (
            ("implementation_category","implementation_category_first_pass","implementation_category_qc","implementation_category_final"),
            ("risk_assessment","risk_first_pass","risk_qc_correction","risk_final")):
            for ev,label in (("first_pass",get(origin)),("qc_correction",get(corrected)),("effective_final",get(final))):
                if ev=="qc_correction" and label is None:continue
                c.execute("INSERT INTO arno_annotation_events(case_id,dimension,event_stage,label_value,source_key,notes) VALUES(?,?,?,?,?,?)",
                          (cid,dimension,ev,label,"first122_normalized_csv",None))
    stages=[(1,"original_mining_scanners","completed","3809 cases and 198 raw positives retained in original tables"),
            (2,"first122_issue_pr_implementation_risk","completed","122 complete classifications and first-pass/QC event history"),
            (3,"new70_classifications","pending","Not yet imported; retain historical/strict-cohort distinction"),
            (4,"canonical_findings_producing_changes","pending","Await frozen mapped files"),
            (5,"implementation_mechanism_choice","pending","Await pilot/holdout decisions"),
            (6,"342_root_decisions","pending","Await final adjudicated root census"),
            (7,"matched_scanner_negative_controls","pending","Await matching crosswalk"),
            (8,"controlled_prompt_context_experiments","pending","Await actual run outputs"),
            (9,"generated_patches_and_repairs","pending","Await raw patch bundles"),
            (10,"scanner_and_functional_retests","pending","Await full run logs, SARIF, and tests")]
    c.executemany("INSERT INTO arno_stage_ledger VALUES(?,?,?,?,?)",[(n,name,status,detail,now) for n,name,status,detail in stages])
    c.commit()
    checks={
      "cases":c.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
      "first122":c.execute("SELECT COUNT(*) FROM arno_classifications").fetchone()[0],
      "first122_distinct_cases":c.execute("SELECT COUNT(DISTINCT case_id) FROM arno_classifications").fetchone()[0],
      "raw_positive":c.execute("SELECT COUNT(*) FROM arno_v_raw_positive198").fetchone()[0],
      "implementation_qc_events":c.execute("SELECT COUNT(*) FROM arno_annotation_events WHERE dimension='implementation_category' AND event_stage='qc_correction'").fetchone()[0],
      "risk_qc_events":c.execute("SELECT COUNT(*) FROM arno_annotation_events WHERE dimension='risk_assessment' AND event_stage='qc_correction'").fetchone()[0],
      "annotation_events":c.execute("SELECT COUNT(*) FROM arno_annotation_events").fetchone()[0],
      "source_csv_blob_roundtrip":hashlib.sha256(zlib.decompress(c.execute("SELECT embedded_bytes FROM arno_sources WHERE source_key='first122_normalized_csv'").fetchone()[0])).hexdigest()==source_csv_sha,
      "first122_foreign_key_errors":len(c.execute("PRAGMA foreign_key_check(arno_classifications)").fetchall()),
      "master_size_bytes":partial.stat().st_size
    }
    if checks["cases"]!=3809 or checks["first122"]!=122 or checks["raw_positive"]!=198 or not checks["source_csv_blob_roundtrip"] or checks["first122_foreign_key_errors"]!=0 or checks["risk_qc_events"]!=4 or checks["implementation_qc_events"]!=2:
        raise RuntimeError("QC mismatch "+str(checks))
    c.close()
    checkpoint("master_data_integrity_verified",checks)
    os.rename(partial,target)
    report["status"]="COMPLETE"
    report["verification"]=checks
    report["elapsed_seconds"]=round(time.time()-start,1)
    checkpoint("published_local_master",{"path":str(target),"size":target.stat().st_size})
except Exception as exc:
    report["status"]="FAILED"
    report["errors"].append(type(exc).__name__+": "+str(exc))
    checkpoint("failure")
    raise
PY