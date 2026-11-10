#!/usr/bin/env python3
"""Offline JS/TS syntax and JSON validity checks for 40 applied O/W/P patches, without executing repo code."""
from pathlib import Path,PurePosixPath
from collections import Counter
import os,subprocess,zipfile,csv,json,re,tempfile,hashlib,shutil,time,traceback
ROOT=Path.home()/"research_artifacts/prevention_pilot_phase2"
PACK=ROOT/"owp14_allcases_packets_job71014"
OUT=ROOT/("owp14_syntax_jsx_checks_job"+os.environ["SLURM_JOB_ID"]);OUT.mkdir(parents=True,exist_ok=False)
pref={"O":ROOT/"owp14_user12_o_preflight_job71153",
      "W":ROOT/"owp14_user14_w_preflight_job71208",
      "P":ROOT/"owp14_user14_p_preflight_job71201"}
data={a:json.loads((v/"SUMMARY.json").read_text())["cases"] for a,v in pref.items()}
with (PACK/"PACKET_INDEX.csv").open(newline="") as f:idx={(int(x["case_id"]),x["arm"]):x for x in csv.DictReader(f)}
BUN=Path.home()/".bun/bin/bun"
assert BUN.exists()
HARNESS=OUT/"SYNTAX_PARSER.mjs"
HARNESS.write_text("""
import fs from 'node:fs';
const out=[];
for (const path of process.argv.slice(2)) {
  const m=path.match(/\\.([a-z0-9]+)$/i);
  const ext=m?.[1]?.toLowerCase()??'';
  const loader=({ts:'ts',mts:'ts',cts:'ts',tsx:'tsx',js:'jsx',mjs:'js',cjs:'js',jsx:'jsx'})[ext];
  if (!loader) continue;
  const source=fs.readFileSync(path,'utf8');
  try {
    const tr=new Bun.Transpiler({loader,target:'node'});
    tr.transformSync(source);
    out.push({path,ext,pass:true});
  } catch (e) {
    out.push({path,ext,pass:false,error:String(e?.stack||e).slice(0,1300)});
  }
}
process.stdout.write(JSON.stringify(out)+'\\n');
""")
def sha(x):return hashlib.sha256(x).hexdigest()
def check(files,tmp,stage):
 if not files:return []
 cmd=[str(BUN),str(HARNESS),*files]
 p=subprocess.run(cmd,cwd=tmp,env={"PATH":str(BUN.parent)+":/usr/bin:/bin","HOME":str(tmp),
  "BUN_INSTALL_CACHE_DIR":str(tmp/"bun-cache"),"NO_COLOR":"1","CI":"1"},
  stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
 if p.returncode!=0:raise RuntimeError(stage+" parser launcher failed "+p.stderr[:600])
 try:result=json.loads(p.stdout)
 except Exception as e:raise RuntimeError(stage+" invalid parser output "+repr(e)+" "+p.stdout[:300])
 return result
summary={"stage":"IN_PROGRESS","syntax_parser":"Bun.Transpiler 1.4.2 (JSX-aware .js)","patches":{}}
def save(): (OUT/"SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
allarms=[(cid,a) for cid in sorted({int(x) for arm in data for x in data[arm]}) for a in ("O","W","P") if str(cid) in data[a]]
assert len(allarms)==40
scratch=ROOT/"owp14_syntax_scratch";scratch.mkdir(exist_ok=True)
for cid,arm in allarms:
 key="%05d_%s"%(cid,arm)
 entry=data[arm][str(cid)]
 rec={"case_id":cid,"arm":arm,"status":"START",
  "patch_sha256":entry["original_patch_sha256"],
  "patch_applies_in_prior_preflight":entry["patch_applied"],
  "syntax_valid_count":0,"syntax_invalid_count":0,"baseline_invalid_count":0,
  "syntax_failures":[],"file_parse_details":[]}
 try:
  assert entry["patch_applied"]
  source=PACK/("CASE_%05d_O.zip"%cid)
  assert idx[(cid,"O")]["sha256"]==sha(source.read_bytes())
  origpatch=pref[arm]/("CASE_%05d"%cid)/entry["filename"]
  raw=origpatch.read_bytes()
  assert sha(raw)==entry["original_patch_sha256"]
  paths=entry["changed_paths"]
  with tempfile.TemporaryDirectory(prefix=key+"_",dir=scratch) as tmpdir:
   tmp=Path(tmpdir);repo=tmp/"repo";repo.mkdir()
   oldfiles=[]
   with zipfile.ZipFile(source) as z:
    for p in paths:
     rel=PurePosixPath(p);assert ".." not in rel.parts and ".git" not in rel.parts
     packed="REPO/"+p
     if packed not in z.namelist():continue
     content=z.read(packed)
     file=repo.joinpath(*rel.parts);file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(content)
     if file.suffix.lower() in [".js",".mjs",".cjs",".jsx",".ts",".tsx",".mts",".cts"]:oldfiles.append(str(file))
   old=check(oldfiles,repo,"baseline")
   rec["baseline_invalid_count"]=sum(not v["pass"] for v in old)
   p=subprocess.run(["git","apply","--check",str(origpatch)],cwd=repo,
      stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=140,
      env={"HOME":str(tmp),"PATH":"/usr/bin:/bin","GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null","GIT_TERMINAL_PROMPT":"0"})
   if p.returncode:raise RuntimeError("partial source context did not apply: "+p.stdout[:500])
   p=subprocess.run(["git","apply",str(origpatch)],cwd=repo,stdout=subprocess.PIPE,
     stderr=subprocess.STDOUT,text=True,timeout=140,
     env={"HOME":str(tmp),"PATH":"/usr/bin:/bin","GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null","GIT_TERMINAL_PROMPT":"0"})
   if p.returncode:raise RuntimeError("apply fail "+p.stdout[:400])
   parsepaths=[];countjson=0
   for q in paths:
    f=repo/q
    if not f.exists():continue
    if f.suffix.lower() in [".js",".mjs",".cjs",".jsx",".ts",".tsx",".mts",".cts"]:parsepaths.append(str(f))
    elif f.suffix.lower()==".json":
     countjson+=1
     try:json.loads(f.read_text())
     except Exception as e:rec["syntax_failures"].append({"file":q,"reason":"invalid_json","detail":str(e)[:400]})
   parsed=check(parsepaths,repo,"patched")
   rec["file_parse_details"]=[{"file":str(Path(x["path"]).relative_to(repo)),**{k:v for k,v in x.items() if k!="path"}} for x in parsed]
   rec["syntax_valid_count"]=sum(x["pass"] for x in parsed)+countjson
   rec["syntax_failures"] += [x for x in rec["file_parse_details"] if not x["pass"]]
   rec["syntax_invalid_count"]=len(rec["syntax_failures"])
   rec["syntax_parsed_file_count"]=len(parsed)
   rec["status"]="SYNTAX_PASS" if rec["syntax_invalid_count"]==0 else "SYNTAX_FAIL"
 except Exception as e:
  rec["status"]="HARNESS_FAILED";rec["error"]=repr(e)
  rec["traceback"]=traceback.format_exc()[-1600:]
 summary["patches"][key]={k:v for k,v in rec.items() if k!="file_parse_details"}
 (OUT/(key+".json")).write_text(json.dumps(rec,indent=2)+"\n")
 save()
 print("SYNTAX",key,rec["status"],rec.get("syntax_parsed_file_count"),
  rec.get("syntax_invalid_count"),flush=True)
summary["stage"]="COMPLETE"
summary["count"]=len(summary["patches"])
summary["passed"]=sum(x["status"]=="SYNTAX_PASS" for x in summary["patches"].values())
summary["syntax_failed"]=sum(x["status"]=="SYNTAX_FAIL" for x in summary["patches"].values())
summary["harness_failed"]=sum(x["status"]=="HARNESS_FAILED" for x in summary["patches"].values())
save()
print("SYNTAX_COMPLETE",summary["passed"],summary["syntax_failed"],summary["harness_failed"],OUT,flush=True)
