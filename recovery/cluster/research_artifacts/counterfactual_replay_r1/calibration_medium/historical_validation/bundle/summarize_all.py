import csv, glob, sys
paths=sorted(glob.glob(sys.argv[1]+'/S5PAIR-*.csv'))
rows=[]
for p in paths:
    rows.extend(csv.DictReader(open(p,encoding='utf-8')))
if not rows:
    raise SystemExit('no result CSVs found')
fields=list(rows[0].keys())
with open(sys.argv[2],'w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
print(f'PAIRS_SUMMARIZED={len(rows)}')
for r in rows:
    print(f"{r['pair_id']}: base={r['base_target_count']} head={r['head_target_count']} introduced={r['introduced_target_count']} added_line={r['head_target_on_added_line_count']} STATUS={r['historical_validation']}")
print('ALL_PASS='+str(all(r['historical_validation']=='PASS' for r in rows)))
