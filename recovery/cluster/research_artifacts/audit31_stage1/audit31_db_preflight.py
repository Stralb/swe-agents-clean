import csv, sqlite3
from pathlib import Path

DB=Path('/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db')
SEED=Path(__file__).with_name('AUDIT31_STAGE1_INPUT_v1.csv')

with SEED.open(newline='',encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
ids=sorted({int(r['positive_case_id']) for r in rows}|{int(r['control_case_id']) for r in rows})
print('AUDIT31_PAIRS=',len(rows))
print('UNIQUE_CASE_IDS=',len(ids))
print('CASE_IDS=',','.join(map(str,ids)))
print('DB_EXISTS=',DB.exists())
if not DB.exists():
    raise SystemExit(2)
con=sqlite3.connect(f'file:{DB}?mode=ro',uri=True)
con.row_factory=sqlite3.Row

def qident(s): return '"'+s.replace('"','""')+'"'

tables=[r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]
print('\nTABLES_RELEVANT')
for t in tables:
    if any(k in t.lower() for k in ['case','issue','pull','pr_','repo','scanner','finding','file']):
        print(t)

print('\nSCHEMAS')
for t in ['cases','repos','issues','pull_requests','pr_files','scanner_findings','scanner_runs','scanner_jobs']:
    if t not in tables: continue
    cols=[r['name'] for r in con.execute(f'pragma table_info({qident(t)})')]
    print(t+': '+','.join(cols))

print('\nLIKELY_CONTENT_COLUMNS')
for t in tables:
    if t not in ['cases','repos','issues','pull_requests','pr_files','scanner_findings','scanner_runs','scanner_jobs']:
        continue
    cols=[r['name'] for r in con.execute(f'pragma table_info({qident(t)})')]
    keep=[c for c in cols if any(k in c.lower() for k in ['case','issue','pr','repo','title','body','patch','diff','file','path','line','rule','sha','base','head','scanner','finding'])]
    print(t+': '+','.join(keep))

print('\nCASE_SAMPLE')
if 'cases' in tables:
    cols=[r['name'] for r in con.execute('pragma table_info(cases)')]
    key='id' if 'id' in cols else ('case_id' if 'case_id' in cols else None)
    if key:
        for cid in [334,314]:
            row=con.execute(f'SELECT * FROM cases WHERE {qident(key)}=? LIMIT 1',(cid,)).fetchone()
            print('CASE',cid, dict(row) if row else None)

con.close()
