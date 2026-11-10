#!/usr/bin/env python3
import sqlite3,base64,zlib,json,hashlib,shutil,datetime
from pathlib import Path
ROOT=Path.home()/"research_artifacts"
MASTER=ROOT/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
CANDIDATE=ROOT/"mcp_uploads/jobs/arno_reviewer_release_20261031_v3/output/ARNO_REVIEWER_RESTRICTED_CANDIDATE.sqlite"
OUT=ROOT/"mcp_uploads/jobs/arno_d7_human_review_ingest_20261031_v1/result"
OUT.mkdir(parents=True,exist_ok=True)
ENCODED="eNq1WF1vozgU/S88d1R/4Y95ixq6zaptViTtPIxGFqFoGykTViSZeVjtf18bG7jMhEAqeGg4OMUn1z73+F7+DQ75qUgzfXhPSMiDzwFRnEgmWCo5pwzhRKQ0pXgjNxkRmDBJBaWIpiyRG84TJsmbDEOebMJQhZnkwU2wSY7pu5lqFj8v9Vzo2Wq1WK2juY6j10X0RYdIE0Q4RhTrV2weSPPdIfj8NSiyH9vsp96+mbEiz48Opckhc+hHVrxt06M+HJPj6WAG8mL793af7HSRn44ZHDhus8LOUs6YFbo47XXy68DGDLyfvid7fch2WXrM3uqJfhn206X593+SYnvI9/qY64os+GZ/7k8bwtcgRsiGdBcvl+tPmDJCPtmBEt0Es8dHvX6Io0jP/rCfZoFeVlGsX6N4vrhbmwft3/PtzKLb1nV/2u3cR/C8XOvZ/M8X88jMrKvhL3lJw4swCx2vRRPz0poXhTR0vBbcBCUHfOImeLIz2xV6ul083y2f/nqM1lF560brr2fru4dopb8s1quKiDVEiDNZEplrNw87y0Oqry2YL+7vo3il7+PlU4ssBGREoZLMXK8ka9/W/3YmON7w0RCxks+CPkIXzhmii9EJwMa9Ri3oZqNgk8Be0Y5wZCNGHFLlxGhRL4OLx931xqGA5s2eec0b9GFR4At0GIGoiOA+KoOmTTHcWApiBDteCyambRwFcSypSzgDpkoCDKyEEi6cLA24bCUvPq4BHoIbD8GEYhdSia4VDB0kGOAiSimXZxb0ZUHvCl5kBV4iFHXeZUGfI1e5R/pWEdgHo8hltwXdBKRFgAeFATwEUR9Gia7dKzzESzDwklBUlmXRVHInwE4YVs7zSzTQ9IcdZQRDzTNWaZ5dT9MVCGnJXFYyl0PNvkXQGUfjDpgT7gsri4bqus8dCIO6FpWuhRptoUIQAmXefiyaTGMcbj6tN5+OrDEBcpUI4XPVoGurwD7vIdAVhN+jEnmmeWR+YfxbNE3h0nvuEQVkwJCTswVX++elJaMg+5HEVSAGjV04U1A+mMPBM3E1bfVA2/0Ir/sRPlY2UQrrE9/x8LLhGVbFDtsn1spZXOcs/nCN2RUPcIeQS5+rFk28U6BeQJVHDHCIj3oSFXBFaWXkBn34YO9ikrDPUb6gNGD0FIONiFC4ciWFrxb7pZKIIeBMEjsaC8ZKKYZbba/ybe9oByADlQJi3AfA8VRSY62aAVXWR9B4EcGOQhHfglo0bdKytlnw2iz4lb3FQOVxWIyTys0Nmmzr2iUFqksKNPHCytZrJuVfM50XzENN0343AsbPRKbgeRxWPt/tt2d7z4HHV4igBfpDhZZnyrivzb799z8ps3RY"
payload=json.loads(zlib.decompress(base64.b64decode(ENCODED)))
assert len(payload["rows"])==50
fields=payload["cols"]
assert len(set(tuple(row)[0] for row in payload["rows"]))==50
source=sqlite3.connect("file:"+str(MASTER)+"?mode=ro",uri=True,timeout=120)
problems=[]
counts={"USER_ADJUDICATED":0,"ALL_THREE_AGREE_NO_USER_VERDICT":0,"USER_DEFERRED":0}
records=[]
for values in payload["rows"]:
 r=dict(zip(fields,values));root=r["root_id"]
 historical=source.execute("SELECT case_id,final_route,final_tier FROM arno_d7_final_roots_342 WHERE root_id=?",(root,)).fetchone()
 if historical is None or (int(historical[0]),historical[1],str(historical[2]).replace('/',''))!=(int(r["case_id"]),r["original_route"],str(r["original_tier"]).replace('/','')):
  problems.append([r["review_id"],root,"WITS_MASTER_REFERENCE_MISMATCH"])
 if r["verdict_status"] not in counts:problems.append([r["review_id"],root,"INVALID_VERDICT_STATUS"])
 else:counts[r["verdict_status"]]+=1
 if r["verdict_status"]=="USER_ADJUDICATED" and not (r["human_selected_route"] and r["human_selected_tier"]):
  problems.append([r["review_id"],root,"MISSING_USER_FINAL"])
 if r["verdict_status"]!="USER_ADJUDICATED" and (r["human_selected_route"] or r["human_selected_tier"]):
  problems.append([r["review_id"],root,"NON_HUMAN_ROW_HAS_USER_FINAL"])
 records.append(r)
source.close()
assert not problems,problems
assert counts=={"USER_ADJUDICATED":41,"ALL_THREE_AGREE_NO_USER_VERDICT":8,"USER_DEFERRED":1}
assert sum(r["comparison_to_original"]=="DIFFERS_FROM_WITS" for r in records)==17
assert sum(r["comparison_to_original"]=="MATCHES_WITS" for r in records)==24
assert sum((r["human_selected_route"]==r["original_route"]) for r in records if r["human_selected_route"])==41
TARGET=OUT/"ARNO_REVIEWER_WITH_D7_ASSISTED_ANNOTATIONS_20261031.sqlite"
assert not TARGET.exists(),"Refusing to overwrite an existing reviewer output"
shutil.copy2(CANDIDATE,TARGET)
conn=sqlite3.connect(str(TARGET),timeout=120)
conn.executescript("""
CREATE TABLE human_review_batches(
 batch_id TEXT PRIMARY KEY,source_workbook_sha256 TEXT NOT NULL,
 source_sample_sha256 TEXT NOT NULL,review_mode TEXT NOT NULL,
 selected_verdicts INTEGER NOT NULL,consensus_without_user_verdict INTEGER NOT NULL,
 deferred_cases INTEGER NOT NULL,independent_blind_human_raters INTEGER NOT NULL,
 annotation_reason_source TEXT NOT NULL);
CREATE TABLE human_review_labels(
 batch_id TEXT NOT NULL REFERENCES human_review_batches(batch_id),
 review_id TEXT NOT NULL,root_id TEXT NOT NULL,case_id INTEGER NOT NULL,
 verdict_status TEXT NOT NULL,original_route TEXT,original_tier TEXT,
 run_a_label TEXT,run_b_label TEXT,human_selected_route TEXT,human_selected_tier TEXT,
 comparison_to_original TEXT,reason_sha256 TEXT,
 full_source_record_sha256 TEXT,PRIMARY KEY(batch_id,review_id),UNIQUE(batch_id,root_id));
CREATE INDEX human_review_by_root ON human_review_labels(root_id);
CREATE INDEX human_review_by_case ON human_review_labels(case_id);
CREATE VIEW review_d7_cases_findings AS
 SELECT h.review_id,h.root_id,h.case_id,h.verdict_status,h.human_selected_route,h.human_selected_tier,
 h.original_route,h.original_tier,c.repository,f.finding_id,f.scanner,f.rule_id,f.file_path,
 f.description AS scanner_description
 FROM human_review_labels h JOIN research_cases c ON c.case_id=h.case_id
 LEFT JOIN mined_findings f ON f.case_id=h.case_id;
""")
conn.execute("INSERT INTO human_review_batches VALUES (?,?,?,?,?,?,?,?,?)",
 (payload["batch"],payload["sha"],payload["sample_sha"],"POST_HOC_AI_ASSISTED_USER_SELECTION_NOT_BLIND",41,8,1,0,
  "Full reasons and 227 supporting evidence rows are archived in the matching local supplementary SQLite and uploaded workbook; source SHA recorded here"))
for r in records:
 conn.execute("INSERT INTO human_review_labels VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
  (payload["batch"],r["review_id"],r["root_id"],r["case_id"],r["verdict_status"],
  r["original_route"],r["original_tier"],r["reviewer_run_a"],r["reviewer_run_b"],
  r["human_selected_route"],r["human_selected_tier"],r["comparison_to_original"],r["reason_sha"],r["full_flat_record_sha"]))
conn.commit()
assert conn.execute("PRAGMA quick_check").fetchone()[0]=="ok"
assert conn.execute("SELECT COUNT(*) FROM human_review_labels").fetchone()[0]==50
assert conn.execute("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='USER_ADJUDICATED'").fetchone()[0]==41
assert conn.execute("SELECT COUNT(*) FROM human_review_labels WHERE verdict_status='USER_DEFERRED' AND human_selected_route IS NULL").fetchone()[0]==1
conn.close()
report={"result":"PASS","source_master_read_only":True,"reviewer_candidate_unchanged":True,
 "target":str(TARGET),"target_bytes":TARGET.stat().st_size,
 "target_sha256":hashlib.sha256(TARGET.read_bytes()).hexdigest(),
 "workbook_sha256":payload["sha"],"records":len(records),"outcomes":counts,
 "primary_route_agreements":41,"full_label_agreements":24,"full_label_disagreements":17,
 "exact_Wits_root_id_case_id_reference_validated":50,"full_reason_material":"LOCAL_SIDE_CAR_AND_IMMUTABLE_WORKBOOK"}
(OUT/"IMPORT_VERIFIED.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2),flush=True)
