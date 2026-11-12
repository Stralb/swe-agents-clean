#!/usr/bin/env python3
from pathlib import Path
from hashlib import sha256
import zipfile,json
root=Path.home()/'research_artifacts/prevention_pilot_phase2/minimal_prompt_full_3x4_20261019'
m=root/'ALL_12_FULL_SOURCE_MINIMAL_PROMPT_PACKETS.zip'
expected=json.loads((root/'RESULT_MANIFEST.json').read_text())
checks=[]
with zipfile.ZipFile(m) as outer:
 assert outer.testzip() is None
 for item in expected:
  p=root/item['filename']
  assert sha256(p.read_bytes()).hexdigest()==item['sha256']
  with zipfile.ZipFile(p) as z:
   assert z.testzip() is None
   assert z.read('OUTPUT_FILENAME.txt').decode().strip()==f"CASE_{item['case_id']}_{item['arm']}_r01.patch"
   assert z.read('RUNLOG_FILENAME.txt').decode().strip()==f"CASE_{item['case_id']}_{item['arm']}_r01_runlog.txt"
   assert len([x for x in z.namelist() if x.startswith('REPO/') and not x.endswith('/')])==item['repo_file_count']
  assert outer.read(item['filename'])==p.read_bytes()
  checks.append(item['filename'])
print(json.dumps(dict(master_bytes=m.stat().st_size,master_sha256=sha256(m.read_bytes()).hexdigest(),packets=len(checks),verified=checks),indent=2))
