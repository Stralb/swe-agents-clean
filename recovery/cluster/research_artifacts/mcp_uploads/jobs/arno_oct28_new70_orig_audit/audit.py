#!/usr/bin/env python3
"""Byte-identity and row-key audit for recovered NEW70 final originals, read-only."""
import hashlib,zipfile,csv,io,json,sqlite3
from pathlib import Path
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
BASE=Path("mcp_uploads/jobs/arno_two_delta_master_import_")
FILES=["Step1_NEW70_FINAL.zip","NEW70_Phase6_Step2_Mapping_FINAL_v1.0.zip","NEW70_Phase6_Producing_Changes_FINAL_v1.0.csv"]
def hash(b):return hashlib.sha256(b).hexdigest()
out={"utc":datetime.now(timezone.utc).isoformat(),"files":{},"status":"PRELIMINARY"}
for name in FILES:
 reps=[]
 for v in ["v02","v03"]:
  p=R/("mcp_uploads/jobs/arno_two_delta_master_import_"+v+"_20261028/expanded/inputs")/name
  if not p.is_file():raise RuntimeError("Missing "+str(p))
  raw=p.read_bytes()
  entry={"path":str(p.relative_to(R)),"size":len(raw),"sha256":hash(raw)}
  if name.endswith(".zip"):
   with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    sub=[]
    for f in z.infolist():
     if f.is_dir():continue
     subentry={"path":f.filename,"bytes":f.file_size,"sha256":hash(z.read(f))}
     if f.filename.lower().endswith(".csv") and f.file_size<5000000:
      rows=list(csv.DictReader(io.StringIO(z.read(f).decode("utf-8-sig"))))
      subentry["rows"]=len(rows)
      subentry["columns"]=list(rows[0]) if rows else []
     sub.append(subentry)
    entry["members"]=sub
  else:
   rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
   entry["rows"]=len(rows)
   entry["columns"]=list(rows[0]) if rows else []
  reps.append(entry)
 if reps[0]["sha256"]!=reps[1]["sha256"]:
  raise RuntimeError("Original copy disagreement: "+name)
 out["files"][name]={"identical_copies":True,"source":reps[0],"duplicate_location":reps[1]["path"]}
db=sqlite3.connect("file:"+str(R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite")+"?mode=ro",uri=True)
db.execute("PRAGMA query_only=ON")
out["master_rows"]={"new70_final_findings":db.execute("select count(*) from arno_new70_final_findings").fetchone()[0],
"new70_final_producing_changes":db.execute("select count(*) from arno_new70_final_producing_changes").fetchone()[0],
"new70_final_unresolved":db.execute("select count(*) from arno_new70_final_unresolved").fetchone()[0]}
out["source_registry_exact_matches"]=[list(x) for x in db.execute("select source_key,source_locator from arno_sources where lower(source_locator) like '%step1_new70_final%' OR lower(source_locator) like '%step2_mapping_final%' OR lower(source_locator) like '%producing_changes_final%'")]
db.close()
out["status"]="TWO_COPIES_SHA256_IDENTICAL_AND_ZIP_CRC_OK"
o=R/"mcp_uploads/jobs/arno_oct28_new70_orig_audit/REPORT.json"
o.parent.mkdir(parents=True,exist_ok=True)
if o.exists():raise RuntimeError("Report exists; refusing overwrite")
o.write_text(json.dumps(out,indent=2))
print(json.dumps({"status":out["status"],"report":str(o),"sources":{k:{"sha256":v["source"]["sha256"],"size":v["source"]["size"]} for k,v in out["files"].items()},"master":out["master_rows"]},indent=2))
