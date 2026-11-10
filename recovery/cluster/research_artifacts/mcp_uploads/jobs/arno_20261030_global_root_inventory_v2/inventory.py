#!/usr/bin/env python3
"""Read-only global research-root file census, excluding reproducible caches and code installs.
No file contents exposed, no existing artifacts modified.
"""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import os,csv,json,sys,time
R=Path.home()/"research_artifacts"
O=R/"mcp_uploads/jobs/arno_20261030_global_root_inventory_v2"
SKIP_TOP={"ARNO_MASTER_DB","ARNO_CODEQL_EXPORT_20261019"}
SKIP_NAMES={".git","node_modules",".venv","venv","__pycache__", ".mypy_cache",".pytest_cache",".next","dist","build","REPO"}
SKIP_TOP_PREFIX=("f1f5_qc_cache_","f1f5_qc_remaining_","real122_repo_cache","provenance_phase2_repo_cache","DECISION_LEVEL_STEP7_REPO_CACHE")
SUFFIXES={".zip",".tar",".gz",".tgz",".xz",".patch",".diff",".sarif",".json",".jsonl",".csv",".tsv",".txt",".md",".log",".out",".err",".sbatch",".py",".ipynb",".db",".sqlite",".xlsx",".parquet",".pkl"}
def category(p):
 n=p.name.lower()
 if n.endswith((".patch",".diff")):return "PATCH"
 if n.endswith(".sarif"):return "SARIF"
 if n.endswith((".zip",".tar",".gz",".tgz",".xz")):return "ARCHIVE"
 if n.endswith((".sqlite",".db")):return "SQLITE"
 if n.endswith((".csv",".tsv",".xlsx",".parquet")):return "DATA"
 if n.endswith((".log",".out",".err")):return "LOG"
 if n.endswith((".sbatch",".py")):return "SCRIPT"
 if n.endswith((".json",".jsonl")):return "JSON"
 if n.endswith((".md",".txt")):return "TEXT"
 return "OTHER"
def main():
 if (O/"REPORT.json").exists() or (O/"ROOT_ARTIFACTS.csv").exists():raise RuntimeError("Audit outputs already exist")
 O.mkdir(parents=True,exist_ok=True)
 stats=Counter();top=defaultdict(lambda:Counter());skipped=[]
 start=time.time()
 with (O/"ROOT_ARTIFACTS.csv").open("x",newline="",encoding="utf8") as f:
  w=csv.writer(f);w.writerow(["relative_path","top_level","role","bytes","modified_ns"])
  for where,dirs,files in os.walk(R,topdown=True,followlinks=False):
   loc=Path(where)
   rel=loc.relative_to(R);level=len(rel.parts) if str(rel)!="." else 0
   keeping=[]
   for d in dirs:
    bad=(d in SKIP_NAMES)
    if level==0 and (d in SKIP_TOP or d.startswith(SKIP_TOP_PREFIX)):bad=True
    if loc==R/"mcp_uploads/jobs" and d=="arno_20261030_global_root_inventory_v1":bad=True
    if bad:skipped.append(str(rel/d))
    else:keeping.append(d)
   dirs[:]=keeping
   for name in files:
    p=loc/name;relative=p.relative_to(R)
    if p.is_symlink():continue
    if p.suffix.lower() not in SUFFIXES:continue
    try:s=p.stat()
    except OSError:continue
    if not p.is_file():continue
    role=category(p);t=relative.parts[0] if len(relative.parts)>1 else "[root]"
    w.writerow((str(relative),t,role,s.st_size,s.st_mtime_ns))
    stats["files"]+=1;stats["bytes"]+=s.st_size
    stats[role]+=1;top[t]["files"]+=1;top[t]["bytes"]+=s.st_size;top[t][role]+=1
    if stats["files"]>1500000:raise RuntimeError("Safety cap on file enumeration reached")
   if level==0:print("ROOT_SCAN_STARTED",len(dirs),flush=True)
 result={"status":"READ_ONLY_GLOBAL_RESEARCH_FILE_CENSUS",
  "date_utc":datetime.now(timezone.utc).isoformat(),
  "file_counts":dict(stats),"by_top_level":{k:dict(v) for k,v in top.items()},
  "excluded_reproducible_cache_and_big_snapshot_directories":skipped,
  "file_csv":str(O/"ROOT_ARTIFACTS.csv"),
  "limitations":"Metadata only; this is not a hash-complete or all-file census. File categories/archives in cache directories and main DB snapshots are excluded deliberately. No raw content was copied, and originals remain unmodified."}
 with (O/"REPORT.json").open("x") as f:json.dump(result,f,indent=2)
 print(json.dumps({k:v for k,v in result.items() if k not in ("by_top_level","excluded_reproducible_cache_and_big_snapshot_directories")},sort_keys=True),flush=True)
 print("TOP_BY_BYTES",json.dumps(sorted(((k,int(v["bytes"]),int(v["files"])) for k,v in top.items()),key=lambda x:x[1],reverse=True)[:25]),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:print("ROOT_INVENTORY_FAILED "+repr(e),file=sys.stderr,flush=True);sys.exit(1)
