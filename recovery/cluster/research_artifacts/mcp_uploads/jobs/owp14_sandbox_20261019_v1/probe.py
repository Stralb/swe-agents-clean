#!/usr/bin/env python3
"""Check if namespace sandbox is available on Wits before executing untrusted patch modules."""
import subprocess,os,json,tempfile
from pathlib import Path
root=Path.home()/"research_artifacts/prevention_pilot_phase2"
out=root/("owp14_sandbox_capability_job"+os.environ["SLURM_JOB_ID"])
out.mkdir(parents=True,exist_ok=False)
with tempfile.TemporaryDirectory(prefix="bwrap_",dir=out) as td:
 args=["/usr/bin/bwrap","--unshare-user","--unshare-net",
  "--ro-bind","/","/","--bind",td,td,"--proc","/proc","--dev","/dev",
  "--chdir",td,"/bin/true"]
 try:
  p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20,text=True)
  d={"bwrap_supported":p.returncode==0,"returncode":p.returncode,"message":p.stdout[:900]}
 except Exception as e:d={"bwrap_supported":False,"error":repr(e)}
(out/"RESULT.json").write_text(json.dumps(d,indent=2)+"\n")
print("SANDBOX_PROBE",json.dumps(d),flush=True)
