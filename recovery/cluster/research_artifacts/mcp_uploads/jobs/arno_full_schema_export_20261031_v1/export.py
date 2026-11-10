#!/usr/bin/env python3
"""Read-only SQLite schema export, no source data copied."""
import csv
import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
from collections import defaultdict
root=Path.home()/"research_artifacts"
db=root/"ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite"
out=root/"mcp_uploads/jobs/arno_full_schema_export_20261031_v1/output"
out.mkdir(parents=True,exist_ok=True)
con=sqlite3.connect("file:"+quote(str(db))+"?mode=ro",uri=True,timeout=90)
con.row_factory=sqlite3.Row
con.execute("PRAGMA query_only=ON")
records=[dict(r) for r in con.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE type IN ('table','index','view','trigger') ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 WHEN 'view' THEN 2 ELSE 3 END,name")]
objs=[r for r in records if not r["name"].startswith("sqlite_")]
counts={kind:sum(r["type"]==kind for r in objs) for kind in ["table","index","view","trigger"]}
assert counts["table"]>=126 and counts["view"]>=7 and counts["index"]>=19,counts
def family(name):
 if not name.startswith("arno_"):return "00_CORE_MINING_PIPELINE"
 if any(x in name for x in ("owp14","rq3_","screen65","seven_final","recovered_agent","generated_patches","experiment_","chat_","patch_fragment","exp_transfer")):return "30_RQ3_PATCHES_SCANNER_EXPERIMENTS"
 if any(x in name for x in ("rq2_","matched_control_","c6_","choice_")):return "20_RQ2_MATCHED_CONTROLS_STATISTICS"
 if any(x in name for x in ("new70","d7_","D_root","root_decisions","pc_root","classifications","annotation_events","canonical_id","cohort","original_","frozen_broad","mechanism_selection")):return "10_RQ1_FINDINGS_CLASSIFICATION_ROOTS"
 return "40_EVIDENCE_VAULT_MANIFESTS_PROVENANCE"
def csvout(name,cols,entries):
 with (out/name).open("w",newline="",encoding="utf8") as f:
  w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader();w.writerows(entries)
tables=[];columns=[];fkeys=[];indexes=[];views=[]
for obj in objs:
 if obj["type"]=="table":
  n=obj["name"];qn=n.replace('"','""')
  cols=[dict(x) for x in con.execute('PRAGMA table_xinfo("'+qn+'")')]
  keys=[dict(x) for x in con.execute('PRAGMA foreign_key_list("'+qn+'")')]
  ix=[dict(x) for x in con.execute('PRAGMA index_list("'+qn+'")')]
  tables.append(dict(table=n,family=family(n),column_count=len(cols),primary_key_columns=",".join(x["name"] for x in cols if x["pk"]>0),foreign_key_links=len(keys),indexes=len(ix)))
  for c in cols:columns.append(dict(table=n,family=family(n),cid=c["cid"],column=c["name"],type=c["type"],not_null=c["notnull"],default_value=c["dflt_value"],pk_position=c["pk"],hidden=c["hidden"]))
  for fk in keys:fkeys.append(dict(from_table=n,fk_id=fk["id"],sequence=fk["seq"],from_column=fk["from"],to_table=fk["table"],to_column=fk["to"],on_update=fk["on_update"],on_delete=fk["on_delete"],match=fk["match"]))
  for idx in ix:indexes.append(dict(table=n,index_name=idx["name"],unique=idx["unique"],origin=idx["origin"],partial=idx["partial"]))
 elif obj["type"]=="view":views.append(dict(name=obj["name"],sql=obj["sql"]))
assert len(tables)==counts["table"]
now=datetime.now(timezone.utc).isoformat()
ddl="-- Complete ARNO Wits master SQLite schema; contains DDL only, NOT data.\n-- Export: "+now+"\n-- Source: "+str(db)+"\n-- Opened file in SQLite URI mode=ro with PRAGMA query_only=ON.\n\nBEGIN TRANSACTION;\n\n"
for o in objs:
 if o["sql"]:ddl+="-- "+o["type"].upper()+": "+o["name"]+"\n"+o["sql"].rstrip().rstrip(";")+";\n\n"
ddl+="COMMIT;\n"
(out/"ARNO_MASTER_FULL_SCHEMA.sql").write_text(ddl,encoding="utf8")
csvout("ALL_TABLES.csv",["family","table","column_count","primary_key_columns","foreign_key_links","indexes"],tables)
csvout("ALL_COLUMNS.csv",["family","table","cid","column","type","not_null","default_value","pk_position","hidden"],columns)
csvout("FOREIGN_KEYS.csv",["from_table","fk_id","sequence","from_column","to_table","to_column","on_update","on_delete","match"],fkeys)
csvout("ALL_INDEXES_INCLUDING_AUTO.csv",["table","index_name","unique","origin","partial"],indexes)
csvout("VIEWS.csv",["name","sql"],views)
catalog={"exported_utc":now,"source_path":str(db),"source_file_bytes":db.stat().st_size,"sqlite_version":sqlite3.sqlite_version,"counts":counts,
 "total_columns":len(columns),"fk_links":len(fkeys),"index_count_including_auto":len(indexes),
 "schema_objects":objs,"tables":tables,"columns":columns,"foreign_keys":fkeys,"indexes":indexes,"views":views,
 "schema_only":True,"hf_copy_verified_identical":False,"user_computer_copy_verified_identical":False}
(out/"ARNO_MASTER_SCHEMA_CATALOG.json").write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
lines=["# Complete ARNO Master SQLite Schema","",
 "The authoritative live source is the Wits cluster master, not the August Hugging Face dataset.",
 "This package contains no database contents and is NOT a backup.",
 "",
 "Exported UTC: "+now,
 "Source database: "+str(db),
 "Source database bytes: "+str(db.stat().st_size),
 "SQLite version: "+sqlite3.sqlite_version,
 "Tables: "+str(counts["table"]),
 "Views: "+str(counts["view"]),
 "Explicit indexes: "+str(counts["index"]),
 "Triggers: "+str(counts["trigger"]),
 "Declared columns: "+str(len(columns)),
 "Foreign key column links: "+str(len(fkeys)),
 "Indexes including autoindexes: "+str(len(indexes)),
 "",
 "## Package contents","",
 "ARNO_MASTER_FULL_SCHEMA.sql - exact CREATE TABLE, INDEX and VIEW DDL for all schema objects.",
 "ARNO_MASTER_SCHEMA_CATALOG.json - machine readable schema including columns and foreign keys.",
 "ALL_TABLES.csv - all table names and logical groupings.",
 "ALL_COLUMNS.csv - full column inventory and types.",
 "FOREIGN_KEYS.csv - declared relationships.",
 "ALL_INDEXES_INCLUDING_AUTO.csv - indexes and constraints.",
 "VIEWS.csv - view SQL text.",
 "MANIFEST_SHA256.json - hashes and bytes for exported files.",
 "",
 "## Core evidence chain","",
 "arno_experiment_runs.run_id connects to arno_generated_patches, arno_experiment_scans, arno_chat_codeql_metrics, arno_chat_codeql_findings, and arno_chat_evidence_objects.",
 "arno_owp14_fresh_o_reruns_20261031 marks the two October 31 non-blind reruns, not recovered historical O-arm outputs.",
 "",
 "## All tables grouped by research component",""]
by=defaultdict(list)
for x in tables:by[x["family"]].append(x["table"])
for k,v in sorted(by.items()):
 lines.extend(["### "+k+" ("+str(len(v))+" tables)","",", ".join(v),""])
lines+=["## Sync caveat","","This schema came from Wits. No October master upload to Hugging Face has been verified. A personal computer copy has not been hash-compared.",""]
(out/"README_SCHEMA.md").write_text("\n".join(lines),encoding="utf8")
manifest={}
for f in out.iterdir():
 if f.is_file():manifest[f.name]={"bytes":f.stat().st_size,"sha256":hashlib.sha256(f.read_bytes()).hexdigest()}
(out/"MANIFEST_SHA256.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf8")
pack=out/"ARNO_MASTER_COMPLETE_SCHEMA_20261031.zip"
with zipfile.ZipFile(pack,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for f in sorted(out.iterdir()):
  if f.is_file() and f.name!=pack.name:z.write(f,arcname=f.name)
print(json.dumps({"status":"SCHEMA_EXPORTED_READONLY","zip":str(pack),"zip_bytes":pack.stat().st_size,"counts":counts,"columns":len(columns),"fk_links":len(fkeys),"all_indexes_including_auto":len(indexes)},indent=2))
con.close()
