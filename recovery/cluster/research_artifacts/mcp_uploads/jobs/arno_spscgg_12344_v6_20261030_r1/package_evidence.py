from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from datetime import datetime,timezone
import hashlib,json
R=Path.home()/"research_artifacts"
D=R/"mcp_uploads/jobs/arno_spscgg_12344_v6_20261030_r1"
O=D/"results"
BASE=R/"mcp_uploads/jobs/arno_20261030_rpl7_fresh_codeql_baselines/results/CASE_12344"
HIST=R/"mcp_uploads/jobs/arno_20261030_rpl7_patch_codeql_scans/results/CASE_12344/RPL7_RUN_E0EDE434153B"
SCGG=R/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/results_12344"
def digest(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for ch in iter(lambda:f.read(1048576),b""):h.update(ch)
 return h.hexdigest()
s=json.loads((O/"RESULT.json").read_text())
b=json.loads((BASE/"RESULT.json").read_text())
h=json.loads((HIST/"RESULT.json").read_text())
c=json.loads((SCGG/"RESULT.json").read_text())
assert s["status"]=="CODEQL_SCAN_COMPLETE"
assert s["codeql_version"]=="2.25.6"
assert s["baseline_total"]==758 and s["historical_p1_total"]==763
assert s["prior_scgg_after_total"]==763 and s["prior_scgg_new"]==5
assert s["source_files"]==10341 and s["source_kind"]=="FILTERED_SOURCE_PROVISIONAL"
assert s["checks"]["apply_check"]["exit"]==0 and s["checks"]["apply"]["exit"]==0
assert s["checks"]["database_create"]["exit"]==0 and s["checks"]["analysis"]["exit"]==0
assert digest(O/"after.sarif")==s["after_sarif_sha256"]
assert digest(BASE/"baseline.sarif")==b["sarif_sha256"]
assert digest(HIST/"after.sarif")==h["after_sarif_sha256"]
assert digest(SCGG/"after.sarif")==c["after_sarif_sha256"]
assert digest(O/"PATCH_SPSCGG_12344_R1.patch")==s["patch_sha256"]
assert digest(O/"RECEIPT_SPSCGG_12344_R1.json")==s["receipt_sha256"]
assert digest(O/"IMPLEMENTATION_PROMPT_SPSCGG_12344_R1.md")==s["self_prompt_sha256"]
files={}
for n in ["RESULT.json","warning_delta.json","after.sarif","apply_check.log","apply.log","create.log",
"analyze.log","codeql_version.log","PATCH_SPSCGG_12344_R1.patch","RECEIPT_SPSCGG_12344_R1.json","IMPLEMENTATION_PROMPT_SPSCGG_12344_R1.md"]:
 files["spscgg/"+n]=O/n
for n in ["RESULT.json","baseline.sarif"]:files["baseline/"+n]=BASE/n
for n in ["RESULT.json","after.sarif"]:files["historical_p1/"+n]=HIST/n
for n in ["RESULT.json","after.sarif","warning_delta.json"]:files["previous_scgg/"+n]=SCGG/n
for n in ["evaluate.py","scan.sbatch"]:files["scripts/"+n]=D/n
readme=(
"Experiment: single-chat self-prompted SCGG, 12344, first-delivered patch\n"
"Frozen source: FILTERED_SOURCE_PROVISIONAL, 10341 source files\n"
"Security suite: CodeQL 2.25.6 javascript-security-extended\n"
"Comparison uses line-agnostic (ruleId,relative file,normalized message) multiset\n"
f"Baseline findings 758; historical P1 763 (+5); previous SCGG 763 (+5); self-prompted SCGG {s['after_total']} (+{s['new_vs_baseline']}).\n"
"All SARIF and source-digest metadata retained. Original full source ZIP not included.\n"
"No native Windows tests or end-to-end functional confirmation. Self-prompt order is agent-reported.\n"
)
archive=D/"ARNO_SPSCGG_12344_V6_FULL_CODEQL_EVIDENCE.zip"
assert not archive.exists()
with ZipFile(archive,"x",ZIP_DEFLATED,compresslevel=7) as z:
 for n,p in sorted(files.items()):z.write(p,n)
 z.writestr("README.txt",readme)
with ZipFile(archive) as z:assert z.testzip() is None
info={"status":"VERIFIED_AND_PACKAGED","case":"12344","condition":"SPSCGG_SELF_PROMPT_ONE_CHAT",
 "archive_relative_path":str(archive.relative_to(R)),"archive_bytes":archive.stat().st_size,
 "archive_sha256":digest(archive),"files":len(files)+1,
 "baseline":s["baseline_total"],"historical_p1_new":s["historical_p1_new"],
 "previous_scgg_new":s["prior_scgg_new"],"spscgg_new":s["new_vs_baseline"],
 "functional_status":"NOT_VERIFIED","created_utc":datetime.now(timezone.utc).isoformat()}
out=D/"EVIDENCE_PACKAGE_INFO.json"
assert not out.exists()
out.write_text(json.dumps(info,indent=2)+"\n")
print(json.dumps(info,indent=2),flush=True)
