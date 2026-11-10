#!/usr/bin/env python3
import csv, glob, os
from collections import defaultdict
root=os.path.expanduser('~/research_artifacts/counterfactual_replay_r1/calibration_medium/target_scan')
files=sorted(glob.glob(root+'/results/C???.csv'))
rows=[]
for p in files:
    rows.extend(csv.DictReader(open(p,encoding='utf-8')))
out=root+'/TARGET_SCAN_SUMMARY.csv'
if rows:
    with open(out,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
print(f'RUNS_SUMMARIZED={len(rows)}')
by=defaultdict(lambda:{'P0':[],'N0':[]})
for r in rows: by[r['pair_id']][r['role']].append(r)
for pair in sorted(by):
    p=by[pair]['P0']; n=by[pair]['N0']
    p_repro=sum(r['historical_rule_reproduced']=='YES' for r in p)
    n_repro=sum(r['historical_rule_reproduced']=='YES' for r in n)
    print(f'{pair}: P0_target_repro={p_repro}/{len(p)} N0_target_repro={n_repro}/{len(n)}')
