#!/usr/bin/env python3
"""READ ONLY: Historical O-arm 08461/15151 patch alias and archive search.
Reads only within ~/research_artifacts, writes only a NEW JSON report.
Does NOT change old data or promote a later patch as historical.
"""
from pathlib import Path
from collections import Counter
import os,zipfile,hashlib,json,re,time
root=Path.home()/"research_artifacts"
output=root/"mcp_uploads/jobs/arno_o_patch_search_20261101"
output.mkdir(parents=True,exist_ok=True)
dest=output/"HISTORICAL_O_PATCH_CANDIDATES.json"
if dest.exists():raise FileExistsError("Refusing to overwrite existing report")
patterns=("08461","8461","15151","owp14","screen65")
def sha_file(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for chunk in iter(lambda:f.read(2*1024*1024),b""):h.update(chunk)
 return h.hexdigest()
matches=[];archived=[];roots=[];scanned=0;archive_count=0
skip={"node_modules",".git","__pycache__","REPO","repo","repo_after","repo_before","before","after","scratch","cache",".venv","venv","codeql_db","database","databases"}
extensions={".patch",".diff",".zip",".json",".jsonl",".md",".txt",".csv",".log",".sqlite"}
for base in (root/"prevention_pilot_phase2",root/"mcp_uploads",root/"ARNO_CODEQL_EXPORT_20261019"):
 if not base.exists():continue
 root_count=0;root_matches=0
 for current,dirs,files in os.walk(base,followlinks=False):
  dirs[:]=[d for d in dirs if d not in skip and not d.startswith(".") and not d.startswith("node_modules")]
  for f in files:
   scanned+=1;root_count+=1
   p=Path(current)/f
   rel=str(p.relative_to(root))
   low=rel.lower()
   relevant=any(k in low for k in patterns)
   ext=p.suffix.lower()
   if relevant and ext in extensions:
    try:
     size=p.stat().st_size
     entry={"path":rel,"bytes":size,"extension":ext}
     if (ext in {".patch",".diff",".json",".txt",".md",".csv"} and size<25_000_000):
      entry["sha256"]=sha_file(p)
     matches.append(entry);root_matches+=1
    except (OSError,PermissionError) as e:matches.append({"path":rel,"error":str(e)})
   # Only inspect archive member listings for focused research archives,
   # and small case-specific ZIPs; avoid scanning every repository source ZIP.
   focus=("owp14" in low or "screen65" in low or "agent_prompts" in low or
          f in ("02_ALL_GENERATED_PATCHES.zip","06_EARLIER_CAUSAL_EXPERIMENTS.zip",
                "07_AGENT_PROMPTS_AND_TRACES.zip","ARNO_CODEQL_COMPLETE_RESEARCH_HANDOFF_20261019.zip"))
   if ext==".zip" and focus:
    try:
     sz=p.stat().st_size
     if sz>1_900_000_000:continue
     archive_count+=1
     with zipfile.ZipFile(p) as z:
      candidates=[v for v in z.infolist() if
                  ("08461" in v.filename or "15151" in v.filename or
                   "8461" in v.filename) and
                  not v.is_dir() and (
                   v.filename.lower().endswith((".patch",".diff",".json",".txt",".md",".zip",".log")))]
      for v in candidates[:100]:
       info={"archive":rel,"member":v.filename,"uncompressed_bytes":v.file_size}
       if v.file_size<=20_000_000 and v.filename.lower().endswith((".patch",".diff")):
        raw=z.read(v);info["sha256"]=hashlib.sha256(raw).hexdigest()
       archived.append(info)
    except (zipfile.BadZipFile,OSError,PermissionError,RuntimeError) as e:
     archived.append({"archive":rel,"error":str(e)})
  if root_count>150_000:break
 roots.append({"root":str(base.relative_to(root)),"files_seen":root_count,"matches":root_matches})
if len(matches)>10000 or len(archived)>10000:raise RuntimeError("Unexpectedly large match set; review script")
report={"status":"INVENTORY_COMPLETE_NO_ORIGIN_ASSUMPTIONS","searched_for":["08461","8461","15151","owp14","screen65"],
        "total_files_seen":scanned,"archives_inspected":archive_count,
        "scan_roots":roots,"matching_paths":matches,
        "matching_archive_members":archived,
        "notes":["Matching a case number or patch hash alone does NOT establish original O-arm provenance.",
                 "Candidate scanner patches remain separate until dated origin / original receipt verified."]}
dest.write_text(json.dumps(report,indent=2),encoding="utf-8")
short=[e for e in matches if e.get("extension") in (".patch",".diff") and ("08461" in e["path"] or "15151" in e["path"])]
print(json.dumps({"status":"PASS","candidate_files":len(matches),"patch_candidates":short[:80],
                 "archive_member_candidates":len(archived),"archive_patch_candidates":[e for e in archived if e.get("member","").endswith(".patch")][:60],
                 "scanned_files":scanned,"archives_inspected":archive_count,"report":str(dest)},indent=2),flush=True)
