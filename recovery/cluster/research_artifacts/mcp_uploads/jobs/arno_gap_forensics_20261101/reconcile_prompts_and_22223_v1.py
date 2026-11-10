#!/usr/bin/env python3
import json,zipfile,hashlib,sqlite3,zlib
from pathlib import Path
R=Path.home()/"research_artifacts";J=R/"mcp_uploads/jobs"
p=J/"arno_six_case_abc_preparation_20261030_r1";q=J/"arno_case22223_three_arm_eval_20261030_r1/results2"
out=J/"arno_gap_forensics_20261101/addendum_v1";out.mkdir(parents=True,exist_ok=True)
dbf=out/"RECOVERED_A_C_INPUT_PROMPTS_AND_22223.sqlite";report=out/"RESULT.json"
assert not dbf.exists() and not report.exists()
h=lambda b:hashlib.sha256(b).hexdigest()
d=sqlite3.connect(dbf)
d.executescript("CREATE TABLE initial_packets(case_id TEXT,arm TEXT,run_id TEXT,zip_name TEXT,zip_sha256 TEXT,prompt_sha256 TEXT,prompt_zlib BLOB,issue_sha256 TEXT,stage2_prompt_attested INTEGER,PRIMARY KEY(case_id,arm));CREATE TABLE recovered_22223(arm TEXT PRIMARY KEY,run_id TEXT,patch_sha256 TEXT,receipt_sha256 TEXT,sarif_sha256 TEXT,after_results INTEGER,new_warnings INTEGER,intermediate_sha256 TEXT,functional_status TEXT);CREATE TABLE recovered_22223_assets(arm TEXT,role TEXT,sha256 TEXT,data_zlib BLOB,PRIMARY KEY(arm,role));")
entries=json.loads((p/"PACKAGING_REPORT.json").read_text())["packets"]
assert len(entries)==18
for e in entries:
 file=p/"ready_initial"/e["filename"]
 with zipfile.ZipFile(file) as z:
  prompt=z.read("PROMPT.md");issue=z.read("ISSUE.md")
  assert h(issue)==e["issue_sha256"]
  assert h(file.read_bytes())==e["sha256"]
  run=e["stage2_model_run_id"] if e["arm"]=="C" else e["stage1_model_run_id"]
  d.execute("INSERT INTO initial_packets VALUES(?,?,?,?,?,?,?,?,0)",(e["case"],e["arm"],run,e["filename"],e["sha256"],h(prompt),sqlite3.Binary(zlib.compress(prompt,6)),h(issue)))
 print("PROMPT_PACKET",e["case"],e["arm"],h(prompt),flush=True)
for arm in "ABC":
 folder=q/arm;r=json.loads((folder/"RESULT.json").read_text());receipt=(folder/"RECEIPT.json").read_bytes()
 patch=(folder/"PATCH.patch").read_bytes();sarif=(folder/"after.sarif").read_bytes()
 assert h(patch)==r["patch_sha256"] and h(receipt)==r["receipt_sha256"] and h(sarif)==r["sarif_sha256"]
 assert r["baseline_total"]==r["after_total"]==41 and r["new_line_agnostic"]==0
 assert all(r[x]==0 for x in ["git_apply_check_exit","git_apply_exit","database_create_exit","codeql_analysis_exit"])
 rec=json.loads(receipt);assert rec["run_id"]==r["run_id"]
 mid=None
 extra={"B":("REVIEW.json","review_sha256"),"C":("RISKS.json","prediction_report_sha256")}.get(arm)
 if extra:
  midbytes=(folder/extra[0]).read_bytes();mid=h(midbytes)
  assert mid==rec[extra[1]]
 d.execute("INSERT INTO recovered_22223 VALUES(?,?,?,?,?,?,?,?,?)",(arm,r["run_id"],h(patch),h(receipt),h(sarif),r["after_total"],r["new_line_agnostic"],mid,r["functional_status"]))
 for role,raw in [("PATCH",patch),("RECEIPT",receipt),("AFTER_SARIF",sarif),("RESULT",(folder/"RESULT.json").read_bytes())]:
  d.execute("INSERT INTO recovered_22223_assets VALUES(?,?,?,?)",(arm,role,h(raw),sqlite3.Binary(zlib.compress(raw,6))))
 if extra:d.execute("INSERT INTO recovered_22223_assets VALUES(?,?,?,?)",(arm,extra[0],mid,sqlite3.Binary(zlib.compress(midbytes,6))))
 print("VERIFIED_22223",arm,r["run_id"],flush=True)
d.commit()
assert d.execute("PRAGMA quick_check").fetchone()[0]=="ok"
assert d.execute("SELECT count(*) FROM initial_packets").fetchone()[0]==18
assert d.execute("SELECT count(*) FROM recovered_22223").fetchone()[0]==3
d.close()
result={"status":"VERIFIED_INITIAL_PACKETS_AND_22223_SCANS","initial_prompts":18,"recovered_22223_runs":3,
"runtime_prompt_transcript_attested":False,"case22223_functionally_validated":False,
"sqlite":str(dbf),"sha256":h(dbf.read_bytes())}
report.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
