#!/usr/bin/env python3
from pathlib import Path
import csv,zipfile
root=Path.home()/'research_artifacts'
src=root/'mcp_uploads/jobs/arno_sample_50_20261031_v3/BLIND_FINAL/01_BLINDED_REVIEW_50.csv'
out=root/'mcp_uploads/jobs/arno_d7_blind50_slim_20261031_v2/out'
out.mkdir(parents=True,exist_ok=False)
with src.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
keep=['review_id','root_reference','case_id','repository','issue_url','issue_title','pr_url','pr_title','root_implementation_summary','root_member_change_ids','scanner_warning_count_case_level']+[n for n in rows[0] if n.startswith('YOUR_')]
file=out/'D7_50_BLIND_COMPACT.csv'
with file.open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=keep);w.writeheader();w.writerows([{n:r.get(n,'') for n in keep} for r in rows])
with zipfile.ZipFile(out/'D7_50_BLIND_COMPACT.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.write(file,file.name)
print('records',len(rows),'zip bytes',(out/'D7_50_BLIND_COMPACT.zip').stat().st_size)
