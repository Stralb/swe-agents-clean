#!/bin/bash
#SBATCH --job-name=final-yield-report
#SBATCH --partition=bigbatch
#SBATCH --dependency=afterok:281
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/%u/final_yield_report_%j.log

set -euo pipefail

cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart

source .venv/bin/activate
source .env.cluster
source .snapshot_eval_codeql_done_db

echo "FINAL DB=$DB_PATH"
echo "START=$(date)"

make methodology-profile
make methodology-status
make region-yield

echo
echo "===== DB SUMMARY ====="
./.venv/bin/python - <<'PY'
import os, sqlite3
con = sqlite3.connect(os.environ["DB_PATH"])
cur = con.cursor()

print("DB:", os.environ["DB_PATH"])
print("quick_check:", cur.execute("PRAGMA quick_check").fetchone())
print("cases:", cur.execute("SELECT COUNT(*) FROM cases").fetchone()[0])
print("repos:", cur.execute("SELECT COUNT(DISTINCT repo_id) FROM cases").fetchone()[0])

print("\nSCANNER JOBS")
for r in cur.execute("""
SELECT job_type,status,COUNT(*)
FROM scanner_jobs
GROUP BY job_type,status
ORDER BY job_type,status
"""):
    print(r)

print("\nFINDINGS")
for r in cur.execute("""
SELECT scanner,finding_type,introduced,COUNT(*)
FROM scanner_findings
GROUP BY scanner,finding_type,introduced
ORDER BY scanner,finding_type,introduced
"""):
    print(r)

print("\nNEEDS REVIEW")
for r in cur.execute("""
SELECT c.id, repos.full_name, issues.number, pull_requests.number, COUNT(sf.id) AS findings
FROM cases c
JOIN repos ON c.repo_id=repos.id
JOIN issues ON c.issue_id=issues.id
JOIN pull_requests ON c.pr_id=pull_requests.id
LEFT JOIN scanner_findings sf ON sf.case_id=c.id AND sf.introduced=1
WHERE c.status='needs_review'
GROUP BY c.id
ORDER BY findings DESC, c.id
LIMIT 50
"""):
    print(r)

con.close()
PY

echo "END=$(date)"
