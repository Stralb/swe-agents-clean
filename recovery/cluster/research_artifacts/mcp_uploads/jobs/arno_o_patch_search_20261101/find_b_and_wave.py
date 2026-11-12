#!/usr/bin/env python3
"""READ-ONLY targeted filename search for B-arm and screen-wave outputs."""
from pathlib import Path
import os,json,re,zipfile
ROOT=Path.home()/"research_artifacts"
TARGET=ROOT/"mcp_uploads/jobs/arno_o_patch_search_20261101"
DEST=TARGET/"OTHER_PENDING_OUTPUT_SEARCH.json"
if DEST.exists():raise FileExistsError("Refusing overwrite")
cases={"03429","03581","08152","12344","31207","32759"}
found=[];visited=0;zips=[]
skip={"node_modules",".git","__pycache__","REPO","repo","before","after","scratch","cache","codeql_db","database","databases"}
for top in (ROOT/"mcp_uploads",ROOT/"prevention_pilot_phase2",ROOT/"ARNO_CODEQL_EXPORT_20261019"):
 if not top.exists():continue
 for base,dirs,files in os.walk(top):
  dirs[:]=[d for d in dirs if d not in skip and not d.startswith(".")]
  for f in files:
   visited+=1
   up=f.upper();path=Path(base)/f;rel=str(path.relative_to(ROOT))
   case=next((c for c in cases if c in up),None)
   btarget=(case is not None and ("BLIND" in up or "B_STAGE2" in up or
             (f.lower().endswith((".patch",".json",".zip")) and
              ("_B_" in up or up.endswith("_B.PATCH"))))
   wave=("SCREEN_RESULTS_WAVE_12" in up or "SCREEN_WAVE_12" in up)
   if btarget or wave:
    found.append({"path":rel,"case":case,"type":"B_CANDIDATE" if btarget else "SCREEN_WAVE"})
   if f.lower().endswith(".zip") and
      ("blind_repair" in rel.lower() or "all12" in rel.lower() or
       "screen_wave" in rel.lower() or "screen_results_wave" in rel.lower()):
    try:
     with zipfile.ZipFile(path) as z:
      zz=[n for n in z.namelist() if re.search(r'PILOT(?:03429|03581|08152|12344|31207|32759)_BLIND|(?:03429|03581|08152|12344|31207|32759)_B_STAGE2|SCREEN_RESULTS_WAVE_12',n,re.I)]
      zips.extend({"zip_path":rel,"member":n} for n in zz[:50])
    except (zipfile.BadZipFile,OSError,RuntimeError):pass
  if visited>150000:break
report={"scan_files":visited,"matches":found,"archive_members":zips,"result":"FILENAME_INVENTORY_ONLY"}
DEST.write_text(json.dumps(report,indent=2))
print(json.dumps({"scanned":visited,"match_count":len(found),"matches":found[:120],"zip_members":zips[:60]},indent=2),flush=True)
