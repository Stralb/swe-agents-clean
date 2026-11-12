#!/usr/bin/env python3
import csv,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2/seven_case_scans_20261020"
CASES=["03429","03581","08152","12344","22223","31207","32759"]
rows=[]
alerts=[]
for case in CASES:
 f=ROOT/case/"RESULT.json"
 assert f.is_file(),f
 d=json.loads(f.read_text())
 assert d["case"]==case and d["scan_completed"] and d["apply_check"]=="PASS"
 rows.append({"case":case,"baseline":d["baseline_count"],"patched":d["patched_count"],"new_fingerprint":d["new_strong_count"],"new_conservative":d["new_conservative_count"],"scanner_negative_both":d["new_strong_count"]==0 and d["new_conservative_count"]==0,"patch_sha256":d["patch_sha256"],"source_sha256":d["source_sha256"],"functional_validity":"NOT VERIFIED"})
 for a in d["new_strong"]:
  alerts.append({"case":case,"rule":a["rule"],"path":a["uri"],"line":a["line"],"message":a["message"]})
def csvdata(xs):
 s=io.StringIO()
 if not xs:return b""
 w=csv.DictWriter(s,fieldnames=list(xs[0]))
 w.writeheader();w.writerows(xs)
 return s.getvalue().encode()
summary="# Seven-case new CodeQL evaluation, 2026-10-20\n\n"
summary+="CodeQL 2.25.6, JavaScript security-extended. Seven unique patches, because P1/P2/P3 were byte-identical within each case. Functionality is NOT verified. No minimum safety text can be concluded.\n\n"
summary+="| Case | Before | After | New (fingerprint) | New (conservative) | Scanner-negative |\n|---|---:|---:|---:|---:|---|\n"
for x in rows:
 summary+="| {case} | {baseline} | {patched} | {new_fingerprint} | {new_conservative} | {scanner_negative_both} |\n".format(**x)
summary+="\nThe 12344 discrepancy (7 fingerprint vs 6 conservative) is preserved as an unresolved identity/granularity disagreement; no automatic normalization is assumed. Inspect both before/after SARIF.\n\n## Finding detail\n"
for a in alerts:summary+="\n- {case}: {rule}, {path}:{line} — {message}".format(**a)
summary+="\n\nZero new CodeQL findings does not prove security or functional completeness.\n"
out=ROOT/"SEVEN_CASE_CODEQL_COMPLETE_RESULTS_20261020.zip"
with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 z.writestr("SUMMARY.md",summary)
 z.writestr("RESULTS.csv",csvdata(rows))
 z.writestr("NEW_ALERTS.csv",csvdata(alerts))
 z.writestr("MANIFEST.json",json.dumps({"cases":CASES,"patches_unique":7,"results":rows,"matching_disagreement":{"case":"12344","fingerprint":7,"conservative":6}},indent=2))
 for case in CASES:
  for f in (ROOT/case).iterdir():
   if f.is_file() and f.name!="ERROR.txt":
    z.write(f,"CASES/"+case+"/"+f.name)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
print(json.dumps({"zip":str(out),"bytes":out.stat().st_size,"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"cases":len(rows)},indent=2))
print(summary)
