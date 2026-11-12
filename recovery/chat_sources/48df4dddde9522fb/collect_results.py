#!/usr/bin/env python3
from pathlib import Path
import csv, sys
if len(sys.argv)!=3:
    raise SystemExit('usage: collect_results.py <output_dir> <csv_out>')
root=Path(sys.argv[1]); out=Path(sys.argv[2])
rows=[]
for d in sorted(p for p in root.iterdir() if p.is_dir()):
    def txt(name, default=''):
        p=d/name
        return p.read_text(errors='replace').strip() if p.exists() else default
    rows.append({
      'run_id':d.name,
      'apply_rc':txt('apply.rc','MISSING'),
      'install':txt('install.status',''),
      'build':txt('build.status',''),
      'functional':txt('functional.status',''),
      'target_scanner':txt('target_scanner.status',''),
      'security_oracle':txt('security_oracle.status',''),
      'mechanism_label':'',
      'notes':''
    })
fields=list(rows[0]) if rows else ['run_id']
with out.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
