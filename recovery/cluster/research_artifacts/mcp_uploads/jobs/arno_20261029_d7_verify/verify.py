#!/usr/bin/env python3
"""Independent read-only D7 master post-import audit against the exact uploaded CSV."""
from pathlib import Path
from collections import Counter
import csv,hashlib,io,json,sqlite3
from datetime import datetime,timezone
R=Path.home()/"research_artifacts"
DB=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
SOURCE=R/"mcp_uploads/arno_master_20261028/D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv"
KEY="d7_final_342_user_csv_be316e7e_20261028"
SHA="be316e7eb5708d4cf5ac71baafaf82f84fbe15fbb44deb651ac76712d24083b4"
OUT=R/"mcp_uploads/jobs/arno_20261029_d7_verify/RESULT.json"
def check(ok,msg):
 if not ok:raise RuntimeError(msg)
raw=SOURCE.read_bytes();check(hashlib.sha256(raw).hexdigest()==SHA,"CSV source SHA failed")
rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
check(len(rows)==342,"source row count")
c=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True,timeout=60)
c.execute("PRAGMA query_only=ON")
src=c.execute("SELECT embedded_bytes,source_sha256,verification FROM arno_sources WHERE source_key=?",(KEY,)).fetchone()
check(src is not None and src[0]==raw and src[1]==SHA and src[2]=="EXACT_SHA256_VERIFIED","Embedded original not identical")
dbrows={r[0]:r for r in c.execute("""SELECT root_id,case_id,repository,pc_count,final_route,final_tier,
 d7_cohort,final_route_confidence,final_explanation_confidence,chronology_status,
 evidence_complete,evidence_ids,adjudication_rationale,original_row_json,source_key
 FROM arno_d7_final_roots_342""")}
check(len(dbrows)==342,"final D7 root count")
for row in rows:
 id=row["root_id"];db=dbrows.get(id)
 check(db is not None,"missing root "+id)
 check(db[1]==int(row["case_id"]) and db[2]==row["repository"] and db[3]==int(row["pc_count"]),"record metadata mismatch "+id)
 check(db[4]==row["final_route"] and db[5]==row["final_tier"] and db[6]==row["d7_m_cohort"],"record final coding mismatch "+id)
 check(db[7]==row["final_route_confidence"] and db[8]==row["final_explanation_confidence"],"confidence mismatch "+id)
 check(db[9]==row["final_chronology_ok"] and db[10]==row["final_evidence_complete"],"evidence status mismatch "+id)
 check(db[11]==row["final_evidence_ids"] and db[12]==row["adjudication_rationale"],"evidence fields mismatch "+id)
 check(json.loads(db[13])==row and db[14]==KEY,"frozen original row mismatch "+id)
ms=dict(c.execute("SELECT root_id,final_tier FROM arno_d7_final_M_roots_233"))
check(len(ms)==233,"M233 preserved")
check(all(ms[x["root_id"]]==x["final_tier"] for x in rows if x["final_route"]=="M"),"M233 altered")
check(c.execute("SELECT COUNT(*) FROM arno_root_decisions").fetchone()[0]==342,"C6 roots altered")
check(c.execute("SELECT COUNT(*) FROM arno_pc_root_lineage").fetchone()[0]==455,"lineage count altered")
check(not c.execute("PRAGMA foreign_key_check(arno_d7_final_roots_342)").fetchone(),"D7 foreign key failure")
c.close()
result={"status":"POSTCHECK_PASS","verified_utc":datetime.now(timezone.utc).isoformat(),
"source_sha256":SHA,"original_embedded_bytes_equal_uploaded_source":True,
"final_roots":342,"route_counts":dict(Counter(x["final_route"] for x in rows)),
"existing_M233_unchanged":True,"lineage_count":455,"original_row_json_exact_matches":342,
"foreign_keys":"PASS","huggingface_updated":False}
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("x") as f:json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))
