#!/usr/bin/env python3
"""Read-only inventory for an evidence export; does not execute experiments."""
import json,os,stat,re
from pathlib import Path
root=Path.home()/"research_artifacts"
phase=root/"prevention_pilot_phase2"
out=root/"mcp_uploads"/"jobs"/"arno_handoff_inventory_20261019_v1"/"HPC_EXPORT_INVENTORY.json"
def entries(path):
 out=[]
 if not path.is_dir():return out
 for p in sorted(path.iterdir(),key=lambda x:x.name.lower()):
  try:
   s=p.lstat()
   out.append({"name":p.name,"kind":"dir" if p.is_dir() else "file","bytes":s.st_size if p.is_file() else None,"symlink":p.is_symlink()})
  except OSError as e:out.append({"name":p.name,"error":repr(e)})
 return out
groups={
 "research_root":entries(root),
 "phase2":entries(phase),
 "mcp_jobs":entries(root/"mcp_uploads"/"jobs"),
 "mcp_uploads":entries(root/"mcp_uploads"),
 "owp_inputs":entries(phase/"owp14_allcases_packets_job71014"),
 "causal":entries(root/"matched_issue_controls_v1"),
}
out.write_text(json.dumps(groups,indent=2)+"\n")
print("INVENTORY_READY",str(out),flush=True)
for name,data in groups.items():
 print("GROUP",name,"count",len(data),flush=True)
 print("ITEMS",",".join(x["name"] for x in data if re.search(r"screen65|owp14|case_screen|pilot3|matching|matched|control|experiment|census|precedent|phase.?2|phase.?3|trac|causal|summary",x["name"],re.I))[:12000],flush=True)
