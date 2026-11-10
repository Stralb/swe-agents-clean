#!/usr/bin/env python3
import csv,json,sys
from collections import defaultdict
from pathlib import Path
OUT=Path(sys.argv[1])
rows=[]
for i in range(1,17):
    rid=f"C{i:03d}"; p=OUT/"run_results"/f"{rid}.json"
    if not p.exists():
        rows.append({"run_id":rid,"status":"MISSING"}); continue
    rows.append(json.loads(p.read_text(encoding='utf-8')))
cols=["run_id","pair_id","condition","target_rule","status","base_target_count","patched_target_count","new_target_count","new_primary_changed_count","new_any_changed_count","target_introduced_primary","target_introduced_diff_linked","historical_file","historical_line","same_historical_file","changed_files","base_tree","base_cache_key","query_file","error"]
with (OUT/"CORRECTED_TARGET_EVAL.csv").open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
    for r in rows:
        q={k:r.get(k,'') for k in cols}
        if isinstance(q['changed_files'],list): q['changed_files']=';'.join(q['changed_files'])
        w.writerow(q)
summary=[]
summary.append("CORRECTED TARGET-RULE DIFFERENTIAL EVALUATION")
summary.append("Primary security endpoint: exact historical rule, absent as same SARIF fingerprint in base, and linked to a generated changed line/hunk.")
summary.append("Both primary-location and any-SARIF-evidence linkage are reported; diff-linked is the main replay flag.")
summary.append("")
summary.append(f"RUNS_PRESENT={sum(r.get('status')!='MISSING' for r in rows)}/16")
summary.append(f"RUNS_OK={sum(r.get('status')=='OK' for r in rows)}/16")
summary.append("")
for pair in ["S5PAIR-001","S5PAIR-016","S5PAIR-025","S5PAIR-044"]:
    for cond in ["P0","N0"]:
        rr=[r for r in rows if r.get('pair_id')==pair and r.get('condition')==cond and r.get('status')=='OK']
        hit=sum(bool(r.get('target_introduced_diff_linked')) for r in rr)
        phit=sum(bool(r.get('target_introduced_primary')) for r in rr)
        summary.append(f"{pair} {cond}: target_diff_linked={hit}/{len(rr)} target_primary_changed={phit}/{len(rr)}")
summary.append("")
summary.append("RUN LEVEL")
for r in rows:
    summary.append(f"{r.get('run_id')} {r.get('pair_id','?')} {r.get('condition','?')} status={r.get('status')} base={r.get('base_target_count','?')} patched={r.get('patched_target_count','?')} new={r.get('new_target_count','?')} diff_linked={r.get('target_introduced_diff_linked','?')} same_hist_file={r.get('same_historical_file','?')}")
errs=[r for r in rows if r.get('status') not in {"OK"}]
if errs:
    summary.append("")
    summary.append("ERRORS")
    for r in errs: summary.append(f"{r.get('run_id')}: {r.get('error',r.get('status'))}")
text='\n'.join(summary)+'\n'
(OUT/"SUMMARY.txt").write_text(text,encoding='utf-8')
print(text)
