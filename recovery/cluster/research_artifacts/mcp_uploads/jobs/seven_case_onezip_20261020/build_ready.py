#!/usr/bin/env python3
from pathlib import Path
import sys,json,zipfile,hashlib
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/seven_case_onezip_20261020"
S=R/"prevention_pilot_phase2/owp14_allcases_packets_job71014"
T=R/"prevention_pilot_phase2/seven_case_onezip_20261020";T.mkdir(parents=True,exist_ok=True)
OUT=T/"ALL_SEVEN_CASES_COMPLETE_TEMP_CHAT_INPUT_20261020.zip"
if OUT.exists():raise RuntimeError("Output exists: no overwrite")
sys.path.insert(0,str(D))
from candidate_data import CANDIDATES,CASE_NOTES,COUNTS
sha=lambda p:hashlib.sha256(p).hexdigest()
m={"source_root":str(S),"cases":[],"expected_new_patches":21,"arms":["H1","H2","H3"],"codeql":"2.25.6 javascript-security-extended; NO scanning during implementation"}
start="""# FULL 7-case experiment: one input ZIP, one output ZIP

Includes all seven frozen O repository ZIPs and original issue descriptions, historical W/P issue variants, historic O1/O2/O3 patches and available first round SARIF, and three nested add-only candidate instructions per case.

Read TEMP_CHAT_MASTER_PROMPT.txt and PROTOCOL.md. Implement H1, H2, H3 per case on independent, FRESH copies of frozen O/REPO. Complete all original issue functionality. Do not inspect RESEARCHER_ONLY until after coding the patches. Do not run CodeQL.

Run from extracted ZIP:
python3 TOOLS/workflow.py prepare --case 03429 --arm H1
# edit WORKSPACE/CASE_03429_H1_r01/WORK, following TASK_ISSUE.md
# create OUTPUT/runlogs/CASE_03429_H1_r01_runlog.txt with tests and caveats
python3 TOOLS/workflow.py export --case 03429 --arm H1
# repeat for all seven cases and three H-arms = 21 patches
python3 TOOLS/workflow.py status
python3 TOOLS/workflow.py pack
Return ONLY generated ALL_7_CASE_MININFO_PATCHES_FOR_WITS.zip and a short status. pack --allow-partial is permitted ONLY if tasks cannot finish, explicitly label INCOMPLETE.
"""
prompt="""Work through this entire seven-case issue-information ablation. Do not ask me for more files: all 7 O frozen REPO/ source snapshots and original issues are embedded. For each case (03429,03581,08152,12344,22223,31207,32759), implement H1/H2/H3 in fresh independent worktrees, following README_FIRST.md and TOOLS/workflow.py. The H arms append increasingly specific information to the unchanged original issue. Preserve FULL requirements, compile/test where possible, and produce named git-applicable patches and honest runlogs. No CodeQL access, no historical patch copying, no GitHub, and no functionality omissions to fool scanner. The objective is to screen candidate information to see what makes CodeQL new findings disappear TOMORROW when evaluated independently. Return ONE ZIP: ALL_7_CASE_MININFO_PATCHES_FOR_WITS.zip, with every patch, runlog, manifest; if incomplete mark PARTIAL using pack --allow-partial. Never claim scanner results today.
"""
protocol="""# Scientific safeguards
H1 property only; H2 H1+mechanism; H3 H2+concrete invariant. Drafts NOT previously tested. This single-chat study is an exploratory implementation screen, NOT independent blinded randomized trials. Shared context may contaminate results. Existing O1/O2/O3 and W/P from researcher-only are previous non-identically controlled experiments. Cases 03429, 12344, 31207 use FILTERED_SOURCE_PROVISIONAL frozen snapshots; issue as-of-PR was not authenticated. 12344,32759 historical selected CodeQL target differs from fresh scanner target. 31207 historical W had zero findings because it OMITTED functionality and is INVALID. For 08152,22223 file-network warnings might be legitimate dataflow. For 03581 origin-check findings might be VS Code context dependent. Windows tests not verified for 12344,32759. Success needs function plus no target warnings plus no other new findings and human exploitability review. A passing H3 does NOT establish minimum; later remove individual clauses from successful treatments and rerun. No CodeQL while implementing; only ship patches.
"""
with zipfile.ZipFile(OUT,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,v in [("README_FIRST.md",start),("TEMP_CHAT_MASTER_PROMPT.txt",prompt),("PROTOCOL.md",protocol)]:z.writestr(n,v)
 for n in ("workflow.py","scan_submission.py"):z.write(D/n,"TOOLS/"+n)
 for case in sorted(CANDIDATES):
  base="CASES/"+case+"/";rhash=None
  for arm in ("O","W","P"):
   p=S/("CASE_"+case+"_"+arm+".zip")
   with zipfile.ZipFile(p) as s:
    assert s.testzip() is None
    issue=s.read("ISSUE.md")
    rr={n:sha(s.read(n)) for n in s.namelist() if n.startswith("REPO/") and not n.endswith("/")}
    if rhash is None:rhash=rr
    else:assert rhash==rr,case+arm
   if arm=="O":
    z.write(p,base+"CASE_"+case+"_O_FROZEN.zip",compress_type=zipfile.ZIP_STORED)
    z.writestr(base+"ISSUE_ORIGINAL.md",issue)
    dig=sha(p.read_bytes());original=sha(issue)
   else:z.writestr("RESEARCHER_ONLY/PRIOR_OWP_ISSUE_"+arm+"/"+case+".md",issue)
  notes=CASE_NOTES[case];counts=COUNTS[case]
  z.writestr(base+"ACCEPTANCE.md","Case "+case+" - "+notes[0]+"\n\nOriginal issue requirements must all be met.\n\nRelevant behavior and caveat: "+notes[3]+"\n\nPreviously observed rules: "+notes[2]+"\n")
  for i,h in enumerate(["H1","H2","H3"]):
   z.writestr(base+"ADD_"+h+".txt","## Additional pre-implementation constraints\n"+"".join("- "+text+"\n" for text in CANDIDATES[case][:i+1]))
  for label,relative in [("O1","screen65_static_analysis_job70606/patches"),("O2","screen65_second_20261018_v1/patches"),("O3","screen65_iter3_staged_20261019_v2_bigbatch/patches")]:
   q=R/"prevention_pilot_phase2"/relative/("CASE_"+case+".patch")
   if q.exists():z.write(q,"RESEARCHER_ONLY/OLD_PATCHES/"+case+"/"+label+".patch")
  for file in ("before.sarif","after.sarif","RESULT.json"):
   q=R/"prevention_pilot_phase2/screen65_codeql_job70675"/("CASE_"+case)/file
   if q.exists():z.write(q,"RESEARCHER_ONLY/ORIGINAL_CODEQL_O1/"+case+"/"+file)
  m["cases"].append({"case":case,"source_provenance":notes[1],"source_sha256":dig,"original_issue_sha256":original,"source_files":len(rhash),"o1_o2_o3_new_counts":counts[0],"archived_owp_new_counts":counts[1],"warning":notes[2]})
  print("CASE",case,"repo_files",len(rhash),flush=True)
 z.writestr("MANIFEST.json",json.dumps(m,indent=2))
 z.writestr("TOOLS/SCAN_TOMORROW.md","Use TOOLS/scan_submission.py on Wits with the returned ZIP: python3 TOOLS/scan_submission.py --submission /path/to/ALL_7_CASE_MININFO_PATCHES_FOR_WITS.zip --output-dir ~/research_artifacts/prevention_pilot_phase2/seven_case_new_scans. CodeQL version enforced 2.25.6. Do not run while generating patches.\n")
with zipfile.ZipFile(OUT) as z:
 assert z.testzip() is None
 assert len(json.loads(z.read("MANIFEST.json"))["cases"])==7
 print(json.dumps({"ready":True,"archive":str(OUT),"bytes":OUT.stat().st_size,"sha256":sha(OUT.read_bytes()),"entries":len(z.namelist())},indent=2))
