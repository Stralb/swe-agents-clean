#!/usr/bin/env python3
import csv,json,zipfile,shutil,datetime
from pathlib import Path
R=Path.home()/"research_artifacts"
OUT=Path.home()/("ARNO_EVIDENCE_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
POS="154 291 299 653 3340 3429 3448 3582 3592 4134 4216 4811 10145 10326 10773 10791 11276 12313 12334 12354 15686 15748 16209 16213 3375 16372 16394 16469 16476 16536 16680 16681 16871 16999 17428 25496 28354 31593".split()
EXTRA="3581 8152 12344 16633 668 6104 8461 15151 20094 21682 22223 31207 32759".split()
def tab(path):
 with (R/path).open(encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))
def cp(a,b):
 if not a.is_file():return False
 b.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(a,b)
 return True
def jsonout(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding="utf-8")
m=json.loads((R/"C_ROOT_CENSUS_FIX2_LATEST/final_selected/PRIVATE_MAPPING.json").read_text())["true_case_metadata"]
pairs={v["positive_case_id"]:v for v in tab("matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv")}
controls={v["control_case_id"]:v for v in tab("c6_context_completion_v1_0/C6_CONTROL_CONTEXT_190.csv")}
blinds={(v["repository"].lower(),str(v["issue_number"])):v["blind_id"] for v in tab("matched_control_c3_v1_0/C3_CONTROL_MANIFEST_BLINDED.csv")}
idx={v["case_id"]:v for v in tab("new70-step2-patches-20260829T091415Z/index.csv")}
casesdir=R/"PROVENANCE_SCALEOUT_Phase6_Context_MERGED_20260901T222058Z/cases"
OUT.mkdir()
manifest=[]
for n in POS+EXTRA:
 v=m.get(n)
 if not v:
  print("NOT FOUND",n,flush=True)
  continue
 kind="positive" if n in POS else "additional"
 d=OUT/"cases"/(kind+"_"+n)
 d.mkdir(parents=True)
 rec={"case_id":n,"kind":kind,"repo":v["repository"],"issue":v["issue"],"pr":v["pr"],"pc_ids":v["pc_ids"]}
 rec["pr_diff_url"]="https://github.com/"+v["repository"]+"/pull/"+str(v["pr"])+".diff"
 item=idx.get(n)
 rec["frozen_full_diff"]=False
 if item:
  rec["frozen_full_diff"]=cp(R/"new70-step2-patches-20260829T091415Z/diffs"/item["diff_filename"],d/"PR_FULL_FROZEN.diff")
  rec["base_sha"]=item["base_sha"];rec["head_sha"]=item["head_sha"]
 folder=list(casesdir.glob(str(int(n)).zfill(6)+"_*"))
 if folder:
  src=folder[0]
  for name in ("issue.json","issue_comments.json","pr.json","pr_commits.json","pr_reviews.json","timeline_all.csv"):
   cp(src/name,d/"historical"/name)
  for pc in v["pc_ids"]:
   x=src/pc
   for name in ("pr_target_diff.patch","scanner_evidence.txt","producing_change.txt","introduction_commit.json","pre_introduction_human_context.csv","file_context_index.json","diff_evidence.txt"):
    cp(x/name,d/"producing_changes"/pc/name)
 jsonout(d/"metadata.json",rec)
 manifest.append(rec)
 if n in POS and n in pairs:
  match=pairs[n]["control_case_id"]
  ctl=controls.get(match)
  if ctl:
   cd=OUT/"cases"/("control_"+match);cd.mkdir(parents=True,exist_ok=True)
   bid=blinds.get((ctl["repository"].lower(),str(ctl["issue_number"])),"")
   ok=cp(R/("matched_control_c3_v1_0/03_IMPLEMENTATION_FULL_RAW/"+bid+".txt"),cd/"CONTROL_FULL_IMPLEMENTATION.txt")
   manifest.append({"case_id":match,"kind":"control","repo":ctl["repository"],"issue":ctl["issue_number"],"pr":ctl["pr_number"],"paired_positive":n,"raw_implementation_present":ok,"pr_diff_url":"https://github.com/"+ctl["repository"]+"/pull/"+str(ctl["pr_number"])+".diff"})
for name,p in [("455_producing_changes.csv","C_ROOT_CENSUS_FIX2_LATEST/final_selected/STEP2_EVIDENCE_AUDIT_455_NORMALIZED.csv"),("342_root_packets.jsonl","D_COMPLETE_ROOT_PROVENANCE_v1_0/02_PACKETS/D2_CODER_A_PACKETS_342.jsonl"),("190_pairs.csv","matched_control_c2_v1_0/C2_MATCHED_PAIRS_FROZEN.csv")]:
 cp(R/p,OUT/"reference"/name)
with (OUT/"manifest.csv").open("w",encoding="utf-8",newline="") as f:
 keys=sorted(set().union(*(v.keys() for v in manifest)))
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
 for v in manifest:w.writerow({k:json.dumps(x) if isinstance(x,list) else x for k,x in v.items()})
(OUT/"READ_ME.txt").write_text("This archive contains frozen source evidence when available, not verified security vulnerabilities. New70 full diffs are archived; original122 often only have targeted patches. For any missing full patch use the manifest pr_diff_url. Historical AI labels are NOT independent human annotation.\n",encoding="utf-8")
z=OUT.with_suffix(".zip")
with zipfile.ZipFile(z,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as pack:
 for f in OUT.rglob("*"):
  if f.is_file():pack.write(f,f.relative_to(OUT))
with zipfile.ZipFile(z) as pack:assert pack.testzip() is None
print("DONE:",z)
print("CASES:",len(manifest))
print("SIZE_MB:",round(z.stat().st_size/1048576,2))
