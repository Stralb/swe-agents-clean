#!/bin/bash
#SBATCH --job-name=arno_new70_source_audit
#SBATCH --partition=stampede
#SBATCH --time=00:04:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
python3 - <<'PY'
from pathlib import Path
import collections,csv,json,datetime
root=Path.home()/"research_artifacts"
out=root/"mcp_uploads/jobs/new70_source_audit_20261028"
out.mkdir(parents=True,exist_ok=True)
source=root/"new70_frozen_methodology_20260829T091932Z/90_LOCKED_FOR_LATER/scanner_findings_raw_NEW70.csv"
missing={3375,4131,4812,6103,6185,10806,12014,16372,17077,18777}
counts=collections.Counter()
introductions=collections.Counter()
scanners=collections.defaultdict(set)
evidence=collections.defaultdict(collections.Counter)
rules=collections.defaultdict(collections.Counter)
with source.open('r',encoding='utf-8-sig',newline='') as f:
  rd=csv.DictReader(f)
  for row in rd:
    case=int(row["case_id"])
    counts[case]+=1
    introductions[case]+=(str(row.get("introduced","")).strip() in ("1","True","true"))
    scanners[case].add(row.get("scanner"))
    rules[case][row.get("rule_id")]+=1
    if case in missing:
      ev=row.get("evidence","")
      try: obj=json.loads(ev)
      except Exception:obj={}
      for key in ("promoted","confidence","rejection_reasons","validation_state"):
        if key in obj:evidence[case][key+"="+str(obj[key])]+=1
results=[{
 "case_id":i,"new70_raw_rows":counts[i],"new70_introduced_1":introductions[i],
 "scanners":sorted(scanners[i]),"evidence_fields":dict(evidence[i]),
 "top_rules":rules[i].most_common(5)
} for i in sorted(missing)]
report={
 "read_only":True,
 "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "source":str(source),
 "all_rows":sum(counts.values()),
 "all_cases":len(counts),
 "all_rows_with_introduced_true":sum(introductions.values()),
 "missing10":results
}
(out/"NEW70_FROZEN_SOURCE_MISSING10_AUDIT.json").write_text(json.dumps(report,indent=2,default=str)+"\n")
print(json.dumps(report,indent=2,default=str)[:15000])
PY