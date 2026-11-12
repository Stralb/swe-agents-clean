#!/usr/bin/env python3
"""New versioned target-specific index; does not alter original frozen 42 ZIPs."""
import os,csv,json,hashlib
from pathlib import Path
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
base=R/"owp14_allcases_packets_job71014"
ids=json.loads((base/"RESEARCHER_ONLY/MANIFEST.json").read_text())
targets=json.loads((base/"RESEARCHER_ONLY/TARGETS_AND_PROPERTIES.json").read_text())
out=R/("owp14_target_specific_index_job"+os.environ["SLURM_JOB_ID"]);out.mkdir(exist_ok=False)
rows=[];confirmed=[];provisional=[]
for v in ids["case_detail"]:
 cid=v["case_id"];rule=targets[str(cid)]["historical_target_rule"]
 audit=json.loads((R/"dual_o_audit14_job70958"/"cases"/("CASE_%05d.json"%cid)).read_text())
 attempt=[]
 for x in audit["attempts"]:
  found=[y for y in x["findings"] if y["rule"]==rule]
  attempt.append(len(found))
 target_any=bool(sum(attempt))
 if target_any:confirmed.append(cid)
 else:provisional.append(cid)
 row={"case_id":cid,"repository":v["repo"],"target_rule":rule,
  "O1_target_warning_count":attempt[0],"O2_target_warning_count":attempt[1],
  "any_O_target_warning":target_any,"source_mode":v["source"],
  "historical_issue_asofpr_verified":False,"status":"EXPLORATORY_TARGET_RECURRED" if target_any else "DISCOVERY_ONLY_TARGET_NOT_RECURRED"}
 rows.append(row)
assert len(rows)==14
assert confirmed==[668,3429,3581,6104,8152,8461,22223,31207],confirmed
assert 20094 in provisional
with (out/"TARGET_SPECIFIC_INDEX_CORRECTED.csv").open("x",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(out/"TARGET_SPECIFIC_INDEX_CORRECTED.json").write_text(json.dumps({"source_packets":str(base),
 "untouched_original_packet_hashes":{str(x["case_id"]):x["packets"] for x in ids["case_detail"]},
 "historical_target_recurrence_cases":confirmed,
 "no_historical_target_recurrence_cases":provisional,"reproducing_target_count":len(confirmed),
 "analysis_correction":"Prior source manifest's historical_target_reproduced_by_prior_O incorrectly used ANY historical rule. This corrected index requires the SPECIFIC frozen W-target rule.",
 "rows":rows},indent=2)+"\n")
print("CORRECTED_TARGET_INDEX",out,"TARGETS",confirmed,"OTHER",provisional,flush=True)
