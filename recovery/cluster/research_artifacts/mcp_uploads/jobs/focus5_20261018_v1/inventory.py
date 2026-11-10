#!/usr/bin/env python3
import os,json,zipfile,hashlib,re,subprocess,shutil
from pathlib import Path
R=Path.home()/"research_artifacts/prevention_pilot_phase2"
IDs=[668,3581,6104,8152,22223]
job=os.environ["SLURM_JOB_ID"]
OUT=R/("focus5_inventory_job"+job);OUT.mkdir(exist_ok=False)
for cid in IDs:
 name="CASE_%05d"%cid
 src=R/"remaining65_archives_oct17_v1"/(name+".zip")
 with zipfile.ZipFile(src) as z:
  names=set(z.namelist());packs={}
  for n in sorted(names):
   if not n.startswith("REPO/") or not n.endswith("package.json") or n.count("/")>6:continue
   if n.count("/")>1 and not any(k in n.lower() for k in ("server/","webview/","packages/","src/")):continue
   try:
    js=json.loads(z.read(n))
    packs[n]={"name":js.get("name"),"packageManager":js.get("packageManager"),"engines":js.get("engines"),
             "scripts":js.get("scripts"),"dependencies":{k:v for k,v in (js.get("dependencies") or {}).items() if k in ("grammy","@grammyjs/files","pnpm","typescript","vitest","better-sqlite3","@types/node","sanitize-html")},
             "devdeps":{k:v for k,v in (js.get("devDependencies") or {}).items() if k in ("vite","vitest","typescript","@types/node")}}
   except:pass
  target_terms={668:["hud","git"],3581:["commentary","webview","workflow"],6104:["communication-adapter","buzz","squad"],8152:["telegram","audio","voice","media"],22223:["browser","artifact","download","chatgpt"]}[cid]
  likely=[x for x in sorted(names) if x.startswith("REPO/") and ("/test" in x or ".test." in x or ".spec." in x) and any(t in x.lower() for t in target_terms)]
  others=[x for x in sorted(names) if x.startswith("REPO/") and any(x.endswith(y) for y in (".npmrc",".nvmrc","pnpm-workspace.yaml","bunfig.toml"))]
  patches={}
  for i,stage in enumerate(("screen65_static_analysis_job70606","screen65_second_20261018_v1")):
   path=R/stage/"patches"/(name+".patch")
   text=path.read_text(errors="replace")
   patches["O"+str(i+1)]={"patch_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"diff":text[:42000],"diff_bytes":len(text)}
  result={"case_id":cid,"package_info":packs,"relevant_test_paths":likely[:65],"configuration_files":others[:30],"o_patches":{k:{s:v for s,v in p.items() if s!="diff"} for k,p in patches.items()}}
  (OUT/(name+".json")).write_text(json.dumps(result,indent=2)+"\n")
  for k,v in patches.items():(OUT/(name+"_"+k+"_PATCH_EXCERPT.txt")).write_text(v["diff"])
  if cid in (668,8152,3581,6104,22223):
   for rel in {668:["src/__tests__/hud/git.test.ts","src/__tests__/hud/state.test.ts","src/hud/state.ts","src/hud/render.ts","src/hud/elements/git.ts"],
   8152:["src/telegram/bridge.ts","src/grok/media.ts","src/grok/media.test.ts","src/telegram/index.ts"],
   3581:["src/webview/package.json","src/extension/services/terminal-execution-service.ts"],
   6104:["server/package.json","shared/package.json","pnpm-workspace.yaml"],
   22223:["pnpm-workspace.yaml","src/browser/artifacts.ts"]}[cid]:
    key="REPO/"+rel
    if key in names:
     data=z.read(key).decode("utf-8","replace")
     target=OUT/(name+"_"+rel.replace("/","__")+".txt")
     target.write_text(data[:45000])
print("INVENTORY_OK",OUT)
