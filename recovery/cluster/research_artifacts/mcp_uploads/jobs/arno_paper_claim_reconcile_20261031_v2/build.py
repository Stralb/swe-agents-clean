#!/usr/bin/env python3
"""Read-only quantitative reconciliation of current Arno manuscript.
Outputs only aggregate statistics and case-level replay counts; never raw source bodies.
"""
from pathlib import Path
import sqlite3,json,csv,zipfile,datetime,hashlib
base=Path.home()/"research_artifacts"
dbpath=base/"mcp_uploads/jobs/arno_unified_evidence_20261031_v1/output/ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
out=base/"mcp_uploads/jobs/arno_paper_claim_reconcile_20261031_v2/output"
out.mkdir(parents=True,exist_ok=True)
assert dbpath.exists()
db=sqlite3.connect("file:"+str(dbpath)+"?mode=ro",uri=True,timeout=90)
db.row_factory=sqlite3.Row
db.execute("PRAGMA query_only=ON")
def data(sql):return [dict(x) for x in db.execute(sql).fetchall()]
def one(sql):return dict(db.execute(sql).fetchone())
pop=one("SELECT COUNT(*) cases,COUNT(DISTINCT repo_id) repos FROM cases")
lang=data("SELECT r.language,COUNT(*) n FROM cases c JOIN repos r ON c.repo_id=r.id GROUP BY r.language")
cohort=data("SELECT collection_phase,COUNT(*) n FROM study_cases GROUP BY collection_phase")
findings=data("SELECT collection_phase,COUNT(*) n FROM study_findings f JOIN study_cases c ON f.case_id=c.case_id GROUP BY collection_phase")
mapped=data("SELECT mapping_status,COUNT(*) n FROM study_findings GROUP BY mapping_status")
attr=data("SELECT c.collection_phase,p.attribution,COUNT(*) n FROM study_producing_changes p JOIN study_cases c ON p.case_id=c.case_id GROUP BY c.collection_phase,p.attribution")
roots=data("SELECT route,COUNT(*) n FROM study_roots GROUP BY route")
root_sizes=one("SELECT SUM(CASE WHEN pc_count=1 THEN 1 ELSE 0 END) single_change,SUM(CASE WHEN pc_count>1 THEN 1 ELSE 0 END) multi_change,SUM(pc_count) producing_changes FROM arno_d7_final_roots_342")
t4=one("SELECT COUNT(*) n FROM arno_d7_final_roots_342 WHERE final_tier='T4'")
issueonly=one("SELECT COUNT(*) n FROM (SELECT case_id FROM ai_markers WHERE case_id IS NOT NULL GROUP BY case_id HAVING SUM(CASE WHEN marker_location IN ('issue_body','issue_title') THEN 0 ELSE 1 END)=0)")
rq2positive=data("SELECT json_extract(original_row_json,'$.positive_instruction_specificity') category,COUNT(*) n FROM arno_rq2_c6_pairs GROUP BY category")
rq2control=data("SELECT json_extract(original_row_json,'$.control_instruction_specificity') category,COUNT(*) n FROM arno_rq2_c6_pairs GROUP BY category")
rq2tests=data("SELECT variable,calculated_p,frozen_p,tolerance_status FROM arno_rq2_c6_reproduced_tests")
family=data("""WITH f AS (SELECT DISTINCT m.source_producing_change_id pc,json_extract(x.row_json,'$."Finding Family"') family
FROM arno_original_step1_detail x JOIN arno_original_step2_detail m ON x.canonical_finding_id=m.canonical_finding_id)
SELECT f.family,s.final_attribution attribution,COUNT(*) n FROM f JOIN arno_original_step3_detail s ON f.pc=s.source_producing_change_id
GROUP BY f.family,s.final_attribution ORDER BY f.family,s.final_attribution""")
matched=one("SELECT COUNT(*) pairs,SUM(same_repository) within_repository FROM arno_matched_control_pairs_C2")
unmatched=one("SELECT COUNT(*) n FROM arno_matched_control_unmatched_C2")
replays=data("""SELECT case_id,MAX(CASE WHEN arm='O' THEN new_strong_count END) O,
 MAX(CASE WHEN arm='W' THEN new_strong_count END) W,MAX(CASE WHEN arm='P' THEN new_strong_count END) P
 FROM arno_rq3_owp14_run_scans GROUP BY case_id HAVING COUNT(DISTINCT arm)=3 ORDER BY case_id""")
arms=data("SELECT arm,COUNT(*) n FROM arno_rq3_owp14_run_scans GROUP BY arm")
functions=data("SELECT functional_status,COUNT(*) n FROM arno_rq3_owp14_run_scans GROUP BY functional_status")
runcov=data("SELECT experimental_family,COUNT(*) n,SUM(patch_embedded) patches,SUM(raw_scan_embedded) scan_bytes FROM study_runs GROUP BY experimental_family")
reviews=data("SELECT status,COUNT(*) n FROM study_human_reviews GROUP BY status")
assert pop=={"cases":3809,"repos":723}
assert {x["language"]:x["n"] for x in lang}=={"JavaScript":609,"TypeScript":3200}
assert sorted(x["n"] for x in cohort)==[70,122]
assert sorted(x["n"] for x in findings)==[237,605]
assert {x["mapping_status"]:x["n"] for x in mapped}=={"MAPPED":781,"NOT_ISOLATED":61}
assert sum(x["n"] for x in attr)==455
assert {x["route"]:x["n"] for x in roots}=={"H":6,"M":233,"T":103}
assert root_sizes=={"single_change":283,"multi_change":59,"producing_changes":455}
assert t4["n"]==128
assert issueonly["n"]==236
assert {r["category"]:r["n"] for r in rq2positive}=={"Explicit instruction":121,"Problem only":36,"Suggests solution":33}
assert {r["category"]:r["n"] for r in rq2control}=={"Explicit instruction":148,"Problem only":33,"Suggests solution":9}
assert len(rq2tests)==9 and all(r["tolerance_status"]=="PASS_MATCHES_FROZEN_P" for r in rq2tests)
assert matched=={"pairs":190,"within_repository":115} and unmatched["n"]==2
assert len(replays)==12
assert (sum(x["O"] for x in replays),sum(x["W"] for x in replays),sum(x["P"] for x in replays))==(21,10,15)
assert (sum(x["W"]<x["O"] for x in replays),sum(x["P"]<x["O"] for x in replays))==(7,4)
assert {x["arm"]:x["n"] for x in arms}=={"O":12,"W":14,"P":14}
assert functions==[{"functional_status":"NOT_VALIDATED","n":40}]
assert sum(x["n"] for x in runcov)==68
assert sum(x["patches"] for x in runcov)==61
assert sum(x["scan_bytes"] for x in runcov)==68
assert {x["status"]:x["n"] for x in reviews}=={"USER_ADJUDICATED":41,"ALL_THREE_AGREE_NO_USER_VERDICT":8,"USER_DEFERRED":1}
assert sum(x["n"] for x in family)==322
checks=[
("A01","Methods 3.1","3,809 workflows / 723 repositories","PASS","cases, repos"),
("A02","Methods Table 1","609 JavaScript / 3,200 TypeScript","PASS","cases join repos"),
("A03","Methods 3.3","192 cases, 122 initial and 70 extension","PASS","study_cases"),
("A04","RQ1","605+237 canonical findings; 781 mapped; 61 not isolated","PASS","study_findings"),
("A05","RQ1","455 mapped producing changes with Direct/Side-effect/Unclear","PASS","study_producing_changes"),
("A06","RQ1 Table 2","Original 122: category-by-attribution 322 changes","PASS","original step 1/2/3, distinct PC"),
("A07","RQ1 Table 3","342 roots H6/T103/M233","PASS","study_roots"),
("A08","RQ1","283 single-change and 59 multi-change roots","PASS","arno_d7_final_roots_342"),
("A09","RQ1","128 explanation tier T4 cases","PASS","arno_d7_final_roots_342"),
("A10","RQ2","190 pairs,115 same-repo,2 unmatched","PASS","arno_matched_control_pairs_C2"),
("A11","RQ2 Table 4","63.7/77.9 etc. issue wording percentages","PASS","190 frozen pair-level positive/control labels in arno_rq2_c6_pairs"),
("A12","RQ3 Table 5","12 complete triples O21 W10 P15; improvement W7 P4","PASS","arno_rq3_owp14_run_scans"),
("A13","RQ3","40 historical O12/W14/P14","PASS","arno_rq3_owp14_run_scans"),
("A14","RQ3 Validity","Historical functional outcome not validated","LIMITATION","arno_rq3_owp14_run_scans"),
("A15","Artifact audit","68 runs 61 patch bytes 68 scanner results","PASS","study_runs"),
("A16","Review","41/8/1 AI-assisted one-person audit","LIMITATION","study_human_reviews"),
("A17","Study Validity","Historical PR baseline exact revision equivalence unverified","LIMITATION","study_runs"),
("A18","Methods","236 issue-only agent markers","PASS","ai_markers grouped case-wise with issue-only locations"),
("A19","Threats section","RQ2 semantic labels and 342 roots described as unavailable for recount","WORDING_UPDATE","both are preserved and recountable; not independently human re-adjudicated"),
("A20","Distribution","Raw 42 GB dataset safe for public distribution","BLOCKED","third-party rights/privacy/secret review not completed")
]
with (out/"CLAIM_RECONCILIATION.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.writer(f);w.writerow(["id","paper_location","claim","status","evidence"]);w.writerows(checks)
for name,rows,fields in [
 ("RQ1_FINDING_FAMILY_CHANGE_COUNTS.csv",family,["family","attribution","n"]),
 ("RQ3_COMPLETE_TRIPLES.csv",replays,["case_id","O","W","P"]),
 ("EXPERIMENT_ARTIFACT_COVERAGE.csv",runcov,["experimental_family","n","patches","scan_bytes"])]:
 with (out/name).open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
audit={
"status":"RESTRICTED_PAPER_CLAIM_RECONCILIATION_COMPLETE",
"paper_title":"Between the Issue and the Warning: Tracing Security-Relevant Decisions in Agent-Associated Pull Requests",
"paper_file":"https://github.com/Stralb/adversarial-swe-agents/blob/main/paper/main.tex",
"paper_blob_sha":"b7f0dac499d2469fb7648a6f9bcddfd750e2e454",
"database":str(dbpath),"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
"population":pop,"languages":lang,"cohorts":cohort,"findings":findings,
"mapping":mapped,"producing_changes":attr,"root_routes":roots,"root_sizes":root_sizes,
"t4":t4,"issue_only":issueonly,"rq2_labels":{"positive":rq2positive,"control":rq2control},"rq2_reproduced_tests":rq2tests,"matched":matched,"unmatched":unmatched,"replays":replays,
"replay_arms":arms,"historical_functional_status":functions,
"experiment_artifacts":runcov,"human_reviews":reviews,
"checks":[{"id":c[0],"location":c[1],"claim":c[2],"status":c[3],"evidence":c[4]} for c in checks],
"privacy_status":"RESTRICTED_NOT_PUBLIC","original_databases_changed":False}
(out/"PAPER_CLAIM_AUDIT.json").write_text(json.dumps(audit,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
(out/"REVIEWER_README.md").write_text("""# Restricted publication audit: Between the Issue and the Warning

Source paper: https://github.com/Stralb/adversarial-swe-agents/blob/main/paper/main.tex
Source GitHub blob SHA: b7f0dac499d2469fb7648a6f9bcddfd750e2e454

**The attached ZIP contains aggregates and case-level alert counts only.** It does NOT distribute raw patches, SARIF, issue bodies, researcher notes or the 42 GB master.

Verified: 3,809 workflows / 723 repos; 122+70 positive cases; 605+237 canonical findings; 781 mapped, 61 not isolated; 455 producing changes; 342 roots; 190 matched pairs / 115 within repository; O/W/P 12 complete tasks with 21/10/15 alerts and improvements 7/4.

Table 4 was reproduced from the preserved 190 matched-pair classification rows: explicit 121/190 vs 148/190, suggested-solution 33/190 vs 9/190, problem-only 36/190 vs 33/190. All nine frozen statistical-test p-values match independently recalculated records. Historical semantic labels remain AI-assisted, not independently human-validated.

The historical replay outputs all have functional_status NOT_VALIDATED. Do not infer feature completion or deployable prevention from fewer scanner alerts.
No second independent human coder. The 41 post-hoc human-selected decisions, 8 consensus-only and 1 deferred are documented.
The RQ2 pair-level semantic labels and 342 root labels are preserved in full, so the paper's prior phrase 'unavailable for independent recount' needs precision: recount is possible but independent semantic re-adjudication was not performed.
Historical PR baseline equivalence is not independently verified. Do not claim an exact historical pre-PR counterfactual.
The full raw source database is RESTRICTED pending privacy and third-party license review.

See CLAIM_RECONCILIATION.csv and PAPER_CLAIM_AUDIT.json for source-specific status.
""",encoding="utf-8")
(out/"REPRODUCE_SQL.sql").write_text("""-- Run in read-only mode on ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite
SELECT COUNT(*) cases,COUNT(DISTINCT repo_id) repos FROM cases;
SELECT collection_phase,COUNT(*) FROM study_cases GROUP BY collection_phase;
SELECT mapping_status,COUNT(*) FROM study_findings GROUP BY mapping_status;
SELECT attribution,COUNT(*) FROM study_producing_changes GROUP BY attribution;
SELECT route,COUNT(*) FROM study_roots GROUP BY route;
SELECT COUNT(*) pairs,SUM(same_repository) same_repo FROM arno_matched_control_pairs_C2;
WITH x AS (SELECT case_id,MAX(CASE WHEN arm='O' THEN new_strong_count END) O,
MAX(CASE WHEN arm='W' THEN new_strong_count END) W,
MAX(CASE WHEN arm='P' THEN new_strong_count END) P
FROM arno_rq3_owp14_run_scans GROUP BY case_id HAVING COUNT(DISTINCT arm)=3)
SELECT COUNT(*) triples,SUM(O) O_total,SUM(W) W_total,SUM(P) P_total,
SUM(W<O) W_improved,SUM(P<O) P_improved FROM x;
SELECT status,COUNT(*) FROM study_human_reviews GROUP BY status;
""",encoding="utf-8")
with zipfile.ZipFile(out/"ARNO_RESTRICTED_PUBLICATION_CLAIM_AUDIT.zip","w",zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for x in out.iterdir():
  if x.is_file() and x.suffix in (".csv",".json",".md",".sql"): z.write(x,x.name)
assert zipfile.ZipFile(out/"ARNO_RESTRICTED_PUBLICATION_CLAIM_AUDIT.zip").testzip() is None
print(json.dumps({"status":"PASS","checks":len(checks),"verified_or_limitations":sum(c[3] in ("PASS","LIMITATION") for c in checks),"unreproduced":sum(c[3]=="NOT_REPRODUCED" for c in checks),"output":str(out),"zip_bytes":(out/"ARNO_RESTRICTED_PUBLICATION_CLAIM_AUDIT.zip").stat().st_size},indent=2),flush=True)
db.close()
