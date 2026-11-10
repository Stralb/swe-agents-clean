#!/usr/bin/env python3
"""Read-only requirement/manifest inventory from frozen O/W/P packets, no code execution."""
from pathlib import Path
import csv,hashlib,json,os,re,zipfile
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2"
PACK=ROOT/"owp14_allcases_packets_job71014"
OUT=ROOT/("owp14_functional_intake_job"+os.environ["SLURM_JOB_ID"])
OUT.mkdir(parents=True,exist_ok=False)
with (PACK/"PACKET_INDEX.csv").open(newline="") as f:
 source={(int(x["case_id"]),x["arm"]):x for x in csv.DictReader(f)}
assert len(source)==42
pre={"O":ROOT/"owp14_user12_o_preflight_job71153",
     "W":ROOT/"owp14_user14_w_preflight_job71208",
     "P":ROOT/"owp14_user14_p_preflight_job71201"}
pre={a:json.loads((p/"SUMMARY.json").read_text()) for a,p in pre.items()}
def filehash(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for s in iter(lambda:f.read(2*1024*1024),b""):h.update(s)
 return h.hexdigest()
cases={}
for cid in sorted({i for i,arm in source}):
 num="%05d"%cid
 out=OUT/("CASE_"+num);out.mkdir()
 o=PACK/("CASE_"+num+"_O.zip")
 assert filehash(o)==source[(cid,"O")]["sha256"]
 with zipfile.ZipFile(o) as z:
  assert z.testzip() is None
  filenames=z.namelist()
  assert "ISSUE.md" in filenames
  raw=z.read("ISSUE.md")
  assert len(raw)<250000
  original=raw.decode("utf8","replace")
  (out/"ORIGINAL_ISSUE.md").write_text(original)
  runinstr=z.read("RUN_INSTRUCTIONS.md").decode("utf8","replace") if "RUN_INSTRUCTIONS.md" in filenames else ""
  (out/"RUN_INSTRUCTIONS.md").write_text(runinstr)
  allpaths=[n for n in filenames if n.startswith("REPO/") and not n.endswith("/")]
  tests=[n[5:] for n in allpaths if re.search(r"(?i)(^|/)(test|tests|__tests__|spec|specs)/|(\.test\.|\.spec\.)",n)]
  (out/"EXISTING_TEST_PATHS.txt").write_text("\n".join(tests[:1500])+"\n")
  packages=[]
  for n in allpaths:
   if not n.endswith("/package.json") and n!="REPO/package.json":continue
   if n.count("/")>4:continue
   try:
    item=json.loads(z.read(n))
    packages.append({"path":n[5:],"name":item.get("name"),
     "scripts":item.get("scripts",{}),
     "packageManager":item.get("packageManager"),
     "engines":item.get("engines",{})})
   except Exception:pass
  (out/"PACKAGE_SCRIPTS.json").write_text(json.dumps(packages,indent=2)+"\n")
  rootfiles=[n for n in allpaths if n.count("/")==1][:100]
  # CRC32 checks ensure O/W/P identical sources without unpacking multi-GB archives.
  source_index={n:(z.getinfo(n).CRC,z.getinfo(n).file_size) for n in allpaths}
 arm_data={}
 for arm in ("O","W","P"):
  path=PACK/("CASE_"+num+"_"+arm+".zip")
  assert filehash(path)==source[(cid,arm)]["sha256"]
  with zipfile.ZipFile(path) as z:
   other=z.read("ISSUE.md").decode("utf8","replace")
   contents=[n for n in z.namelist() if n.startswith("REPO/") and not n.endswith("/")]
   m={n:(z.getinfo(n).CRC,z.getinfo(n).file_size) for n in contents}
   matching=(m==source_index)
   changes=[n for n in m if n not in source_index or m[n]!=source_index[n]]
   changes+=["MISSING: "+n for n in source_index if n not in m]
   (out/("ISSUE_"+arm+".md")).write_text(other)
   rec={"frozen_repo_crc_match":matching,"frozen_repo_differing_paths":changes[:30],
     "zip_sha256":source[(cid,arm)]["sha256"],
     "issue_sha256":hashlib.sha256(other.encode()).hexdigest(),
     "issue_bytes":len(other.encode()),"issue_prefix_equal_to_original":other.startswith(original),
     "issue_same_as_original":other==original}
   p=pre[arm]["cases"].get(str(cid))
   if p:
    rec.update({"patch_applied":p.get("patch_applied"),
      "patch_bytes":p.get("original_patch_bytes"),
      "patch_sha256":p.get("original_patch_sha256"),
      "changed_paths":p.get("changed_paths",[]),
      "changed_test_files":[x for x in p.get("changed_paths",[]) if re.search(r"(?i)(test|spec)",x)]})
   else:rec["patch_applied"]=None
   arm_data[arm]=rec
 rec={"case_id":cid,"repository":source[(cid,"O")]["repository"],
   "source_type":source[(cid,"O")]["source_type"],
   "original_issue_excerpt":original[:700],
   "original_issue_chars":len(original),
   "test_file_count":len(tests),"test_file_examples":tests[:12],
   "root_files":rootfiles,"package_scripts":packages,
   "arms":arm_data}
 (out/"INTAKE.json").write_text(json.dumps(rec,indent=2)+"\n")
 cases[str(cid)]={"case_id":cid,"repository":rec["repository"],"original_issue_chars":len(original),
   "test_file_count":len(tests),"frozen_repo_equal":all(arm_data[a]["frozen_repo_crc_match"] for a in ("W","P")),
   "issue_excerpt":original[:700], "patch_applied":{a:arm_data[a]["patch_applied"] for a in ("O","W","P")},
   "patch_bytes":{a:arm_data[a].get("patch_bytes") for a in ("O","W","P")},
   "modified_test_counts":{a:len(arm_data[a].get("changed_test_files",[])) for a in ("O","W","P")},
   "package_scripts":packages[:5]}
 print("INTAKE",cid,"same_repo",cases[str(cid)]["frozen_repo_equal"],
  "issue_len",len(original),"test_paths",len(tests),flush=True)
(OUT/"ISSUES_INTAKE_SUMMARY.json").write_text(json.dumps({"stage":"COMPLETE","cases":cases},indent=2)+"\n")
print("INTAKE_COMPLETE",OUT,flush=True)
