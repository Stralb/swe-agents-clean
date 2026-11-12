#!/usr/bin/env python3
from pathlib import Path
import ast,base64,hashlib,json,zipfile,stat
ROOT=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_ac_six_v6_20261030_r1"
EXPECTED_SHA="d0319135b633c5c0d949e705af4ad99f7a415bd2cd6357d9fbe101bebf3e27b1"
EXPECTED_SIZE=76512
cases=["03429","03581","08152","12344","31207","32759"]
arms=[("A","MECHANISM"),("C","PROSPECTIVE_BUILD")]
parts=[]
for i in range(12):
 p=ROOT/("in_%02d.py"%i)
 t=p.read_text()
 assert t.startswith("DATA = ")
 v=ast.literal_eval(t[7:])
 assert isinstance(v,str) and v and all(ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for ch in v)
 parts.append(v)
raw=base64.b64decode("".join(parts),validate=True)
assert len(raw)==EXPECTED_SIZE
assert hashlib.sha256(raw).hexdigest()==EXPECTED_SHA
out=ROOT/"evidence"
out.mkdir(parents=False,exist_ok=False)
zip_path=out/"ARNO_A_C_ALL12_EVIDENCE_INPUT.zip"
zip_path.write_bytes(raw)
report={"archive_sha256":EXPECTED_SHA,"bytes":len(raw),"status":"CHECKING","cases":[]}
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 names=z.namelist()
 assert len(names)==30 and len(set(names))==len(names)
 expected=set()
 for case in cases:
  for arm,suffix in arms:
   rid="PILOT"+case+"_"+suffix+"_R1"
   expected.update({"PATCH_"+rid+".patch","RECEIPT_"+rid+".json"})
  expected.add("RISKS_PILOT"+case+"_PROSPECTIVE_PREDICT_R1.json")
 assert set(names)==expected
 for info in z.infolist():
  assert info.file_size<5000000
  assert ((info.external_attr>>16)&0o170000)!=stat.S_IFLNK
  assert not info.is_dir() and "/" not in info.filename and "\\" not in info.filename
 for case in cases:
  row={"case":case,"arms":{}}
  risk_name="RISKS_PILOT"+case+"_PROSPECTIVE_PREDICT_R1.json"
  risk=z.read(risk_name);risksha=hashlib.sha256(risk).hexdigest()
  assert json.loads(risk)["run_id"]=="PILOT"+case+"_PROSPECTIVE_PREDICT_R1"
  for arm,suffix in arms:
   rid="PILOT"+case+"_"+suffix+"_R1"
   pn="PATCH_"+rid+".patch";rn="RECEIPT_"+rid+".json"
   patch=z.read(pn);receipt=z.read(rn);rec=json.loads(receipt)
   assert rec["run_id"]==rid
   assert patch.startswith(b"diff --git a/")
   if arm=="C":assert rec["prediction_report_sha256"]==risksha
   row["arms"][arm]={"patch_sha256":hashlib.sha256(patch).hexdigest(),"receipt_sha256":hashlib.sha256(receipt).hexdigest(),"generation_status":rec.get("generation_status","UNSPECIFIED")}
   (out/pn).write_bytes(patch);(out/rn).write_bytes(receipt)
  (out/risk_name).write_bytes(risk)
  report["cases"].append(row)
report["status"]="ALL_30_FILES_VERIFIED"
(out/"INTEGRITY.json").write_text(json.dumps(report,indent=2))
print(json.dumps({"status":report["status"],"files":len(names),"sha256":EXPECTED_SHA}),flush=True)
