#!/usr/bin/env python3
"""Cancel only stale pending jobs from the superseded research recovery chain.
Requires independent MASTER_RECOVERY_VERIFIED proof. No database access for writes.
"""
from pathlib import Path
import json,subprocess,sys
R=Path.home()/"research_artifacts"
PROOF=R/"mcp_uploads/jobs/arno_20261029_terminal_integrity_audit/RESULT.json"
OUT=R/"mcp_uploads/jobs/arno_20261029_retire_stale_jobs/RESULT.json"
STALE=["77360","77365","77378","77734","77765","77766"]
def run(*args):
 return subprocess.run(args,capture_output=True,text=True,timeout=35)
def main():
 p=json.loads(PROOF.read_text())
 assert p["status"]=="MASTER_RECOVERY_VERIFIED"
 assert p["row_counts"]["arno_d7_final_roots_342"]==342
 assert p["row_counts"]["arno_experiment_runs"]==40
 assert p["row_counts"]["arno_generated_patches"]==40
 assert p["row_counts"]["arno_experiment_scans"]==40
 result={"success":True,"master_untouched":True,"old_jobs_inspected":[],"cancelled":[],"untouched":[]}
 for job in STALE:
  status=run("squeue","--noheader","--jobs",job,"--format","%i|%T|%j")
  if status.returncode!=0:
   result["untouched"].append({"job":job,"reason":"squeue failed","stderr":status.stderr[:200]})
   continue
  lines=status.stdout.strip().splitlines()
  if len(lines)!=1:
   result["untouched"].append({"job":job,"reason":"not an active unique Slurm job"})
   continue
  parts=lines[0].split("|")
  if len(parts)<3 or parts[0].strip()!=job or parts[1].strip()!="PENDING" or not parts[2].strip().startswith("arno_"):
   result["untouched"].append({"job":job,"reason":"job not the identified pending ARNO job"})
   continue
  result["old_jobs_inspected"].append({"job":job,"state":parts[1],"name":parts[2]})
  resp=run("scancel",job)
  if resp.returncode==0:result["cancelled"].append(job)
  else:result["untouched"].append({"job":job,"reason":"scancel rejected","stderr":resp.stderr[:200]})
 OUT.parent.mkdir(parents=True,exist_ok=True)
 with OUT.open("x") as f:json.dump(result,f,indent=2)
 print(json.dumps(result,indent=2))
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("STALE_JOB_CLEANUP_REFUSED "+repr(e),file=sys.stderr)
  sys.exit(1)
