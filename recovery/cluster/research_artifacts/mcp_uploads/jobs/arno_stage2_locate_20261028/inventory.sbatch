#!/bin/bash
#SBATCH --job-name=arno_stage2_inventory
#SBATCH --partition=stampede
#SBATCH --time=00:06:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G

python3 - <<'PY'
from pathlib import Path
import json, datetime, collections
root=Path.home()/"research_artifacts"
out=root/"mcp_uploads/jobs/arno_stage2_locate_20261028"
out.mkdir(parents=True,exist_ok=True)
keywords=["new70","classification","canonical","risk_assess","step1","step2","step3","mechanism","implementation_choice","final_root","adjudicat","stage4c","cohort_192","positive_192"]
results=[]
visited=0
for p in root.rglob("*"):
    visited+=1
    if not p.is_file():continue
    s=p.name.lower()
    if any(q in s for q in keywords):
        stat=p.stat()
        results.append({"relative_path":str(p.relative_to(root)),"bytes":stat.st_size,"mtime_utc":datetime.datetime.fromtimestamp(stat.st_mtime,datetime.timezone.utc).isoformat()})
results.sort(key=lambda x:x["relative_path"])
report={"read_only":True,"generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"root":str(root),"visited_paths":visited,"matches":len(results),"files":results}
(out/"STAGE2_MATCHING_SOURCE_FILES.json").write_text(json.dumps(report,indent=2)+"\n")
slim={"matches":len(results),"by_keyword":{k:sum(k in x["relative_path"].lower().split("/")[-1] for x in results) for k in keywords},"examples":results[:80]}
(out/"STAGE2_INVENTORY_SUMMARY.json").write_text(json.dumps(slim,indent=2)+"\n")
print(json.dumps({"visited_paths":visited,"matched_files":len(results),"summary_path":str(out/"STAGE2_INVENTORY_SUMMARY.json")}))
PY