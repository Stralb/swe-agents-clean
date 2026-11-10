#!/usr/bin/env python3
import csv,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2/seven_case_scans_20261020"
CASES=["03429","03581","08152","12344","22223","31207","32759"]
records=[]
alerts=[]
for case in CASES:
 path=ROOT/case/"RESULT.json"
 if not path.is_file():raise RuntimeError("MISSING COMPLETED SCAN "+str(path))
 result=json.loads(path.read_text())
 assert result["case"]==case and result["scan_completed"] and result["apply_check"]=="PASS"
 assert result["new_strong_count"]==result["new_conservative_count"],("matching differs",case)
 records.append({"case":case,"codeql_version":"2.25.6","baseline":result["baseline_count"],"patched":result["patched_count"],"new":result["new_strong_count"],"scanner_negative":result["new_strong_count"]==0,"patch_sha256":result["patch_sha256"],"source_sha256":result["source_sha256"],"functionality":"NOT VERIFIED"})
 for a in result["new_strong"]:
  alerts.append({"case":case,"rule":a["rule"],"path":a["uri"],"line":a["line"],"message":a["message"]})
out=ROOT/"SEVEN_CASE_CODEQL_RESULTS_20261020.zip"
def as_csv(rows):
 if not rows:return b""
 s=io.StringIO()
 w=csv.DictWriter(s,fieldnames=list(rows[0]))
 w.writeheader();w.writerows(rows)
 return s.getvalue().encode("utf-8")
head="# Seven-case CodeQL evaluation\n\nCodeQL 2.25.6, javascript-security-extended. Seven UNIQUE implementations; P1/P2/P3 per case were identical, so the experiment cannot establish minimum added information. Functional correctness is NOT verified.\n\n"
table="| Case | Baseline | Patched | New warnings | Scanner-negative? |\n|---|---:|---:|---:|---|\n"
for r in records:
 table+="| {case} | {baseline} | {patched} | {new} | {scanner_negative} |\n".format(**r)
summary=head+table+"\n## Newly introduced findings\n\n"
for a in alerts:
 summary+="- {case}: {rule} at {path}:{line}: {message}\n".format(**a)
summary+="\nResults include both test and production code; interpret paths accordingly. SARIF strong and conservative differential counts agree. Zero CodeQL warnings does not prove actual security or functionality.\n"
with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=7,allowZip64=True) as z:
 z.writestr("SUMMARY.md",summary)
 z.writestr("RESULTS.csv",as_csv(records))
 z.writestr("NEW_ALERTS.csv",as_csv(alerts) if alerts else "case,rule,path,line,message\n")
 for case in CASES:
  for f in (ROOT/case).iterdir():
   if f.is_file() and f.name!="ERROR.txt":z.write(f,"CASES/"+case+"/"+f.name)
 z.writestr("MANIFEST.json",json.dumps({"case_ids":CASES,"unique_patches":7,"duplicate_treatments":["P2","P3"],"results":records},indent=2))
with zipfile.ZipFile(out) as z:assert z.testzip() is None
print("ARCHIVE",out,out.stat().st_size,hashlib.sha256(out.read_bytes()).hexdigest())
print(summary)
