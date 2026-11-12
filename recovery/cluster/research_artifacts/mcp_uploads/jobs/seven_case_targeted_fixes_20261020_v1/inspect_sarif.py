#!/usr/bin/env python3
import json,os
from pathlib import Path
root=Path.home()/"research_artifacts/prevention_pilot_phase2/seven_case_scans_20261020"
cases=["03429","08152","31207"]
for cid in cases:
    d=json.loads((root/cid/"RESULT.json").read_text())
    sarif=json.loads((root/cid/"after.sarif").read_text())
    output=[]
    for target in d["new_strong"]:
        matches=[]
        for run in sarif.get("runs",[]):
            for result in run.get("results",[]):
                if result.get("ruleId")!=target["rule"]:continue
                locs=result.get("locations") or []
                p=locs[0].get("physicalLocation",{}) if locs else {}
                uri=(p.get("artifactLocation",{}).get("uri","")).replace("\\","/")
                line=p.get("region",{}).get("startLine",0)
                if not uri.endswith(target["uri"]) or line!=target["line"]:continue
                threads=[]
                for cf in result.get("codeFlows") or []:
                    for tf in cf.get("threadFlows") or []:
                        chain=[]
                        for node in tf.get("locations") or []:
                            t=(node.get("location") or {})
                            physical=t.get("physicalLocation") or {}
                            reg=physical.get("region") or {}
                            chain.append({
                              "path":(physical.get("artifactLocation") or {}).get("uri",""),
                              "line":reg.get("startLine"),
                              "message":(t.get("message") or {}).get("text","")
                            })
                        threads.append(chain)
                matches.append({"rule":result.get("ruleId"),"path":uri,"line":line,"message":(result.get("message") or {}).get("text",""),"chains":threads})
        output.append({"target":target,"matches":matches})
    (root/cid/"TARGET_DATAFLOW.json").write_text(json.dumps(output,indent=2))
    print(cid,[(x["target"]["rule"],len(x["matches"]),[len(t) for y in x["matches"] for t in y["chains"]]) for x in output])
