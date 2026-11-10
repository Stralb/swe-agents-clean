#!/usr/bin/env python3
from pathlib import Path
import csv,json
root=Path.home()/"research_artifacts"
p=root/"prevention_pilot_phase2"
out=p/"seven_case_complete_handoff_20261020/WORKING"
ids=["03429","03581","08152","12344","22223","31207","32759"]
stages={
 "03429":[("FIRST_AGENT","seven_case_scans_20261020/03429"),("REPAIR_V2","seven_case_targeted_fixes_20261020/03429"),("FINAL_TEST_FIXTURE","seven_case_targeted_v3_20261020/03429")],
 "03581":[("FIRST_AGENT","seven_case_scans_20261020/03581")],
 "08152":[("FIRST_AGENT","seven_case_scans_20261020/08152"),("REPAIR_V2_URL_MOCK","seven_case_targeted_fixes_20261020/08152"),("FINAL_GRAMMY_FILES","provider_variants_20261020_retry/scans/08152")],
 "12344":[("FIRST_AGENT","seven_case_scans_20261020/12344"),("FINAL_CANONICAL_FILENAME","seven_case_targeted_fixes_20261020/12344")],
 "22223":[("FIRST_AGENT","seven_case_scans_20261020/22223")],
 "31207":[("FIRST_AGENT","seven_case_scans_20261020/31207"),("REPAIR_V2_RESTRICT_CORS","seven_case_targeted_fixes_20261020/31207"),("FINAL_RUNTIME_SECRET","provider_variants_20261020/scans/31207")],
 "32759":[("FIRST_AGENT","seven_case_scans_20261020/32759")],
}
rows=[];alerts=[]
for cid in ids:
 for label,folder in stages[cid]:
  f=p/folder/"RESULT.json"
  assert f.is_file(),str(f)
  x=json.loads(f.read_text())
  assert x["case"]==cid, (cid,label)
  if label=="FIRST_AGENT":
   before=x.get("baseline_count");after=x.get("patched_count");s=x.get("new_strong_count");w=x.get("new_conservative_count")
  elif label in ("FINAL_GRAMMY_FILES","FINAL_RUNTIME_SECRET"):
   before=x.get("baseline_count");after=x.get("patched_count");s=x.get("new_strong_count");w=x.get("new_conservative_count")
  else:
   before=x.get("before_count");after=x.get("after_count");s=x.get("new_strong_count");w=x.get("new_conservative_count")
  assert all(isinstance(v,int) for v in (before,after,s,w)),(cid,label,(before,after,s,w))
  record={"case":cid,"stage":label,"before_total":before,"after_total":after,"new_fingerprint":s,"new_conservative":w,"zero_new_both":s==0 and w==0,"source_path":str(f.relative_to(root))}
  rows.append(record)
  for a in x.get("new_strong",[]) or x.get("new_alerts",[]):
   alerts.append({"case":cid,"stage":label,"rule":a.get("rule"),"path":a.get("uri"),"line":a.get("line"),"message":a.get("message"),"fingerprints":json.dumps(a.get("fingerprints",{}),sort_keys=True)})
 assert rows[-1]["zero_new_both"],"FINAL scanner negative expected "+cid
assert len(rows)==14,(len(rows),[v["stage"] for v in rows])
def writecsv(name,data):
 with (out/name).open("w",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
writecsv("FOURTEEN_STAGE_RESULTS.csv",rows)
if alerts:writecsv("INTRODUCED_ALERTS_ALL_STAGES.csv",alerts)
text=["# Per-stage CodeQL results; 7 cases, 14 scan stages","",
"CodeQL 2.25.6, JavaScript security-extended. ALL counts are vs EACH CASE'S pristine frozen original source. A baseline may have hundreds of old findings; only DIFFERENTIAL NEW alerts are the evaluation variable.",
"",
"| Case | Stage | Before | After | NEW fingerprint | NEW conservative | Both 0? |",
"|---|---|---:|---:|---:|---:|---|"]
for x in rows:
 text.append("| {case} | {stage} | {before_total} | {after_total} | {new_fingerprint} | {new_conservative} | {zero_new_both} |".format(**x))
text+=["",
"Difference between 12344 original first-agent strong fingerprint 7 and conservative 6 MUST be retained: identity/granularity ambiguity. A net reduction of total alerts does not mean zero new findings.",
"",
"All seven latest selected patches scanner-negative: 03581, 22223 and 32759 on the first unique agent implementation; 03429, 08152, 12344 and 31207 after researcher-directed repair(s). Full integration acceptance is incomplete.",
"",
"Classify FIRST_AGENT separately from researcher-guided stages. Original 21 submitted candidate files were byte-identical across P1/P2/P3 within each case. No information-minimization causal conclusion can be drawn.",
"",
"## Provenance/functional validity gates",
"",
"- Filtered/provisional snapshots: 03429, 12344 and 31207; historical issue-as-of-PR and full source not verified.",
"- 03429 final zero signal changes an already-existing test fixture, not only newly added feature code.",
"- 08152 three voice unit tests pass, but tsc missing and @grammyjs/files dependency lockfile/integration absent.",
"- 12344 native Windows DPAPI/key-store correctness unverified.",
"- 31207 short-lived process environment carries Docker-file-origin PAT; this may hide CodeQL taint without improving actual security. Node probe unit test 1/1.",
"- 32759 real Windows npm .cmd/.ps1 shims and arguments have not been verified on Windows.",
"- 03581 requires live VS Code webview host/Claude commentary tests; 22223 requires authenticated browser download tests.",
"",
"## SARIF evidence",
"",
"Full first-stage baseline/after SARIF and logs: CODEQL_FIRST_SEVEN / original first scan directories.",
"Targeted stage SARIF/patches: CODEQL_REPAIRS; last two: CODEQL_LAST_TWO.",
"Historic O/W/P: EARLIER_EXPERIMENTS/03_CODEQL_SARIF_AND_SCANS.zip and EVIDENCE_65/OWP14_NEW_ALERTS_ALL_ARMS.json.",
"Other 65 original-task runs: EVIDENCE_65/ROUND_R1_R2_R3_CASE_RESULT_JSON plus 65-row matrix.",
"Use exact rule+path+message and fingerprints; distinguish on-added-line from existing sinks made reachable.",
"",
"## Historical O/W/P paired results (not random matched)",
"",
"| Case | O | W | P | Historical target reproduced? |",
"|---|---:|---:|---:|---|",
"| 03429 | 1 | 1 | 0 | yes |",
"| 03581 | 3 | 1 | 1 | yes (race removed by W/P) |",
"| 08152 | 2 | 1 | 2 | yes (file-to-HTTP persists) |",
"| 12344 | 6 | 3 | 6 | NO (historical ReDoS absent) |",
"| 22223 | 2 | 1 | 2 | yes (network-to-file persists) |",
"| 31207 | 2 | 0 | 2 | yes, but W removed required feature |",
"| 32759 | 2 | 2 | 0 | NO (historical temp-file absent) |",
"",
"The fixed scanner version and suite do not imply the historical agent generations used identical models or random seeds."]
(out/"04_EVALUATION_RESULTS.md").write_text("\n".join(text)+"\n")
print("RESULTS",len(rows),"NEW ALERTS",len(alerts))
