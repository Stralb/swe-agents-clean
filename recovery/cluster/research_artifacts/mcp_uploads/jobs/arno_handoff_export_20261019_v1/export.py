#!/usr/bin/env python3
"""Evidence-only archive export; scans and agent implementations are never executed."""
from pathlib import Path
import os,sys,csv,io,json,re,hashlib,zipfile
R=Path.home()/"research_artifacts";P=R/"prevention_pilot_phase2";D=R/"ARNO_CODEQL_EXPORT_20261019"
if D.exists():raise SystemExit("Refusing to overwrite "+str(D))
D.mkdir(mode=0o700)
def gp(pattern):return [p for p in P.iterdir() if p.is_dir() and p.name.startswith(pattern)]
groups={
"01_ORIGINAL_OWP_INPUTS":[P/"owp14_allcases_packets_job71014"],
"02_ALL_GENERATED_PATCHES":[P/x for x in ("owp14_user12_o_preflight_job71153","owp14_user14_w_preflight_job71208","owp14_user14_p_preflight_job71201","screen65_static_analysis_job70606","screen65_second_20261018_v1","screen65_iter3_staged_20261019_v2_bigbatch")],
"03_CODEQL_SARIF_AND_SCANS":[P/x for x in ("owp14_user12_o_codeql_job71159","owp14_user14_w_codeql_job71209","owp14_user14_p_codeql_job71204","owp14_allarm_comparison_job71212","owp14_user12_o_report_job71167","owp14_target_specific_index_job71021")],
"04_FUNCTIONAL_TESTS_AND_TRIAGE":gp("owp14_functional")+gp("owp14_syntax")+gp("owp14_targeted")+gp("owp14_sandbox")+gp("pilot3_functional"),
"05_SCREEN65_EVIDENCE":gp("screen65_codeql")+gp("screen65_second_codeql")+gp("screen65_iter3_codeql")+gp("screen65_triage")+gp("screen65_preflight")+gp("remaining65_archives")+gp("remaining65_targeted"),
"06_EARLIER_CAUSAL_EXPERIMENTS":gp("pilot3_")+gp("case_screen_")+gp("historical_controls")+gp("phase2_eval_results")+[R/x for x in ("matched_control_c1_v1_0","matched_control_c1_v1_1","matched_control_c2_v1_0","matched_control_c3_v1_0")],
"07_AGENT_PROMPTS_AND_TRACES":[p for p in (R/"mcp_uploads"/"jobs").iterdir() if p.is_dir() and p.name.startswith(("owp14","pilot3","screen65","phase2"))],
"08_SCRIPTS_CONFIGS_AND_PROVENANCE":[R/"mcp_uploads"/"owp14_20261018_transfer_v1",R/"mcp_uploads"/"owp14_w14_20261018_transfer_v1"],
"09_RESEARCH_CONCLUSIONS_AND_LIMITATIONS":[R/x for x in ("DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz","D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv","T2_FINAL4_SCANNER_SUMMARY_FROZEN_v1.json","T1_SELECTED6_EXTRACT_v1.tar.gz","T1_REPLACEMENT3_EXTRACT_v1.tar.gz")]}
SKIP={"__pycache__",".git",".venv","node_modules","dist","build","REPO","repos","scratch","cache","repo_cache","db_before","db_after","database_before","database_after"}
EXT=(".zip",".gz",".tar.xz",".csv",".json",".jsonl",".md",".txt",".yaml",".yml",".toml",".patch",".diff",".sarif",".log",".out",".err",".sqlite",".db",".ql",".sbatch",".sh",".py",".js",".mjs",".ts",".tsx",".ps1")
BAD=re.compile(r"(^|/)(?:\.env(?:\..*)?|\.ssh|id_(?:rsa|ed25519)|[^/]+\.(?:pem|p12|pfx|key)|credentials\.json|secrets?\.json)$",re.I)
SECRET=[re.compile(x) for x in (rb"AIza[\w-]{25,}",rb"gh[pousr]_[\w-]{25,}",rb"sk-[\w-]{25,}",rb"AKIA[A-Z0-9]{16}",rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----")]
cols=["original_filename","source_path","case_id","condition","generation","sha256","evaluation_status","archive_path","bytes","group"]
rows=[];skips=[];parts={}
def csvtext(r):
 s=io.StringIO();w=csv.DictWriter(s,fieldnames=cols);w.writeheader();w.writerows(r);return s.getvalue()
def sourcefiles(roots):
 found=set()
 for base in roots:
  if base.is_symlink():continue
  if base.is_file():allfiles=[base]
  elif base.is_dir():
   allfiles=[]
   for parent,dirs,fs in os.walk(base,followlinks=False):
    dirs[:]=[x for x in dirs if x not in SKIP and not (Path(parent)/x).is_symlink()]
    allfiles.extend(Path(parent)/f for f in sorted(fs))
  else:continue
  for p in allfiles:
   if p.is_file() and not p.is_symlink() and str(p) not in found:
    found.add(str(p));yield p
def exclude(p,g):
 if BAD.search(p.name):return "SENSITIVE_FILENAME"
 if not p.name.lower().endswith(EXT):return "NON_EVIDENCE"
 if g=="01_ORIGINAL_OWP_INPUTS" and p.suffix==".zip":
  try:
   with zipfile.ZipFile(p) as z:
    if any(BAD.search(i.filename) for i in z.infolist()):return "SENSITIVE_MEMBER_NAME"
  except Exception:return "INVALID_INPUT_ZIP"
 if g!="01_ORIGINAL_OWP_INPUTS" and p.stat().st_size>128*1024*1024:return "OVER_128MB_NONPRIMARY"
 if p.stat().st_size<8*1024*1024 and p.name.lower().endswith((".txt",".json",".py",".sbatch",".sh",".md",".csv",".patch",".log")):
  if any(rex.search(p.read_bytes()) for rex in SECRET):return "POSSIBLE_CREDENTIAL"
 return ""
for g,roots in groups.items():
 print("EXPORT_START",g,flush=True)
 dest=D/(g+".zip");start=len(rows)
 with zipfile.ZipFile(dest,"x",allowZip64=True,compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
  for p in sourcefiles(roots):
   try:
    reason=exclude(p,g)
    if reason:
     if reason!="NON_EVIDENCE":skips.append([g,str(p),reason])
     continue
    path=g+"/"+p.relative_to(R).as_posix()
    h=hashlib.sha256();st=p.stat()
    zi=zipfile.ZipInfo(path);zi.compress_type=zipfile.ZIP_STORED if p.name.lower().endswith((".zip",".gz",".xz",".sqlite",".db")) else zipfile.ZIP_DEFLATED
    with p.open("rb") as inp,z.open(zi,"w",force_zip64=True) as out:
     while True:
      b=inp.read(1048576)
      if not b:break
      h.update(b);out.write(b)
    m=re.search(r"CASE_(\d{5})(?:_([OWP]))?",str(p))
    rows.append(dict(original_filename=p.name,source_path=str(p),case_id=str(int(m.group(1))) if m else "",condition=m.group(2) if m else "",
    generation="O3" if "iter3" in str(p) else "O2" if "second" in str(p) else "O1" if "screen65" in str(p) else "OWP14" if "owp14" in str(p) else "UNSPECIFIED",
    sha256=h.hexdigest(),evaluation_status="RAW_SOURCE_PRESERVED_NOT_REEVALUATED",archive_path=path,bytes=st.st_size,group=g))
   except Exception as e:skips.append([g,str(p),"COPY_ERROR_"+str(type(e).__name__)])
  z.writestr("00_README_AND_MANIFEST/PART_INDEX.csv",csvtext(rows[start:]))
 with zipfile.ZipFile(dest) as z:
  if z.testzip():raise RuntimeError("ZIP CRC mismatch "+g)
 with dest.open("rb") as f:sha=hashlib.file_digest(f,"sha256").hexdigest()
 parts[g]={"file":dest.name,"bytes":dest.stat().st_size,"sha256":sha,"member_count":len(rows)-start}
 (D/"LIVE_PROGRESS.json").write_text(json.dumps({"parts":parts,"rows":len(rows)},indent=2)+"\n")
 print("EXPORT_FINISHED",g,parts[g],flush=True)
(D/"ARTIFACT_INDEX.csv").write_text(csvtext(rows))
(D/"MISSING_ARTIFACTS.md").write_text("# Missing/excluded originals\nThe initial O arm lacks CASE_08461_O.patch and CASE_15151_O.patch. Original agent full trajectories are unverified. The local conversation ZIP is a separate companion archive. Exclusions:\n"+"\n".join(str(x) for x in skips)+"\n")
summary={"status":"COMPLETE","part_files":parts,"raw_files":len(rows),"exclusions":len(skips)}
(D/"EXPORT_SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
master=D/"ARNO_CODEQL_COMPLETE_RESEARCH_HANDOFF_20261019.zip"
with zipfile.ZipFile(master,"x",allowZip64=True,compression=zipfile.ZIP_STORED) as z:
 for x in parts.values():z.write(D/x["file"],arcname=x["file"],compress_type=zipfile.ZIP_STORED)
 for f in ("ARTIFACT_INDEX.csv","MISSING_ARTIFACTS.md","EXPORT_SUMMARY.json"):
  z.write(D/f,arcname="00_README_AND_MANIFEST/"+f)
with zipfile.ZipFile(master) as z:
 if z.testzip():raise RuntimeError("MASTER CRC mismatch")
with master.open("rb") as f:msha=hashlib.file_digest(f,"sha256").hexdigest()
summary["master"]={"path":str(master),"bytes":master.stat().st_size,"sha256":msha}
(D/"EXPORT_SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
print("EXPORT_DONE",json.dumps(summary),flush=True)
