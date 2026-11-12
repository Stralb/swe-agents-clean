#!/usr/bin/env python3
"""Read-only CodeQL pack and query-source provenance pinning."""
from pathlib import Path
import hashlib,json,os,subprocess,re
H=Path.home()
ROOT=H/"research_artifacts/prevention_pilot_phase2"
OUT=ROOT/("focus5_codeql_pin_job"+os.environ["SLURM_JOB_ID"]);OUT.mkdir(exist_ok=False)
TARGET={"js/file-system-race","js/missing-origin-check","js/prototype-polluting-assignment",
        "js/remote-property-injection","js/file-access-to-http","js/http-to-file-access"}
r={"target_rules":sorted(TARGET),"resolved":{},"suite":"codeql/javascript-queries:codeql-suites/javascript-security-extended.qls"}
exe=H/"tools/codeql/codeql"
def sha(p):
 x=hashlib.sha256()
 with p.open("rb") as f:
  for q in iter(lambda:f.read(4*1024*1024),b""):x.update(q)
 return x.hexdigest()
r["codeql_binary_sha256"]=sha(exe) if exe.is_file() else None
v=subprocess.run([str(exe),"version"],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=35,text=True)
r["codeql_version"]=v.stdout[:1600]
packs=(H/".codeql/packages/codeql/javascript-queries")
scanroots=[packs] if packs.is_dir() else [H/".codeql/packages"]
checked=0
for root in scanroots:
 if not root.is_dir():continue
 for p in root.rglob("*.ql"):
  checked+=1
  if checked>14000:break
  try:content=p.read_text(errors="replace")
  except:continue
  match=re.search(r"@id\s+(js/[a-z0-9-]+)",content)
  if match and match.group(1) in TARGET:
   rule=match.group(1)
   r["resolved"].setdefault(rule,[]).append({"file":str(p),"sha256":sha(p),
      "bytes":p.stat().st_size,"relative_to_packs":str(p.relative_to(root))})
r["ql_files_inspected"]=checked
r["unresolved"]=sorted(TARGET-set(r["resolved"]))
(OUT/"CODEQL_QUERY_PINS.json").write_text(json.dumps(r,indent=2)+"\n")
print("QUERY_PINS",len(r["resolved"]),"missing",r["unresolved"],"files",checked,flush=True)
