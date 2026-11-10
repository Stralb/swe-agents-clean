from pathlib import Path
import json
root=Path.home()/"research_artifacts"/"mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1"
out={}
for case, rule in [("08152","js/file-access-to-http"),("12344","js/path-injection")]:
 src=root/("results_"+case)/"after.sarif"
 data=json.loads(src.read_text())
 paths=[]
 for run in data.get("runs",[]):
  for result in run.get("results",[]):
   if result.get("ruleId")!=rule:continue
   pl=(result.get("locations") or [{}])[0].get("physicalLocation",{})
   target=pl.get("artifactLocation",{}).get("uri","")
   if (case=="08152" and target!="src/telegram/voice.ts") or (case=="12344" and target!="apps/daemon/src/byok/credential-service.ts"):continue
   details=[]
   for flow in result.get("codeFlows",[]):
    for tf in flow.get("threadFlows",[]):
     steps=[]
     for item in tf.get("locations",[]):
      loc=item.get("location",{})
      p=loc.get("physicalLocation",{})
      steps.append({"path":p.get("artifactLocation",{}).get("uri",""),
       "line":p.get("region",{}).get("startLine"),
       "text":loc.get("message",{}).get("text","")})
     details.append({"first_steps":steps[:6],"last_steps":steps[-6:],"total_steps":len(steps)})
   paths.append({"rule":rule,"file":target,"sink_line":pl.get("region",{}).get("startLine"),
    "message":result.get("message",{}).get("text",""),
    "flows":details[:4]})
 out[case]={"matching_results":len(paths),"examples":paths[:8]}
dest=root/"SCGG_08152_12344_CODEQL_FLOW_TRACES.json"
assert not dest.exists()
dest.write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2),flush=True)
