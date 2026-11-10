#!/usr/bin/env python3
"""Read-only node suitability report: CPU, memory, scratch, shared data filesystem."""
import json,os,socket,time
from pathlib import Path
R=Path.home()/"research_artifacts"
def fs(path):
 try:
  p=Path(path)
  s=os.statvfs(p)
  return {"path":str(p),"free_gib":round(s.f_bavail*s.f_frsize/2**30,1),"block_size":s.f_frsize}
 except Exception as e:return {"path":str(path),"error":str(e)}
mem={}
for line in Path("/proc/meminfo").read_text().splitlines():
 k,_,v=line.partition(":")
 if k in ("MemTotal","MemAvailable","SwapTotal"):mem[k]=v.strip()
out={"host":socket.gethostname(),"cpus_visible":os.cpu_count(),"memory":mem,"tmpdir":os.environ.get("SLURM_TMPDIR"),"fs":{"tmp":fs("/tmp"),"research":fs(R)},"slurm":{k:os.getenv(k) for k in ("SLURM_JOB_ID","SLURM_JOB_PARTITION","SLURM_CPUS_PER_TASK","SLURM_MEM_PER_NODE")}}
d=R/"mcp_uploads/jobs/arno_20261029_resource_survey";o=d/("SURVEY_"+out["slurm"]["SLURM_JOB_PARTITION"]+".json")
with o.open("x") as f:json.dump(out,f,indent=2)
print(json.dumps(out,indent=2))
