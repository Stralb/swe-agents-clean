#!/usr/bin/env python3
import sqlite3,csv,json,hashlib,datetime,zipfile,lzma,base64,collections
from pathlib import Path
from urllib.parse import quote
R=Path.home()/"research_artifacts"
OUT=R/"mcp_uploads/jobs/arno_d7_primary50_20261031_v1/output"
OUT.mkdir(parents=True,exist_ok=True)
assert not any(OUT.iterdir()),"No overwrite allowed"
pairs="""R001|CROOT-13422-01|13422
R002|CROOT-10145-01|10145
R003|CROOT-05355-01|5355
R004|CROOT-00648-01|648
R005|CROOT-00290-01|290
R006|CROOT-03504-01|3504
R007|CROOT-03622-01|3622
R008|CROOT-11539-01|11539
R009|CROOT-10005-01|10005
R010|CROOT-11276-01|11276
R011|CROOT-04216-01|4216
R012|CROOT-06183-01|6183
R013|CROOT-03267-01|3267
R014|CROOT-12313-01|12313
R015|CROOT-09992-01|9992
R016|CROOT-07930-01|7930
R017|CROOT-04309-01|4309
R018|CROOT-10330-01|10330
R019|CROOT-15739-01|15739
R020|CROOT-14194-01|14194
R021|CROOT-12344-01|12344
R022|CROOT-09998-01|9998
R023|CROOT-16262-01|16262
R024|CROOT-04379-01|4379
R025|CROOT-16343-01|16343
R026|CROOT-12334-01|12334
R027|CROOT-10277-01|10277
R028|CROOT-10779-01|10779
R029|CROOT-04408-01|4408
R030|CROOT-10819-01|10819
R031|CROOT-00169-01|169
R032|CROOT-10146-01|10146
R033|CROOT-06145-01|6145
R034|CROOT-16341-01|16341
R035|CROOT-15684-01|15684
R036|CROOT-00334-01|334
R037|CROOT-16332-01|16332
R038|CROOT-03697-01|3697
R039|CROOT-10791-01|10791
R040|CROOT-04811-01|4811
R041|CROOT-00299-01|299
R042|CROOT-00461-01|461
R043|CROOT-16209-01|16209
R044|CROOT-12925-01|12925
R045|CROOT-15686-01|15686
R046|CROOT-10326-01|10326
R047|CROOT-10270-01|10270
R048|CROOT-00649-01|649
R049|CROOT-00154-01|154
R050|CROOT-03684-01|3684"""
pairs=[s.split("|") for s in pairs.splitlines()]
assert len(pairs)==50 and len(set(x[1] for x in pairs))==50
master=R/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
db=sqlite3.connect("file:"+quote(str(master))+"?mode=ro",uri=True,timeout=120)
db.row_factory=sqlite3.Row
db.execute("PRAGMA query_only=ON")
hdr=["review_id","root_id","case_id","original_wits_route","original_wits_tier","original_wits_decision_id","original_wits_rationale","original_wits_source_path","original_decision_created_utc","original_decision_updated_utc","raw_export_generated_utc"]
now=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rows=[];sources=[];conflicts=[]
for review_id,root_id,case_id in pairs:
 rec=db.execute("""SELECT d.root_id,d.case_id,d.final_route,d.final_tier,
 d.adjudication_rationale,d.original_row_json,d.source_key,
 s.source_locator,s.source_sha256,s.verification,s.source_kind
 FROM arno_d7_final_roots_342 d LEFT JOIN arno_sources s
 ON s.source_key=d.source_key WHERE d.root_id=?""",(root_id,)).fetchone()
 assert rec is not None and str(rec["case_id"])==case_id,(review_id,root_id,case_id)
 j=json.loads(rec["original_row_json"])
 for key,col in [("final_route","final_route"),("final_tier","final_tier"),("adjudication_rationale","adjudication_rationale")]:
  if key in j and j[key]!=rec[col]: conflicts.append([review_id,key,j[key],rec[col]])
 created=next((str(j[k]) for k in ["original_decision_created_utc","decision_created_utc","created_at","created_utc"] if j.get(k)), "")
 updated=next((str(j[k]) for k in ["original_decision_updated_utc","decision_updated_utc","updated_at","updated_utc"] if j.get(k)), "")
 rows.append(dict(review_id=review_id,root_id=root_id,case_id=case_id,original_wits_route=rec["final_route"],
 original_wits_tier=rec["final_tier"],original_wits_decision_id=rec["root_id"],
 original_wits_rationale=rec["adjudication_rationale"],original_wits_source_path=rec["source_locator"] or "",
 original_decision_created_utc=created,original_decision_updated_utc=updated,raw_export_generated_utc=now))
 sources.append(dict(root_id=root_id,source_key=rec["source_key"],source_locator=rec["source_locator"],
 source_sha256=rec["source_sha256"],source_verification=rec["verification"],source_kind=rec["source_kind"],
 original_row_json_sha256=hashlib.sha256(rec["original_row_json"].encode()).hexdigest()))
assert len(rows)==50
name="ARNO_D7_REQUIRED_PRIMARY_WITS_REFERENCE_EXPORT_FILLED.csv"
with (OUT/name).open("w",encoding="utf-8-sig",newline="") as f:
 w=csv.DictWriter(f,fieldnames=hdr);w.writeheader();w.writerows(rows)
manifest={"source_table":"arno_d7_final_roots_342","source_metadata_table":"arno_sources",
"rows":len(rows),"route_counts":dict(collections.Counter(r["original_wits_route"] for r in rows)),
"rationale_nonempty":sum(bool(r["original_wits_rationale"]) for r in rows),
"created_timestamps_found":sum(bool(r["original_decision_created_utc"]) for r in rows),
"updated_timestamps_found":sum(bool(r["original_decision_updated_utc"]) for r in rows),
"source_record_json_conflicts":conflicts,"per_row_source":sources,"exported_utc":now,
"original_wits_decision_id_definition":"D7 table PRIMARY KEY root_id; no separate decision_id column",
"original_wits_source_path_definition":"arno_sources.source_locator via D7 source_key",
"rationale_definition":"D7 adjudication_rationale verbatim; no invented rationale",
"missing_timestamp_policy":"Leave blank if no timestamp in original table or preserved original JSON"}
(OUT/"WITS_ORIGINAL_DECISION_PROVENANCE.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
(OUT/"README.txt").write_text("Exact 50-row template filled using Wits D7 final-root decisions. Rationale from adjudication_rationale. Decision ID is the D7 root_id primary key. Source path is arno_sources.source_locator. Original created/updated timestamps are blank if absent, distinct from raw_export_generated_utc. Original human review not inferred. No database records were modified.")
with zipfile.ZipFile(OUT/"WITS_PRIMARY_D7_50_BUNDLE.zip","w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for fn in [name,"WITS_ORIGINAL_DECISION_PROVENANCE.json","README.txt"]:z.write(OUT/fn,fn)
raw=(OUT/"WITS_PRIMARY_D7_50_BUNDLE.zip").read_bytes()
(OUT/"TRANSFER_LZMA_BASE64.txt").write_text(base64.b64encode(lzma.compress(raw,preset=9)).decode())
print(json.dumps({"status":"COMPLETE","rows":len(rows),"rationale_nonempty":manifest["rationale_nonempty"],
"timestamps_created":manifest["created_timestamps_found"],"timestamps_updated":manifest["updated_timestamps_found"],
"source_conflicts":len(conflicts),"csv_bytes":(OUT/name).stat().st_size,
"zip_bytes":len(raw),"b64_chars":(OUT/"TRANSFER_LZMA_BASE64.txt").stat().st_size}))
db.close()
