#!/usr/bin/env python3
import json,zlib,csv,io,sqlite3
from pathlib import Path
R=Path.home()/"research_artifacts"
db=sqlite3.connect("file:"+str(R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite")+"?mode=ro",uri=True)
db.execute("PRAGMA query_only=ON")
names=["C5_CONTEXT_190_FROZEN.csv","C6_MATCHED_PAIR_MASTER_190.csv","C6_CONTEXT_QC_CORRECTIONS.csv","C5_CORRECTIONS_ONLY.csv"]
data={}
for name in names:
 src=db.execute("SELECT source_path,original_bytes,content_zlib,source_sha256 FROM arno_evidence_assets WHERE source_path LIKE ?",("%/"+name,)).fetchone()
 if not src:data[name]={"status":"NOT_EMBEDDED"};continue
 path,size,blob,sha=src
 rows=list(csv.DictReader(io.StringIO(zlib.decompress(blob).decode("utf-8-sig"))))
 data[name]={"source_path":path,"bytes":size,"sha256":sha,"rows":len(rows),"columns":list(rows[0]) if rows else []}
db.close()
out=R/"mcp_uploads/jobs/arno_oct28_c5c6_compare_v1/REPORT.json"
out.parent.mkdir(parents=True,exist_ok=True)
if out.exists():raise RuntimeError("Refusing overwrite")
out.write_text(json.dumps(data,indent=2))
print(json.dumps(data,indent=2))
