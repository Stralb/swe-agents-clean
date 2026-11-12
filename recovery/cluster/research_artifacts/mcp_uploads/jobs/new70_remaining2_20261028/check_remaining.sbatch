#!/bin/bash
#SBATCH --job-name=arno_remaining_two
#SBATCH --partition=stampede
#SBATCH --time=00:03:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
python3 - <<'PY'
import csv,collections,json
from pathlib import Path
base=Path.home()/"research_artifacts"
f=base/"new70_frozen_methodology_20260829T091932Z/90_LOCKED_FOR_LATER/scanner_findings_raw_NEW70.csv"
out=base/"mcp_uploads/jobs/new70_remaining2_20261028"
out.mkdir(parents=True,exist_ok=True)
by=collections.defaultdict(lambda:{"total":0,"promoted":0,"unpromoted":[]})
with f.open("r",encoding="utf-8-sig",newline="") as fd:
  for x in csv.DictReader(fd):
    d=by[int(x["case_id"])];d["total"]+=1
    if x["introduced"].strip()=="1":d["promoted"]+=1
    else:d["unpromoted"].append({"raw_finding_id":x["raw_finding_id"],"scanner":x["scanner"],"rule_id":x["rule_id"]})
mixed={str(k):v for k,v in by.items() if v["promoted"] and v["unpromoted"]}
report={"mixed_cases":mixed,"total_unpromoted_in_mixed":sum(len(v["unpromoted"]) for v in mixed.values())}
(out/"MIXED_PROMOTED_UNPROMOTED.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report))
PY