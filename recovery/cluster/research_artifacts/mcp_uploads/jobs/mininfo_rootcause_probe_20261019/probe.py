#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import json,zipfile,re
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
out={}
def alerts(p):
 z=json.loads(p.read_text())
 rows=[]
 for run in z.get('runs',[]):
  for x in run.get('results',[]):
   loc=(x.get('locations') or [{}])[0].get('physicalLocation',{})
   rows.append(dict(rule=x.get('ruleId'),path=loc.get('artifactLocation',{}).get('uri'),line=loc.get('region',{}).get('startLine'),message=x.get('message',{}).get('text'),fingerprint=x.get('partialFingerprints')))
 return rows
b=alerts(root/'mininfo_3x4_scan_job71825/03429_baseline.sarif')
for arm in ['C0','C1','C2','C3']:
 a=alerts(root/('mininfo_3x4_scan_job71825/03429_'+arm+'_after.sarif'))
 out['03429_'+arm]=dict(baseline_filtered=[x for x in b if x['path']=='src/core/FileSystemUtils.ts' or x['rule']=='js/insecure-temporary-file'],after_filtered=[x for x in a if x['path']=='src/core/FileSystemUtils.ts' or x['rule']=='js/insecure-temporary-file'])
for case in ['03429','03581','32759']:
 p=root/('owp14_allcases_packets_job71014/CASE_'+case+'_O.zip')
 matches=[]
 pat=re.compile(r'\bshell\s*:\s*true\b|shell\s*:\s*process\.platform|cmd\.exe|addEventListener\s*\(\s*[\x27\x22]message|onmessage\s*=|\b(?:statSync|lstatSync|existsSync|\.stat\(|\.lstat\(|\.access\(|\.open\()')
 with zipfile.ZipFile(p) as z:
  for n in z.namelist():
   if not n.startswith('REPO/') or n.endswith('/') or not n.lower().endswith(('.js','.mjs','.ts','.tsx')):continue
   if z.getinfo(n).file_size>250000:continue
   s=z.read(n).decode('utf-8','replace')
   for idx,line in enumerate(s.splitlines(),1):
    if pat.search(line):
     matches.append(dict(file=n[5:],line=idx,text=line[:280]))
 out['patterns_'+case]=dict(total=len(matches),samples=matches[:100])
print(json.dumps(out,indent=2)[:30000])
