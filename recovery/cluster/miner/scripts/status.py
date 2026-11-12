from src.db.database import Database
from src.settings import load_settings

s = load_settings()
db = Database(s.db_path)

print("Cases by status:")
for row in db.query("select status, count(*) as n from cases group by status order by status"):
    print(f"  {row['status']}: {row['n']}")

print("\nCases by AI cohort:")
for row in db.query("select ai_cohort, count(*) as n from cases group by ai_cohort order by ai_cohort"):
    print(f"  {row['ai_cohort']}: {row['n']}")

print("\nCases by downstream signal:")
for row in db.query("select coalesce(downstream_signal,'none') as signal, count(*) as n from cases group by coalesce(downstream_signal,'none') order by signal"):
    print(f"  {row['signal']}: {row['n']}")

print("\nScanner runs:")
for row in db.query("select scanner, status, count(*) as n from scanner_runs group by scanner, status order by scanner, status"):
    print(f"  {row['scanner']} [{row['status']}]: {row['n']}")

print("\nPending work:")
rows = db.query("""
select
  count(*) as total,
  sum(case when not exists (select 1 from scanner_runs sr where sr.case_id=c.id and sr.scanner='gitleaks') then 1 else 0 end) as missing_gitleaks,
  sum(case when not exists (select 1 from scanner_runs sr where sr.case_id=c.id and sr.scanner='dependency-diff') then 1 else 0 end) as missing_dependency_diff,
  sum(case when not exists (select 1 from scanner_runs sr where sr.case_id=c.id and sr.scanner='osv-scanner') then 1 else 0 end) as missing_osv,
  sum(case when not exists (select 1 from scanner_runs sr where sr.case_id=c.id and sr.scanner='codeql') then 1 else 0 end) as missing_codeql
from cases c
where c.status not in ('reviewed','excluded')
""")
if rows:
    r = rows[0]
    print(f"  active cases: {r['total']}")
    print(f"  missing Gitleaks: {r['missing_gitleaks'] or 0}")
    print(f"  missing dependency diff: {r['missing_dependency_diff'] or 0}")
    print(f"  missing OSV: {r['missing_osv'] or 0}")
    print(f"  missing CodeQL: {r['missing_codeql'] or 0}")
