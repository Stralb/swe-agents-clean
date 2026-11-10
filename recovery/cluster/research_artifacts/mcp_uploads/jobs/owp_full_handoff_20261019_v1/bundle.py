#!/usr/bin/env python3
"""Create analysis-ready, append-only research handoff without modifying any input."""
from pathlib import Path
import csv, hashlib, json, os, time, zipfile, traceback, sys, re
ROOT=Path.home()/"research_artifacts"
PHASE=ROOT/"prevention_pilot_phase2"
job=os.getenv("SLURM_JOB_ID","manual")
OUT=PHASE/("owp_research_handoff_job"+job)
OUT.mkdir(parents=True,exist_ok=False)
DEST=OUT/"OWP_65x3_14OWP_RESEARCH_HANDOFF.zip"
README=OUT/"README_FIRST.md"
MISSING=[]
EXCLUDED=[]
CONTENT={}
seen=set()
allinfo=[]
def safe(n):
 assert not n.startswith("/") and ".." not in Path(n).parts
 return n
def add(path,arcname=None):
 p=Path(path)
 if not p.exists() or not p.is_file():
  MISSING.append(str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p))
  return
 if p.is_symlink():
  EXCLUDED.append({"path":str(p),"reason":"symlink"})
  return
 arc=safe(arcname or str(p.relative_to(ROOT)))
 if arc in seen:return
 seen.add(arc)
 allinfo.append((str(p),arc,p.stat().st_size))
def walk_files(relative,ext=None,only_cases=False,exclude=None):
 base=ROOT/relative
 if not base.exists():
  MISSING.append(relative);return
 for f in sorted(base.rglob("*")):
  if not f.is_file() or f.is_symlink():continue
  if exclude and exclude(f):continue
  if ext and f.suffix.lower() not in ext:continue
  if only_cases and not any(x.startswith("CASE_") for x in f.relative_to(base).parts):continue
  add(f)
# The full independent O1/O2/O3 generated code diffs and source manifests.
for rel in [
 "prevention_pilot_phase2/screen65_static_analysis_job70606/patches",
 "prevention_pilot_phase2/screen65_second_20261018_v1/patches",
 "prevention_pilot_phase2/screen65_iter3_staged_20261019_v2_bigbatch/patches"]:
 walk_files(rel)
for rel,files in [
 ("prevention_pilot_phase2/screen65_static_analysis_job70606",["TRANSFER_MANIFEST.json"]),
 ("prevention_pilot_phase2/screen65_second_20261018_v1",["TRANSFER_MANIFEST.json"]),
 ("prevention_pilot_phase2/screen65_iter3_staged_20261019_v2_bigbatch",["MANIFEST.json","RESULTS_INDEX_ORIGINAL.csv"]),
 ("prevention_pilot_phase2/screen65_codeql_summary_job70694",["SCREEN65_CODEQL_RESULTS.csv","SCREEN65_CODEQL_SUMMARY.json"]),
 ("prevention_pilot_phase2/screen65_iter3_codeql_job71507",["SCREEN65_ITER3_RESULTS.csv","SCREEN65_ITER3_SUMMARY.json","SCREEN65_ITER3_SCREENING_REPORT.md"]),
 ("prevention_pilot_phase2/owp14_allarm_comparison_job71212",["OWP14_SCANNER_COMPARISON.csv","OWP14_SCANNER_COMPARISON.md","OWP14_SUMMARY.json","OWP14_NEW_ALERTS_ALL_ARMS.json"]),
 ("prevention_pilot_phase2/owp14_user12_o_report_job71167",["O_ONLY_CODEQL12.csv","O_ONLY_CODEQL12.md","O_ONLY_CODEQL12.json"]),
 ("prevention_pilot_phase2/owp14_allcases_packets_job71014",["PACKET_INDEX.csv"])
]:
 for name in files:
  f=ROOT/rel/name
  if f.exists():add(f)
# Every individual result and SARIF from all three rounds (not just scanner positives).
round_roots={
 "R1":"prevention_pilot_phase2/screen65_codeql_job70675",
 "R2":"prevention_pilot_phase2/screen65_second_codeql_job70782",
 "R3":"prevention_pilot_phase2/screen65_iter3_codeql_job71507",
 "OWP_O":"prevention_pilot_phase2/owp14_user12_o_codeql_job71159",
 "OWP_W":"prevention_pilot_phase2/owp14_user14_w_codeql_job71209",
 "OWP_P":"prevention_pilot_phase2/owp14_user14_p_codeql_job71204"
}
for key,rel in round_roots.items():
 base=ROOT/rel
 if not base.exists():MISSING.append(rel);continue
 for case in sorted(base.glob("CASE_*")):
  if not case.is_dir():continue
  for f in sorted(case.iterdir()):
   if f.is_file() and f.suffix.lower() in {".json",".sarif",".csv",".txt",".log"}:
    add(f)
# OWP actual original/experimental patch artifacts and issue prompts; no artificial fusion.
for rel in ["owp14_user12_o_preflight_job71153","owp14_user14_w_preflight_job71208","owp14_user14_p_preflight_job71201"]:
 base=PHASE/rel
 if not base.exists():MISSING.append(str(base));continue
 for f in sorted(base.rglob("*")):
  if f.is_file() and f.suffix.lower() in {".patch",".json",".csv",".md",".txt",".log"}:add(f)
for rel in ["owp14_functional_intake_job71357","owp14_syntax_checks_job71361",
            "owp14_syntax_jsx_checks_job71362","owp14_targeted_behavior_job71363",
            "owp14_sandbox_capability_job71395",
            "owp14_toolchain_paths_job71360",
            "owp14_functional_env_job71359",
            "owp14_watcher_blackbox_job71395"]:
 base=PHASE/rel
 if not base.exists():continue
 for f in sorted(base.rglob("*")):
  if f.is_file() and f.suffix.lower() in {".json",".csv",".md",".txt",".log",".mjs"}:add(f)
# Early pilot and taxonomy/census artifacts: source text and small analyses, not giant databases.
for rel in ["case_screen_results_v1","case_screen_dossier_v1","case_screen_preaudit_v1",
            "phase2_eligibility_dossier_v1","pilot3_arms_job69775",
            "pilot3_intervention_eval_job69794",
            "owp14_target_specific_index_job71021",
            "owp14_user12_o_report_job71167"]:
 base=PHASE/rel
 if not base.exists():continue
 for f in sorted(base.rglob("*")):
  if not f.is_file():continue
  if f.suffix.lower() in {".csv",".json",".md",".txt",".patch"} and f.stat().st_size < 8000000:
   add(f)
# All relevant replay/CodeQL/analysis/packing scripts, unchanged.
jobs=ROOT/"mcp_uploads/jobs"
if jobs.exists():
 for sub in sorted(jobs.iterdir()):
  if not sub.is_dir() or not any(sub.name.startswith(s) for s in ["screen65_","owp14_","pilot3_","case_screen_"]):continue
  for f in sorted(sub.rglob("*")):
   if f.is_file() and f.suffix.lower() in {".py",".sbatch",".js",".mjs",".json",".csv",".md",".txt"} and f.stat().st_size < 2000000:add(f)
# References to exact frozen source archives make the archive reproducible on Wits but keep it portable.
source_refs=[]
for name in ["remaining65_archives_oct17_v1","remaining65_targeted14_v1","owp14_allcases_packets_job71014"]:
 base=PHASE/name
 if base.exists():
  for f in sorted(base.glob("*.zip")):
   source_refs.append({"path":str(f.relative_to(ROOT)),"bytes":f.stat().st_size})
sources_json=json.dumps({"root_on_wits":str(ROOT),"files":source_refs,"note":"Frozen repositories are NOT embedded because they are larger than a portable chat handoff. Reconstruct with frozen source ZIP plus independent Git patch. Exact paths listed."},indent=2)
notes="""# O/W/P research handoff: 65 tasks, 3 original generations, 14 intervention cohort

This archive includes ALL available generated patch diffs from three 65-case
original-only generations; all archived CodeQL per-case RESULT.json and SARIF
files in each generation; 12 O and 14 W/P intervention implementation patches
and scanner results; each O/W/P issue text (the exact intervention language);
scanner comparison reports, diagnostics, analysis scripts and selected
historical taxonomy artifacts.

WARNING: The 65 frozen full repository source ZIPs and the 14*3 duplicate
frozen source packets are not embedded. Their exact Wits paths are listed
in FROZEN_SOURCE_INDEX.json. A new chat can analyze all patches and scans
offline; to replay CodeQL or run functional integration, it needs access
to the frozen repositories on Wits.

Correct interpretation:
- The three generations are distinct patches, not repeated scans of one patch.
- 65 tasks screened 3 rounds (some scans failed in R2).
- The case-level positive union across O1/O2/O3 is 19.
- Round positives: R1 9; R2 12; R3 15; 7 positives in all 3 rounds.
- A new CodeQL warning does not automatically prove exploitability.
- A selected historical warning class does not imply identical source-to-sink.
- Some W/P scanner improvements result from omitted functionality.
- The strongest complete snapshot historical warning evidence includes
  00668, 03581, 08152, and 22223 in OWP initial comparison.
- Separate O/W/P patch inputs are never equivalent to repairing the same O patch.
- Source snapshots or issue version may still require chronological verification.
- Scanner clean != functional completion != fixed vulnerability.
- Generated patches may include inferred/skipped functionality.
- Privacy: treat this archive as research-confidential; no external publication
  without reviewing repository licenses, issue body content and credentials.
"""
README.write_text(notes)
meta={
 "created_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
 "root_on_wits":str(ROOT),"source_files":len(allinfo),
 "missing_explicit_files":MISSING,"excluded_symlinks":EXCLUDED,
 "full_frozen_sources_embedded":False,"source_index_file":"FROZEN_SOURCE_INDEX.json",
 "categories":[str(x) for x in round_roots],"archive_size_limit":None}
def write_archive():
 with zipfile.ZipFile(DEST,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  z.writestr("README_FIRST.md",notes)
  z.writestr("FROZEN_SOURCE_INDEX.json",sources_json)
  for ix,(path,arc,rawsize) in enumerate(allinfo):
   try:
    z.write(path,arc)
   except Exception as e:
    EXCLUDED.append({"path":path,"error":str(e)})
   if ix%100==0:print("HANDOFF_PROGRESS",ix,"of",len(allinfo),"zip_mb",round(DEST.stat().st_size/1e6,2),flush=True)
  meta["included_entries"]=len(z.namelist())+1
  meta["excluded_files"]=EXCLUDED
  z.writestr("HANDOFF_MANIFEST.json",json.dumps(meta,indent=2))
write_archive()
with zipfile.ZipFile(DEST) as z:
 bad=z.testzip()
 assert bad is None,bad
 count=len(z.namelist())
 digest=hashlib.sha256(DEST.read_bytes()).hexdigest()
 index={"archive":str(DEST),"bytes":DEST.stat().st_size,"sha256":digest,
        "entries":count,"source_refs":len(source_refs),"missing":len(MISSING),
        "skipped":len(EXCLUDED),"tested_ok":True}
(OUT/"HANDOFF_RESULT.json").write_text(json.dumps(index,indent=2)+"\n")
print("HANDOFF_DONE "+json.dumps(index),flush=True)
