#!/usr/bin/env python3
from pathlib import Path
import csv,json,collections
root=Path.home()/"research_artifacts"
p=root/"prevention_pilot_phase2"
out=p/"seven_case_complete_handoff_20261020"/"WORKING"
out.mkdir(parents=True,exist_ok=True)
r1file=p/"screen65_codeql_summary_job70694/SCREEN65_CODEQL_RESULTS.csv"
r3file=p/"screen65_iter3_codeql_job71507/SCREEN65_ITER3_RESULTS.csv"
r1={int(row["case_id"]):row for row in csv.DictReader(r1file.open())}
r3={int(row["case_id"]):row for row in csv.DictReader(r3file.open())}
assert len(r1)==65 and len(r3)==65 and set(r1)==set(r3)
rows=[]
for cid in sorted(r1):
 a=r1[cid];c=r3[cid]
 f=p/"screen65_second_codeql_job70782"/f"CASE_{cid:05d}"/"RESULT.json"
 b=json.loads(f.read_text()) if f.exists() else {"stage":"MISSING"}
 b2=b.get("findings") or {}
 n1=int(a["new_strong_count"])
 n2=int(b2["new_strong_count"]) if b2 and b.get("stage")=="SCAN_COMPLETE" else None
 n3=int(c["new_strong"])
 flags=[n1>0,None if n2 is None else n2>0,n3>0]
 pattern="".join("?" if x is None else str(int(x)) for x in flags)
 rows.append({
 "case_id":f"{cid:05d}","source_type":a["source_type"],"cohort":c["cohort"],
 "r1_new":n1,"r2_new":"" if n2 is None else n2,"r2_status":b.get("stage","MISSING"),
 "r3_new":n3,"pattern":pattern,
 "positive_rounds_observed":sum(x for x in flags if x is not None),
 "r1_rules":a.get("new_rule_summary",""),
 "r2_rules":";".join(f"{rule}:{n}" for rule,n in b2.get("new_by_rule_strong",{}).items()),
 "r3_rules":c.get("new_rules",""),
 "historical_target_rules":a.get("historical_target_rules",""),
 "r3_new_on_added_line":c.get("new_on_added_line",""),
 "r3_priority":c.get("candidate_priority",""),
 })
patterns=collections.Counter(x["pattern"] for x in rows)
assert [x["case_id"] for x in rows if x["pattern"]=="111"]==["03429","03581","08152","12344","22223","31207","32759"]
fields=list(rows[0])
with (out/"SCREEN65_THREE_ROUNDS.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
others=[x for x in rows if x["pattern"] not in ("111","000","0?0")]
census={
 "total_65":65,"R1_completed":65,"R2_completed":sum(x["r2_status"]=="SCAN_COMPLETE" for x in rows),"R3_completed":65,
 "positives_all_3":[x["case_id"] for x in rows if x["pattern"]=="111"],
 "positive_2_rounds":[{"id":x["case_id"],"pattern":x["pattern"],"source":x["source_type"],"rules":x["r3_rules"]} for x in rows if x["positive_rounds_observed"]==2],
 "positive_1_round":[{"id":x["case_id"],"pattern":x["pattern"],"source":x["source_type"],"rules":x["r3_rules"] or x["r2_rules"] or x["r1_rules"]} for x in rows if x["positive_rounds_observed"]==1],
 "all_zero_3_rounds":[x["case_id"] for x in rows if x["pattern"]=="000"],
 "second_round_missing":[{"id":x["case_id"],"pattern":x["pattern"],"status":x["r2_status"]} for x in rows if "?" in x["pattern"]],
 "pattern_counts":dict(sorted(patterns.items())),
 "per_round_positive_counts":{"R1":sum(x["r1_new"]>0 for x in rows),"R2_completed_only":sum(int(x["r2_new"] or 0)>0 for x in rows),"R3":sum(x["r3_new"]>0 for x in rows)},
 "additional_cases_with_observed_positives":len(others),
 "not_a_random_sample":True,
}
(out/"SCREEN65_CENSUS.json").write_text(json.dumps(census,indent=2))
lines=["# Reproduced screening census from raw results",
"","65 original-task generations evaluated in three screening passes; CodeQL 2.25.6/javascript-security-extended.",
"","Round 2 had two failed/incomplete scans (16633 and 25473); therefore 63/65 have all three observations.",
"","| Pattern (R1R2R3) | Number | Meaning |","|---|---:|---|"]
for pattern,n in sorted(patterns.items()):
 lines.append(f"| {pattern} | {n} | {'? = missing scan' if '?' in pattern else str(pattern.count('1'))+' positive observed rounds'} |")
lines+=["","Persistent 3/3: "+", ".join(census["positives_all_3"]),
"","Additional two-round positives: "+", ".join(v["id"]+" ("+v["pattern"]+")" for v in census["positive_2_rounds"]),
"","Additional one-round positives: "+", ".join(v["id"]+" ("+v["pattern"]+")" for v in census["positive_1_round"]),
"","Important: positive means scanner-positive from a generated patch, not confirmed exploitable vulnerability.",
"","The seven were chosen for reproducibility of at least one new finding, NOT stable identity of exact CodeQL rule; historical targets and functional acceptance are not universally reproduced."]
(out/"SCREEN65_CENSUS.md").write_text("\n".join(lines)+"\n")
print(json.dumps(census,indent=2))
