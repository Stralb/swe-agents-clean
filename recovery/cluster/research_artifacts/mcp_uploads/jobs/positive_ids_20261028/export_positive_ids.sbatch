#!/bin/bash
#SBATCH --job-name=arno_positive_ids
#SBATCH --partition=stampede
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
python3 - <<'PY'
import csv, datetime, hashlib, json, sqlite3
from pathlib import Path
root=Path.home()/"research_artifacts"/"mcp_uploads"/"jobs"/"positive_ids_20261028"
root.mkdir(parents=True,exist_ok=True)
db=Path.home()/"new"/"malicious-issue-miner-rate-smart"/"data"/"final-study-snapshot-20260829"/"full3809-scanner-complete-20260829.db"
if not db.is_file():
    raise FileNotFoundError(str(db))
c=sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True,timeout=30)
c.execute("PRAGMA query_only=ON")
sql="""SELECT c.id AS case_id,c.status AS miner_case_status,r.full_name AS repository,
i.number AS issue_number,i.url AS issue_url,p.number AS pr_number,p.url AS pr_url,
COUNT(sf.id) AS raw_introduced_finding_rows,
GROUP_CONCAT(DISTINCT sf.scanner) AS scanners,
GROUP_CONCAT(DISTINCT sf.finding_type) AS raw_finding_types
FROM scanner_findings sf
JOIN cases c ON c.id=sf.case_id
JOIN repos r ON r.id=c.repo_id
JOIN issues i ON i.id=c.issue_id
JOIN pull_requests p ON p.id=c.pr_id
WHERE sf.introduced=1
GROUP BY c.id,c.status,r.full_name,i.number,i.url,p.number,p.url
ORDER BY c.id"""
cur=c.execute(sql)
columns=[x[0] for x in cur.description]
rows=[dict(zip(columns,row)) for row in cur]
ids=[r["case_id"] for r in rows]
if len(ids)!=len(set(ids)):
    raise RuntimeError("Duplicate case IDs in query")
if len(rows)!=198:
    raise RuntimeError("Expected 198 rows, got "+str(len(rows)))
files=[
  ("RAW_198_SCANNER_POSITIVE_CASE_IDS.csv",["case_id"],[[i] for i in ids]),
  ("RAW_198_SCANNER_POSITIVE_CASE_DETAILS.csv",columns,[[r[k] for k in columns] for r in rows])
]
hashes={}
for name,header,data in files:
    fp=root/name
    with fp.open("x",newline="",encoding="utf-8") as handle:
        writer=csv.writer(handle)
        writer.writerow(header)
        writer.writerows(data)
    hashes[name]=hashlib.sha256(fp.read_bytes()).hexdigest()
stats={
    "snapshot_path":str(db),
    "snapshot_bytes":db.stat().st_size,
    "snapshot_hf_revision":"145e38bf736d5475c736ce1c78f02b4ca54306e6",
    "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "query_semantics":"Introduced scanner_findings joined to cases, deduplicated by case_id; these are raw candidates, not 192 validated positives",
    "raw_distinct_case_ids":len(ids),
    "raw_introduced_rows_in_join":sum(r["raw_introduced_finding_rows"] for r in rows),
    "raw_total_introduced_rows":c.execute("SELECT COUNT(*) FROM scanner_findings WHERE introduced=1").fetchone()[0],
    "raw_null_case_id_rows":c.execute("SELECT COUNT(*) FROM scanner_findings WHERE introduced=1 AND case_id IS NULL").fetchone()[0],
    "raw_cases_status_counts":list(c.execute("SELECT status,COUNT(*) FROM cases GROUP BY status").fetchall()),
    "case_id_first_15":ids[:15],
    "case_id_last_15":ids[-15:],
    "files_sha256":hashes,
    "source_sql":sql
}
c.close()
(root/"EXTRACTION_REPORT.json").write_text(json.dumps(stats,indent=2)+"\n")
print("raw_positive_cases="+str(len(ids)))
print("introduced_finding_rows_in_join="+str(stats["raw_introduced_rows_in_join"]))
print("total_introduced_finding_rows="+str(stats["raw_total_introduced_rows"]))
print("orphans="+str(stats["raw_null_case_id_rows"]))
print("first15="+json.dumps(stats["case_id_first_15"]))
print("last15="+json.dumps(stats["case_id_last_15"]))
print("outputs="+str(root))
PY
