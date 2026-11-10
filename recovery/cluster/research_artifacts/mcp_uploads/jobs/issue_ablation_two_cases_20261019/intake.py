#!/usr/bin/env python3
from pathlib import Path
import json,zipfile,hashlib
root=Path.home()/'research_artifacts'
src=root/'prevention_pilot_phase2/owp14_allcases_packets_job71014'
out=root/'prevention_pilot_phase2/issue_ablation_two_cases_20261019'
out.mkdir(parents=True,exist_ok=True)
for case in ('03429','03581'):
 p=src/('CASE_'+case+'_O.zip')
 with zipfile.ZipFile(p) as z:
  issue=z.read('ISSUE.md').decode('utf-8')
  n=[x for x in z.namelist() if x.startswith('REPO/') and not x.endswith('/')]
 (out/('ISSUE_'+case+'_ORIGINAL.md')).write_text(issue)
 print(json.dumps({'case':case,'source_bytes':p.stat().st_size,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'repo_files':len(n),'issue_bytes':len(issue.encode()),'issue_sha256':hashlib.sha256(issue.encode()).hexdigest(),'headings':[x for x in issue.splitlines() if x.startswith('#')]}))
