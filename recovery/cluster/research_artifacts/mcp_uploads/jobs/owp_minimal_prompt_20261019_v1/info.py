#!/usr/bin/env python3
from pathlib import Path
import zipfile,json,hashlib
root=Path.home()/"research_artifacts"
base=root/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
out=root/"prevention_pilot_phase2/minimal_prompt_source_intake_20261019_v1"
out.mkdir(parents=True,exist_ok=True)
for case in ["03429","03581"]:
 p=base/f"CASE_{case}_O.zip"
 with zipfile.ZipFile(p) as z:
  manifest=[]
  for item in z.infolist():
   if item.is_dir():continue
   manifest.append(dict(name=item.filename,bytes=item.file_size,zip_bytes=item.compress_size))
  texts={}
  for name in ["ISSUE.md","RUN_INSTRUCTIONS.md","SOURCE_SNAPSHOT.md","REPO/README.md","REPO/package.json","REPO/.git/config"]:
   if name in z.namelist():
    b=z.read(name)
    texts[name]=b.decode("utf-8",errors="replace")[:28000]
 (out/f"CASE_{case}_INFO.json").write_text(json.dumps(dict(case=case,size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),manifest=manifest,texts=texts),indent=2))
 print(case,p.stat().st_size,len(manifest),sum(x["bytes"] for x in manifest),flush=True)
