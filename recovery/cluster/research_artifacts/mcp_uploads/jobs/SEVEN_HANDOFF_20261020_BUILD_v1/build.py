from pathlib import Path
import json,hashlib,zipfile
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
D=R/"FINAL_SEVEN_CASE_RESEARCH_HANDOFF_20261020"
out=D/"COMPLETE_7_CASE_RESEARCH_HANDOFF_20261020.zip"
ids=["03429","03581","08152","12344","22223","31207","32759"]
archives={
"SOURCE/ALL_7_FROZEN_REPOSITORIES.zip":R/"seven_case_delivery_20261020/SEVEN_CASES_ALL_7_FROZEN_REPOSITORIES.zip",
"SCANS/INITIAL_7_CODEQL.zip":R/"seven_case_scans_20261020/SEVEN_CASE_CODEQL_COMPLETE_RESULTS_20261020.zip",
"SCANS/FOUR_TARGETED_REPAIRS.zip":R/"seven_case_targeted_final_20261020/SEVEN_CASE_TARGETED_REPAIRS_WITH_CODEQL_20261020.zip",
"SCANS/FINAL_TWO_CODEQL_NEGATIVE.zip":R/"both_remaining_negative_delivery_20261020/BOTH_REMAINING_CASES_CODEQL_NEGATIVE_20261020.zip"}
patches={
"03429":R/"seven_case_targeted_v3_20261020/03429/CASE_03429_TARGETED_V3.patch",
"03581":R/"seven_case_scans_20261020/03581/CASE_03581_P1_r01.patch",
"08152":R/"provider_variants_20261020_retry/08152/CASE_08152_PROVIDER_V1.patch",
"12344":R/"seven_case_targeted_fixes_20261020/12344/CASE_12344_TARGETED_V2.patch",
"22223":R/"seven_case_scans_20261020/22223/CASE_22223_P1_r01.patch",
"31207":R/"provider_variants_20261020/31207/CASE_31207_PROVIDER_V1.patch",
"32759":R/"seven_case_scans_20261020/32759/CASE_32759_P1_r01.patch"}
latest={
"03429":R/"seven_case_targeted_v3_20261020/03429/RESULT.json",
"03581":R/"seven_case_scans_20261020/03581/RESULT.json",
"08152":R/"provider_variants_20261020_retry/scans/08152/RESULT.json",
"12344":R/"seven_case_targeted_fixes_20261020/12344/RESULT.json",
"22223":R/"seven_case_scans_20261020/22223/RESULT.json",
"31207":R/"provider_variants_20261020/scans/31207/RESULT.json",
"32759":R/"seven_case_scans_20261020/32759/RESULT.json"}
def hashfile(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  while True:
   b=f.read(1048576)
   if not b:break
   h.update(b)
 return h.hexdigest()
for x in list(archives.values())+list(patches.values())+list(latest.values())+[D/"START_HERE.md"]:
 assert x.is_file(),str(x)
with zipfile.ZipFile(archives["SOURCE/ALL_7_FROZEN_REPOSITORIES.zip"]) as z:
 assert all("CASE_INPUTS/CASE_"+i+"_O.zip" in z.namelist() for i in ids)
result=[]
for c in ids:
 initial=json.loads((R/"seven_case_scans_20261020"/c/"RESULT.json").read_text())
 final=json.loads(latest[c].read_text())
 new=final.get("new_strong_count",final.get("new_fingerprint"))
 assert new==0,(c,new)
 result.append({"case":c,"P1_initial_new":initial["new_strong_count"],"final_new":new,
 "P1_total_before":initial["baseline_count"],"P1_total_after":initial["patched_count"],
 "final_patch_sha256":hashfile(patches[c]),"final_result_sha256":hashfile(latest[c])})
index={"cases":ids,"seven_latest_scanner_negative":True,"full_functional_acceptance_proven":False,
 "minimum_additive_issue_information_demonstrated":False,"remaining_candidate_cases_in_screen65":["04134","04379","06150","16209","16213"],
 "remaining_owp14_cases":["00668","06104","08461","15151","16633","20094","21682"],
 "results":result,"source_archives":{k:{"bytes":v.stat().st_size,"sha256":hashfile(v)} for k,v in archives.items()}}
with zipfile.ZipFile(out,"w",allowZip64=True,compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.write(D/"START_HERE.md","START_HERE.md")
 z.writestr("MASTER_INDEX.json",json.dumps(index,indent=2))
 for dest,p in archives.items():z.write(p,dest,compress_type=zipfile.ZIP_STORED)
 for c in ids:
  z.write(patches[c],"FINAL_PATCHES/CASE_"+c+"_FINAL.patch")
  z.write(latest[c],"CASE_DETAILS/CASE_"+c+"_FINAL_RESULT.json")
  orig=R/"seven_case_scans_20261020"/c
  for n in ["RESULT.json","before.sarif","after.sarif","CASE_"+c+"_P1_r01.patch"]:
   f=orig/n
   if f.is_file():z.write(f,"CASE_DETAILS/"+c+"/INITIAL_"+n)
  if c=="03429":finaldir=R/"seven_case_targeted_v3_20261020/03429"
  elif c=="12344":finaldir=R/"seven_case_targeted_fixes_20261020/12344"
  elif c=="08152":finaldir=R/"provider_variants_20261020_retry/scans/08152"
  elif c=="31207":finaldir=R/"provider_variants_20261020/scans/31207"
  else:finaldir=orig
  for n in ["before.sarif","after.sarif","RESULT.json","analyze.log","after_analyze.log","apply_check.log"]:
   f=finaldir/n
   if f.is_file():z.write(f,"CASE_DETAILS/"+c+"/FINAL_"+n)
  if c=="08152":
   for n in ["TEST_REPORT.json","test_0.log","test_1.log"]:
    f=R/"provider_variants_20261020_retry/08152"/n
    if f.is_file():z.write(f,"CASE_DETAILS/08152/"+n)
  if c=="31207":
   f=R/"both_remaining_negative_delivery_20261020/31207_NODE_TEST.log"
   if f.is_file():z.write(f,"CASE_DETAILS/31207/31207_NODE_TEST.log")
  for arm in ["W","P"]:
   f=R/"owp14_allcases_packets_job71014"/("CASE_"+c+"_"+arm+".zip")
   if f.is_file():
    with zipfile.ZipFile(f) as zz:
     if "ISSUE.md" in zz.namelist():z.writestr("RESEARCHER_ONLY/HISTORICAL_"+c+"_"+arm+"_ISSUE.md",zz.read("ISSUE.md"))
 for folder,prefix in [
 ("screen65_iter3_codeql_job71507","SCREEN65_RESULTS"),
 ("screen65_codeql_summary_job70694","SCREEN65_RESULTS"),
 ("owp14_allarm_comparison_job71212","HISTORICAL_OWP14"),
 ("issue_ablation_O_scans_job71871","ISSUE_ABLATIONS/ORIGINAL"),
 ("issue_ablation_P_scans_job71872","ISSUE_ABLATIONS/PROBLEM_ONLY")]:
  d=R/folder
  if d.is_dir():
   for f in d.iterdir():
    if f.is_file() and f.suffix.lower() in [".zip",".md",".csv",".json"]:z.write(f,prefix+"/"+f.name)
 for c in ["04134","04379","06150","16209","16213"]:
  d=R/"screen65_iter3_codeql_job71507"/("CASE_"+c)
  if d.is_dir():
   for f in d.iterdir():
    if f.is_file() and f.suffix.lower() in [".json",".md",".csv",".patch"] and f.stat().st_size<4_000_000:
     z.write(f,"OTHER_CANDIDATES/"+c+"/"+f.name)
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 assert sum(n.startswith("FINAL_PATCHES/") for n in z.namelist())==7
print(json.dumps({"status":"VERIFIED","path":str(out),"bytes":out.stat().st_size,
 "sha256":hashfile(out),"items":len(zipfile.ZipFile(out).namelist()),"cases":ids},indent=2))
