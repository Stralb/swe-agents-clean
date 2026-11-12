#!/usr/bin/env python3
"""Read-only compare C5 frozen context to the one recorded C6 correction."""
import csv,io,json,sqlite3,zlib
from pathlib import Path
R=Path.home()/"research_artifacts"
C=sqlite3.connect("file:"+str(R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite")+"?mode=ro",uri=True)
C.execute("PRAGMA query_only=ON")
def embedded(name):
 p=C.execute("SELECT content_zlib FROM arno_evidence_assets WHERE source_path LIKE ?",("%/"+name,)).fetchone()
 if p is None:raise ValueError("Not found: "+name)
 return list(csv.DictReader(io.StringIO(zlib.decompress(p[0]).decode("utf-8-sig"))))
cs=embedded("C6_CONTEXT_QC_CORRECTIONS.csv")
c5=embedded("C5_CONTEXT_190_FROZEN.csv")
c6=embedded("C6_MATCHED_PAIR_MASTER_190.csv")
assert len(cs)==1 and len(c5)==len(c6)==190
out=[]
for r in cs:
 case=int(r["control_case_id"])
 links=[pair for pair in c6 if int(pair["control_case_id"])==case]
 assert len(links)==1,case
 p=links[0]
 old=[row for row in c5 if row["blind_id"]==p["control_blind_id"]]
 assert len(old)==1,(case,p["control_blind_id"])
 field=r["field"]
 out.append({"type":r["type"],"control_case_id":case,
     "field":field,"original_value":r["original_value"],"c6_value":r["c6_value"],
     "reason":r["reason"],"C5_context_has_same_field":field in old[0],
     "C5_field_value":old[0].get(field,"NOT_IN_C5_CONTEXT_COLUMNS"),
     "C6_pair_field_value":p.get("control_"+field,"NOT_IN_C6_PAIR_COLUMNS"),
     "matched_pair_index":p["pair_index"]})
C.close()
res={"status":"C5_C6_SOURCE_RECONCILIATION_CHECKED","c5_context_rows":190,
     "c6_matched_pairs":190,"corrections":out,
     "interpretation":"C6 is a derived corrected analysis source, not a byte-identical copy of the frozen C5 context."}
dest=R/"mcp_uploads/jobs/arno_oct28_c5c6_correction_audit/REPORT.json"
dest.parent.mkdir(parents=True,exist_ok=True)
if dest.exists():raise RuntimeError("Report exists")
dest.write_text(json.dumps(res,indent=2))
print(json.dumps(res,indent=2))
