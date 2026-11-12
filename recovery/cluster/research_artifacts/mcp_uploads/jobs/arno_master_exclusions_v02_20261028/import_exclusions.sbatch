#!/bin/bash
#SBATCH --job-name=arno_exclusions_v01
#SBATCH --partition=stampede
#SBATCH --time=00:06:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
python3 - <<'PY'
import csv,datetime,hashlib,json,sqlite3,zlib
from pathlib import Path
root=Path.home()/"research_artifacts"
db=root/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
inp=root/"mcp_uploads/arno_master_20261028/excluded16_frozen.csv"
out=root/"mcp_uploads/jobs/arno_master_exclusions_v02_20261028"
out.mkdir(parents=True,exist_ok=True)
report={"step":"Import original first-cohort 16 exclusion decisions","source":str(inp),"db":str(db),"status":"STARTED"}
try:
    raw=inp.read_bytes()
    records=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    ids=[int(x["Case ID"]) for x in records]
    if len(records)!=16 or len(set(ids))!=16:raise ValueError("Expected 16 unique exclusions")
    if not all(x["Verdict"] in ("NO_LONGER_POSITIVE","NO_ATTRIBUTABLE_INTRODUCED_FINDING") for x in records):raise ValueError("Unexpected verdict")
    h=hashlib.sha256(raw).hexdigest()
    con=sqlite3.connect(str(db),timeout=35)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=35000")
    if con.execute("SELECT COUNT(*) FROM arno_classifications").fetchone()[0]!=122:raise ValueError("First122 not preserved")
    positive={x[0] for x in con.execute("SELECT DISTINCT case_id FROM scanner_findings WHERE introduced=1")}
    first={x[0] for x in con.execute("SELECT case_id FROM arno_classifications")}
    allcases={x[0] for x in con.execute("SELECT id FROM cases")}
    if len(positive)!=198 or not set(ids).issubset(positive) or not set(ids).isdisjoint(first) or not set(ids).issubset(allcases):raise ValueError("Cohort/ID mismatch")
    cur=con.cursor()
    cur.execute("BEGIN IMMEDIATE")
    cur.execute("""CREATE TABLE arno_excluded_cases(
        case_id INTEGER PRIMARY KEY REFERENCES cases(id),
        repository TEXT, pr_number INTEGER, validation_type TEXT,
        historical_verdict TEXT NOT NULL, old_finding_count INTEGER,
        corrected_finding_count INTEGER, exclusion_reason TEXT NOT NULL,
        original_row_json TEXT NOT NULL, source_key TEXT NOT NULL REFERENCES arno_sources(source_key)
    )""")
    cur.execute("""CREATE TABLE arno_cohort_membership(
        case_id INTEGER NOT NULL REFERENCES cases(id),
        cohort_key TEXT NOT NULL, membership_label TEXT NOT NULL,
        source_key TEXT NOT NULL REFERENCES arno_sources(source_key),
        PRIMARY KEY(case_id,cohort_key)
    )""")
    cur.execute("INSERT INTO arno_sources VALUES(?,?,?,?,?,?,?,?,?)",(
        "first122_excluded16_frozen","original_workbook_sheet_csv",
        "Excluded_16 frozen worksheet, 16 historical raw positives subsequently excluded",
        "issue_pr_manual_evaluation_master_122(1).xlsx / Excluded_16",
        h,"zlib/bytes",zlib.compress(raw,9),"VERIFIED_16_ROWS",
        "Original exclusions remain distinct from raw scanner_findings and never overwrite introduced flags."
    ))
    for x in records:
      cur.execute("INSERT INTO arno_excluded_cases VALUES(?,?,?,?,?,?,?,?,?,?)",(
        int(x["Case ID"]),x["Repository"],int(x["PR #"]),x["Validation Type"],
        x["Verdict"],int(x["Old Finding Count"]),int(x["Corrected Finding Count"]),
        x["Reason"],json.dumps(x,ensure_ascii=False,sort_keys=True),"first122_excluded16_frozen"))
    for case in sorted(positive):
        cur.execute("INSERT INTO arno_cohort_membership VALUES(?,?,?,?)",(case,"raw_scanner_positive_198","RAW_INTRODUCED_1","miner_aug29_snapshot"))
    for case in sorted(first):
        cur.execute("INSERT INTO arno_cohort_membership VALUES(?,?,?,?)",(case,"first122_frozen_active","ORIGINAL_VALIDATED_ACTIVE","first122_normalized_csv"))
    for case in sorted(ids):
        cur.execute("INSERT INTO arno_cohort_membership VALUES(?,?,?,?)",(case,"first122_excluded16","HISTORICAL_EXCLUDED_REVALIDATED","first122_excluded16_frozen"))
    cur.execute("UPDATE arno_stage_ledger SET detail=detail||'; 16 frozen exclusions and raw-198 membership mapped' WHERE stage_number=2")
    con.commit()
    report["counts"]={t:con.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in ["arno_classifications","arno_excluded_cases","arno_cohort_membership"]}
    report["by_cohort"]=dict(con.execute("SELECT cohort_key,COUNT(*) FROM arno_cohort_membership GROUP BY cohort_key"))
    report["verdict_counts"]={v:sum(x["Verdict"]==v for x in records) for v in ("NO_LONGER_POSITIVE","NO_ATTRIBUTABLE_INTRODUCED_FINDING")}
    report["source_sha256"]=h
    report["source_embedded_and_verified"]=hashlib.sha256(zlib.decompress(con.execute("SELECT embedded_bytes FROM arno_sources WHERE source_key='first122_excluded16_frozen'").fetchone()[0])).hexdigest()==h
    report["foreign_key_violations"]=len(con.execute("PRAGMA foreign_key_check").fetchall())
    con.close()
    if not report["source_embedded_and_verified"] or report["foreign_key_violations"]:raise RuntimeError("Integrity failure")
    report["status"]="COMPLETE"
except Exception as ex:
    report["status"]="FAILED"; report["error"]=type(ex).__name__+": "+str(ex)
    raise
finally:
    (out/"IMPORT_EXCLUSIONS_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2),flush=True)
PY