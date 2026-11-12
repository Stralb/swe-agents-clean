#!/usr/bin/env python3
from pathlib import Path
import csv,json,collections
root=Path.home()/"research_artifacts"
p=root/"prevention_pilot_phase2"
dest=p/"seven_case_complete_handoff_20261020"
dest.mkdir(parents=True,exist_ok=True)
items=[]
for base in (root,p):
 for child in sorted(base.iterdir()):
  if not any(x in child.name.lower() for x in ("screen65","handoff","owp","codeql","second","iter2","iter3","phase6","d7_final","screencases")):continue
  if child.is_file():
   items.append({"directory":str(base.relative_to(root)),"path":child.name,"size":child.stat().st_size})
  elif child.is_dir():
   for f in child.iterdir():
    if f.is_file() and f.suffix in (".csv",".md",".json",".zip"):
     items.append({"directory":str(child.relative_to(root)),"path":f.name,"size":f.stat().st_size})
manifest=dest/"AVAILABLE_SCREENING_SOURCES.json"
manifest.write_text(json.dumps(items,indent=2))
for a in items:
 if any(z in a["path"].lower() for z in ("screen65","iter2","second","summary","handoff")):print(a)
print("TOTAL ITEMS",len(items),"OUTPUT",manifest)
