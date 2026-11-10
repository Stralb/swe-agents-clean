#!/usr/bin/env python3
from pathlib import Path
import zipfile,json,hashlib
root=Path.home()/"research_artifacts"
src=root/"prevention_pilot_phase2/owp14_allcases_packets_job71014/CASE_03581_O.zip"
dst=root/"prevention_pilot_phase2/minimal_prompt_source_intake_20261019_v1/CASE_03581_CODE_COMPLETE_NO_DEMO_MEDIA.zip"
removed=[]
with zipfile.ZipFile(src) as zin,zipfile.ZipFile(dst,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zout:
 for item in zin.infolist():
  data=zin.read(item)
  if item.filename.startswith("REPO/resources/") and item.filename.lower().endswith((".gif",".png",".jpg",".jpeg",".webp")):
   removed.append(dict(name=item.filename,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()));continue
  zout.writestr(item,data)
o=root/"prevention_pilot_phase2/minimal_prompt_source_intake_20261019_v1/MEDIA_EXCLUSIONS.json"
o.write_text(json.dumps(dict(original_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),compact_sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),omitted=removed),indent=2))
print(dst.stat().st_size,len(removed),sum(x["bytes"] for x in removed))
