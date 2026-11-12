#!/usr/bin/env python3
from pathlib import Path
import hashlib,zipfile,json
f=Path.home()/'research_artifacts/prevention_pilot_phase2/owp14_allcases_packets_job71014/CASE_32759_O.zip'
a={'path':str(f),'size':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
with zipfile.ZipFile(f) as z:
 a['files']=len([n for n in z.namelist() if n.startswith('REPO/') and not n.endswith('/')])
 a['issue_sha256']=hashlib.sha256(z.read('ISSUE.md')).hexdigest()
print(json.dumps(a,indent=2))
