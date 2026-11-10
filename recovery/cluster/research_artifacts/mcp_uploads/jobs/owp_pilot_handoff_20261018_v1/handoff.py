#!/usr/bin/env python3
from pathlib import Path
import os,shutil,subprocess,json,hashlib,zipfile
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
source=R/"owp_pilot_generator_packets_job71002"
root=R/("owp_pilot_handoff_job"+os.environ["SLURM_JOB_ID"])
root.mkdir(exist_ok=False)
manifest=json.loads((source/"RESEARCHER_TREATMENT_MANIFEST.json").read_text())
mapping=manifest["packets"]
assert len(mapping)==12 and len(set(p["packet_id"] for p in mapping))==12
def hashfile(p):
 m=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):m.update(b)
 return m.hexdigest()
for row in mapping:
 p=Path(row["packet_path"])
 assert p.is_file() and hashfile(p)==row["packet_sha256"]
artifacts={}
for group,name in [([r for r in mapping if r["case_id"]==668],"CASE668_FRESH_AGENT_STARTER.zip"),
                   (mapping,"THREE_CASES_FRESH_AGENT_PACKETS.zip")]:
 path=root/name
 with zipfile.ZipFile(path,"x",compression=zipfile.ZIP_STORED) as z:
  for r in group:
   packet=Path(r["packet_path"])
   z.write(packet,arcname="packets/"+packet.name)
  for common in ("RESEARCHER_RUN_ASSIGNMENTS.csv","RESEARCHER_TREATMENT_MANIFEST.json","README_OPERATORS.md"):
   z.write(source/common,arcname="RESEARCHER_ONLY/"+common)
 assert zipfile.ZipFile(path).testzip() is None
 artifacts[name]={"bytes":path.stat().st_size,"sha256":hashfile(path),"packet_count":len(group)}
external={}
for cmd in ("codex","claude","aider","opencode","gemini"):
 tool=shutil.which(cmd)
 external[cmd]={"installed":bool(tool),"binary_path":tool}
 if tool:
  try:
   x=subprocess.run([tool,"--version"],capture_output=True,text=True,timeout=12)
   external[cmd]["version"]=x.stdout[:280] or x.stderr[:280]
   external[cmd]["exit"]=x.returncode
  except Exception as e:external[cmd]["version_error"]=repr(e)[:200]
manifest2={"source_run_dir":str(source),"artifact_files":artifacts,
           "local_agent_clis_version_check_only":external,
           "notes":["No LLM code generation was executed on the cluster","No network credentials checked or used",
             "Never upload researcher-only manifest to blinded patch generation agent."]}
(root/"HANDOFF_MANIFEST.json").write_text(json.dumps(manifest2,indent=2)+"\n")
print("HANDOFF_COMPLETE",str(root),"artifacts",artifacts,"runners",external,flush=True)
