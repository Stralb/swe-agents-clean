#!/bin/bash
#SBATCH --job-name=arno_miner_new70_find
#SBATCH --partition=stampede
#SBATCH --time=00:06:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
python3 - <<'PY'
import os,json,csv,datetime,collections
from pathlib import Path
src=Path.home()/"new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/manual-review"
out=Path.home()/"research_artifacts/mcp_uploads/jobs/arno_miner_new70_find_20261028"
out.mkdir(parents=True,exist_ok=True)
found=[]
for directory,dirs,files in os.walk(src):
    dirs[:]=[d for d in dirs if not d.startswith(".")]
    for f in files:
        if not (f.lower().endswith((".csv",".xlsx",".json",".jsonl",".md"))):continue
        path=Path(directory)/f
        found.append({"path":str(path),"rel":str(path.relative_to(src)),"bytes":path.stat().st_size})
found.sort(key=lambda x:x["rel"])
for x in found:
  if x["rel"].lower().endswith(".csv") and x["bytes"]<15_000_000:
    try:
      with open(x["path"],encoding="utf-8-sig",newline="") as fin:
        reader=csv.reader(fin)
        hdr=next(reader,[])
        x["header"]=hdr[:40]
        x["rows"]=sum(1 for _ in reader)
    except Exception as ex:x["error"]=str(ex)[:150]
report={"origin":str(src),"source_exists":src.is_dir(),"total_files":len(found),"files":found,
        "collected_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
(out/"MINER_MANUAL_REVIEW_INVENTORY.json").write_text(json.dumps(report,indent=2)+"\n")
brief=[x for x in found if any(z in x["rel"].lower() for z in ("new70","classification","step1","step2","step3","risk","master","stage4"))]
(out/"MINER_MANUAL_REVIEW_SHORTLIST.json").write_text(json.dumps(brief,indent=2)+"\n")
print(json.dumps({"base_exists":src.is_dir(),"files":len(found),"shortlist":len(brief),"shortlist_path":str(out/"MINER_MANUAL_REVIEW_SHORTLIST.json")}))
PY